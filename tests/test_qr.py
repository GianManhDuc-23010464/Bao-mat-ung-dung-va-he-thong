from app import qr

KEY = b"k" * 32
NOW = 1_700_000_002.3  # giữa một khung 5 giây


def test_1_current_frame_code_accepted():
    code = qr.current_code(KEY, NOW)
    assert qr.verify_code(KEY, code, NOW)
    # Vẫn cùng khung ở cuối khung
    assert qr.verify_code(KEY, code, (qr.frame_at(NOW) + 1) * 5 - 0.01)


def test_2_previous_frame_code_rejected():
    old = qr.current_code(KEY, NOW - 5)
    assert old != qr.current_code(KEY, NOW)
    assert not qr.verify_code(KEY, old, NOW)
    # Mã vừa sang khung mới cũng bị từ chối
    code = qr.current_code(KEY, NOW)
    assert not qr.verify_code(KEY, code, (qr.frame_at(NOW) + 1) * 5)


def test_3_wrong_code_rejected():
    assert not qr.verify_code(KEY, "0000000000", NOW)
    assert not qr.verify_code(KEY, "", NOW)
    assert not qr.verify_code(KEY, None, NOW)
    assert not qr.verify_code(b"x" * 32, qr.current_code(KEY, NOW), NOW)
    assert not qr.verify_code(None, qr.current_code(KEY, NOW), NOW)


def test_expires_in_and_url(app):
    assert 1 <= qr.expires_in(NOW) <= 5
    url = qr.checkin_url(7, "abcdef1234")
    assert url == "http://testserver/checkin?s=7&c=abcdef1234"
