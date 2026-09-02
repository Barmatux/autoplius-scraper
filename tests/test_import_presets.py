from autoplius.import_presets import (
    IMPORT_PRESETS,
    preset_query_pairs,
    preset_query_string,
)


def test_import_presets_count():
    assert len(IMPORT_PRESETS) == 5


def test_peugeot_3008_preset_query():
    preset = IMPORT_PRESETS[0]
    assert preset.make == "Peugeot"
    assert preset.model == "3008"
    pairs = dict(preset_query_pairs(preset))
    assert pairs["year_from"] == "2011"
    assert pairs["year_to"] == "2016"
    assert pairs["fuel"] == "Дизель"
    assert pairs["volume_from"] == "1.6"
    assert pairs["volume_to"] == "1.6"


def test_volvo_preset_has_make_only():
    preset = IMPORT_PRESETS[3]
    assert preset.make == "Volvo"
    assert preset.model == ""
    pairs = preset_query_pairs(preset)
    assert ("model", "Volvo") not in pairs
    assert ("year_from", "2011") in pairs
    assert ("year_to", "2017") in pairs


def test_nissan_qashqai_volume():
    preset = IMPORT_PRESETS[4]
    qs = preset_query_string(preset)
    assert "make=Nissan" in qs or "make=Nissan" in qs.replace("+", " ")
    assert "model=Qashqai" in qs.replace("+", " ")
    assert "volume_from=1.5" in qs
    assert "fuel=" in qs
