"""Contract-staff accounts (login → /admin/contracts only)."""

from __future__ import annotations

import os
import re
import secrets

# Built-in staff for contracts UI. Override with CONTRACT_USERS=login:pass,...
DEFAULT_CONTRACT_USERS: tuple[tuple[str, str], ...] = (
    ("dir_max", "77997799"),
    ("manager_alex", "77997799"),
    ("roman1067", "10671067"),
)


def parse_contract_users(raw: str) -> dict[str, str]:
    users: dict[str, str] = {}
    for part in re.split(r"[,;\n]+", raw or ""):
        part = part.strip()
        if not part or ":" not in part:
            continue
        username, password = part.split(":", 1)
        username = username.strip()
        password = password.strip()
        if username and password:
            users[username] = password
    return users


def contract_credentials() -> dict[str, str]:
    raw = (os.environ.get("CONTRACT_USERS") or "").strip()
    if raw:
        return parse_contract_users(raw)
    return {user: password for user, password in DEFAULT_CONTRACT_USERS}


def check_contract_credentials(username: str, password: str) -> str | None:
    """Return canonical login if credentials match a contract staff account."""
    users = contract_credentials()
    expected = users.get(username)
    matched = username
    if expected is None:
        lowered = {key.lower(): key for key in users}
        key = lowered.get(username.lower())
        if key is None:
            return None
        expected = users[key]
        matched = key
    if not secrets.compare_digest(expected, password):
        return None
    return matched
