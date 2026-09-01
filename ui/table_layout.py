from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LAYOUT_VERSION = 1
COL_KEYS = (
    "photo",
    "auto",
    "engine",
    "price-lt",
    "price-rb",
    "city",
    "description",
    "date",
)


def bundled_layout_path() -> Path:
    return Path(__file__).resolve().parent / "table_layout.json"


def user_layout_path(data_dir: Path) -> Path:
    return data_dir / "table_layout.json"


def validate_layout(data: dict[str, Any]) -> bool:
    widths = data.get("widths")
    if not isinstance(widths, dict):
        return False
    for key in COL_KEYS:
        value = widths.get(key)
        if not isinstance(value, (int, float)) or value < 40:
            return False
    return True


def load_table_layout(data_dir: Path) -> dict[str, Any] | None:
    for path in (user_layout_path(data_dir), bundled_layout_path()):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if validate_layout(data):
            return data
    return None


def save_table_layout(
    data_dir: Path,
    widths: dict[str, Any],
    *,
    source: str = "ui",
) -> dict[str, Any]:
    payload = {
        "version": LAYOUT_VERSION,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": source,
        "widths": {key: round(float(widths[key]), 2) for key in COL_KEYS},
    }
    path = user_layout_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
