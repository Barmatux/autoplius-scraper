from __future__ import annotations

import pytest


def test_normalize_database_url_strips_sqlalchemy_prefix():
    from scraper.db_backend import normalize_database_url

    assert (
        normalize_database_url("postgresql+psycopg://scrape:scrape@db:5432/scrape")
        == "postgresql://scrape:scrape@db:5432/scrape"
    )
    assert normalize_database_url("postgresql://x") == "postgresql://x"


def test_sqlite_default_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from scraper import db_backend, sql_dialect

    assert db_backend.using_postgres() is False
    assert sql_dialect.get_dialect() == "sqlite"
    assert sql_dialect.listings_source_clause() == ""
    assert sql_dialect.listing_id_expr() == "autoplius_id"
    assert "instr(" in sql_dialect.instr_expr("title", "','")


def test_postgres_dialect_helpers(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://scrape:scrape@127.0.0.1:5433/scrape",
    )
    from scraper import db_backend, sql_dialect

    assert db_backend.using_postgres() is True
    assert sql_dialect.get_dialect() == "postgres"
    assert sql_dialect.listings_source_clause() == "source = 'autoplius'"
    assert "external_id" in sql_dialect.listing_id_expr()
    assert "parameters AS parameters_json" in sql_dialect.listing_select_columns("full")
    assert "strpos(" in sql_dialect.instr_expr("title", "','")
    adapted = sql_dialect.adapt_sql_for_postgres(
        "SELECT * FROM t WHERE id = ? AND name = :name AND x::text = ? AND y LIKE '%pikap%'"
    )
    assert "%s" in adapted
    assert "%(name)s" in adapted
    assert "::text" in adapted
    assert "%%pikap%%" in adapted


def test_build_listing_where_adds_source_on_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://scrape:scrape@127.0.0.1:5433/scrape")
    from scraper.listing_sql_filters import ListingFilters, build_listing_where

    clauses, _ = build_listing_where(ListingFilters())
    assert "source = 'autoplius'" in clauses


def test_postgres_bool_and_manual_electric_sql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://scrape:scrape@10.129.0.33:5433/scrape")
    from scraper.sql_dialect import manual_electric_sql_expr, truthy_int_bool_sql
    from autoplius.electric import electric_sql_clause

    assert "IS TRUE" in truthy_int_bool_sql("detail_scraped")
    assert "manual_overrides" in manual_electric_sql_expr()
    assert "manual_overrides" in electric_sql_clause(include=True)
    assert "COALESCE(manual_electric" not in electric_sql_clause(include=True)


def test_postgres_age_months_uses_case_not_bool_mul(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://scrape:scrape@127.0.0.1:5433/scrape")
    from scraper.sql_dialect import age_months_sql, order_ci

    expr = age_months_sql("y", "m")
    assert "CASE WHEN" in expr
    assert " * " not in expr.split("THEN", 1)[0]
    assert "LOWER(name)" == order_ci("name")
