"""Chứng chỉ HTTPS tự ký cho mạng nội bộ (để trình duyệt điện thoại cho bật camera trên trang /scan)."""
import ipaddress
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CERT_FILE = "tls_cert.pem"
KEY_FILE = "tls_key.pem"


def _cert_covers(cert_path, ips):
    try:
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False
    covered = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    return set(ips) <= covered and cert.not_valid_after_utc > datetime.now(timezone.utc)


def ensure_tls_cert(keys_dir, ips):
    """Trả (cert_path, key_path); sinh lại nếu chưa có, hết hạn, hoặc IP mạng đã đổi."""
    os.makedirs(keys_dir, exist_ok=True)
    cert_path = os.path.join(keys_dir, CERT_FILE)
    key_path = os.path.join(keys_dir, KEY_FILE)
    ips = sorted(set(ips) | {"127.0.0.1"})
    if os.path.exists(key_path) and _cert_covers(cert_path, ips):
        return cert_path, key_path

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Diem danh QR")])
    now = datetime.now(timezone.utc)
    san = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    os.chmod(key_path, 0o600)
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def serve_https(app, host, port, cert_path, key_path):
    """Chạy server HTTPS đa luồng.

    app.run(ssl_context=...) bắt tay TLS ngay trong luồng chính: một kết nối mở sẵn mà
    chưa gửi gì (trình duyệt hay làm vậy) sẽ chặn mọi kết nối khác. Ở đây bắt tay
    được dời sang luồng xử lý của từng kết nối.
    """
    import ssl

    from werkzeug.serving import make_server

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    srv = make_server(host, port, app, threaded=True)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)
    srv.ssl_context = ctx
    srv.log_startup()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
