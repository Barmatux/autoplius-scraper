"""Public company / seller identification for Belarus site disclosure."""

from __future__ import annotations

import os
from typing import Any

# Defaults from ООО «Сканди Моторс» (Корж XL договор подбора ЕС). Env COMPANY_* overrides.
_SCANDI_DEFAULTS: dict[str, str] = {
    "COMPANY_FULL_NAME": "Общество с ограниченной ответственностью «Сканди Моторс»",
    "COMPANY_SHORT_NAME": "ООО «Сканди Моторс»",
    "COMPANY_UNP": "193866357",
    "COMPANY_LEGAL_ADDRESS": "г. Минск, ул. Скрыганова, дом 6, помещение 7",
    "COMPANY_POSTAL_ADDRESS": "г. Минск, ул. Скрыганова, дом 6, помещение 7",
    "COMPANY_DIRECTOR": "Герасимец Максим Сергеевич",
    "COMPANY_DIRECTOR_GENITIVE": "Герасимца Максима Сергеевича",
    "COMPANY_DIRECTOR_SHORT": "Герасимец М.С.",
    "COMPANY_EMAIL": "scandimotorsby@gmail.com",
    "COMPANY_PHONE": "+375 (33) 698-77-99",
    "COMPANY_WORK_HOURS": "Пн–Пт 10:00–19:00 (время Минска)",
    "COMPANY_BANK_NAME": "ЗАО «Альфа-Банк», 220013, г. Минск, ул. Сурганова, 43-47",
    "COMPANY_BANK_BIC": "ALFABY2X",
    "COMPANY_BANK_ACCOUNT": "BY58 ALFA 3012 2G91 3900 1027 0000",
    "COMPANY_BANK_SWIFT": "ALFABY2X",
    "COMPANY_BANK_UNP": "101541947",
    "COMPANY_OKPO": "37526626",
}


def _env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if value:
        return value
    return _SCANDI_DEFAULTS.get(name, "")


def company_info() -> dict[str, Any]:
    """Fields for the legal-entity page, footer, and contract defaults."""
    full_name = _env("COMPANY_FULL_NAME")
    short_env = (os.environ.get("COMPANY_SHORT_NAME") or "").strip()
    if short_env:
        short_name = short_env
    elif (os.environ.get("COMPANY_FULL_NAME") or "").strip():
        short_name = full_name
    else:
        short_name = _SCANDI_DEFAULTS.get("COMPANY_SHORT_NAME") or full_name
    legal_address = _env("COMPANY_LEGAL_ADDRESS")
    postal_env = (os.environ.get("COMPANY_POSTAL_ADDRESS") or "").strip()
    postal_address = postal_env or legal_address
    return {
        "full_name": full_name,
        "short_name": short_name,
        "unp": _env("COMPANY_UNP"),
        "legal_address": legal_address,
        "postal_address": postal_address,
        "reg_authority": _env("COMPANY_REG_AUTHORITY"),
        "reg_date": _env("COMPANY_REG_DATE"),
        "reg_number": _env("COMPANY_REG_NUMBER"),
        "director": _env("COMPANY_DIRECTOR"),
        "director_genitive": _env("COMPANY_DIRECTOR_GENITIVE"),
        "director_short": _env("COMPANY_DIRECTOR_SHORT"),
        "email": _env("COMPANY_EMAIL"),
        "phone": _env("COMPANY_PHONE"),
        "work_hours": _env("COMPANY_WORK_HOURS"),
        "bank_name": _env("COMPANY_BANK_NAME"),
        "bank_bic": _env("COMPANY_BANK_BIC"),
        "bank_account": _env("COMPANY_BANK_ACCOUNT"),
        "bank_swift": _env("COMPANY_BANK_SWIFT") or _env("COMPANY_BANK_BIC"),
        "bank_unp": _env("COMPANY_BANK_UNP"),
        "okpo": _env("COMPANY_OKPO"),
        "trade_register_date": _env("COMPANY_TRADE_REGISTER_DATE"),
        "support_telegram": _env("COMPANY_SUPPORT_TELEGRAM") or _env("FEEDBACK_TELEGRAM_URL"),
        "is_configured": bool(full_name and _env("COMPANY_UNP") and legal_address),
    }
