from __future__ import annotations

import pytest

pytest.importorskip("werkzeug")


def test_favorite_db_helpers(tmp_path):
    from scraper.db import (
        add_user_favorite,
        create_user,
        fetch_user_favorite_ids,
        init_db,
        is_listing_favorited,
        remove_user_favorite,
        toggle_user_favorite,
        upsert_listing_item,
    )

    db_path = tmp_path / "test.db"
    init_db(db_path)
    user = create_user(db_path, "alice", "secret123")
    upsert_listing_item(db_path, {"autoplius_id": 101, "title": "Test", "price_eur": 1000})
    upsert_listing_item(db_path, {"autoplius_id": 202, "title": "Test 2", "price_eur": 2000})

    assert fetch_user_favorite_ids(db_path, user["id"]) == []
    assert add_user_favorite(db_path, user["id"], 101) is True
    assert is_listing_favorited(db_path, user["id"], 101) is True
    assert fetch_user_favorite_ids(db_path, user["id"]) == [101]

    assert add_user_favorite(db_path, user["id"], 101) is True
    assert fetch_user_favorite_ids(db_path, user["id"]) == [101]

    assert toggle_user_favorite(db_path, user["id"], 101) is False
    assert is_listing_favorited(db_path, user["id"], 101) is False

    assert toggle_user_favorite(db_path, user["id"], 202) is True
    assert fetch_user_favorite_ids(db_path, user["id"]) == [202]

    assert remove_user_favorite(db_path, user["id"], 202) is True
    assert fetch_user_favorite_ids(db_path, user["id"]) == []


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_toggle_favorite_route_and_cabinet(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import create_user, init_db, upsert_listing_item

    db_path = tmp_path / "test.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    user = create_user(db_path, "bob", "pass12345", display_name="Bob")
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 555001,
            "url": "https://autoplius.lt/555001",
            "title": "BMW 320",
            "year": "2018",
            "price_eur": 15000,
        },
    )

    client = ui_app.app.test_client()

    denied = client.post("/favorites/555001", follow_redirects=False)
    assert denied.status_code == 302
    assert "/login" in denied.headers["Location"]

    client.post(
        "/login",
        data={"username": "bob", "password": "pass12345"},
        follow_redirects=True,
    )

    add = client.post(
        "/favorites/555001",
        data={"next": "/cabinet"},
        follow_redirects=False,
    )
    assert add.status_code == 302
    assert add.headers["Location"].endswith("/cabinet")

    cabinet = client.get("/cabinet")
    assert cabinet.status_code == 200
    body = cabinet.get_data(as_text=True)
    assert "Избранные объявления" in body
    assert "BMW" in body
    assert "is-active" in body

    remove = client.post(
        "/favorites/555001",
        data={"next": "/cabinet"},
        follow_redirects=False,
    )
    assert remove.status_code == 302

    cabinet_empty = client.get("/cabinet")
    assert "Пока ничего нет" in cabinet_empty.get_data(as_text=True)

    with client.session_transaction() as sess:
        assert sess.get("user_id") == user["id"]
