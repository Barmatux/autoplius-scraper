from __future__ import annotations

from autoplius.engine_volume import (
    _parse_volume_cm3_from_text,
    engine_volume_cm3,
    engine_volume_from_listing,
)


def test_parse_cyrillic_cm3_from_engine_param():
    assert _parse_volume_cm3_from_text("1598 см³, 102 Л.С. (75кВ)") == 1598
    assert _parse_volume_cm3_from_text("1998 cm³, 150 AG") == 1998


def test_parse_cyrillic_liters_from_volume_param():
    assert _parse_volume_cm3_from_text("1.6 л") == 1600
    assert _parse_volume_cm3_from_text("2,0 l.") == 2000


def test_engine_volume_from_listing_parameters():
    item = {
        "title": "Volkswagen Caddy Maxi",
        "parameters": {
            "Двигатель": "1598 см³, 102 Л.С. (75кВ)",
            "Объём двигателя, см³": "1.6 л",
        },
    }
    assert engine_volume_cm3(item) == 1598
    assert engine_volume_from_listing(item) == "1.6 L"


def test_engine_volume_uses_stored_engine_liters():
    item = {
        "engine_liters": 1.6,
        "parameters": {},
    }
    assert engine_volume_from_listing(item) == "1.6 L"
