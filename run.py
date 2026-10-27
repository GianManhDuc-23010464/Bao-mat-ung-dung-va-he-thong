from app import create_app

app = create_app()

if __name__ == "__main__":
    if app.config["HTTPS"]:
        from app.qr import detect_lan_ip
        from app.tls import ensure_tls_cert, serve_https
        cert_path, key_path = ensure_tls_cert(app.config["KEYS_DIR"], [detect_lan_ip()])
        serve_https(app, "0.0.0.0", app.config["PORT"], cert_path, key_path)
    else:
        app.run(host="0.0.0.0", port=app.config["PORT"])
