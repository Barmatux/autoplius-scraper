from autoplius.transmission_labels import (
    classify_transmission_slug,
    parse_transmission_filter_values,
    transmission_db_values_for_slugs,
    transmission_filter_display_label,
    transmission_short_label,
)


def test_short_label_maps_autoplius_values():
    assert transmission_short_label("Механическая") == "МКПП"
    assert transmission_short_label("Автоматическая") == "АКПП"
    assert transmission_short_label("Automatinė") == "АКПП"
    assert transmission_short_label("Mechaninė") == "МКПП"
    assert transmission_short_label("Автоматическая / Tiptronic") == "АКПП"


def test_filter_slugs_match_autoplius_binary_options():
    assert parse_transmission_filter_values(["АКПП", "МКПП"]) == ["auto", "manual"]
    assert parse_transmission_filter_values(["акпп"]) == ["auto"]
    values = transmission_db_values_for_slugs(
        ["Автоматическая", "Механическая"],
        ["auto"],
    )
    assert values == ["Автоматическая"]
    values = transmission_db_values_for_slugs(
        ["Автоматическая", "Механическая"],
        ["manual"],
    )
    assert values == ["Механическая"]


def test_filter_display_uses_short_labels():
    assert transmission_filter_display_label(["auto"]) == "АКПП"
    assert transmission_filter_display_label(["manual"]) == "МКПП"
    assert transmission_filter_display_label(["auto", "manual"]).startswith("Выбрано")


def test_classify_keeps_manual_and_auto():
    assert classify_transmission_slug("Механическая") == "manual"
    assert classify_transmission_slug("Автоматическая") == "auto-classic"
