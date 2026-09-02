from __future__ import annotations

import pytest

pytest.importorskip("werkzeug")


def test_create_user_and_verify_password(tmp_path):
    from scraper.db import create_user, get_user_by_username, verify_user_password

    db_path = tmp_path / "test.db"
    user = create_user(db_path, "alice", "secret123", display_name="Alice")
    assert user["username"] == "alice"
    assert user["display_name"] == "Alice"

    assert verify_user_password(db_path, "alice", "secret123") is not None
    assert verify_user_password(db_path, "Alice", "secret123") is not None
    assert verify_user_password(db_path, "alice", "wrong") is None

    loaded = get_user_by_username(db_path, "alice")
    assert loaded is not None
    assert loaded["last_login_at"] is not None


def test_create_user_rejects_duplicate_username(tmp_path):
    from scraper.db import create_user

    db_path = tmp_path / "test.db"
    create_user(db_path, "bob", "pass12345")
    with pytest.raises(ValueError, match="already exists"):
        create_user(db_path, "bob", "other-pass")


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_login_and_cabinet_flow(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import create_user, init_db

    db_path = tmp_path / "test.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    create_user(db_path, "carol", "cabinet-pass", display_name="Carol")

    client = ui_app.app.test_client()

    cabinet = client.get("/cabinet")
    assert cabinet.status_code == 302
    assert "/login" in cabinet.headers["Location"]

    bad = client.post("/login", data={"username": "carol", "password": "wrong"})
    assert bad.status_code == 200
    assert "Неверный логин или пароль" in bad.get_data(as_text=True)

    ok = client.post(
        "/login",
        data={"username": "carol", "password": "cabinet-pass", "next": "/cabinet"},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers["Location"].endswith("/cabinet")

    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None
        assert sess.get("username") == "carol"

    page = client.get("/cabinet")
    assert page.status_code == 200
    assert "Carol" in page.get_data(as_text=True)

    out = client.get("/logout", follow_redirects=False)
    assert out.status_code == 302


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_admin_login_via_single_form(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import init_db

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    db_path = tmp_path / "test.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)

    client = ui_app.app.test_client()
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin-secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?sort=added_desc")

    with client.session_transaction() as sess:
        assert sess.get("admin") is True
        assert sess.get("user_id") is None

    page = client.get("/")
    assert page.status_code == 200
    assert "Архив" in page.get_data(as_text=True)
