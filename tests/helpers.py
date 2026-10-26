from app import db
from app.models import ClassSession, Course, Enrollment, User

PASSWORD = "Matkhau@123"


def make_user(username, role="student", code=None, name=None):
    u = User(username=username, role=role, full_name=name or username.upper(),
             student_code=code)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    return u


def make_course(lecturer, students, code="BMUD01", sessions=10):
    from datetime import date, timedelta
    c = Course(code=code, name="Môn " + code, lecturer_id=lecturer.id)
    db.session.add(c)
    db.session.flush()
    for s in students:
        db.session.add(Enrollment(course_id=c.id, student_id=s.id))
    for n in range(1, sessions + 1):
        db.session.add(ClassSession(course_id=c.id, number=n,
                                    date=date.today() + timedelta(weeks=n), status="scheduled"))
    db.session.commit()
    return c


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def logout(client):
    return client.post("/logout")
