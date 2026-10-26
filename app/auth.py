from functools import wraps

import bcrypt
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired

from .models import User

bp = Blueprint("auth", __name__)

# Dùng khi tài khoản không tồn tại để thời gian phản hồi tương đương
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(4))

CHECKIN_LOGIN_NOTE = "Đăng nhập xong, hãy quét lại mã mới trên máy chiếu."


class LoginForm(FlaskForm):
    username = StringField("Tên đăng nhập", validators=[DataRequired()])
    password = PasswordField("Mật khẩu", validators=[DataRequired()])


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


lecturer_required = role_required("lecturer")
student_required = role_required("student")


def home_url(user):
    return url_for("lecturer.index") if user.is_lecturer else url_for("student.me")


def _safe_next(target):
    # Chỉ chấp nhận đường dẫn nội bộ; không quay lại /checkin vì mã đã hết hạn
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if target.startswith("/checkin"):
        return None
    return target


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None:
            bcrypt.checkpw(form.password.data.encode(), _DUMMY_HASH)
        if user is not None and user.check_password(form.password.data):
            login_user(user, remember=True)
            return redirect(_safe_next(request.args.get("next")) or home_url(user))
        error = "Tên đăng nhập hoặc mật khẩu không đúng."
    note = CHECKIN_LOGIN_NOTE if request.args.get("from") == "checkin" else None
    return render_template("login.html", form=form, error=error, note=note)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    # CSRF đã được CSRFProtect kiểm tra trước khi vào view
    logout_user()
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))
