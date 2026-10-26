import pytest

from app import db, qr, student
from app.models import AttendanceEvent
from helpers import login, logout, make_course, make_user

NOW = 1_700_000_002.0


@pytest.fixture
def setup(app, client, monkeypatch):
    monkeypatch.setattr(student, "_now", lambda: NOW)
    gv = make_user("gv01", role="lecturer")
    sv1 = make_user("sv01", code="22520001")
    sv2 = make_user("sv02", code="22520002")
    outsider = make_user("sv99", code="22520099")
    course = make_course(gv, [sv1, sv2])
    sess = course.sessions[4]
    login(client, "gv01")
    client.post(f"/lecturer/sessions/{sess.id}/open")
    logout(client)
    db.session.refresh(sess)
    return {"gv": gv, "sv1": sv1, "outsider": outsider, "course": course, "sess": sess}


def url(sess, code=None):
    code = code if code is not None else qr.current_code(sess.secret_key, NOW)
    return f"/checkin?s={sess.id}&c={code}"


def count(sess):
    return AttendanceEvent.query.filter_by(session_id=sess.id).count()


def test_checkin_success(setup, client):
    sess = setup["sess"]
    login(client, "sv01")
    page = client.get(url(sess)).get_data(as_text=True)
    assert "Điểm danh thành công lúc" in page and "Môn BMUD01" in page
    ev = AttendanceEvent.query.filter_by(session_id=sess.id).one()
    assert ev.kind == "scan" and ev.student_id == setup["sv1"].id
    live = None
    logout(client)
    login(client, "gv01")
    live = client.get(f"/lecturer/sessions/{sess.id}/live").get_json()
    assert live["count"] == 1 and live["students"][0]["student_code"] == "22520001"


def test_old_code_rejected_via_route(setup, client):
    sess = setup["sess"]
    login(client, "sv01")
    old = qr.current_code(sess.secret_key, NOW - 5)
    assert "Mã đã đổi" in client.get(url(sess, old)).get_data(as_text=True)
    assert count(sess) == 0


def test_4_closed_session_rejected_even_with_valid_code(setup, client):
    sess = setup["sess"]
    valid = url(sess)
    login(client, "gv01")
    client.post(f"/lecturer/sessions/{sess.id}/close")
    logout(client)
    login(client, "sv01")
    assert "Giảng viên đã kết thúc điểm danh." in client.get(valid).get_data(as_text=True)
    assert count(sess) == 0


def test_4b_scheduled_session_rejected(setup, client):
    other = setup["course"].sessions[5]
    login(client, "sv01")
    r = client.get(f"/checkin?s={other.id}&c=0123456789")
    assert "Giảng viên đã kết thúc điểm danh." in r.get_data(as_text=True)


def test_5_student_not_in_course_rejected(setup, client):
    sess = setup["sess"]
    login(client, "sv99")
    r = client.get(url(sess))
    assert "Bạn không thuộc lớp này." in r.get_data(as_text=True)
    assert count(sess) == 0


def test_5b_lecturer_cannot_checkin(setup, client):
    sess = setup["sess"]
    login(client, "gv01")
    assert "Bạn không thuộc lớp này." in client.get(url(sess)).get_data(as_text=True)
    assert count(sess) == 0


def test_6_double_scan_records_once(setup, client):
    sess = setup["sess"]
    login(client, "sv01")
    client.get(url(sess))
    page = client.get(url(sess)).get_data(as_text=True)
    assert "Bạn đã điểm danh buổi này lúc" in page
    assert count(sess) == 1


def test_7_not_logged_in_redirects_and_records_nothing(setup, client):
    sess = setup["sess"]
    r = client.get(url(sess))
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert count(sess) == 0
    page = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Đăng nhập xong, hãy quét lại mã mới trên máy chiếu." in page
    # Đăng nhập xong không tự điểm danh
    r = client.post(r.headers["Location"], data={"username": "sv01", "password": "Matkhau@123"})
    assert r.headers["Location"].endswith("/me")
    assert count(sess) == 0


def test_8_lecturer_cannot_access_other_lecturers_session(setup, client):
    sess, course = setup["sess"], setup["course"]
    make_user("gv02", role="lecturer")
    other_scheduled = course.sessions[6]
    login(client, "gv02")
    assert client.get("/lecturer").status_code == 200
    assert "Môn BMUD01" not in client.get("/lecturer").get_data(as_text=True)
    assert client.get(f"/lecturer/courses/{course.id}").status_code == 403
    assert client.post(f"/lecturer/sessions/{other_scheduled.id}/open").status_code == 403
    db.session.refresh(other_scheduled)
    assert other_scheduled.status == "scheduled"
    for path in ("present", "qr", "live", ""):
        u = f"/lecturer/sessions/{sess.id}" + (f"/{path}" if path else "")
        assert client.get(u).status_code == 403
    assert client.post(f"/lecturer/sessions/{sess.id}/close").status_code == 403
    db.session.refresh(sess)
    assert sess.status == "open"


def test_rate_limit(setup, client):
    sess = setup["sess"]
    login(client, "sv01")
    codes = [client.get(url(sess, "0000000000")).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429
