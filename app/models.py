from datetime import datetime, timezone

import bcrypt
from flask import current_app
from flask_login import UserMixin
from sqlalchemy import event

from . import db, login_manager


def utcnow():
    """Thời điểm hiện tại theo UTC (naive, làm tròn đến giây) để lưu CSDL."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False)  # lecturer / student
    student_code = db.Column(db.String(16), nullable=True)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(current_app.config.get("BCRYPT_ROUNDS", 12))).decode()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    @property
    def is_lecturer(self):
        return self.role == "lecturer"

    @property
    def is_student(self):
        return self.role == "student"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    lecturer = db.relationship("User")
    sessions = db.relationship("ClassSession", back_populates="course",
                               order_by="ClassSession.number")
    enrollments = db.relationship("Enrollment", back_populates="course")

    @property
    def students(self):
        return sorted((e.student for e in self.enrollments), key=lambda s: s.student_code or "")

    def has_student(self, user):
        return any(e.student_id == user.id for e in self.enrollments)


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)

    course = db.relationship("Course", back_populates="enrollments")
    student = db.relationship("User")


class ClassSession(db.Model):
    __tablename__ = "class_sessions"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # 1–10
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="scheduled")
    secret_key = db.Column(db.LargeBinary, nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    finalized_at = db.Column(db.DateTime, nullable=True)

    course = db.relationship("Course", back_populates="sessions")
    events = db.relationship("AttendanceEvent", order_by="AttendanceEvent.id",
                             back_populates="session")
    signatures = db.relationship("SessionSignature", order_by="SessionSignature.id",
                                 back_populates="session")

    STATUS_LABELS = {
        "scheduled": "Chưa diễn ra",
        "open": "Đang điểm danh",
        "closed": "Đã kết thúc, chưa chốt",
        "finalized": "Đã chốt",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    def latest_events(self):
        """Sự kiện mới nhất của từng sinh viên: {student_id: AttendanceEvent}."""
        latest = {}
        for ev in self.events:
            latest[ev.student_id] = ev
        return latest

    def is_present(self, student_id, latest=None):
        latest = self.latest_events() if latest is None else latest
        ev = latest.get(student_id)
        return ev is not None and ev.kind in ("scan", "manual_present")

    def cell_state(self, student_id, latest=None):
        """present / absent / pending (đang mở, chưa điểm danh) / scheduled."""
        if self.status == "scheduled":
            return "scheduled"
        if self.is_present(student_id, latest):
            return "present"
        return "pending" if self.status == "open" else "absent"

    def first_scan(self, student_id):
        for ev in self.events:
            if ev.student_id == student_id and ev.kind == "scan":
                return ev
        return None


class AttendanceEvent(db.Model):
    """Chỉ thêm, không sửa, không xóa."""
    __tablename__ = "attendance_events"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(16), nullable=False)  # scan / manual_present / manual_absent
    created_at = db.Column(db.DateTime, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ip = db.Column(db.String(64), nullable=True)
    prev_hash = db.Column(db.String(64), nullable=False)
    hash = db.Column(db.String(64), nullable=False)

    session = db.relationship("ClassSession", back_populates="events")
    student = db.relationship("User", foreign_keys=[student_id])
    actor = db.relationship("User", foreign_keys=[actor_id])


@event.listens_for(AttendanceEvent, "before_update")
def _forbid_update(mapper, connection, target):
    raise RuntimeError("attendance_events là bảng chỉ thêm, không được sửa.")


@event.listens_for(AttendanceEvent, "before_delete")
def _forbid_delete(mapper, connection, target):
    raise RuntimeError("attendance_events là bảng chỉ thêm, không được xóa.")


class SessionSignature(db.Model):
    __tablename__ = "session_signatures"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id"), nullable=False)
    final_hash = db.Column(db.String(64), nullable=False)
    signature = db.Column(db.String(128), nullable=False)  # hex
    signed_at = db.Column(db.DateTime, nullable=False)

    session = db.relationship("ClassSession", back_populates="signatures")
