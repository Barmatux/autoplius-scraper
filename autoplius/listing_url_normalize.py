"""Normalize listing index query strings for SEO, redirects, and cache keys."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

# Params that do not change listing results when empty / default.
_DEFAULT_SORT = "added_desc"
_DEFAULT_TAB = "all"
_DEFAULT_VIEW = "table"

# Any of these with a non-empty value => filtered (indexable=False / noindex).
_FILTER_KEYS = frozenset(
    {
        "q",
        "min_price",
        "max_price",
        "make",
        "model",
        "year_from",
        "year_to",
        "city",
        "body_type",
        "fuel",
        "transmission",
        "volume_from",
        "volume_to",
    }
)


def _nonempty_values(pairs: list[tuple[str, str]], key: str) -> list[str]:
    return [v.strip() for k, v in pairs if k == key and (v or "").strip()]


def parse_listing_query_pairs(query: str) -> list[tuple[str, str]]:
    return parse_qsl(query or "", keep_blank_values=True)


def listing_query_has_active_filters(query: str | list[tuple[str, str]]) -> bool:
    """True when the query meaningfully filters/sorts away from the default home."""
    pairs = (
        list(query)
        if isinstance(query, list)
        else parse_listing_query_pairs(query)
    )
    for key in _FILTER_KEYS:
        if _nonempty_values(pairs, key):
            return True

    tabs = _nonempty_values(pairs, "tab")
    if any(t != _DEFAULT_TAB for t in tabs):
        return True

    sorts = _nonempty_values(pairs, "sort")
    if any(s != _DEFAULT_SORT for s in sorts):
        return True

    pages = _nonempty_values(pairs, "page")
    if any(p != "1" for p in pages):
        return True

    keys_present = {k for k, _ in pairs}

    # Defaults when param absent: upto_19l=on, over_3y=on, passable=off.
    if "upto_19l" in keys_present and "1" not in [v for k, v in pairs if k == "upto_19l"]:
        return True
    if "over_3y" in keys_present and "1" not in [v for k, v in pairs if k == "over_3y"]:
        return True
    if "passable" in keys_present and "1" in [v for k, v in pairs if k == "passable"]:
        return True

    return False


def normalize_listing_cache_query(query: str) -> str:
    """Stable cache key fragment: drop empties/defaults, sort keys, keep real filters."""
    pairs = parse_listing_query_pairs(query)
    cleaned: list[tuple[str, str]] = []
    for key, raw in pairs:
        value = (raw or "").strip()
        if not value:
            continue
        if key == "tab" and value == _DEFAULT_TAB:
            continue
        if key == "sort" and value == _DEFAULT_SORT:
            continue
        if key == "page" and value == "1":
            continue
        if key == "view" and value == _DEFAULT_VIEW:
            continue
        # Default toggles matching index() when param absent.
        if key == "upto_19l" and value == "1":
            continue
        if key == "over_3y" and value == "1":
            continue
        if key == "passable" and value == "0":
            continue
        cleaned.append((key, value))

    cleaned.sort(key=lambda item: (item[0], item[1]))
    return urlencode(cleaned, doseq=True)


def default_equivalent_home_target(query: str) -> str | None:
    """If query is equivalent to default home, return canonical path (+ optional view).

    Returns ``/`` or ``/?view=cards`` when a redirect should run, else ``None``.
    """
    if listing_query_has_active_filters(query):
        return None
    norm = normalize_listing_cache_query(query)
    if norm == "view=cards":
        # Already canonical when only view=cards remains after normalize;
        # still redirect when raw query had default/empty noise.
        pairs = parse_listing_query_pairs(query)
        kept = [(k, (v or "").strip()) for k, v in pairs if (v or "").strip()]
        if kept == [("view", "cards")]:
            return None
        return "/?view=cards"
    if norm:
        # Non-default params that are not "filters" — keep as-is.
        return None
    if not (query or "").strip():
        return None
    return "/"
