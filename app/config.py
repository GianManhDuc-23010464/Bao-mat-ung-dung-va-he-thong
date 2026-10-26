import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Để trống = tự phát hiện IP mạng nội bộ
    BASE_URL = os.environ.get("BASE_URL", "").strip()
    PORT = 5000

    KEYS_DIR = os.path.join(BASE_DIR, "keys")

    # Cookie phiên
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Giới hạn quét /checkin: 10 lượt/phút mỗi tài khoản
    CHECKIN_RATE_LIMIT = 10
    CHECKIN_RATE_WINDOW = 60

    WTF_CSRF_TIME_LIMIT = None
    BCRYPT_ROUNDS = 12


def ensure_secret_key(config):
    if not config.get("SECRET_KEY"):
        # Chỉ dùng khi chưa cấu hình .env; phiên sẽ mất khi khởi động lại.
        config["SECRET_KEY"] = secrets.token_hex(32)
        print("Cảnh báo: chưa đặt SECRET_KEY trong .env, đang dùng khóa tạm thời.")
