from app import db
from app.models import ClassSession
from helpers import login, make_course, make_user


def setup(app):
    gv = make_user("gv01", role="lecturer")
    svs = [make_user(f"sv{i:02d}", code=f"2252{i:04d}") for i in range(1, 4)]
    course = make_course(gv, svs)
    return gv, svs, course


def test_index_and_course_pages(app, client):
    _, _, course = setup(app)
    login(client, "gv01")
    assert "Môn BMUD01" in client.get("/lecturer").get_data(as_text=True)
    page = client.get(f"/lecturer/courses/{course.id}").get_data(as_text=True)
    assert "Tạo buổi điểm danh" in page


def test_open_present_qr_live_close(app, client):
    _, _, course = setup(app)
    sess = course.sessions[4]
    login(client, "gv01")
    r = client.post(f"/lecturer/sessions/{sess.id}/open")
    assert r.headers["Location"].endswith(f"/lecturer/sessions/{sess.id}/present")
    db.session.refresh(sess)
    assert sess.status == "open" and sess.secret_key and sess.opened_at

    assert client.get(f"/lecturer/sessions/{sess.id}/present").status_code == 200
    data = client.get(f"/lecturer/sessions/{sess.id}/qr").get_json()
    assert data["url"].startswith(f"http://testserver/checkin?s={sess.id}&c=")
    assert set(data) == {"url", "frame", "expires_in"}
    assert sess.secret_key.hex() not in str(data)
    live = client.get(f"/lecturer/sessions/{sess.id}/live").get_json()
    assert live["count"] == 0 and live["total"] == 3

    client.post(f"/lecturer/sessions/{sess.id}/close")
    db.session.refresh(sess)
    assert sess.status == "closed" and sess.closed_at
    assert client.get(f"/lecturer/sessions/{sess.id}/qr").status_code == 409
    # Không mở lại được buổi đã kết thúc
    client.post(f"/lecturer/sessions/{sess.id}/open")
    db.session.refresh(sess)
    assert sess.status == "closed"


def test_student_cannot_use_lecturer_api(app, client):
    _, _, course = setup(app)
    sess = course.sessions[0]
    login(client, "sv01")
    assert client.get(f"/lecturer/sessions/{sess.id}/qr").status_code == 403
    assert client.post(f"/lecturer/sessions/{sess.id}/open").status_code == 403
    assert db.session.get(ClassSession, sess.id).status == "scheduled"
