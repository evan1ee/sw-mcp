"""Live tests run only when asked for, because they drive whichever SOLIDWORKS is open.

These only collect tests. Collecting imports the modules and never connects to SOLIDWORKS.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NO_TESTS_COLLECTED = 5


def _collect(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/live", "--collect-only", "-q", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_default_run_selects_no_live_test() -> None:
    result = _collect()
    assert result.returncode == NO_TESTS_COLLECTED, result.stdout
    assert "::test_" not in result.stdout
    assert "deselected" in result.stdout


def test_asking_for_live_selects_them() -> None:
    result = _collect("-m", "live")
    assert result.returncode == 0, result.stdout
    assert "::test_" in result.stdout
