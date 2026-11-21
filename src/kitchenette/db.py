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

-- ── the upgrade (docs/UPGRADE.md). Tables are only ever added to; switching a feature off deletes nothing.
CREATE TABLE IF NOT EXISTS recipe_pages (           -- the role's own recipe pages
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  kind TEXT NOT NULL,                  -- fav | adapt | own | menu | code
  ref_id TEXT,                         -- fav: public recipe id; adapt: what it was adapted from
  ref_version INTEGER,
  cur_version INTEGER NOT NULL DEFAULT 1,
  content_id TEXT,                     -- imported code: the same code imported twice is the same page
  src_label TEXT,
  src_by TEXT,
  created_at REAL NOT NULL,
  deleted_at REAL
);
CREATE INDEX IF NOT EXISTS idx_recipe_pages_who ON recipe_pages(who, kind, deleted_at);
CREATE TABLE IF NOT EXISTS recipe_page_versions (   -- every version of every page, never rewritten
  page_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  items_json TEXT NOT NULL DEFAULT '[]',
  optional_json TEXT NOT NULL DEFAULT '[]',
  method TEXT,
  minutes INTEGER,
  note TEXT NOT NULL DEFAULT '',
  menu_json TEXT,
  created_at REAL NOT NULL,
  PRIMARY KEY (page_id, version)
);
CREATE TABLE IF NOT EXISTS recipe_notes (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, page_id TEXT NOT NULL, session_id TEXT,
  text TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_orders (          -- the human's orders
  id TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, name TEXT NOT NULL,
  state TEXT NOT NULL,                 -- received | planned | cooking | done | withdrawn
  his_note TEXT NOT NULL DEFAULT '', session_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recipe_orders ON recipe_orders(who, identity, state, created_at);
CREATE TABLE IF NOT EXISTS recipe_firsts (          -- the first time a recipe was eaten (the new-dish bonus)
  who TEXT NOT NULL, identity TEXT NOT NULL, eat_key TEXT NOT NULL, session_id TEXT,
  name TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY (who, identity)
);
CREATE TABLE IF NOT EXISTS recipe_buys (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, items_json TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_flags (           -- a recipe with a mistake can be taken out of circulation
  recipe_id TEXT PRIMARY KEY, stopped INTEGER NOT NULL DEFAULT 1, why TEXT NOT NULL DEFAULT '', at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kitchen_prefs (          -- things the human does not want recommended
  who TEXT NOT NULL, kind TEXT NOT NULL, item TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (who, kind, item)
);
CREATE TABLE IF NOT EXISTS dish_counts (            -- proficiency, by dish name (free pots and changed recipes)
  who TEXT NOT NULL, dish TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, dish)
);
CREATE TABLE IF NOT EXISTS recipe_counts (          -- proficiency, by recipe (pots that followed it)
  who TEXT NOT NULL, identity TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, identity)
);
CREATE TABLE IF NOT EXISTS cook_settlements (       -- written once when a pot is served, never changed
  session_id TEXT PRIMARY KEY, who TEXT NOT NULL, dish TEXT NOT NULL, method TEXT,
  outcome TEXT NOT NULL, link TEXT NOT NULL, recipe_id TEXT, recipe_version INTEGER,
  book TEXT, book_key TEXT, before_n INTEGER, after_n INTEGER, before_tier TEXT, after_tier TEXT,
  first_time INTEGER NOT NULL DEFAULT 0, mishap_id TEXT, mishap_ver INTEGER, rescued_item TEXT,
  started_at REAL NOT NULL, settled_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cook_settlements_who ON cook_settlements(who, settled_at);
CREATE TABLE IF NOT EXISTS achievements_earned (    -- earned is kept for good
  who TEXT NOT NULL, ach TEXT NOT NULL, earned_at REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '',
  why TEXT NOT NULL DEFAULT '', PRIMARY KEY (who, ach)
);
CREATE TABLE IF NOT EXISTS dex_art (                -- one picture per dish page; redrawing keeps the old ones
  page_key TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, path TEXT NOT NULL DEFAULT '',
  err TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY (page_key, version)
);
CREATE TABLE IF NOT EXISTS dex_art_choice (page_key TEXT PRIMARY KEY, version INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS dex_notes (who TEXT NOT NULL, page_key TEXT NOT NULL, text TEXT NOT NULL, at REAL NOT NULL,
  PRIMARY KEY (who, page_key));
CREATE TABLE IF NOT EXISTS dex_merges (who TEXT NOT NULL, dish TEXT NOT NULL, page_key TEXT NOT NULL, at REAL NOT NULL,
  PRIMARY KEY (who, dish));
CREATE TABLE IF NOT EXISTS dishes (                 -- plates: one per meal
  id TEXT PRIMARY KEY, who TEXT NOT NULL, eat_key TEXT NOT NULL UNIQUE, dish TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL,                 -- sink | washing | clean | broken | machine
  job_id TEXT, done_at REAL, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dishes_who ON dishes(who, state, created_at);
CREATE TABLE IF NOT EXISTS wash_jobs (              -- one washing-up: how many, how long each, which breaks, fixed at the start
  id TEXT PRIMARY KEY, who TEXT NOT NULL, key TEXT NOT NULL UNIQUE, dish_ids_json TEXT NOT NULL, per_s REAL NOT NULL,
  break_idx_json TEXT NOT NULL DEFAULT '[]', started_at REAL NOT NULL, state TEXT NOT NULL, ended_at REAL,
  told INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wash_jobs_running ON wash_jobs(who) WHERE state='running';
CREATE TABLE IF NOT EXISTS wash_settings (who TEXT PRIMARY KEY, self_wash INTEGER NOT NULL DEFAULT 0, quota INTEGER,
  updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jars (                   -- the three jars on the sill
  who TEXT NOT NULL, slot INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'empty', item_id TEXT, item_name TEXT,
  freshness TEXT, how TEXT, how_word TEXT, note TEXT NOT NULL DEFAULT '', sealed_at REAL, due_at REAL, seal_key TEXT,
  PRIMARY KEY (who, slot)
);
CREATE TABLE IF NOT EXISTS jar_goods (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL, item_name TEXT NOT NULL, ok INTEGER NOT NULL,
  total INTEGER NOT NULL, left_n INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', opened_at REAL NOT NULL,
  told INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jar_goods_who ON jar_goods(who, name, opened_at);
CREATE TABLE IF NOT EXISTS jar_takes (
  take_key TEXT PRIMARY KEY, who TEXT NOT NULL, goods_id TEXT NOT NULL, day TEXT NOT NULL, by_who TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jar_takes_day ON jar_takes(who, day);
CREATE TABLE IF NOT EXISTS jar_caps (who TEXT PRIMARY KEY, cap INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_days (day TEXT PRIMARY KEY, plan_json TEXT NOT NULL, weather TEXT NOT NULL DEFAULT '',
  made_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_visits (
  id TEXT PRIMARY KEY, day TEXT NOT NULL, slot INTEGER NOT NULL, vendor TEXT NOT NULL,
  arrive_at REAL NOT NULL, leave_at REAL NOT NULL, goods_json TEXT NOT NULL, told TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL, UNIQUE(day, slot)
);
CREATE INDEX IF NOT EXISTS idx_vendor_visits_time ON vendor_visits(arrive_at, leave_at);
CREATE TABLE IF NOT EXISTS vendor_orders (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, visit_id TEXT NOT NULL, vendor TEXT NOT NULL,
  item_id TEXT NOT NULL, item_name TEXT NOT NULL, kind TEXT NOT NULL, unit TEXT NOT NULL,
  qty INTEGER NOT NULL, unit_price INTEGER NOT NULL, total INTEGER NOT NULL,
  payer TEXT NOT NULL, day TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', balance INTEGER,
  deliver_tries INTEGER NOT NULL DEFAULT 0, receipt_extra TEXT NOT NULL DEFAULT '[]',
  debit_unsure INTEGER NOT NULL DEFAULT 0, told INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vendor_orders_state ON vendor_orders(state);
CREATE INDEX IF NOT EXISTS idx_vendor_orders_quota ON vendor_orders(who, payer, day);
CREATE TABLE IF NOT EXISTS vendor_regulars (who TEXT NOT NULL, vendor TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  last_items TEXT NOT NULL DEFAULT '', last_at REAL, PRIMARY KEY (who, vendor));
CREATE TABLE IF NOT EXISTS vendor_gifts (order_id TEXT PRIMARY KEY, who TEXT NOT NULL, item_id TEXT NOT NULL,
  text TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_talks (visit_id TEXT NOT NULL, who TEXT NOT NULL, history_json TEXT NOT NULL DEFAULT '[]',
  n INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY (visit_id, who));
CREATE TABLE IF NOT EXISTS vendor_talk_lines (msg_key TEXT PRIMARY KEY, visit_id TEXT NOT NULL, who TEXT NOT NULL,
  nth INTEGER NOT NULL, his TEXT NOT NULL, shown TEXT NOT NULL, from_model INTEGER NOT NULL, receipt TEXT NOT NULL,
  at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_flowers (id TEXT PRIMARY KEY, who TEXT NOT NULL, order_id TEXT NOT NULL UNIQUE,
  variety TEXT NOT NULL, name TEXT NOT NULL, bought_at REAL NOT NULL, removed_at REAL, gifted_at REAL, gift_note TEXT);
CREATE INDEX IF NOT EXISTS idx_vendor_flowers_who ON vendor_flowers(who, bought_at);
CREATE TABLE IF NOT EXISTS vendor_flower_requests (id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL,
  msg_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL, created_at REAL NOT NULL, decided_at REAL);
CREATE TABLE IF NOT EXISTS wallet_local (           -- the built-in pocket-money ledger (when no wallet is configured)
  id TEXT PRIMARY KEY, who TEXT NOT NULL, kind TEXT NOT NULL,   -- grant | vendor
  amount INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', at REAL NOT NULL
);
"""

# Columns added to tables that already existed before the upgrade (older databases get them on open).
_ADDED_COLUMNS = (("cook_sessions", "recipe_id", "TEXT"), ("cook_sessions", "recipe_version", "INTEGER"),
                  ("cook_sessions", "recipe_link", "TEXT"), ("cook_sessions", "mishap_id", "TEXT"),
                  ("cook_sessions", "mishap_ver", "INTEGER"))

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
        for table, col, decl in _ADDED_COLUMNS:
            if col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
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
