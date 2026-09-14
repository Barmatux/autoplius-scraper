"""Shared SQL expressions to split listing titles into make and model."""

from __future__ import annotations

from scraper.sql_dialect import get_dialect, instr_expr

MULTI_WORD_MAKES: tuple[str, ...] = (
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


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_max2(a: str, b: str) -> str:
    """Two-argument max; SQLite ``max(a,b)`` vs Postgres ``GREATEST``."""
    if get_dialect() == "postgres":
        return f"GREATEST({a}, {b})"
    return f"max({a}, {b})"


def title_headline_expr(title_col: str = "title") -> str:
    text = f"COALESCE({title_col}, '')"
    comma_at = instr_expr(f"{text} || ','", "','")
    return f"trim(substr({text}, 1, {_sql_max2('0', f'{comma_at} - 1')}))"


def title_make_expr(title_col: str = "title") -> str:
    headline = title_headline_expr(title_col)
    cases: list[str] = []
    for make in sorted(MULTI_WORD_MAKES, key=len, reverse=True):
        prefix = make.casefold().replace("'", "''")
        cases.append(
            f"WHEN lower({headline}) LIKE {_sql_literal(prefix + '%')} THEN {_sql_literal(make)}"
        )
    space_at = instr_expr(f"{headline} || ' '", "' '")
    first_word = (
        f"trim(substr({headline}, 1, "
        f"CASE WHEN {space_at} = 0 THEN length({headline}) "
        f"ELSE {space_at} - 1 END))"
    )
    if not cases:
        return first_word
    return f"CASE {' '.join(cases)} ELSE {first_word} END"


def title_model_expr(title_col: str = "title") -> str:
    headline = title_headline_expr(title_col)
    cases: list[str] = []
    for make in sorted(MULTI_WORD_MAKES, key=len, reverse=True):
        prefix = make.casefold().replace("'", "''")
        cases.append(
            f"WHEN lower({headline}) LIKE {_sql_literal(prefix + '%')} "
            f"THEN trim(substr({headline}, {len(make) + 1}))"
        )
    space_at = instr_expr(f"{headline} || ' '", "' '")
    rest = f"trim(substr({headline}, {space_at} + 1))"
    if not cases:
        return rest
    return f"CASE {' '.join(cases)} ELSE {rest} END"
