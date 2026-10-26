import time

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from . import db, qr
from .auth import lecturer_required
from .integrity import append_event, chain_transaction, sign_session, verify_session
from .models import ClassSession, Course, User, utcnow
from .utils import fmt_time

bp = Blueprint("lecturer", __name__, url_prefix="/lecturer")


def _own_course(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    if course.lecturer_id != current_user.id:
        abort(403)
    return course


def _own_session(session_id):
    sess = db.session.get(ClassSession, session_id)
    if sess is None:
        abort(404)
    if sess.course.lecturer_id != current_user.id:
        abort(403)
    return sess


def present_list(sess):
    """Sinh viên đang có mặt, mới nhất ở trên: [(student, time)]."""
    latest = sess.latest_events()
    rows = []
    for student in sess.course.students:
        if sess.is_present(student.id, latest):
            first = sess.first_scan(student.id)
            rows.append((student, (first or latest[student.id]).created_at))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


@bp.route("")
@lecturer_required
def index():
    courses = Course.query.filter_by(lecturer_id=current_user.id).order_by(Course.id).all()
    return render_template("lecturer/index.html", courses=courses)


@bp.route("/courses/<int:course_id>")
@lecturer_required
def course(course_id):
    course = _own_course(course_id)
    return render_template("lecturer/course.html", course=course)


@bp.route("/courses/<int:course_id>/sheet")
@lecturer_required
def sheet(course_id):
    course = _own_course(course_id)
    latest = {s.id: s.latest_events() for s in course.sessions}
    rows = []
    for student in course.students:
        cells = [s.cell_state(student.id, latest[s.id]) for s in course.sessions]
        rows.append((student, cells, cells.count("absent")))
    return render_template("lecturer/sheet.html", course=course, rows=rows)


@bp.route("/sessions/<int:session_id>/open", methods=["POST"])
@lecturer_required
def open_session(session_id):
    sess = _own_session(session_id)
    if sess.status != "scheduled":
        flash("Buổi này không ở trạng thái chưa diễn ra.", "warning")
        return redirect(url_for("lecturer.course", course_id=sess.course_id))
    sess.secret_key = qr.new_secret()
    sess.status = "open"
    sess.opened_at = utcnow()
    db.session.commit()
    return redirect(url_for("lecturer.present", session_id=sess.id))


@bp.route("/sessions/<int:session_id>/present")
@lecturer_required
def present(session_id):
    sess = _own_session(session_id)
    if sess.status != "open":
        return redirect(url_for("lecturer.session_detail", session_id=sess.id))
    return render_template("lecturer/present.html", sess=sess)


@bp.route("/sessions/<int:session_id>/qr")
@lecturer_required
def qr_api(session_id):
    sess = _own_session(session_id)
    if sess.status != "open" or not sess.secret_key:
        return jsonify({"error": "Buổi không mở.", "status": sess.status}), 409
    resp = jsonify(qr.qr_payload(sess, time.time()))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/sessions/<int:session_id>/live")
@lecturer_required
def live_api(session_id):
    sess = _own_session(session_id)
    rows = present_list(sess)
    resp = jsonify({
        "status": sess.status,
        "count": len(rows),
        "total": len(sess.course.enrollments),
        "students": [{"name": s.full_name, "student_code": s.student_code,
                      "time": fmt_time(t)} for s, t in rows],
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@lecturer_required
def close_session(session_id):
    sess = _own_session(session_id)
    if sess.status == "open":
        sess.status = "closed"
        sess.closed_at = utcnow()
        db.session.commit()
        flash("Đã kết thúc điểm danh.", "success")
    return redirect(url_for("lecturer.session_detail", session_id=sess.id))


def _render_session(sess, verify=None):
    latest = sess.latest_events()
    rows = [(s, sess.is_present(s.id, latest), latest.get(s.id)) for s in sess.course.students]
    return render_template("lecturer/session.html", sess=sess, rows=rows, verify=verify, signature=sess.signatures[-1] if sess.signatures else None)


@bp.route("/sessions/<int:session_id>")
@lecturer_required
def session_detail(session_id):
    sess = _own_session(session_id)
    if sess.status == "open":
        return redirect(url_for("lecturer.present", session_id=sess.id))
    return _render_session(sess)


@bp.route("/sessions/<int:session_id>/finalize", methods=["POST"])
@lecturer_required
def finalize_session(session_id):
    sess = _own_session(session_id)
    if sess.status != "closed":
        flash("Chỉ chốt được buổi đã kết thúc điểm danh.", "warning")
    else:
        with chain_transaction():
            sess.status = "finalized"
            sess.finalized_at = utcnow()
            sess.secret_key = None
            sign_session(sess)
        flash("Đã chốt buổi và ký số kết quả.", "success")
    return redirect(url_for("lecturer.session_detail", session_id=sess.id))


@bp.route("/sessions/<int:session_id>/mark", methods=["POST"])
@lecturer_required
def mark(session_id):
    """Sửa tay: thêm một sự kiện mới (không sửa sự kiện cũ)."""
    sess = _own_session(session_id)
    student = db.session.get(User, request.form.get("student_id", type=int) or 0)
    kind = {"present": "manual_present", "absent": "manual_absent"}.get(request.form.get("state"))
    if student is None or kind is None or not sess.course.has_student(student):
        abort(400)
    if sess.status not in ("closed", "finalized"):
        flash("Chỉ sửa tay sau khi đã kết thúc điểm danh.", "warning")
        return redirect(url_for("lecturer.session_detail", session_id=sess.id))
    if sess.is_present(student.id) == (kind == "manual_present"):
        flash("Trạng thái không thay đổi.", "info")
        return redirect(url_for("lecturer.session_detail", session_id=sess.id))
    with chain_transaction():
        append_event(sess, student.id, kind, actor_id=current_user.id, ip=request.remote_addr)
        if sess.status == "finalized":
            sign_session(sess)
    label = "có mặt" if kind == "manual_present" else "vắng"
    flash(f"Đã ghi {student.full_name}: {label}"
          + (" và ký lại kết quả buổi." if sess.status == "finalized" else "."), "success")
    return redirect(url_for("lecturer.session_detail", session_id=sess.id))


@bp.route("/sessions/<int:session_id>/verify")
@lecturer_required
def verify(session_id):
    sess = _own_session(session_id)
    if sess.status == "open":
        return redirect(url_for("lecturer.present", session_id=sess.id))
    return _render_session(sess, verify=verify_session(sess))
