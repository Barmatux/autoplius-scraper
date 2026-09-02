from autoplius.detail_display import detail_spec_rows


def test_detail_spec_rows_skip_hidden_and_duplicate_params():
    item = {
        "year": "2016-05",
        "fuel": "Дизель",
        "mileage_km": 120000,
        "parameters": {
            "Пробег": "120 000 km",
            "Тип топлива": "Дизель",
            "Выброс CO₂, г/км": "119",
            "ID объявления": "12345",
            "Регистр. взнос": "нет",
            "Цвет": "Balta",
        },
    }
    rows = detail_spec_rows(item)
    labels = [row["label"] for row in rows]
    assert "Выброс CO₂, г/км" not in labels
    assert "ID объявления" not in labels
    assert "Регистр. взнос" not in labels
    assert "Тип топлива" not in labels
    assert labels.count("Пробег") == 1
    assert "Цвет" in labels
    assert not any("Проверьте" in label for label in labels)


def test_mileage_dedupes_km_variants():
    item = {
        "mileage_km": 130000,
        "parameters": {"Пробег": "130 000 km"},
    }
    rows = detail_spec_rows(item)
    assert [row["label"] for row in rows].count("Пробег") == 1


def test_detail_engine_line_merges_fuel_volume_and_power():
    item = {
        "year": "2013-08",
        "fuel": "Дизель",
        "engine_liters": 1.6,
        "parameters": {
            "Двигатель": "1560 см³, 111 Л.С. (82кВ)",
            "Тип топлива": "Дизель",
            "Объём двигателя, см³": "1.6 л",
        },
    }
    rows = detail_spec_rows(item)
    labels = [row["label"] for row in rows]
    engine = next(row for row in rows if row["label"] == "Двигатель")
    assert "Топливо" not in labels
    assert "Тип топлива" not in labels
    assert "Объём двигателя, см³" not in labels
    assert labels.count("Двигатель") == 1
    assert engine["value"] == "Дизель 1.6л (1560 см³) 111 Л.С. (82кВ)"


def test_detail_city_row_uses_city_kind():
    rows = detail_spec_rows({"city": "Мажейкяй"})
    city = next(row for row in rows if row["label"] == "Город")
    assert city["kind"] == "city"
    assert city["value"] == "Мажейкяй"
