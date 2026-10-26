import logging
import re

import pytest

from app import create_app, db
from app.models import ClassSession
from app.security import RedactQrCodeFilter
from helpers import login, make_course, make_user


@pytest.fixture
def csrf_app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "csrf.db"),
        "KEYS_DIR": str(tmp_path / "keys"),
        "WTF_CSRF_ENABLED": True,
        "BCRYPT_ROUNDS": 4,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def csrf_token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)


def test_13_post_without_csrf_rejected(csrf_app):
    client = csrf_app.test_client()
    gv = make_user("gv01", role="lecturer")
    course = make_course(gv, [make_user("sv01", code="22520001")])
    sess_id = course.sessions[0].id

    # Đăng nhập thiếu token bị từ chối
    assert login(client, "gv01").status_code == 400
    assert client.get("/lecturer").status_code == 302

    # Đăng nhập đúng cách, có token
    token = csrf_token(client, "/login")
    r = client.post("/login", data={"username": "gv01", "password": "Matkhau@123", "csrf_token": token})
    assert r.status_code == 302 and client.get("/lecturer").status_code == 200

    # Mở buổi thiếu token / token sai: bị từ chối, trạng thái không đổi
    assert client.post(f"/lecturer/sessions/{sess_id}/open").status_code == 400
    assert client.post(f"/lecturer/sessions/{sess_id}/open",
                       data={"csrf_token": "sai"}).status_code == 400
    assert db.session.get(ClassSession, sess_id).status == "scheduled"

    # Đăng xuất thiếu token bị từ chối
    assert client.post("/logout").status_code == 400
    assert client.get("/lecturer").status_code == 200

    # Có token thì mở được
    token = csrf_token(client, f"/lecturer/courses/{course.id}")
    r = client.post(f"/lecturer/sessions/{sess_id}/open", data={"csrf_token": token})
    assert r.status_code == 302
    db.session.expire_all()
    assert db.session.get(ClassSession, sess_id).status == "open"

    # Kết thúc, chốt, sửa tay thiếu token đều bị từ chối
    for action in ("close", "finalize", "mark"):
        assert client.post(f"/lecturer/sessions/{sess_id}/{action}").status_code == 400
    db.session.expire_all()
    assert db.session.get(ClassSession, sess_id).status == "open"


def test_security_headers(app, client):
    r = client.get("/login")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "same-origin"


def test_session_cookie_flags(app, client):
    make_user("sv01", code="22520001")
    cookies = login(client, "sv01").headers.getlist("Set-Cookie")
    session_cookie = next(c for c in cookies if c.startswith("session="))
    assert "HttpOnly" in session_cookie and "SameSite=Lax" in session_cookie


def test_qr_code_redacted_from_access_log():
    record = logging.LogRecord("werkzeug", logging.INFO, __file__, 1,
                               '%s - - [%s] "%s" %s -',
                               ("10.0.0.5", "now", "GET /checkin?s=3&c=a1b2c3d4e5 HTTP/1.1", "200"),
                               None)
    RedactQrCodeFilter().filter(record)
    msg = record.getMessage()
    assert "a1b2c3d4e5" not in msg and "c=***" in msg and "s=3" in msg


def test_no_inline_scripts(app, client):
    gv = make_user("gv01", role="lecturer")
    course = make_course(gv, [])
    login(client, "gv01")
    client.post(f"/lecturer/sessions/{course.sessions[0].id}/open")
    for path in (f"/lecturer/courses/{course.id}", f"/lecturer/sessions/{course.sessions[0].id}/present"):
        html = client.get(path).get_data(as_text=True)
        assert "<script>" not in html and "onsubmit=" not in html
