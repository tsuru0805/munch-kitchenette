"""SQLite storage: one file holds every table.

Keeping the fridge, the pots and the appetite in the same file is what lets
"take the ingredients and start the pot" or "mark the dish eaten, raise
satiety and start the dizziness" each happen in a single transaction.
"""
from __future__ import annotations

import os
import sqlite3

from . import clock, config

SCHEMA = """
-- Fridge: one row per purchase. Freshness is computed on read from bought_at.
CREATE TABLE IF NOT EXISTS batches (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  bought_at REAL NOT NULL,
  by_who TEXT NOT NULL,                 -- self | her
  source TEXT NOT NULL DEFAULT '',
  wormed_at REAL,                       -- when a spoiled fruit grew worms
  shelf_days REAL                       -- shelf life frozen at purchase (custom kinds only)
);
CREATE INDEX IF NOT EXISTS idx_batches_who ON batches(who, item_id, bought_at);

CREATE TABLE IF NOT EXISTS coupons (
  who TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0
);

-- Idempotency keys: one coupon per piece of writing, one purchase per order, one bite per meal.
CREATE TABLE IF NOT EXISTS once_keys (
  key TEXT PRIMARY KEY,
  at REAL NOT NULL,
  result TEXT NOT NULL DEFAULT ''
);

-- What happened in the kitchen, newest shown on the page.
CREATE TABLE IF NOT EXISTS fridge_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fridge_log_who ON fridge_log(who, at);

CREATE TABLE IF NOT EXISTS appetite (
  who TEXT PRIMARY KEY,
  satiety REAL NOT NULL,
  satiety_at REAL NOT NULL,
  dizzy_until REAL,
  dizzy_dish TEXT,
  dizzy_since REAL,
  dizzy_over_told INTEGER NOT NULL DEFAULT 1,
  hungry_told INTEGER NOT NULL DEFAULT 0
);

-- Ingredient kinds added from the page. Removing one sets removed_at; rows are never deleted.
CREATE TABLE IF NOT EXISTS kinds (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  pack_qty INTEGER NOT NULL DEFAULT 1,
  shelf_days REAL,
  raw_edible INTEGER NOT NULL DEFAULT 0,
  art_state TEXT NOT NULL DEFAULT 'pending',
  art_v INTEGER NOT NULL DEFAULT 0,
  art_sizes TEXT NOT NULL DEFAULT '',
  art_err TEXT NOT NULL DEFAULT '',
  art_req INTEGER NOT NULL DEFAULT 1,   -- which drawing request this is; a finished drawing only lands if it matches
  created_at REAL NOT NULL,
  removed_at REAL
);

CREATE TABLE IF NOT EXISTS cook_sessions (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  dish TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  duration_seconds INTEGER NOT NULL,
  started_at REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'cooking',   -- cooking | served | cancelled | ruined
  served_at REAL,
  cancelled_at REAL,
  menu_added_at REAL,
  menu_row_id TEXT,
  woke_at REAL,                             -- when the role was told the dish is ready
  created_at REAL NOT NULL,
  ingredients_json TEXT,
  outcome TEXT,                             -- great | ok | burnt | spoiled | ruined
  eaten_at REAL,
  worm_state TEXT,                          -- NULL | skipped | wormed | noted | tossed | gone
  wormed_at REAL,
  method TEXT
);
CREATE INDEX IF NOT EXISTS idx_cook_sessions_who_status ON cook_sessions(who, status, started_at);

-- The one worm waiting inside a snack (at most one per role).
CREATE TABLE IF NOT EXISTS worm_pending (
  who TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  dish TEXT NOT NULL,
  made_at REAL NOT NULL,
  at REAL NOT NULL,
  snack TEXT NOT NULL DEFAULT 'pudding',
  source TEXT NOT NULL DEFAULT 'dish'
);

-- A worm was bitten into and the role still has to be told.
CREATE TABLE IF NOT EXISTS worm_wakes (
  rid TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  text TEXT NOT NULL DEFAULT '',
  done_at REAL,
  how TEXT
);

CREATE TABLE IF NOT EXISTS potions (
  menu_row_id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  pct INTEGER NOT NULL,                     -- stamina restored, in percentage points
  created_at REAL NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending',    -- pending | taking | used
  taken_at REAL,
  used_at REAL,
  used_by TEXT,                             -- self | her
  energy_after REAL,
  memo TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_potions_who ON potions(who, state);

CREATE TABLE IF NOT EXISTS snack_log (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  snack TEXT NOT NULL,
  variant TEXT NOT NULL DEFAULT '',
  day TEXT NOT NULL,                        -- snack day YYYY-MM-DD (rolls over at the boundary hour)
  by TEXT NOT NULL,                         -- self | her
  gain REAL NOT NULL,
  energy_delta REAL NOT NULL DEFAULT 0,     -- stamina actually added
  ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snack_log_day ON snack_log(who, day, snack);
CREATE TABLE IF NOT EXISTS snack_caps (
  who TEXT NOT NULL,
  snack TEXT NOT NULL,
  cap INTEGER NOT NULL,
  updated_at REAL NOT NULL,
  PRIMARY KEY (who, snack)
);

-- The table: dishes waiting to be eaten. eaten_at NULL = still there.
CREATE TABLE IF NOT EXISTS menu (
  id TEXT PRIMARY KEY,
  dish TEXT NOT NULL,
  note TEXT,
  by TEXT NOT NULL,
  for_who TEXT NOT NULL,
  eaten_at REAL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_menu_for ON menu(for_who, eaten_at);

CREATE TABLE IF NOT EXISTS meals (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  meal TEXT NOT NULL,
  note TEXT,
  at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meals_who ON meals(who, at);

CREATE TABLE IF NOT EXISTS stamina (
  who TEXT PRIMARY KEY,
  value REAL NOT NULL,
  updated_at REAL NOT NULL,
  round_at REAL,                            -- when the current run of tool calls began
  round_kinds TEXT NOT NULL DEFAULT '[]',   -- kinds of work already charged in it
  round_cost REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stamina_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  delta REAL NOT NULL,
  value REAL NOT NULL,
  rule TEXT NOT NULL DEFAULT ''
);

-- Fed by whatever tracks the role's sleep (see docs/HOOKS.md). Unused unless switched on.
CREATE TABLE IF NOT EXISTS sleep_state (
  who TEXT PRIMARY KEY,
  asleep INTEGER NOT NULL DEFAULT 0,
  asleep_until REAL,
  factor REAL NOT NULL DEFAULT 1.0,
  updated_at REAL NOT NULL
);

-- Things to tell a role: read by the queue endpoints, pushed by the webhook.
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  dedupe_key TEXT UNIQUE,
  created_at REAL NOT NULL,
  taken_at REAL,
  pushed_at REAL,
  push_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_notes_who ON notes(who, taken_at);
"""

