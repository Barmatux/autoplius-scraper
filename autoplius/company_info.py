"""Public company / seller identification for Belarus site disclosure."""

from __future__ import annotations

import os
from typing import Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def company_info() -> dict[str, Any]:
    """Fields for the legal-entity page and site footer (fill via env)."""
    full_name = _env("COMPANY_FULL_NAME")
    short_name = _env("COMPANY_SHORT_NAME") or full_name
    return {
        "full_name": full_name,
        "short_name": short_name,
        "unp": _env("COMPANY_UNP"),
        "legal_address": _env("COMPANY_LEGAL_ADDRESS"),
        "postal_address": _env("COMPANY_POSTAL_ADDRESS") or _env("COMPANY_LEGAL_ADDRESS"),
        "reg_authority": _env("COMPANY_REG_AUTHORITY"),
        "reg_date": _env("COMPANY_REG_DATE"),
        "reg_number": _env("COMPANY_REG_NUMBER"),
        "director": _env("COMPANY_DIRECTOR"),
        "email": _env("COMPANY_EMAIL"),
        "phone": _env("COMPANY_PHONE"),
        "work_hours": _env("COMPANY_WORK_HOURS"),
        "bank_name": _env("COMPANY_BANK_NAME"),
        "bank_bic": _env("COMPANY_BANK_BIC"),
        "bank_account": _env("COMPANY_BANK_ACCOUNT"),
        "trade_register_date": _env("COMPANY_TRADE_REGISTER_DATE"),
        "support_telegram": _env("COMPANY_SUPPORT_TELEGRAM") or _env("FEEDBACK_TELEGRAM_URL"),
        "is_configured": bool(full_name and _env("COMPANY_UNP") and _env("COMPANY_LEGAL_ADDRESS")),
    }
