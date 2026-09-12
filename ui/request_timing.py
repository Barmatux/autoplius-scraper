"""Optional per-request timing hooks for the Flask UI."""

from __future__ import annotations

from typing import Any


def init_request_timing(app: Any) -> None:
    """No-op placeholder; kept so production UI can import cleanly."""
    return None
