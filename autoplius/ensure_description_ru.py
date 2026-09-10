"""Ensure seller descriptions have a usable Russian translation."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from autoplius.listing_description import needs_description_translation
from autoplius.translate import translate_to_russian
from scraper.config import Settings
from scraper.db import update_listing_description_ru

logger = logging.getLogger(__name__)
_bg_lock = threading.Lock()
_bg_inflight: set[int] = set()


def _persist_translation(
    db_path: Path,
    listing_id: int,
    original: str,
    settings: Settings,
) -> str | None:
    translated = translate_to_russian(
        original,
        enabled=True,
        min_delay_sec=settings.translate_delay_sec,
    )
    if not translated:
        return None
    update_listing_description_ru(db_path, int(listing_id), translated)
    return translated


def _schedule_background_translate(
    db_path: Path,
    listing_id: int,
    original: str,
    settings: Settings,
) -> None:
    with _bg_lock:
        if listing_id in _bg_inflight:
            return
        _bg_inflight.add(listing_id)

    def worker() -> None:
        try:
            result = _persist_translation(db_path, listing_id, original, settings)
            if result:
                logger.info("Background description_ru saved for listing #%s", listing_id)
            else:
                logger.warning("Background description translation failed for #%s", listing_id)
        except Exception:
            logger.exception("Background description translation crashed for #%s", listing_id)
        finally:
            with _bg_lock:
                _bg_inflight.discard(listing_id)

    threading.Thread(
        target=worker,
        name=f"translate-desc-{listing_id}",
        daemon=True,
    ).start()


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
    listing_id_int = int(listing_id)
    try:
        translated = _persist_translation(db_path, listing_id_int, str(original), cfg)
    except Exception:
        logger.exception("Failed to translate/store description_ru for listing #%s", listing_id_int)
        translated = None
    if translated:
        updated = dict(item)
        updated["description_ru"] = translated
        return updated
    # Keep the page responsive if translators are slow/blocked; finish in background.
    _schedule_background_translate(db_path, listing_id_int, str(original), cfg)
    logger.warning(
        "Serving original description for #%s; queued background Russian translation",
        listing_id_int,
    )
    return item
