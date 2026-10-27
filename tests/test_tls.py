import ssl

from cryptography import x509

from app import qr
from app.tls import ensure_tls_cert


def test_tls_cert_covers_lan_ip(tmp_path):
    cert_path, key_path = ensure_tls_cert(str(tmp_path), ["192.168.1.5"])
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)  # cặp khóa hợp lệ
    with open(cert_path, "rb") as f:
        san = x509.load_pem_x509_certificate(f.read()).extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value
    assert {str(ip) for ip in san.get_values_for_type(x509.IPAddress)} == {"127.0.0.1", "192.168.1.5"}

    # Cùng IP thì giữ nguyên, đổi mạng (IP mới) thì sinh lại
    before = open(cert_path, "rb").read()
    ensure_tls_cert(str(tmp_path), ["192.168.1.5"])
    assert open(cert_path, "rb").read() == before
    ensure_tls_cert(str(tmp_path), ["10.0.0.7"])
    assert open(cert_path, "rb").read() != before


def test_base_url_uses_https_when_enabled(app, monkeypatch):
    monkeypatch.setattr(qr, "detect_lan_ip", lambda: "192.168.1.5")
    app.config.update(BASE_URL="", HTTPS=True)
    assert qr.base_url() == "https://192.168.1.5:5000"
    app.config["HTTPS"] = False
    assert qr.base_url() == "http://192.168.1.5:5000"
