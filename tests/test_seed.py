from app.models import ClassSession, Course, User
from app.seed import seed_data


def test_seed(app):
    seed_data()
    assert User.query.filter_by(role="lecturer").count() == 1
    assert User.query.filter_by(role="student").count() == 20
    courses = Course.query.all()
    assert len(courses) == 3
    for c in courses:
        assert len(c.enrollments) == 10
        assert [s.number for s in c.sessions] == list(range(1, 11))
        for s in c.sessions:
            if s.number <= 4:
                assert s.status == "finalized"
                assert len(s.signatures) == 1
                assert s.secret_key is None
            else:
                assert s.status == "scheduled"
    assert User.query.filter_by(username="sv01").first().check_password("Matkhau@123")


def test_seed_deterministic(app):
    seed_data()
    first = [(e.student_id, e.kind) for s in ClassSession.query.all() for e in s.events]
    seed_data()
    second = [(e.student_id, e.kind) for s in ClassSession.query.all() for e in s.events]
    assert first == second
