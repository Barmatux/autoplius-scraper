from __future__ import annotations

import re
from typing import Any

# Parameter labels on autoplius.lt (LT) -> ru.autoplius.lt (RU).
PARAMETER_LABELS: dict[str, str] = {
    "Pirma registracija": "Первая регистрация",
    "Rida": "Пробег",
    "Kuro tipas": "Тип топлива",
    "Kėbulo tipas": "Тип кузова",
    "Durų skaičius": "Количество дверей",
    "Spalva": "Цвет",
    "Skelbimo ID": "ID объявления",
    "Variklis": "Двигатель",
    "Pavarų dėžė": "Коробка передач",
    "Darbinis tūris, cm³": "Рабочий объём, см³",
    "Varantieji ratai": "Тип трансмиссии",
    "Sėdimų vietų skaičius": "Количество мест",
    "Kėbulo numeris (VIN)": "VIN номер",
    "Registracijos mokestis": "Регистрационный сбор",
    "CO₂ emisija, g/km": "Выброс CO₂, г/км",
    "Tech. apžiūra iki": "Техосмотр до",
    "Klimato valdymas": "Климат-контроль",
    "Ratlankių skersmuo": "Диаметр дисков",
    "Euro standartas": "Экологический стандарт",
    "Nuosava masė, kg": "Собственная масса, кг",
    "Bendroji masė, kg": "Полная масса, кг",
    "Nuosavybės teisė": "Право собственности",
    "Defektai": "Дефекты",
    "Pirmosios pagalbos rinkinys": "Аптечка",
    "Kilimėliai": "Коврики",
    "Pavarų skaičius": "Количество передач",
    "Taip ne": "Нет",
    "Taip": "Да",
}

CITY_NAMES: dict[str, str] = {
    "Vilnius": "Вильнюс",
    "Kaunas": "Каунас",
    "Klaipėda": "Клайпеда",
    "Panevėžys": "Паневежис",
    "Šiauliai": "Шяуляй",
    "Jonava": "Йонава",
    "Telšiai": "Тельшяи",
    "Marijampolė": "Марьямполе",
    "Alytus": "\u0410\u043b\u0438\u0442\u0443\u0441",
    "Šilutė": "Шилуте",
    "Utena": "\u0423\u0442\u0435\u043d\u0430",
    "Mažeikiai": "Мажейкяй",
    "Kėdainiai": "\u041a\u0435\u0434\u0430\u0439\u043d\u044f\u0438",
    "Tauragė": "\u0422\u0430\u0443\u0440\u0430\u0433\u0435",
    "Ukmergė": "\u0423\u043a\u043c\u0435\u0440\u0433\u0435",
    "Plungė": "\u041f\u043b\u0443\u043d\u0433\u0435",
    "Kretinga": "\u041a\u0440\u0435\u0442\u0438\u043d\u0433\u0430",
    "Palanga": "Паланга",
    "Druskininkai": "\u0414\u0440\u0443\u0441\u043a\u0438\u043d\u0438\u043a\u0430\u0438",
    "Rokiškis": "\u0420\u043e\u043a\u0438\u0448\u043a\u0438\u0441",
    "Elektrėnai": "\u042d\u043b\u0435\u043a\u0442\u0440\u0435\u043d\u0430\u0439",
    "Visaginas": "\u0412\u0438\u0441\u0430\u0433\u0438\u043d\u0430\u0441",
    "Gargždai": "\u0413\u0430\u0440\u0433\u0436\u0434\u0430\u0439",
    "Radviliškis": "\u0420\u0430\u0434\u0432\u0438\u043b\u0438\u0448\u043a\u0438\u0441",
}

