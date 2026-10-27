"""Header bảo mật và che mã QR trong log."""
import logging
import re

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' https://cdn.jsdelivr.net",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

_CODE_PARAM = re.compile(r"([?&]c=)[^&\s\"]*")


def redact(text):
    return _CODE_PARAM.sub(r"\1***", text)


class RedactQrCodeFilter(logging.Filter):
    """Không để mã QR trong URL /checkin?...&c=... xuất hiện trong log truy cập."""

    def filter(self, record):
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True


def init_security(app):
    @app.after_request
    def set_headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    werkzeug_logger = logging.getLogger("werkzeug")
    if not any(isinstance(f, RedactQrCodeFilter) for f in werkzeug_logger.filters):
        werkzeug_logger.addFilter(RedactQrCodeFilter())
