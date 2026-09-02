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
