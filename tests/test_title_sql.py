import sqlite3

from autoplius.title_sql import title_make_expr, title_model_expr


def test_title_make_model_sql_split():
    conn = sqlite3.connect(":memory:")
    make_expr = title_make_expr()
    model_expr = title_model_expr()
    row = conn.execute(
        f"SELECT {make_expr} AS make, {model_expr} AS model FROM (SELECT ? AS title)",
        ("Peugeot 508, Универсал, 2011-07 m.",),
    ).fetchone()
    assert row[0] == "Peugeot"
    assert row[1] == "508"

    row = conn.execute(
        f"SELECT {make_expr} AS make, {model_expr} AS model FROM (SELECT ? AS title)",
        ("Alfa Romeo Giulietta, Хэтчбек, 2012-03 m.",),
    ).fetchone()
    assert row[0] == "Alfa Romeo"
    assert row[1] == "Giulietta"

    row = conn.execute(
        f"SELECT {make_expr} AS make, {model_expr} AS model FROM (SELECT ? AS title)",
        ("Volvo V70, Универсал, 2012-09 m.",),
    ).fetchone()
    assert row[0] == "Volvo"
    assert row[1] == "V70"
