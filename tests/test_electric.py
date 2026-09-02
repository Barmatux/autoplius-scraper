from autoplius.electric import is_pure_electric_fuel, is_pure_electric_listing


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
