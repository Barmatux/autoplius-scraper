from __future__ import annotations

from autoplius.nbrb_rates import _direction, get_nbrb_board


def test_direction_up_down_flat():
    assert _direction(3.1, 3.0)[1] == "up"
    assert _direction(2.9, 3.0)[1] == "down"
    assert _direction(3.0, 3.0)[1] == "flat"
    assert _direction(3.0, None)[1] == "unknown"


def test_get_nbrb_board_uses_cache(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(code, *, on_date=None):
        calls["n"] += 1
        if on_date is None:
            return (3.04 if code == "USD" else 3.54, 1, "2026-09-11")
        return (3.02 if code == "USD" else 3.50, 1, "2026-09-10")

    monkeypatch.setattr("autoplius.nbrb_rates.fetch_nbrb_rate", fake_fetch)
    monkeypatch.setattr("autoplius.nbrb_rates._CACHE", {})

    rows = get_nbrb_board(force=True)
    assert len(rows) == 2
    assert rows[0].code == "USD"
    assert rows[0].direction == "up"
    assert rows[1].code == "EUR"
    assert rows[1].direction == "up"
    first_calls = calls["n"]
    rows2 = get_nbrb_board(force=False)
    assert calls["n"] == first_calls
    assert rows2[0].rate == rows[0].rate
