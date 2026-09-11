from __future__ import annotations

from autoplius.engine_catalog import aggregate_catalog_groups
from autoplius.vag_engines import vag_customs_cm3


def test_vag_map_core_engines():
    assert vag_customs_cm3("Volkswagen", "1.0 TSI", "Бензин") == 999
    assert vag_customs_cm3("VW", "1.2i", "Бензин") == 1197
    assert vag_customs_cm3("Audi", "1.2 TDI", "Дизель") == 1199
    assert vag_customs_cm3("SEAT", "1.4 TDI", "Дизель") == 1422
    assert vag_customs_cm3("Volkswagen", "1.6 TDI", "Дизель") == 1598
    assert vag_customs_cm3("Audi", "1.9 TDI", "Дизель") == 1896
    assert vag_customs_cm3("Seat", "1.5 TSI", "Бензин") == 1498
    assert vag_customs_cm3("Volkswagen", "1.8 TSI", "Бензин") == 1798


def test_vag_map_cm3_listing_labels():
    assert (
        vag_customs_cm3("Audi", "1500 cm³, 150 Л.С. (110кВ)", "Бензин") == 1498
    )
    assert (
        vag_customs_cm3(
            "Audi", "1500 cm³, 150 Л.С. (110кВ)", "Бензин / электричество"
        )
        == 1498
    )
    assert (
        vag_customs_cm3("Audi", "1600 cm³, 106 Л.С. (78кВ)", "Дизель") == 1598
    )
    assert (
        vag_customs_cm3("Audi", "1798 cm³, 170 л.с. (125kW)", "Бензин") == 1798
    )


def test_vag_14_hp_variants():
    assert vag_customs_cm3("Audi", "1.4i 122", "Бензин") == 1390
    assert vag_customs_cm3("Audi", "1.4i 125", "Бензин") == 1395
    assert vag_customs_cm3("Volkswagen", "1.4 90 kW", "Бензин") == 1390
    assert vag_customs_cm3("Volkswagen", "1.4 92kW", "Бензин") == 1395
    assert vag_customs_cm3("SEAT", "1.4 TSI", "Бензин") == 1395
    assert vag_customs_cm3("SEAT", "1.4i", "Бензин") == 1390


def test_vag_ignores_non_vag_and_unknown():
    assert vag_customs_cm3("Toyota", "1.6 TDI", "Дизель") is None
    assert vag_customs_cm3("Skoda", "1.6 TDI", "Дизель") is None
    assert vag_customs_cm3("Volkswagen", "2.0 TDI", "Дизель") is None


def test_aggregate_prefers_vag_over_listing_mode():
    listings = [
        {
            "title": "Volkswagen Golf 1.4 TSI",
            "make": "Volkswagen",
            "model": "Golf",
            "engine": "1.4 TSI",
            "fuel": "Бензин",
            "parameters": {"Двигатель": "1400 см³"},
            "status": "active",
        }
    ]
    # listing_make_model may read title; ensure fields used by catalog_key work
    rows = aggregate_catalog_groups(listings)
    assert rows
    # If make/model parsing yields empty, skip assertion soft
    vag_rows = [r for r in rows if r["engine_label"] == "1.4 TSI"]
    assert vag_rows
    assert vag_rows[0]["suggested_cm3"] == 1395
