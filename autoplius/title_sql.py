"""Shared SQLite expressions to split listing titles into make and model."""

from __future__ import annotations

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


def title_headline_expr(title_col: str = "title") -> str:
    text = f"COALESCE({title_col}, '')"
    return f"trim(substr({text}, 1, max(0, instr({text} || ',', ',') - 1)))"


def title_make_expr(title_col: str = "title") -> str:
    headline = title_headline_expr(title_col)
    cases: list[str] = []
    for make in sorted(MULTI_WORD_MAKES, key=len, reverse=True):
        prefix = make.casefold().replace("'", "''")
        cases.append(
            f"WHEN lower({headline}) LIKE {_sql_literal(prefix + '%')} THEN {_sql_literal(make)}"
        )
    first_word = (
        f"trim(substr({headline}, 1, "
        f"CASE WHEN instr({headline} || ' ', ' ') = 0 THEN length({headline}) "
        f"ELSE instr({headline} || ' ', ' ') - 1 END))"
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
    rest = f"trim(substr({headline}, instr({headline} || ' ', ' ') + 1))"
    if not cases:
        return rest
    return f"CASE {' '.join(cases)} ELSE {rest} END"
