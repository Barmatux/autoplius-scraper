"""Background-only listing description translation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import autoplius.ensure_description_ru as ensure_mod


def test_ensure_queues_background_without_sync_translate(monkeypatch, tmp_path: Path):
    calls: list[tuple] = []

    def fake_schedule(db_path, listing_id, original, settings):
        calls.append((db_path, listing_id, original, settings.translate_descriptions))

    def boom(*_a, **_k):
        raise AssertionError("sync translate must not run on the request path")

    monkeypatch.setattr(ensure_mod, "_schedule_background_translate", fake_schedule)
    monkeypatch.setattr(ensure_mod, "_persist_translation", boom)

    original = (
        "Parduodamas labai geros būklės automobilis, pilna serviso istorija, "
        "antras ratų komplektas, važiuoja be priekaištų kiekvieną dieną."
    )
    item = {"autoplius_id": 42, "description": original, "description_ru": None}
    settings = SimpleNamespace(translate_descriptions=True, translate_delay_sec=0.0)

    out = ensure_mod.ensure_listing_description_ru(tmp_path / "x.db", item, settings)  # type: ignore[arg-type]

    assert out is item
    assert out.get("description_ru") is None
    assert len(calls) == 1
    assert calls[0][1] == 42
    assert calls[0][2] == original


def test_ensure_skips_when_russian_already_present(monkeypatch, tmp_path: Path):
    scheduled = []

    monkeypatch.setattr(
        ensure_mod,
        "_schedule_background_translate",
        lambda *a, **k: scheduled.append(a),
    )
    item = {
        "autoplius_id": 7,
        "description": (
            "Parduodamas labai geros būklės automobilis, pilna serviso istorija, "
            "antras ratų komplektas, važiuoja be priekaištų kiekvieną dieną."
        ),
        "description_ru": (
            "Продается автомобиль в отличном состоянии, полная история сервиса, "
            "второй комплект колес, ездит без нареканий каждый день."
        ),
    }
    settings = SimpleNamespace(translate_descriptions=True, translate_delay_sec=0.0)
    out = ensure_mod.ensure_listing_description_ru(tmp_path / "x.db", item, settings)  # type: ignore[arg-type]
    assert out is item
    assert scheduled == []


def test_update_listing_description_ru_uses_listing_pk_where(monkeypatch):
    from scraper import db as db_mod
    from scraper.sql_dialect import listing_pk_where

    monkeypatch.setenv("DATABASE_URL", "postgresql://scrape:scrape@127.0.0.1:5433/scrape")
    captured: dict[str, str] = {}

    class FakeConn:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(db_mod, "init_db", lambda _p: None)
    monkeypatch.setattr(db_mod, "connect", lambda _p: FakeConn())
    monkeypatch.setattr(db_mod, "_utc_now", lambda: "2026-01-01T00:00:00+00:00")

    db_mod.update_listing_description_ru(Path("/tmp/x.db"), 32155716, "Привет")
    assert listing_pk_where() in captured["sql"]
    assert "autoplius_id = ?" not in captured["sql"] or "external_id" in captured["sql"]
    assert "external_id" in captured["sql"]
    assert captured["params"][0] == "Привет"
    assert captured["params"][2] == 32155716
