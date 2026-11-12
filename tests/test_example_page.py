"""examples/kitchen_page.py leaves nothing behind, however it is ended."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENDINGS = [s for s in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, s)]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
@pytest.mark.parametrize("ending", ENDINGS)
def test_the_demo_kitchen_removes_its_temporary_database(tmp_path, ending):
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("KITCHENETTE_")}
    env["TMPDIR"] = str(tmp_path)                       # where the demo makes its throwaway folder
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.Popen([sys.executable, str(ROOT / "examples" / "kitchen_page.py"), "--port", str(port)],
                            env=env, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + 30
        while True:
            assert proc.poll() is None, proc.stderr.read().decode()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1):
                    break
            except OSError:
                assert time.time() < deadline, "the demo kitchen did not answer in time"
                time.sleep(0.1)
        made = list(tmp_path.glob("kitchenette-page-*"))
        assert len(made) == 1 and (made[0] / "kitchen-page.db").is_file()
        proc.send_signal(getattr(signal, ending))
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert list(tmp_path.glob("kitchenette-page-*")) == [], f"left behind after {ending}"
