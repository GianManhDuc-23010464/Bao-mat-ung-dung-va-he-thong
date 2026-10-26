"""Dữ liệu mẫu cho demo. `flask seed` xóa CSDL cũ và tạo lại từ đầu."""
import random
from datetime import date, datetime, time, timedelta

from . import db
from .integrity import append_event, sign_session
from .models import ClassSession, Course, Enrollment, User

PASSWORD = "Matkhau@123"

STUDENT_NAMES = [
    "Trần Thị Bình", "Lê Hoàng Cường", "Phạm Minh Dũng", "Hoàng Thị Hà",
    "Vũ Đức Hải", "Đặng Thu Hằng", "Bùi Quang Huy", "Đỗ Thị Lan",
    "Ngô Văn Long", "Dương Thị Mai", "Lý Hoàng Nam", "Hồ Thị Ngọc",
    "Phan Văn Phúc", "Trịnh Thị Quỳnh", "Mai Đức Sơn", "Đinh Thị Thảo",
    "Võ Minh Tuấn", "Lương Thị Uyên", "Tạ Quốc Việt", "Cao Thị Yến",
]

COURSES = [
    ("BMUD01", "Bảo mật ứng dụng và hệ thống", list(range(1, 11))),
    ("MMT01", "Mạng máy tính", list(range(6, 16))),
    ("CSDL01", "Cơ sở dữ liệu", list(range(1, 6)) + list(range(16, 21))),
]


def seed_data():
    random.seed(42)
    db.drop_all()
    db.create_all()

    lecturer = User(username="gv01", full_name="Nguyễn Văn An", role="lecturer")
    lecturer.set_password(PASSWORD)
    db.session.add(lecturer)

    students = {}
    for i, name in enumerate(STUDENT_NAMES, start=1):
        s = User(username=f"sv{i:02d}", full_name=name, role="student",
                 student_code=f"2252{i:04d}")
        s.set_password(PASSWORD)
        db.session.add(s)
        students[i] = s
    db.session.flush()

    today = date.today()
    for code, name, member_ids in COURSES:
        course = Course(code=code, name=name, lecturer_id=lecturer.id)
        db.session.add(course)
        db.session.flush()
        for i in member_ids:
            db.session.add(Enrollment(course_id=course.id, student_id=students[i].id))

        for number in range(1, 11):
            if number <= 4:
                d = today - timedelta(weeks=5 - number)  # 4, 3, 2, 1 tuần trước
            else:
                d = today + timedelta(weeks=number - 4)
            sess = ClassSession(course_id=course.id, number=number, date=d, status="scheduled")
            db.session.add(sess)
            db.session.flush()
            if number <= 4:
                _fill_past_session(sess, [students[i] for i in member_ids])

    db.session.commit()


def _fill_past_session(sess, members):
    opened = datetime.combine(sess.date, time(7, 0))  # UTC
    sess.opened_at = opened
    scans = []
    for s in members:
        if random.random() < 0.8:
            scans.append((opened + timedelta(seconds=random.randint(5, 600)), s))
    scans.sort(key=lambda x: x[0])
    for created_at, s in scans:
        append_event(sess, s.id, "scan", actor_id=s.id,
                     ip=f"192.168.1.{random.randint(10, 200)}", created_at=created_at)
    sess.closed_at = opened + timedelta(minutes=15)
    sess.finalized_at = opened + timedelta(minutes=20)
    sess.status = "finalized"
    sess.secret_key = None
    sign_session(sess, signed_at=sess.finalized_at)
