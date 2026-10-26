import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user

from . import db, qr
from .auth import student_required
from .integrity import append_event, chain_transaction
from .models import AttendanceEvent, ClassSession, Course, Enrollment
from .utils import fmt_time

bp = Blueprint("student", __name__)


def _now():
    return time.time()


class RateLimiter:
    """Giới hạn đơn giản trong bộ nhớ: tối đa `limit` lượt trong `window` giây."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, window, now):
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


checkin_limiter = RateLimiter()


def _result(ok, message, course=None, status=200):
    return render_template("student/checkin.html", ok=ok, message=message, course=course), status


@bp.route("/checkin")
def checkin():
    # 1. Chưa đăng nhập: không tự điểm danh sau khi đăng nhập vì mã đã hết hạn
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", **{"from": "checkin"}))

    now = _now()
    if not checkin_limiter.allow(current_user.id, current_app.config["CHECKIN_RATE_LIMIT"],
                                 current_app.config["CHECKIN_RATE_WINDOW"], now):
        abort(429)

    session_id = request.args.get("s", type=int)
    code = request.args.get("c", "")
    sess = db.session.get(ClassSession, session_id) if session_id else None

    # 2. Không phải sinh viên, hoặc không thuộc lớp của buổi
    if not current_user.is_student or sess is None or not sess.course.has_student(current_user):
        return _result(False, "Bạn không thuộc lớp này.", status=403)
    course = sess.course

    # 3. Buổi chưa mở hoặc đã kết thúc
    if sess.status != "open":
        return _result(False, "Giảng viên đã kết thúc điểm danh.", course)

    # 4. Mã không khớp khung hiện tại
    if not qr.verify_code(sess.secret_key, code, now):
        return _result(False, "Mã đã đổi, vui lòng quét lại mã trên máy chiếu.", course)

    with chain_transaction():
        # 5. Đã điểm danh
        existing = (AttendanceEvent.query
                    .filter_by(session_id=sess.id, student_id=current_user.id, kind="scan")
                    .order_by(AttendanceEvent.id).first())
        if existing:
            return _result(False, f"Bạn đã điểm danh buổi này lúc {fmt_time(existing.created_at)}.",
                           course)
        # 6. Hợp lệ
        ev = append_event(sess, current_user.id, "scan", actor_id=current_user.id,
                          ip=request.remote_addr)
    return _result(True, f"Điểm danh thành công lúc {fmt_time(ev.created_at)}", course)


@bp.route("/me")
@student_required
def me():
    courses = (Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id)
               .order_by(Course.id).all())
    tables = []
    for course in courses:
        rows = [(s, s.cell_state(current_user.id)) for s in course.sessions]
        tables.append((course, rows, sum(1 for _, st in rows if st == "absent")))
    return render_template("student/me.html", tables=tables)
