def test_create_app(app):
    assert app.config["TESTING"]
    assert app.config["SESSION_COOKIE_HTTPONLY"]
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
