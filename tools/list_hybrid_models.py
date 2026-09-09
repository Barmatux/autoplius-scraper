#!/usr/bin/env python3
"""List distinct hybrid make+model pairs from active listings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.title_sql import title_make_expr, title_model_expr
from scraper.config import Settings
from scraper.db import connect, init_db


def list_hybrids(db_path: Path) -> list[tuple[str, str, int]]:
    init_db(db_path)
    make_expr = title_make_expr()
    model_expr = title_model_expr()
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {make_expr} AS make, {model_expr} AS model, COUNT(*) AS cnt
            FROM listings
            WHERE (status IS NULL OR status = 'active')
              AND (
                trim(COALESCE(fuel, '')) IN (
                  'Бензин / электричество',
                  'Дизель / электричество',
                  'Benzinas / elektra',
                  'Dyzelinas / elektra'
                )
                OR COALESCE(fuel, '') LIKE '%/%лектр%'
                OR lower(COALESCE(fuel, '')) LIKE '%/%elektr%'
                OR COALESCE(fuel, '') LIKE '%гибрид%'
                OR lower(COALESCE(fuel, '')) LIKE '%hybrid%'
              )
              AND {make_expr} != ''
              AND {make_expr} != '—'
            GROUP BY make, model
            ORDER BY cnt DESC, make COLLATE NOCASE, model COLLATE NOCASE
            """
        ).fetchall()
    out: list[tuple[str, str, int]] = []
    for row in rows:
        make = (row["make"] or "").strip()
        model = (row["model"] or "").strip()
        if not make:
            continue
        out.append((make, model or "—", int(row["cnt"] or 0)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    db_path = args.db or Settings.from_env().db_path
    rows = list_hybrids(db_path)
    print(f"hybrid_make_models={len(rows)}")
    for make, model, count in rows:
        print(f"{count:4d}  {make} {model}")


if __name__ == "__main__":
    main()
