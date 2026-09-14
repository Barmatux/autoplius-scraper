"""Database backend selection: SQLite (default) vs Postgres consumer mode."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


_SQLALCHEMY_PG_PREFIX = "postgresql+psycopg://"
_PG_PREFIX = "postgresql://"


def normalize_database_url(url: str) -> str:
    """Normalize a DSN for psycopg (strip SQLAlchemy driver prefix if present)."""
    cleaned = (url or "").strip()
    if cleaned.startswith(_SQLALCHEMY_PG_PREFIX):
        return _PG_PREFIX + cleaned[len(_SQLALCHEMY_PG_PREFIX) :]
    return cleaned


def database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return None
    return normalize_database_url(raw)


def using_postgres() -> bool:
    return database_url() is not None


def db_ready(db_path: Path) -> bool:
    """True when Postgres is reachable via DATABASE_URL, or the SQLite file exists."""
    url = database_url()
    if url:
        try:
            import psycopg

            with psycopg.connect(url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    return Path(db_path).is_file()


def cache_token(db_path: Path) -> str:
    """Stable-ish cache key for query caches.

    Postgres: ``pg:{hash of url}`` plus optional ``DATABASE_CACHE_TOKEN``.
    SQLite: resolved path + mtime + size (same shape as historical UI caches).
    """
    url = database_url()
    if url:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        extra = os.environ.get("DATABASE_CACHE_TOKEN", "").strip()
        if extra:
            return f"pg:{digest}:{extra}"
        return f"pg:{digest}"

    path = Path(db_path)
    try:
        stat = path.resolve().stat()
    except OSError:
        return str(path.resolve())
    return f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