FIELD_VALUES: dict[str, str] = {
    "Dyzelinas": "Дизель",
    "Benzinas": "Бензин",
    "Benzinas / elektra": "Бензин / электричество",
    "Benzinas / dujos": "Бензин / газ",
    "Dyzelinas / elektra": "Дизель / электричество",
    "Elektra": "Электричество",
    "Dujos": "Газ",
    "Vandenilis": "Водород",
    "Automatinė": "Автоматическая",
    "Mechaninė": "Механическая",
    "Automatinė / Tiptronic": "Автоматическая / Tiptronic",
    "Mechaninė / 6 pavarų": "Механическая / 6 передач",
    "Universalas": "Универсал",
    "Hečbekas": "Хэтчбек",
    "Sedanas": "Седан",
    "Visureigis / Krosoveris": "Внедорожник / Кроссовер",
    "Vienatūris": "Минивэн",
    "Kupė (Coupe)": "Купе",
    "kupė (coupe)": "Купе",
    "Kabrioletas": "Кабриолет",
    "Pikapas": "Пикап",
    "Komercinis": "Коммерческий",
    "Krovininis furgonas": "Грузовой фургон",
    "Visi varantys (4х4)": "Полный привод (4х4)",
    "Visi varantys (4x4)": "Полный привод (4x4)",
    "Priekiniai varantys": "Передний привод",
    "Galiniai varantys": "Задний привод",
    "Dešinėje": "Справа",
    "Kairėje": "Слева",
    "Be defektų": "Без дефектов",
    "Yra": "Есть",
    "Nėra": "Нет",
}

_FIELD_VALUES_FOLD = {key.casefold(): value for key, value in FIELD_VALUES.items()}
_PARAMETER_LABELS_FOLD = {key.casefold(): value for key, value in PARAMETER_LABELS.items()}
_CITY_FOLD = {key.casefold(): value for key, value in CITY_NAMES.items()}

_UNIT_REPLACEMENTS = (
    (re.compile(r"\bkm\b", re.I), "км"),
    (re.compile(r"\bAG\b"), "л.с."),
    (re.compile(r"\bkW\b"), "кВт"),
    (re.compile(r"cm³", re.I), "см³"),
)

_TITLE_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    sorted(FIELD_VALUES.items(), key=lambda item: len(item[0]), reverse=True)
)


def _lookup(mapping: dict[str, str], fold_map: dict[str, str], value: str | None) -> str | None:
    if not value:
        return value
    text = value.strip()
    if not text:
        return value
    if text in mapping:
        return mapping[text]
    folded = fold_map.get(text.casefold())
    if folded:
        return folded
    return text


def localize_units(text: str) -> str:
    result = text
    for pattern, repl in _UNIT_REPLACEMENTS:
        result = pattern.sub(repl, result)
    return result


def localize_value(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return value
    mapped = _lookup(FIELD_VALUES, _FIELD_VALUES_FOLD, text)
    return localize_units(mapped)


def localize_label(label: str) -> str:
    text = label.strip()
    if not text:
        return label
    return _lookup(PARAMETER_LABELS, _PARAMETER_LABELS_FOLD, text) or text


def localize_city(city: str | None) -> str | None:
    return _lookup(CITY_NAMES, _CITY_FOLD, city)


def localize_title(title: str | None) -> str | None:
    if not title:
        return title
    result = title.strip()
    for src, dst in _TITLE_REPLACEMENTS:
        result = re.sub(re.escape(src), dst, result, flags=re.I)
    return localize_units(result)


def localize_parameters(parameters: dict[str, str] | None) -> dict[str, str]:
    if not parameters:
        return {}
    localized: dict[str, str] = {}
    for label, value in parameters.items():
        ru_label = localize_label(label)
        ru_value = localize_value(value) or value
        if ru_label in localized and localized[ru_label] and not ru_value:
            continue
        localized[ru_label] = ru_value
    return localized


def localize_listing(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize listing fields to Russian labels/values for UI and storage."""
    row = dict(item)
    for field in ("fuel", "transmission", "body_type", "engine"):
        if row.get(field):
            row[field] = localize_value(str(row[field]))
    if row.get("city"):
        row["city"] = localize_city(str(row["city"]))
    if row.get("title"):
        row["title"] = localize_title(str(row["title"]))
    params = row.get("parameters")
    if isinstance(params, dict) and params:
        row["parameters"] = localize_parameters(params)
    return row
