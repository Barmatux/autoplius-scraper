"""Detect stale Autoplius error titles and recover labels from listing URLs."""

from __future__ import annotations

from autoplius.urls import extract_listing_id

INVALID_LISTING_TITLE_MARKERS = (
    "не существует",
    "neegzistuoja",
    "does not exist",
    "announcement does not exist",
    "skelbimas nebegalioja",
    "skelbimas nerastas",
    "listing not found",
)

_MULTI_WORD_MAKES = (
    "Alfa Romeo",
    "Aston Martin",
    "Land Rover",
    "Range Rover",
    "Rolls-Royce",
    "Rolls Royce",
    "Great Wall",
    "Mercedes-Benz",
    "Mercedes Benz",
)


def is_invalid_listing_title(title: str | None) -> bool:
    text = (title or "").strip()
    if not text:
        return True
    normalized = text.casefold().replace("ё", "е")
    return any(marker in normalized for marker in INVALID_LISTING_TITLE_MARKERS)


def slug_from_listing_url(url: str | None) -> str | None:
    if not url:
        return None
    listing_id = extract_listing_id(url)
    if listing_id is None:
        return None
    clean = url.split("#", 1)[0].split("?", 1)[0]
    stem = clean.rsplit("/", 1)[-1].removesuffix(".html")
    suffix = f"-{listing_id}"
    if stem.endswith(suffix):
        stem = stem[: -len(suffix)]
    return stem or None


def _format_make_token(token: str) -> str:
    if token.isdigit():
        return token
    if token.isupper() and len(token) <= 4:
        return token
    return token.capitalize()


def _format_model_token(token: str) -> str:
    if token.isdigit():
        return token
    if token.isupper() and len(token) <= 4:
        return token
    return token.capitalize()


def _is_year_token(token: str) -> bool:
    return len(token) == 4 and token.isdigit() and token.startswith(("19", "20"))


def _split_slug_parts(slug: str) -> tuple[list[str], list[str]]:
    parts = [part for part in slug.split("-") if part]
    if not parts:
        return [], []

    lower_slug = slug.casefold()
    for make in sorted(_MULTI_WORD_MAKES, key=len, reverse=True):
        make_slug = make.casefold().replace(" ", "-")
        prefix = make_slug + "-"
        if lower_slug == make_slug:
            return make_slug.split("-"), []
        if lower_slug.startswith(prefix):
            return make_slug.split("-"), parts[len(make_slug.split("-")) :]

    return [parts[0]], parts[1:]


def _model_parts_before_specs(tokens: list[str]) -> list[str]:
    model_parts: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if _is_year_token(token):
            break
        if (
            idx + 2 < len(tokens)
            and tokens[idx].replace(".", "", 1).isdigit()
            and tokens[idx + 1].replace(".", "", 1).isdigit()
            and tokens[idx + 2] == "l"
        ):
            break
        if token == "l":
            break
        model_parts.append(token)
        idx += 1
    return model_parts


def make_model_from_listing_url(url: str | None) -> tuple[str, str]:
    slug = slug_from_listing_url(url)
    if not slug:
        return "—", ""

    make_tokens, rest = _split_slug_parts(slug)
    if not make_tokens:
        return "—", ""

    make = " ".join(_format_make_token(token) for token in make_tokens)
    model_tokens = _model_parts_before_specs(rest)
    if not model_tokens:
        return make, ""

    model = " ".join(_format_model_token(token) for token in model_tokens)
    return make, model


def headline_from_listing_url(url: str | None) -> str | None:
    make, model = make_model_from_listing_url(url)
    if make == "—":
        return None
    if model:
        return f"{make} {model}"
    return make


def fallback_listing_title(item: dict) -> str:
    make, model = make_model_from_listing_url(item.get("url"))
    chunks: list[str] = []
    if make != "—":
        if model:
            chunks.extend([make, model])
        else:
            chunks.append(make)
    else:
        listing_id = item.get("autoplius_id")
        chunks.append(f"#{listing_id}" if listing_id else "—")

    year = item.get("year")
    if year:
        year_text = str(year).split("-", 1)[0].strip()
        if year_text and year_text not in chunks:
            chunks.append(year_text)
    return " ".join(chunks)


def resolve_listing_title(
    *,
    title: str | None,
    url: str | None,
    fallback_item: dict | None = None,
) -> str:
    cleaned = (title or "").strip()
    if cleaned and not is_invalid_listing_title(cleaned):
        return cleaned

    from_url = headline_from_listing_url(url)
    if from_url:
        return from_url

    if fallback_item is not None:
        return fallback_listing_title(fallback_item)

    return cleaned or "—"
