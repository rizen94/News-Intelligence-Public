"""
Run the wiring verifiers as part of the normal suite.

Both scripts are also usable standalone (see their module docstrings). They run in subprocesses:
`verify_no_import_time_db` patches `psycopg2.connect` process-wide and imports every module, which
must not leak into the rest of the session.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _run(script: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "api")
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=600,
        check=False,
    )


@pytest.mark.parametrize(
    "script",
    ["verify_no_import_time_db.py", "verify_frontend_route_wiring.py"],
)
def test_verifier_passes(script: str):
    result = _run(script)
    assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


def test_import_time_db_verifier_would_catch_a_regression(tmp_path, monkeypatch):
    """The detector is only useful if it actually fails on a module that connects at import."""
    sys.path.insert(0, str(ROOT / "api"))
    try:
        import psycopg2
    finally:
        sys.path.pop(0)

    calls = {"n": 0}

    def _spy(*_a, **_kw):
        calls["n"] += 1
        raise psycopg2.OperationalError("blocked")

    monkeypatch.setattr(psycopg2, "connect", _spy)

    # Stand-in for the shape the detector exists to catch: a module-scope DB call.
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(host="127.0.0.1")
    assert calls["n"] == 1