_initialized: set[str] = set()


def path() -> str:
    return config.get().server_db_path


def connect() -> sqlite3.Connection:
    p = path()
    os.makedirs(os.path.dirname(os.path.abspath(p)) or ".", exist_ok=True)
    conn = sqlite3.connect(p, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    if p not in _initialized:
        conn.executescript(SCHEMA)
        # Worms only grow on dishes served (and fruit spoiled) after the database was created.
        now = clock.now()
        conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES ('worm_since', ?, '')", (now,))
        conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES ('fruit_worm_since', ?, '')", (now,))
        conn.commit()
        _initialized.add(p)
    return conn


_flags: set[tuple[str, str]] = set()      # flags known to be set; a flag never goes back


def flag(name: str) -> bool:
    """A one-way fact remembered in the database ("this has happened at least once")."""
    key = (path(), name)
    if key in _flags:
        return True
    if not os.path.isfile(key[0]):
        return False
    conn = connect()
    try:
        hit = conn.execute("SELECT 1 FROM once_keys WHERE key=?", (f"flag:{name}",)).fetchone() is not None
    finally:
        conn.close()
    if hit:
        _flags.add(key)
    return hit


def set_flag(name: str) -> None:
    key = (path(), name)
    if key in _flags:
        return
    conn = connect()
    try:
        conn.execute("INSERT OR IGNORE INTO once_keys (key, at, result) VALUES (?,?,'')",
                     (f"flag:{name}", clock.now()))
        conn.commit()
    finally:
        conn.close()
    _flags.add(key)


def forget(p: str | None = None) -> None:
    """Drop the "schema already created" memo (tests point at fresh files)."""
    if p is None:
        _initialized.clear()
        _flags.clear()
    else:
        _initialized.discard(p)
        for key in [k for k in _flags if k[0] == p]:
            _flags.discard(key)
