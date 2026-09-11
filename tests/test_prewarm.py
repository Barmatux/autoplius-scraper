"""Tests for home page prewarm helper."""

from __future__ import annotations

from ui.prewarm import DEFAULT_HOME_PATHS, home_paths, prewarm_home


def test_home_paths_default(monkeypatch):
    monkeypatch.delenv("UI_PREWARM_PATHS", raising=False)
    assert home_paths() == DEFAULT_HOME_PATHS
    assert "/catalog" in DEFAULT_HOME_PATHS


def test_home_paths_override(monkeypatch):
    monkeypatch.setenv("UI_PREWARM_PATHS", "/,/catalog")
    assert home_paths() == ("/", "/catalog")


def test_prewarm_home_hits_urls(monkeypatch):
    calls: list[str] = []

    class _Resp:
        status = 200

        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    rows = prewarm_home(
        base_url="http://127.0.0.1:8080",
        paths=["/"],
        rounds=2,
        timeout_sec=5,
    )
    assert len(rows) == 2
    assert all(r["ok"] for r in rows)
    assert calls == [
        "http://127.0.0.1:8080/",
        "http://127.0.0.1:8080/",
    ]
