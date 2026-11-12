"""Role ids.

A role is whoever owns a fridge: any non-empty string works, so one server
can keep house for several companions. Each role has its own fridge, coupons,
menu, satiety and stamina, and never sees another role's.
"""
from __future__ import annotations

from . import config, db

MAX_LEN = 64

# Every table that carries a role id, for discovering which roles exist.
_ROLE_COLUMNS = (("batches", "who"), ("coupons", "who"), ("appetite", "who"), ("cook_sessions", "who"),
                 ("menu", "for_who"), ("potions", "who"), ("snack_log", "who"), ("stamina", "who"),
                 ("worm_wakes", "who"), ("notes", "who"))


def valid(who) -> bool:
    if not isinstance(who, str):
        return False
    w = who.strip()
    if not w or w != who or len(w) > MAX_LEN or any(ord(c) < 32 for c in w):
        return False
    allowed = config.get().roles_allowed
    return not allowed or w in allowed


def check(who) -> str:
    if not valid(who):
        raise ValueError(f"unknown role {who!r}")
    return who


def resolve(who: str | None) -> str:
    """A role id, falling back to the configured default when omitted."""
    return check(who if who not in (None, "") else config.get().roles_default)


def known() -> list[str]:
    """Roles that have left any trace in the database."""
    conn = db.connect()
    try:
        sql = " UNION ".join(f"SELECT {col} AS who FROM {table}" for table, col in _ROLE_COLUMNS)
        found = {r["who"] for r in conn.execute(sql).fetchall() if r["who"]}
    finally:
        conn.close()
    return sorted(w for w in found if valid(w))
