"""Chuỗi băm cho từng buổi, ký số Ed25519, kiểm tra toàn vẹn."""
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from datetime import timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import current_app
from sqlalchemy import select

from . import db
from .models import AttendanceEvent, SessionSignature, User, utcnow


# Tuần tự hóa "đọc hash cuối -> thêm sự kiện" giữa các luồng của máy chủ
_chain_lock = threading.RLock()


@contextmanager
def chain_transaction():
    """Một transaction cho việc nối chuỗi: đọc hash cuối và ghi sự kiện mới
    cùng commit, hoặc cùng rollback nếu lỗi."""
    with _chain_lock:
        try:
            yield
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


# ---------- Khóa ký ----------

def _key_paths():
    keys_dir = current_app.config["KEYS_DIR"]
    return (os.path.join(keys_dir, "signing_key.pem"),
            os.path.join(keys_dir, "signing_key.pub.pem"))


def get_private_key():
    priv_path, pub_path = _key_paths()
    if not os.path.exists(priv_path):
        os.makedirs(os.path.dirname(priv_path), exist_ok=True)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        with open(pub_path, "wb") as f:
            f.write(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo))
        return key
    with open(priv_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def get_public_key():
    _, pub_path = _key_paths()
    if not os.path.exists(pub_path):
        get_private_key()
    with open(pub_path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


# ---------- Chuỗi băm ----------

def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def genesis_hash(session_id):
    return sha256_hex("GENESIS:" + str(session_id))


def _iso_utc(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat()


def event_payload(session_id, student_id, kind, created_at, actor_id, ip):
    return {
        "session_id": session_id,
        "student_id": student_id,
        "kind": kind,
        "created_at": _iso_utc(created_at),
        "actor_id": actor_id,
        "ip": ip,
    }


def compute_hash(prev_hash, payload):
    return sha256_hex(prev_hash + "|" + json.dumps(payload, sort_keys=True, ensure_ascii=False))


def last_hash(session_id):
    last = (AttendanceEvent.query.filter_by(session_id=session_id)
            .order_by(AttendanceEvent.id.desc()).first())
    return last.hash if last else genesis_hash(session_id)


def append_event(session, student_id, kind, actor_id, ip, created_at=None):
    """Thêm một sự kiện nối vào chuỗi của buổi. Người gọi chịu trách nhiệm commit
    (cùng transaction với việc đọc hash cuối)."""
    created_at = created_at or utcnow()
    prev = last_hash(session.id)
    payload = event_payload(session.id, student_id, kind, created_at, actor_id, ip)
    ev = AttendanceEvent(session_id=session.id, student_id=student_id, kind=kind,
                         created_at=created_at, actor_id=actor_id, ip=ip,
                         prev_hash=prev, hash=compute_hash(prev, payload))
    db.session.add(ev)
    db.session.flush()
    return ev


# ---------- Ký số ----------

def sign_session(session, signed_at=None):
    """Ký hash cuối của buổi, thêm một dòng mới vào session_signatures."""
    final = last_hash(session.id)
    signature = get_private_key().sign(final.encode()).hex()
    sig = SessionSignature(session_id=session.id, final_hash=final,
                           signature=signature, signed_at=signed_at or utcnow())
    db.session.add(sig)
    db.session.flush()
    return sig


# ---------- Kiểm tra toàn vẹn ----------

def _describe(ev):
    from .utils import fmt_datetime
    student = db.session.get(User, ev.student_id)
    who = f"{student.full_name} – {student.student_code}" if student else f"#{ev.student_id}"
    return f"sinh viên {who}, lúc {fmt_datetime(ev.created_at)}"


def verify_session(session):
    """Tính lại chuỗi từ genesis và xác minh chữ ký mới nhất.

    Trả về dict: ok (bool), message, detail (chuỗi phụ hoặc None), event_id.
    """
    events = db.session.execute(
        select(AttendanceEvent).where(AttendanceEvent.session_id == session.id)
        .order_by(AttendanceEvent.id)
        .execution_options(populate_existing=True)
    ).scalars().all()

    prev = genesis_hash(session.id)
    for ev in events:
        payload = event_payload(ev.session_id, ev.student_id, ev.kind, ev.created_at,
                                ev.actor_id, ev.ip)
        if ev.prev_hash != prev:
            detail = "Liên kết với sự kiện trước bị đứt: có sự kiện đã bị xóa hoặc chèn thêm."
        elif compute_hash(prev, payload) != ev.hash or ev.session_id != session.id:
            detail = "Nội dung sự kiện không khớp với hash đã lưu."
        else:
            prev = ev.hash
            continue
        return {"ok": False, "event_id": ev.id, "detail": detail,
                "message": f"Dữ liệu đã bị sửa tại sự kiện #{ev.id} ({_describe(ev)})"}

    sig = db.session.execute(
        select(SessionSignature).where(SessionSignature.session_id == session.id)
        .order_by(SessionSignature.id.desc())
        .execution_options(populate_existing=True)
    ).scalars().first()
    if sig is None:
        if session.status == "finalized":
            return {"ok": False, "event_id": None, "message": "Chữ ký không hợp lệ",
                    "detail": "Buổi đã chốt nhưng không tìm thấy chữ ký."}
        return {"ok": True, "event_id": None, "message": "Còn nguyên vẹn",
                "detail": "Chuỗi băm khớp. Buổi chưa chốt nên chưa có chữ ký."}

    try:
        get_public_key().verify(bytes.fromhex(sig.signature), sig.final_hash.encode())
    except (InvalidSignature, ValueError):
        return {"ok": False, "event_id": None, "message": "Chữ ký không hợp lệ", "detail": None}

    if sig.final_hash != prev:
        last = events[-1] if events else None
        where = f" sau sự kiện #{last.id}" if last else ""
        return {"ok": False, "event_id": None,
                "message": "Dữ liệu đã bị sửa: hash cuối của chuỗi không khớp với bản đã ký",
                "detail": f"Có thể đã mất sự kiện{where}, hoặc chuỗi đã bị tính lại."}

    return {"ok": True, "event_id": None, "message": "Còn nguyên vẹn",
            "detail": f"{len(events)} sự kiện, chữ ký Ed25519 hợp lệ."}
