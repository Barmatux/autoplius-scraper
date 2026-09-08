from autoplius.electric import (
    ELECTRIC_MAKE_MODELS,
    electric_sql_clause,
    is_electric_make_model,
    is_pure_electric_fuel,
    is_pure_electric_listing,
)


def test_pure_electric_fuel_detects_battery_only():
    assert is_pure_electric_fuel("Электричество")
    assert is_pure_electric_fuel("Электричество, 75 кВт·ч")
    assert is_pure_electric_fuel("Elektra, 82 kWh")
    assert is_pure_electric_fuel("Elektra")


def test_pure_electric_fuel_rejects_hybrids():
    assert not is_pure_electric_fuel("Бензин / электричество")
    assert not is_pure_electric_fuel("Дизель / электричество")
    assert not is_pure_electric_fuel("Бензин")
    assert not is_pure_electric_fuel("byenzin-elyektrichyestvo")
    assert not is_pure_electric_fuel("")
    assert not is_pure_electric_fuel(None)


def test_manual_electric_flag_overrides_fuel():
    assert is_pure_electric_listing({"fuel": "Бензин", "manual_electric": 1})
    assert not is_pure_electric_listing({"fuel": "Бензин", "manual_electric": 0})


def test_bmw_i3_is_known_electric_model():
    assert ("BMW", "i3") in ELECTRIC_MAKE_MODELS
    assert is_electric_make_model("BMW", "i3")
    assert is_electric_make_model("bmw", "i3s")
    assert is_electric_make_model("BMW", "i3, 2019")
    assert not is_electric_make_model("BMW", "X3")
    assert is_pure_electric_listing({"title": "BMW i3, 2019", "fuel": "Бензин"})
    assert is_pure_electric_listing({"title": "BMW i3s, 2020", "fuel": ""})
    assert not is_pure_electric_listing({"title": "BMW X3, 2019", "fuel": "Дизель"})


def test_electric_sql_includes_bmw_i3_model():
    sql = electric_sql_clause(include=True)
    assert "manual_electric" in sql
    assert "bmw" in sql
    assert "i3" in sql
    assert "i3s%" in sql
