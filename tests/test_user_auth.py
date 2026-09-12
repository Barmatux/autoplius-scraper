from __future__ import annotations

import pytest

pytest.importorskip("werkzeug")


def test_create_user_and_verify_password(tmp_path):
    from scraper.db import create_user, get_user_by_username, verify_user_password

    db_path = tmp_path / "test.db"
    user = create_user(db_path, "alice", "secret123", display_name="Alice")
    assert user["username"] == "alice"
    assert user["display_name"] == "Alice"
    assert user["role"] == "user"

    assert verify_user_password(db_path, "alice", "secret123") is not None
    assert verify_user_password(db_path, "Alice", "secret123") is not None
    assert verify_user_password(db_path, "alice", "wrong") is None

    loaded = get_user_by_username(db_path, "alice")
    assert loaded is not None
    assert loaded["last_login_at"] is not None
    assert loaded["role"] == "user"


def test_create_user_rejects_duplicate_username(tmp_path):
    from scraper.db import create_user

    db_path = tmp_path / "test.db"
    create_user(db_path, "bob", "pass12345")
    with pytest.raises(ValueError, match="already exists"):
        create_user(db_path, "bob", "other-pass")


def test_user_role_migration_and_setters(tmp_path):
    from scraper.db import (
        count_users_with_role,
        create_user,
        init_db,
        list_users,
        set_user_password,
        set_user_role,
        update_user_rb_extras,
        verify_user_password,
    )

    db_path = tmp_path / "roles.db"
    init_db(db_path)
    user = create_user(db_path, "staff1", "secret123", role="employee")
    assert user["role"] == "employee"

    admin = create_user(db_path, "boss", "secret123", role="admin")
    assert admin["role"] == "admin"
    assert count_users_with_role(db_path, "admin") == 1

    updated = set_user_role(db_path, user["id"], "admin")
    assert updated is not None
    assert updated["role"] == "admin"
    assert count_users_with_role(db_path, "admin") == 2

    set_user_role(db_path, admin["id"], "user")
    assert count_users_with_role(db_path, "admin") == 1
    with pytest.raises(ValueError, match="last admin"):
        set_user_role(db_path, user["id"], "user")

    rb = update_user_rb_extras(db_path, user["id"], privilege_usd=100, delivery_usd=50)
    assert rb is not None
    assert rb["rb_privilege_usd"] == 100.0
    assert rb["rb_delivery_usd"] == 50.0

    set_user_password(db_path, user["id"], "new-secret")
    assert verify_user_password(db_path, "staff1", "new-secret") is not None
    assert verify_user_password(db_path, "staff1", "secret123") is None

    names = {row["username"] for row in list_users(db_path)}
    assert names == {"staff1", "boss"}


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
def test_employee_login_opens_contracts(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import create_user, init_db

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    db_path = tmp_path / "emp.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    create_user(db_path, "worker", "worker-pass", role="employee")

    client = ui_app.app.test_client()
    ok = client.post(
        "/login",
        data={"username": "worker", "password": "worker-pass"},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert "/admin/contracts" in ok.headers["Location"]

    contracts = client.get("/admin/contracts")
    assert contracts.status_code == 200

    forbidden = client.get("/admin/users", follow_redirects=False)
    assert forbidden.status_code == 302
    assert "/admin/contracts" in forbidden.headers["Location"]

    cabinet = client.get("/cabinet")
    assert cabinet.status_code == 200


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_admin_users_page_and_role_change(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import create_user, get_user_by_username, init_db

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    db_path = tmp_path / "admin-users.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    create_user(db_path, "norma", "secret123", role="user")

    client = ui_app.app.test_client()
    login = client.post(
        "/login",
        data={"username": "admin", "password": "admin-secret"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    page = client.get("/admin/users")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Аккаунты" in html
    assert "norma" in html

    target = get_user_by_username(db_path, "norma")
    assert target is not None
    changed = client.post(
        f"/admin/users/{target['id']}/role",
        data={"role": "employee"},
        follow_redirects=False,
    )
    assert changed.status_code == 302
    assert get_user_by_username(db_path, "norma")["role"] == "employee"


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


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_register_and_auto_login(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import get_user_by_username, init_db

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    db_path = tmp_path / "test.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)

    client = ui_app.app.test_client()
    page = client.get("/register")
    assert page.status_code == 200
    assert "Зарегистрироваться" in page.get_data(as_text=True)

    bad = client.post(
        "/register",
        data={
            "username": "ab",
            "password": "secret123",
            "password_confirm": "secret123",
        },
    )
    assert bad.status_code == 200
    assert "от 3 до 32 символов" in bad.get_data(as_text=True)

    reserved = client.post(
        "/register",
        data={
            "username": "admin",
            "password": "secret123",
            "password_confirm": "secret123",
        },
    )
    assert reserved.status_code == 200
    assert "зарезервирован" in reserved.get_data(as_text=True)

    mismatch = client.post(
        "/register",
        data={
            "username": "dave",
            "password": "secret123",
            "password_confirm": "other123",
        },
    )
    assert mismatch.status_code == 200
    assert "не совпадают" in mismatch.get_data(as_text=True)

    ok = client.post(
        "/register",
        data={
            "username": "dave",
            "password": "secret123",
            "password_confirm": "secret123",
            "display_name": "Dave",
        },
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers["Location"].endswith("/cabinet")

    with client.session_transaction() as sess:
        assert sess.get("username") == "dave"

    created = get_user_by_username(db_path, "dave")
    assert created is not None
    assert created["display_name"] == "Dave"
    assert created["role"] == "user"

    cabinet = client.get("/cabinet")
    assert cabinet.status_code == 200
    assert "Dave" in cabinet.get_data(as_text=True)
