"""Ensure seller descriptions have a usable Russian translation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from autoplius.listing_description import needs_description_translation
from autoplius.translate import translate_to_russian
from scraper.config import Settings
from scraper.db import update_listing_description_ru

logger = logging.getLogger(__name__)


def ensure_listing_description_ru(
    db_path: Path,
    item: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Translate and persist description_ru when missing or still non-Russian."""
    if not needs_description_translation(item):
        return item
    cfg = settings or Settings.from_env()
    if not cfg.translate_descriptions:
        return item
    listing_id = item.get("autoplius_id")
    original = item.get("description")
    if listing_id is None or not original:
        return item
    translated = translate_to_russian(
        original,
        enabled=True,
        min_delay_sec=cfg.translate_delay_sec,
    )
    if not translated:
        logger.warning("Failed to translate description for listing #%s", listing_id)
        return item
    try:
        update_listing_description_ru(db_path, int(listing_id), translated)
    except Exception:
        logger.exception("Failed to store description_ru for listing #%s", listing_id)
        return item
    updated = dict(item)
    updated["description_ru"] = translated
    return updated
