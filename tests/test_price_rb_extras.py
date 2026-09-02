from __future__ import annotations

from autoplius.price_rb import estimate_price_rb


def _sample_item(**overrides):
    item = {
        "price_eur": 5000,
        "engine_liters": 1.6,
        "year": "2015-06",
        "fuel": "Дизель",
        "parameters": {"Двигатель": "1560 см³"},
        "title": "Peugeot 3008",
    }
    item.update(overrides)
    return item


def test_estimate_price_rb_adds_cabinet_extras(monkeypatch):
    monkeypatch.setattr("autoplius.price_rb.eur_usd_rate", lambda: 1.1)
    monkeypatch.setattr("autoplius.price_rb.usd_byn_rate", lambda: 3.0)
    monkeypatch.setattr("autoplius.price_rb.listing_age_months", lambda _item: 80)
    monkeypatch.setattr("autoplius.price_rb.customs_engine_volume_cm3", lambda _item: 1600)

    base = estimate_price_rb(_sample_item())
    assert base is not None
    with_extras = estimate_price_rb(
        _sample_item(),
        privilege_usd=100,
        delivery_usd=250,
    )
    assert with_extras is not None
    assert with_extras.total_usd == base.total_usd + 350
    lines = with_extras.tooltip_lines()
    assert "Льгота: 100 $" in lines
    assert "Доставка: 250 $" in lines
    assert lines[-1].startswith("Итого в РБ:")


def test_estimate_price_rb_ignores_negative_extras(monkeypatch):
    monkeypatch.setattr("autoplius.price_rb.eur_usd_rate", lambda: 1.0)
    monkeypatch.setattr("autoplius.price_rb.usd_byn_rate", lambda: 3.0)
    monkeypatch.setattr("autoplius.price_rb.listing_age_months", lambda _item: 80)
    monkeypatch.setattr("autoplius.price_rb.customs_engine_volume_cm3", lambda _item: 1600)

    base = estimate_price_rb(_sample_item())
    same = estimate_price_rb(_sample_item(), privilege_usd=-10, delivery_usd=-5)
    assert base is not None and same is not None
    assert same.total_usd == base.total_usd
    assert same.privilege_usd == 0
    assert same.delivery_usd == 0
