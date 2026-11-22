"""A fresh database opened by several connections at once (threads, or worker processes on a first start):
setting it up happens once, under the write lock; nobody fails on a column another one just added."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from kitchenette import config, db

SRC = str(Path(__file__).resolve().parents[1] / "src")


def _columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _check(path: str) -> None:
    import sqlite3
    conn = sqlite3.connect(path)
    try:
        for table, col, _decl in db._ADDED_COLUMNS:
            cols = _columns(conn, table)
            assert cols.count(col) == 1, (table, col, cols)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"batches", "cook_sessions", "dex_merges", "kitchen_prefs", "once_keys"} <= tables
        keys = [r[0] for r in conn.execute("SELECT key FROM once_keys WHERE key IN ('worm_since','fruit_worm_since')")]
        assert sorted(keys) == ["fruit_worm_since", "worm_since"]
    finally:
        conn.close()


def test_four_threads_opening_a_new_database_at_once(tmp_path):
    p = str(tmp_path / "fresh.db")
    config.override(server_db_path=p)
    db.forget()
    errors: list[BaseException] = []
    go = threading.Barrier(4, timeout=20)

    def one():
        try:
            go.wait()
            db.connect().close()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=one, daemon=True) for _ in range(4)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert not any(t.is_alive() for t in ts) and errors == []
    _check(p)


def test_four_threads_that_each_think_the_database_is_new(tmp_path, monkeypatch):
    """What several processes do: none of them knows another set the database up (no shared memo, no shared
    lock between them), so each runs the whole setup; they must take turns at the write lock."""
    p = str(tmp_path / "fresh.db")
    config.override(server_db_path=p)
    db.forget()
    import sqlite3
    errors: list[BaseException] = []
    go = threading.Barrier(4, timeout=20)

    def one():
        try:
            go.wait()
            conn = sqlite3.connect(p, timeout=10)
            db._wal(conn)
            db._set_up(conn)
            conn.close()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)
    for _ in range(3):           # a few rounds: the interleaving differs from run to run
        ts = [threading.Thread(target=one, daemon=True) for _ in range(4)]
        [t.start() for t in ts]
        [t.join(30) for t in ts]
        assert not any(t.is_alive() for t in ts) and errors == []
        _check(p)
        os.remove(p)
        for extra in ("-wal", "-shm"):
            if os.path.exists(p + extra):
                os.remove(p + extra)


def test_four_processes_starting_on_a_new_database(tmp_path):
    p = str(tmp_path / "fresh.db")
    code = ("import sys, time; sys.path.insert(0, sys.argv[1]);"
            "from kitchenette import config, db;"
            "config.override(server_db_path=sys.argv[2]);"
            "t = float(sys.argv[3]);"
            "time.sleep(max(0, t - time.time()));"
            "db.connect().close()")
    import time
    start = str(time.time() + 1.5)
    env = {k: v for k, v in os.environ.items() if not k.startswith("KITCHENETTE_")}
    procs = [subprocess.Popen([sys.executable, "-c", code, SRC, p, start], env=env, cwd=str(tmp_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    outs = [pr.communicate(timeout=40) for pr in procs]
    assert [pr.returncode for pr in procs] == [0, 0, 0, 0], [o[1].decode()[-600:] for o in outs]
    _check(p)
