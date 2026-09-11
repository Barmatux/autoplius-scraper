from __future__ import annotations

from autoplius.engine_catalog import aggregate_catalog_groups
from autoplius.engine_hints import hint_customs_cm3
from autoplius.vag_engines import vag_customs_cm3


def test_vag_map_core_engines():
    assert vag_customs_cm3("Volkswagen", "1.0 TSI", "Бензин") == 999
    assert vag_customs_cm3("VW", "1.2i", "Бензин") == 1197
    assert vag_customs_cm3("Audi", "1.2 TDI", "Дизель") == 1199
    assert vag_customs_cm3("SEAT", "1.4 TDI", "Дизель") == 1422
    assert vag_customs_cm3("Volkswagen", "1.6 TDI", "Дизель") == 1598
    assert vag_customs_cm3("Audi", "1.6i", "Бензин") == 1598
    assert vag_customs_cm3("VW", "1600 cm³, 102 Л.С. (75кВ)", "Бензин") == 1598
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


def test_hint_bmw_mini():
    assert hint_customs_cm3("BMW", "1.6d N47", "Дизель") == 1598
    assert hint_customs_cm3("MINI", "1.5d B37", "Дизель") == 1496
    assert hint_customs_cm3("MINI", "1.2i B38", "Бензин") == 1198
    assert hint_customs_cm3("BMW", "1.5i B38", "Бензин") == 1499
    assert hint_customs_cm3("MINI", "1.6 EP6", "Бензин") == 1598
    assert hint_customs_cm3("BMW", "2.0d N47", "Дизель") == 1995


def test_hint_other_brands():
    assert hint_customs_cm3("Peugeot", "1.2 PureTech", "Бензин") == 1199
    assert hint_customs_cm3("Renault", "1.5d", "Дизель") == 1461
    assert hint_customs_cm3("Nissan", "1.5", "Бензин", model="Qashqai e-Power") == 1461
    assert hint_customs_cm3("Ford", "1.5 Ecoboost", "Бензин") == 1498
    assert hint_customs_cm3("Honda", "1.5i", "Бензин") == 1498
    assert hint_customs_cm3("Hyundai", "1.6 MPI", "Бензин") == 1591
    assert hint_customs_cm3("Kia", "1.6", "Бензин", model="Niro") == 1580
    assert hint_customs_cm3("Toyota", "1.5 Hybrid", "Бензин / электричество") == 1490
    assert hint_customs_cm3("Volvo", "1.6d", "Дизель") == 1560
    assert hint_customs_cm3("Fiat", "1.3d MultiJet", "Дизель") == 1248


def test_aggregate_prefers_hint_over_listing_mode():
    listings = [
        {
            "title": "Volkswagen Golf 1.4 TSI",
            "make": "Volkswagen",
            "model": "Golf",
            "engine": "1.4 TSI",
            "fuel": "Бензин",
            "parameters": {"Двигатель": "1400 см³"},
            "status": "active",
        },
        {
            "title": "BMW 320d",
            "make": "BMW",
            "model": "320",
            "engine": "2.0d N47",
            "fuel": "Дизель",
            "parameters": {},
            "status": "active",
        },
    ]
    rows = aggregate_catalog_groups(listings)
    vag_rows = [r for r in rows if r["engine_label"] == "1.4 TSI"]
    assert vag_rows
    assert vag_rows[0]["suggested_cm3"] == 1395
    bmw_rows = [r for r in rows if r["engine_label"] == "2.0d N47"]
    assert bmw_rows
    assert bmw_rows[0]["suggested_cm3"] == 1995
