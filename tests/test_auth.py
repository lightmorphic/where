from app import db, settings


def _conn():
    return db.db()


def test_first_visit_asks_you_to_set_yourself_up(anon):
    r = anon.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/signup" in r.headers["Location"]
    r = anon.get("/signup")
    assert b"Set yourself up" in r.data


def test_first_account_runs_the_place_and_is_signed_in(anon):
    r = anon.post("/signup", data={"username": "charlie", "password": "hunter2hunter2",
                                   "password2": "hunter2hunter2"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    assert b"Places" in anon.get("/").data
    with _conn() as conn:
        user = db.get_user_by_name(conn, "charlie")
    assert user["is_admin"] == 1
    assert "hunter2hunter2" not in user["password_hash"]


def test_signup_is_closed_after_the_first_account(client):
    client.post("/logout")
    r = client.get("/signup")
    assert r.status_code == 403 and b"Accounts are closed" in r.data


def test_signup_can_be_opened_again(client):
    client.post("/settings/signup", data={"allow_signup": "1"})
    client.post("/logout")
    assert client.get("/signup").status_code == 200
    r = client.post("/signup", data={"username": "sam", "password": "opensesame1",
                                     "password2": "opensesame1"}, follow_redirects=True)
    assert b"Places" in r.data
    with _conn() as conn:
        assert db.get_user_by_name(conn, "sam")["is_admin"] == 0


def test_signup_refuses_a_taken_name_and_a_mismatch(client):
    client.post("/settings/signup", data={"allow_signup": "1"})
    client.post("/logout")
    r = client.post("/signup", data={"username": "charlie", "password": "hunter2hunter2",
                                     "password2": "hunter2hunter2"})
    assert b"That name is taken" in r.data
    r = client.post("/signup", data={"username": "sam", "password": "opensesame1",
                                     "password2": "different111"})
    assert b"not the same" in r.data
    r = client.post("/signup", data={"username": "sam", "password": "short", "password2": "short"})
    assert b"at least 8 characters" in r.data


def test_sign_out_and_back_in(client):
    client.post("/logout")
    assert client.get("/", follow_redirects=False).headers["Location"].startswith("/login")
    r = client.post("/login", data={"username": "charlie", "password": "wrong-password"})
    assert b"do not match" in r.data
    r = client.post("/login", data={"username": "charlie", "password": "hunter2hunter2"},
                    follow_redirects=True)
    assert b"Places" in r.data


def test_login_name_is_not_case_sensitive(client):
    client.post("/logout")
    r = client.post("/login", data={"username": "CHARLIE", "password": "hunter2hunter2"},
                    follow_redirects=True)
    assert b"Places" in r.data


def test_everything_needs_a_sign_in(client):
    client.post("/places", data={"name": "Tray 14"})
    client.post("/logout")
    for path in ("/", "/search?q=usb", "/places/1", "/items/new", "/bulk", "/labels",
                 "/scan", "/settings", "/photos/nope.jpg"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["Location"], path
    assert client.post("/places", data={"name": "Sneaky"}).status_code == 302
    client.post("/login", data={"username": "charlie", "password": "hunter2hunter2"})
    assert b"Sneaky" not in client.get("/").data


def test_login_only_returns_you_inside_the_app(client):
    client.post("/logout")
    r = client.post("/login", data={"username": "charlie", "password": "hunter2hunter2",
                                    "next": "https://example.com/steal"}, follow_redirects=False)
    assert r.headers["Location"].endswith("/")


def test_health_needs_no_account(anon):
    assert anon.get("/health").get_json()["ok"] is True


def test_everyone_shares_the_same_things(client):
    client.post("/places", data={"name": "Tray 14"})
    client.post("/items", data={"name": "USB-C cable", "place_id": 1})
    client.post("/settings/users", data={"username": "sam", "password": "opensesame1"})
    client.post("/logout")
    client.post("/login", data={"username": "sam", "password": "opensesame1"})
    assert b"USB-C cable" in client.get("/search?q=usb").data


def test_only_an_admin_changes_the_settings(client):
    client.post("/settings/users", data={"username": "sam", "password": "opensesame1"})
    client.post("/logout")
    client.post("/login", data={"username": "sam", "password": "opensesame1"})
    r = client.get("/settings")
    assert b"Only the person who runs this copy" in r.data
    client.post("/settings/descriptions", data={"ollama_host": "http://evil:1", "ollama_model": "x",
                                                "ollama_timeout": "10"})
    with _conn() as conn:
        assert settings.get("ollama_model", conn) == "moondream"


def test_the_last_admin_cannot_be_removed(client):
    client.post("/settings/users", data={"username": "sam", "password": "opensesame1"})
    with _conn() as conn:
        me = db.get_user_by_name(conn, "charlie")["id"]
        sam = db.get_user_by_name(conn, "sam")["id"]
    # Removing yourself is not offered, and removing the only admin is refused.
    client.post("/settings/users/%d/delete" % me)
    with _conn() as conn:
        assert db.get_user(conn, me) is not None
    client.post("/settings/users/%d/delete" % sam)
    with _conn() as conn:
        assert db.get_user(conn, sam) is None


def test_change_your_own_password(client):
    r = client.post("/settings/password", data={"current": "wrong-one", "password": "newpassword1",
                                                "password2": "newpassword1"}, follow_redirects=True)
    assert b"not your current password" in r.data
    client.post("/settings/password", data={"current": "hunter2hunter2", "password": "newpassword1",
                                            "password2": "newpassword1"})
    client.post("/logout")
    r = client.post("/login", data={"username": "charlie", "password": "newpassword1"},
                    follow_redirects=True)
    assert b"Places" in r.data


def test_the_offline_page_needs_no_account(anon):
    r = anon.get("/offline")
    assert r.status_code == 200 and b"Cannot reach Where" in r.data
