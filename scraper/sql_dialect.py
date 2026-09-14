"""SQL dialect helpers for SQLite vs Postgres consumer mode.

Must not import scraper.db (avoids circular imports). Uses db_backend only.
"""

from __future__ import annotations

from typing import Literal

from scraper.db_backend import using_postgres

Dialect = Literal["sqlite", "postgres"]


def get_dialect() -> Dialect:
    return "postgres" if using_postgres() else "sqlite"


def qmark_to_percent(sql: str) -> str:
    """Replace ``?`` placeholders with ``%s``, skipping content inside single-quoted strings."""
    out: list[str] = []
    i = 0
    n = len(sql)
    in_string = False
    while i < n:
        ch = sql[i]
        if in_string:
            out.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "?":
            out.append("%s")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def named_colon_to_pyformat(sql: str) -> str:
    """Convert SQLite ``:name`` binds to psycopg ``%(name)s`` (keep PG ``::`` casts)."""
    out: list[str] = []
    i = 0
    n = len(sql)
    in_string = False
    while i < n:
        ch = sql[i]
        if in_string:
            out.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ":" and i + 1 < n and sql[i + 1] == ":":
            out.append("::")
            i += 2
            continue
        if ch == ":" and i + 1 < n and (sql[i + 1].isalpha() or sql[i + 1] == "_"):
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            out.append(f"%({sql[i + 1 : j]})s")
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def adapt_sql_for_postgres(sql: str) -> str:
    """Apply placeholder rewrites for psycopg."""
    return named_colon_to_pyformat(qmark_to_percent(sql))


def listing_pk_where(alias: str = "") -> str:
    """WHERE fragment matching one listing id placeholder ``?`` (plus source on PG)."""
    prefix = f"{alias}." if alias else ""
    if get_dialect() == "postgres":
        return f"{prefix}source = 'autoplius' AND {prefix}external_id = CAST(? AS TEXT)"
    return f"{prefix}autoplius_id = ?"


def listing_write_column(name: str) -> str:
    """Map SQLite listing column names to Postgres physical columns for UPDATE/INSERT."""
    if get_dialect() != "postgres":
        return name
    return {
        "autoplius_id": "external_id",
        "parameters_json": "parameters",
        "photo_urls_json": "photo_urls",
        "manual_overrides_json": "manual_overrides",
    }.get(name, name)


def instr_expr(haystack_sql: str, needle_sql: str) -> str:
    if get_dialect() == "postgres":
        return f"strpos({haystack_sql}, {needle_sql})"
    return f"instr({haystack_sql}, {needle_sql})"


def age_months_sql(year_expr: str, month_expr: str) -> str:
    """Age in months from registration year/month expressions (0 when year invalid)."""
    if get_dialect() == "postgres":
        return (
            f"(({year_expr} IS NOT NULL AND {year_expr} > 1900) * "
            f"((EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - {year_expr}) * 12 + "
            f"(EXTRACT(MONTH FROM CURRENT_DATE)::INTEGER - {month_expr})))"
        )
    return (
        f"(({year_expr} IS NOT NULL AND {year_expr} > 1900) * "
        f"((CAST(strftime('%Y', 'now') AS INTEGER) - {year_expr}) * 12 + "
        f"(CAST(strftime('%m', 'now') AS INTEGER) - {month_expr})))"
    )


def not_alnum_char_sql(char_expr: str) -> str:
    if get_dialect() == "postgres":
        return f"({char_expr}) !~ '^[a-z0-9]$'"
    return f"({char_expr}) NOT GLOB '[a-z0-9]'"


def ilike_or_lower_like(column_sql: str, placeholder: str = "?") -> str:
    """Case-insensitive LIKE; Postgres prefers ILIKE, SQLite uses lower()+LIKE."""
    if get_dialect() == "postgres":
        return f"{column_sql} ILIKE {placeholder}"
    return f"lower({column_sql}) LIKE {placeholder}"


