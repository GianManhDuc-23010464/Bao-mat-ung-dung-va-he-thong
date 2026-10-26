import pytest

from app import create_app, db


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db"),
        "KEYS_DIR": str(tmp_path / "keys"),
        "BASE_URL": "http://testserver",
        "WTF_CSRF_ENABLED": False,
        "BCRYPT_ROUNDS": 4,
    })
    from app.student import checkin_limiter
    checkin_limiter.reset()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
