import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    from .config import Config, ensure_secret_key

    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    ensure_secret_key(app.config)

    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith("sqlite:///"):
        os.makedirs(os.path.dirname(db_uri[len("sqlite:///"):]) or ".", exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Vui lòng đăng nhập."
    login_manager.login_message_category = "warning"

    from . import models  # noqa: F401  (đăng ký bảng)
    from . import auth, lecturer, student

    app.register_blueprint(auth.bp)
    app.register_blueprint(lecturer.bp)
    app.register_blueprint(student.bp)
    register_error_handlers(app)

    from .utils import register_filters
    register_filters(app)

    from .security import init_security
    init_security(app)

    with app.app_context():
        db.create_all()

    register_cli(app)
    return app


ERROR_MESSAGES = {
    400: "Yêu cầu không hợp lệ.",
    403: "Bạn không có quyền truy cập trang này.",
    404: "Không tìm thấy trang.",
    405: "Phương thức không được hỗ trợ.",
    429: "Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút.",
}


def register_error_handlers(app):
    from flask import render_template, request

    def handler(err):
        code = getattr(err, "code", 500) or 500
        message = ERROR_MESSAGES.get(code, "Đã xảy ra lỗi.")
        if request.path.endswith(("/qr", "/live")):
            return {"error": message}, code
        return render_template("error.html", code=code, message=message), code

    for code in ERROR_MESSAGES:
        app.register_error_handler(code, handler)


def register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        """Xóa CSDL cũ và tạo dữ liệu mẫu."""
        from .seed import seed_data
        seed_data()
        print("Đã tạo dữ liệu mẫu.")
