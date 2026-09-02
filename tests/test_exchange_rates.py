from __future__ import annotations

from autoplius.myfin_rates import eur_usd_rate, usd_byn_rate
from scraper.db import (
    get_latest_exchange_rate,
    get_latest_exchange_rates,
    init_db,
    save_exchange_rates,
)


def test_save_and_read_latest_exchange_rates(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    assert get_latest_exchange_rates(db_path) == {}

    when = save_exchange_rates(
        db_path,
        {"eurusd": 1.11, "usd": 2.99},
    )
    assert when

    assert get_latest_exchange_rate(db_path, "eurusd") == 1.11
    assert get_latest_exchange_rate(db_path, "usd") == 2.99
    assert get_latest_exchange_rates(db_path) == {"eurusd": 1.11, "usd": 2.99}

    save_exchange_rates(db_path, {"eurusd": 1.12, "usd": 3.01})
    assert get_latest_exchange_rate(db_path, "eurusd") == 1.12
    assert get_latest_exchange_rate(db_path, "usd") == 3.01


def test_myfin_rates_read_from_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.delenv("PRICE_RB_EUR_USD", raising=False)
    monkeypatch.delenv("PRICE_RB_USD_BYN", raising=False)

    init_db(db_path)
    save_exchange_rates(db_path, {"eurusd": 1.234, "usd": 3.456})

    assert eur_usd_rate() == 1.234
    assert usd_byn_rate() == 3.456
