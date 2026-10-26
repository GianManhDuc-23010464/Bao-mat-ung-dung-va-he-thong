"""Mã QR động: mã HMAC theo khung 5 giây, chỉ chấp nhận khung hiện tại.

Các hàm nhận `now` (giây, kiểu time.time()) để kiểm thử được; tầng logic không
gọi time.time() trực tiếp.
"""
import hashlib
import hmac
import secrets
import socket
from urllib.parse import urlencode

from flask import current_app

FRAME_SECONDS = 5
CODE_LENGTH = 10


def new_secret():
    return secrets.token_bytes(32)


def frame_at(now):
    return int(now) // FRAME_SECONDS


def expires_in(now):
    return FRAME_SECONDS - (int(now) % FRAME_SECONDS)


def code_for_frame(secret_key, frame):
    return hmac.new(secret_key, str(frame).encode(), hashlib.sha256).hexdigest()[:CODE_LENGTH]


def current_code(secret_key, now):
    return code_for_frame(secret_key, frame_at(now))


def verify_code(secret_key, code, now):
    """Chỉ chấp nhận mã của khung hiện tại."""
    if not secret_key or not isinstance(code, str) or len(code) != CODE_LENGTH:
        return False
    return hmac.compare_digest(current_code(secret_key, now), code)


def detect_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect không gửi gói tin nào, chỉ để hệ điều hành chọn giao diện mạng
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def base_url():
    configured = current_app.config.get("BASE_URL")
    if configured:
        return configured.rstrip("/")
    return f"http://{detect_lan_ip()}:{current_app.config.get('PORT', 5000)}"


def checkin_url(session_id, code):
    return base_url() + "/checkin?" + urlencode({"s": session_id, "c": code})


def qr_payload(session, now):
    """Dữ liệu cho API màn hình chiếu."""
    return {
        "url": checkin_url(session.id, current_code(session.secret_key, now)),
        "frame": frame_at(now),
        "expires_in": expires_in(now),
    }