def lower_like_prep(value: str) -> str:
    """Normalize a Python-side LIKE value for :func:`ilike_or_lower_like` / lower()+LIKE."""
    return value.casefold()


def listings_source_clause() -> str:
    """Filter Autoplius rows on shared Postgres ``listings``; empty on SQLite."""
    if get_dialect() == "postgres":
        return "source = 'autoplius'"
    return ""


def listing_id_expr() -> str:
    """Expression that yields the Autoplius listing id (BIGINT)."""
    if get_dialect() == "postgres":
        return "CAST(external_id AS BIGINT)"
    return "autoplius_id"


def parameters_col() -> str:
    return "parameters" if get_dialect() == "postgres" else "parameters_json"


def photo_urls_col() -> str:
    return "photo_urls" if get_dialect() == "postgres" else "photo_urls_json"


def manual_overrides_col() -> str:
    return "manual_overrides" if get_dialect() == "postgres" else "manual_overrides_json"


def parameters_text_expr() -> str:
    """Text form of parameters JSON for LIKE / search."""
    col = parameters_col()
    if get_dialect() == "postgres":
        return f"COALESCE({col}::text, '')"
    return f"COALESCE({col}, '')"


def listings_from_sql() -> str:
    """FROM clause for listings; source filter belongs in WHERE on Postgres."""
    return "FROM listings"


_FILTER_COLS_SQLITE = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, has_vin_badge, parameters_json, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)

_LITE_COLS_SQLITE = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, photo_urls_json, has_vin_badge, parameters_json, "
    "description, description_ru, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)

_FULL_COLS_SQLITE = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, has_vin_badge, description, description_ru, phone, vin_masked, "
    "parameters_json, photo_urls_json, detail_scraped, detail_error, status, "
    "archived_at, first_seen_at, last_seen_at, last_run_id, updated_at, "
    "manual_overrides_json, engine_liters, manual_electric"
)

_FILTER_COLS_PG = (
    "CAST(external_id AS BIGINT) AS autoplius_id, url, title, year, body_type, "
    "price_eur, price_net_eur, price_gross_eur, price_vat_note, fuel, transmission, "
    "engine, mileage_km, city, photo_url, has_vin_badge, "
    "parameters AS parameters_json, first_seen_at, last_seen_at, status, "
    "archived_at, detail_scraped"
)

_LITE_COLS_PG = (
    "CAST(external_id AS BIGINT) AS autoplius_id, url, title, year, body_type, "
    "price_eur, price_net_eur, price_gross_eur, price_vat_note, fuel, transmission, "
    "engine, mileage_km, city, photo_url, photo_urls AS photo_urls_json, "
    "has_vin_badge, parameters AS parameters_json, description, description_ru, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)

_FULL_COLS_PG = (
    "CAST(external_id AS BIGINT) AS autoplius_id, url, title, year, body_type, "
    "price_eur, price_net_eur, price_gross_eur, price_vat_note, fuel, transmission, "
    "engine, mileage_km, city, photo_url, has_vin_badge, description, description_ru, "
    "phone, vin_masked, parameters AS parameters_json, "
    "photo_urls AS photo_urls_json, detail_scraped, detail_error, status, "
    "archived_at, first_seen_at, last_seen_at, last_run_id, updated_at, "
    "manual_overrides AS manual_overrides_json, engine_liters, manual_electric"
)


def listing_select_columns(kind: Literal["filter", "lite", "full"]) -> str:
    """SELECT list that always exposes SQLite-compatible column aliases."""
    if kind not in {"filter", "lite", "full"}:
        raise ValueError(f"unknown listing select kind: {kind!r}")
    if get_dialect() == "postgres":
        if kind == "filter":
            return _FILTER_COLS_PG
        if kind == "lite":
            return _LITE_COLS_PG
        return _FULL_COLS_PG
    if kind == "filter":
        return _FILTER_COLS_SQLITE
    if kind == "lite":
        return _LITE_COLS_SQLITE
    return _FULL_COLS_SQLITE
