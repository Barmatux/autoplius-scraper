from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("werkzeug")


def _seed_listing(db_path: Path, autoplius_id: int, *, title: str, price: int = 10000) -> None:
    from scraper.db import connect, init_db

    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, url, title, year, price_eur, status,
                first_seen_at, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                int(autoplius_id),
                f"https://en.autoplius.lt/announcements/{autoplius_id}",
                title,
                "2015",
                int(price),
                "2026-09-12T10:00:00+00:00",
                "2026-09-12T10:00:00+00:00",
                "2026-09-12T10:00:00+00:00",
            ),
        )


def _mock_market_deal(monkeypatch, *, savings_by_id: dict[int, float] | None = None, default_savings: float = 1500.0):
    """Patch compare_listing_to_market: positive savings => below market."""
    from types import SimpleNamespace

    savings_by_id = savings_by_id or {}

    def fake_compare(item):
        autoplius_id = int(item.get("autoplius_id") or 0)
        savings = float(savings_by_id.get(autoplius_id, default_savings))
        if savings is None:
            return None
        # delta_usd = listing - avg; negative when cheaper.
        return SimpleNamespace(delta_usd=-savings)

    monkeypatch.setattr(
        "scraper.staff_alerts.compare_listing_to_market",
        fake_compare,
    )



def test_parse_alert_query_and_match_new_listing(tmp_path, monkeypatch):
    from scraper.db import (
        count_unseen_staff_alert_matches,
        create_staff_alert_rule,
        create_user,
        init_db,
        list_staff_alert_matches,
    )
    from scraper.staff_alerts import (
        listing_filters_to_json,
        parse_alert_query_string,
        process_staff_alerts_for_new_listings,
    )

    _mock_market_deal(monkeypatch, savings_by_id={111: 1500.0, 222: 1500.0})
    db_path = tmp_path / "alerts.db"
    init_db(db_path)
    user = create_user(db_path, "staffer", "secret123", role="employee")
    filters, query = parse_alert_query_string("make=BMW&max_price=25000")
    assert filters.max_price == 25000
    assert filters.vehicle_rows
    assert filters.vehicle_rows[0]["make"] == "BMW"
    assert filters.older_than_3_only is False
    assert filters.engine_upto_liters is None

    create_staff_alert_rule(
        db_path,
        user_id=int(user["id"]),
        name="BMW budget",
        filters_json=listing_filters_to_json(filters),
        query_string=query,
    )

    _seed_listing(db_path, 111, title="BMW 320d, 2015 m.", price=18000)
    _seed_listing(db_path, 222, title="Audi A4, 2016 m.", price=15000)

    created = process_staff_alerts_for_new_listings(db_path, [111, 222])
    assert created == 1
    assert count_unseen_staff_alert_matches(db_path, user_id=int(user["id"])) == 1
    matches = list_staff_alert_matches(db_path, user_id=int(user["id"]))
    assert len(matches) == 1
    assert matches[0]["autoplius_id"] == 111

    # Dedupe on second run
    assert process_staff_alerts_for_new_listings(db_path, [111, 222]) == 0


