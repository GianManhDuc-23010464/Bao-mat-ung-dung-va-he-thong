from helpers import login, logout, make_user


def test_login_lecturer_redirects_home(app, client):
    make_user("gv01", role="lecturer")
    r = login(client, "gv01")
    assert r.status_code == 302 and r.headers["Location"].endswith("/lecturer")


def test_login_student_redirects_me(app, client):
    make_user("sv01", code="22520001")
    r = login(client, "sv01")
    assert r.headers["Location"].endswith("/me")


def test_wrong_password_and_unknown_user_same_message(app, client):
    make_user("sv01", code="22520001")
    a = login(client, "sv01", "sai").get_data(as_text=True)
    b = login(client, "khongco", "sai").get_data(as_text=True)
    msg = "Tên đăng nhập hoặc mật khẩu không đúng."
    assert msg in a and msg in b


def test_remember_cookie_set(app, client):
    make_user("sv01", code="22520001")
    r = login(client, "sv01")
    cookies = r.headers.getlist("Set-Cookie")
    assert any(c.startswith("remember_token=") and "HttpOnly" in c for c in cookies)


def test_role_separation(app, client):
    make_user("sv01", code="22520001")
    make_user("gv01", role="lecturer")
    login(client, "sv01")
    assert client.get("/lecturer").status_code == 403
    logout(client)
    login(client, "gv01")
    assert client.get("/me").status_code == 403


def test_requires_login(app, client):
    r = client.get("/lecturer")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_logout(app, client):
    make_user("sv01", code="22520001")
    login(client, "sv01")
    logout(client)
    assert client.get("/me").status_code == 302


def test_next_never_goes_to_checkin(app, client):
    make_user("sv01", code="22520001")
    r = client.post("/login?next=/checkin?s=1%26c=abc",
                    data={"username": "sv01", "password": "Matkhau@123"})
    assert r.headers["Location"].endswith("/me")
