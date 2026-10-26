import pytest
from sqlalchemy import text

from app import db
from app.integrity import append_event, genesis_hash, verify_session
from app.models import AttendanceEvent, SessionSignature
from helpers import login, make_course, make_user


@pytest.fixture
def closed_session(app, client):
    gv = make_user("gv01", role="lecturer")
    svs = [make_user(f"sv{i:02d}", code=f"2252{i:04d}", name=f"Sinh viên {i}") for i in range(1, 5)]
    course = make_course(gv, svs)
    sess = course.sessions[4]
    login(client, "gv01")
    client.post(f"/lecturer/sessions/{sess.id}/open")
    for s in svs[:3]:
        append_event(sess, s.id, "scan", actor_id=s.id, ip="10.0.0.1")
    db.session.commit()
    client.post(f"/lecturer/sessions/{sess.id}/close")
    db.session.refresh(sess)
    return sess, svs


def finalize(client, sess):
    client.post(f"/lecturer/sessions/{sess.id}/finalize")
    db.session.refresh(sess)


def event_ids(sess):
    return [e.id for e in AttendanceEvent.query.filter_by(session_id=sess.id)
            .order_by(AttendanceEvent.id)]


def test_chain_links(closed_session):
    sess, _ = closed_session
    events = AttendanceEvent.query.filter_by(session_id=sess.id).order_by(AttendanceEvent.id).all()
    assert events[0].prev_hash == genesis_hash(sess.id)
    for a, b in zip(events, events[1:]):
        assert b.prev_hash == a.hash


def test_9_finalized_session_is_intact(closed_session, client):
    sess, _ = closed_session
    finalize(client, sess)
    assert sess.status == "finalized" and sess.secret_key is None
    assert len(sess.signatures) == 1
    assert verify_session(sess)["message"] == "Còn nguyên vẹn"
    page = client.get(f"/lecturer/sessions/{sess.id}/verify").get_data(as_text=True)
    assert "Còn nguyên vẹn" in page


def test_9b_empty_session_signs_genesis(app, client):
    gv = make_user("gv01", role="lecturer")
    course = make_course(gv, [make_user("sv01", code="22520001")])
    sess = course.sessions[0]
    login(client, "gv01")
    client.post(f"/lecturer/sessions/{sess.id}/open")
    client.post(f"/lecturer/sessions/{sess.id}/close")
    finalize(client, sess)
    assert sess.signatures[0].final_hash == genesis_hash(sess.id)
    assert verify_session(sess)["ok"]


def test_10_raw_sql_kind_change_detected_at_right_row(closed_session, client):
    sess, svs = closed_session
    finalize(client, sess)
    target = event_ids(sess)[1]
    db.session.execute(text("UPDATE attendance_events SET kind = 'manual_absent' WHERE id = :id"),
                       {"id": target})
    db.session.commit()
    result = verify_session(sess)
    assert not result["ok"]
    assert result["event_id"] == target
    assert result["message"].startswith(f"Dữ liệu đã bị sửa tại sự kiện #{target} (sinh viên Sinh viên 2")
    page = client.get(f"/lecturer/sessions/{sess.id}/verify").get_data(as_text=True)
    assert f"Dữ liệu đã bị sửa tại sự kiện #{target}" in page


def test_11_deleted_middle_row_detected(closed_session, client):
    sess, _ = closed_session
    finalize(client, sess)
    ids = event_ids(sess)
    db.session.execute(text("DELETE FROM attendance_events WHERE id = :id"), {"id": ids[1]})
    db.session.commit()
    result = verify_session(sess)
    assert not result["ok"] and result["event_id"] == ids[2]


def test_11b_deleted_last_row_detected(closed_session, client):
    sess, _ = closed_session
    finalize(client, sess)
    db.session.execute(text("DELETE FROM attendance_events WHERE id = :id"),
                       {"id": event_ids(sess)[-1]})
    db.session.commit()
    result = verify_session(sess)
    assert not result["ok"] and "không khớp với bản đã ký" in result["message"]


def test_12_manual_edit_after_finalize_keeps_chain_and_resigns(closed_session, client):
    sess, svs = closed_session
    finalize(client, sess)
    old_sig = sess.signatures[0]
    old_final = old_sig.final_hash
    client.post(f"/lecturer/sessions/{sess.id}/mark",
                data={"student_id": svs[3].id, "state": "present"})
    client.post(f"/lecturer/sessions/{sess.id}/mark",
                data={"student_id": svs[0].id, "state": "absent"})
    db.session.refresh(sess)
    sigs = SessionSignature.query.filter_by(session_id=sess.id).order_by(SessionSignature.id).all()
    assert len(sigs) == 3
    assert sigs[0].final_hash == old_final  # chữ ký cũ được giữ
    last = AttendanceEvent.query.filter_by(session_id=sess.id).order_by(AttendanceEvent.id.desc()).first()
    assert last.kind == "manual_absent" and sigs[-1].final_hash == last.hash
    assert verify_session(sess)["message"] == "Còn nguyên vẹn"
    latest = sess.latest_events()
    assert sess.is_present(svs[3].id, latest) and not sess.is_present(svs[0].id, latest)


def test_tampered_signature_detected(closed_session, client):
    sess, _ = closed_session
    finalize(client, sess)
    db.session.execute(text("UPDATE session_signatures SET signature = :s"), {"s": "00" * 64})
    db.session.commit()
    assert verify_session(sess)["message"] == "Chữ ký không hợp lệ"


def test_recomputed_chain_detected_by_signature(closed_session, client):
    """Kẻ sửa dữ liệu tính lại toàn bộ hash vẫn bị phát hiện nhờ chữ ký."""
    from app.integrity import compute_hash, event_payload
    sess, _ = closed_session
    finalize(client, sess)
    events = db.session.execute(text(
        "SELECT id FROM attendance_events WHERE session_id = :s ORDER BY id"), {"s": sess.id}).all()
    db.session.execute(text("UPDATE attendance_events SET kind = 'manual_absent' WHERE id = :id"),
                       {"id": events[0][0]})
    prev = genesis_hash(sess.id)
    db.session.expire_all()
    for ev in AttendanceEvent.query.filter_by(session_id=sess.id).order_by(AttendanceEvent.id):
        h = compute_hash(prev, event_payload(ev.session_id, ev.student_id, ev.kind, ev.created_at,
                                             ev.actor_id, ev.ip))
        db.session.execute(text("UPDATE attendance_events SET prev_hash = :p, hash = :h WHERE id = :id"),
                           {"p": prev, "h": h, "id": ev.id})
        prev = h
    db.session.commit()
    result = verify_session(sess)
    assert not result["ok"] and "không khớp với bản đã ký" in result["message"]


def test_orm_forbids_update_and_delete(closed_session):
    sess, _ = closed_session
    ev = AttendanceEvent.query.filter_by(session_id=sess.id).first()
    ev.kind = "manual_absent"
    with pytest.raises(RuntimeError):
        db.session.commit()
    db.session.rollback()
    db.session.delete(AttendanceEvent.query.filter_by(session_id=sess.id).first())
    with pytest.raises(RuntimeError):
        db.session.commit()
    db.session.rollback()


def test_seed_sessions_intact(app):
    from app.models import ClassSession
    from app.seed import seed_data
    seed_data()
    for s in ClassSession.query.filter_by(status="finalized"):
        assert verify_session(s)["ok"], s.id