def test_regular_user_cannot_create_alert(tmp_path):
    from scraper.db import create_staff_alert_rule, create_user, init_db
    from scraper.staff_alerts import listing_filters_to_json, parse_alert_query_string

    db_path = tmp_path / "alerts2.db"
    init_db(db_path)
    user = create_user(db_path, "guest1", "secret123", role="user")
    filters, query = parse_alert_query_string("make=Audi")
    with pytest.raises(ValueError, match="staff"):
        create_staff_alert_rule(
            db_path,
            user_id=int(user["id"]),
            name="Audi",
            filters_json=listing_filters_to_json(filters),
            query_string=query,
        )


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_employee_alerts_page_create_and_match_feed(tmp_path, monkeypatch):
    _mock_market_deal(monkeypatch, default_savings=1500.0)
    import ui.app as ui_app
    from scraper.db import (
        create_user,
        init_db,
        list_staff_alert_matches,
        list_staff_alert_rules,
    )
    from scraper.staff_alerts import process_staff_alerts_for_new_listings

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    db_path = tmp_path / "alerts-ui.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    create_user(db_path, "dir_max", "secret123", role="employee")

    client = ui_app.app.test_client()
    login = client.post(
        "/login",
        data={"username": "dir_max", "password": "secret123"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    page = client.get("/admin/alerts")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Алерты по фильтрам" in html
    assert "Новый алерт" in html

    created = client.post(
        "/admin/alerts/create",
        data={"name": "BMW budget", "query": "make=BMW&max_price=25000"},
        follow_redirects=False,
    )
    assert created.status_code == 302
    rules = list_staff_alert_rules(db_path)
    assert len(rules) == 1
    assert rules[0]["name"] == "BMW budget"

    _seed_listing(db_path, 333, title="BMW 520d, 2014 m.", price=22000)
    assert process_staff_alerts_for_new_listings(db_path, [333]) == 1
    assert len(list_staff_alert_matches(db_path, user_id=int(rules[0]["user_id"]))) == 1

    feed = client.get("/admin/alerts")
    assert feed.status_code == 200
    feed_html = feed.get_data(as_text=True)
    assert "BMW 520d" in feed_html
    assert "новых: 1" in feed_html

    seen = client.post("/admin/alerts/matches/seen", follow_redirects=False)
    assert seen.status_code == 302
    after = client.get("/admin/alerts")
    assert "новых: 1" not in after.get_data(as_text=True)


def test_alert_query_keeps_catalog_filter_off():
    from scraper.staff_alerts import parse_alert_query_string

    filters, _ = parse_alert_query_string("make=BMW&tab=electric")
    assert filters.catalog_filter is False
    assert filters.electric_only is True


def test_market_deal_requires_1000_usd_below_avg(tmp_path, monkeypatch):
    from scraper.db import create_staff_alert_rule, create_user, init_db, list_staff_alert_matches
    from scraper.staff_alerts import (
        listing_filters_to_json,
        parse_alert_query_string,
        process_staff_alerts_for_new_listings,
    )

    db_path = tmp_path / "alerts-market.db"
    init_db(db_path)
    user = create_user(db_path, "staffer2", "secret123", role="employee")
    filters, query = parse_alert_query_string("make=BMW")
    create_staff_alert_rule(
        db_path,
        user_id=int(user["id"]),
        name="BMW deals",
        filters_json=listing_filters_to_json(filters),
        query_string=query,
    )
    _seed_listing(db_path, 501, title="BMW 320d, 2015 m.", price=18000)
    _seed_listing(db_path, 502, title="BMW 520d, 2014 m.", price=20000)

    # 501 is only $500 below avg -> skip; 502 is $1200 below -> match
    _mock_market_deal(monkeypatch, savings_by_id={501: 500.0, 502: 1200.0})
    created = process_staff_alerts_for_new_listings(db_path, [501, 502])
    assert created == 1
    matches = list_staff_alert_matches(db_path, user_id=int(user["id"]))
    assert [m["autoplius_id"] for m in matches] == [502]


def test_no_alert_without_market_compare(tmp_path, monkeypatch):
    from scraper.db import create_staff_alert_rule, create_user, init_db, list_staff_alert_matches
    from scraper.staff_alerts import (
        listing_filters_to_json,
        parse_alert_query_string,
        process_staff_alerts_for_new_listings,
    )

    db_path = tmp_path / "alerts-nomarket.db"
    init_db(db_path)
    user = create_user(db_path, "staffer3", "secret123", role="employee")
    filters, query = parse_alert_query_string("make=BMW")
    create_staff_alert_rule(
        db_path,
        user_id=int(user["id"]),
        name="BMW",
        filters_json=listing_filters_to_json(filters),
        query_string=query,
    )
    _seed_listing(db_path, 601, title="BMW 320d, 2015 m.", price=18000)
    monkeypatch.setattr(
        "scraper.staff_alerts.compare_listing_to_market",
        lambda item: None,
    )
    assert process_staff_alerts_for_new_listings(db_path, [601]) == 0
    assert list_staff_alert_matches(db_path, user_id=int(user["id"])) == []

