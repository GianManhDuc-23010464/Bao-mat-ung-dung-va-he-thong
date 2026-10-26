from app.models import ClassSession, Course, User
from app.seed import seed_data
from helpers import login


def test_sheet(app, client):
    seed_data()
    course = Course.query.filter_by(code="BMUD01").one()
    login(client, "gv01")
    page = client.get(f"/lecturer/courses/{course.id}/sheet").get_data(as_text=True)
    assert "Tổng vắng" in page
    assert page.count("Kiểm tra toàn vẹn") == 4
    assert page.count("Chưa diễn ra") == 10 * 6
    for s in course.students:
        assert s.full_name in page
    assert User.query.filter_by(username="sv11").one().full_name not in page


def test_sheet_absent_totals(app, client):
    seed_data()
    course = Course.query.filter_by(code="BMUD01").one()
    sv = User.query.filter_by(username="sv01").one()
    expected = sum(1 for s in course.sessions if s.cell_state(sv.id) == "absent")
    login(client, "gv01")
    page = client.get(f"/lecturer/courses/{course.id}/sheet").get_data(as_text=True)
    row = page.split(sv.full_name, 1)[1].split("</tr>", 1)[0]
    assert row.count("Vắng") == expected
    assert f'fw-bold">{expected}</td>' in row


def test_me_shows_only_own_courses(app, client):
    seed_data()
    login(client, "sv01")  # học BMUD01 và CSDL01
    page = client.get("/me").get_data(as_text=True)
    assert "Bảo mật ứng dụng và hệ thống" in page
    assert "Cơ sở dữ liệu" in page
    assert "Mạng máy tính" not in page
    assert page.count("Tổng vắng") == 2


def test_cell_states(app):
    seed_data()
    sess = ClassSession.query.filter_by(status="scheduled").first()
    assert sess.cell_state(1) == "scheduled"
