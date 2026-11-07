"""Benchmark tests for Prompt-to-Part-IR evaluation baseline (Debt 3)."""

import json
import subprocess
import sys
from pathlib import Path

from cad_application.authoring_eval.cases import CASES
from cad_application.authoring_eval.checker import score_all

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "score_part_ir.py"
BASELINE_ANSWERS_PATH = REPO_ROOT / "tests" / "cad-benchmark" / "part_ir_baseline_answers.json"


def test_score_part_ir_prompts_lists_all_cases() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--prompts"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == len(CASES)
    case_ids = {line.split("\t", 1)[0] for line in lines}
    assert case_ids == {c.case_id for c in CASES}
    assert "blind_hole_start_face" in case_ids


def test_score_part_ir_baseline_answers_passes_all_cases() -> None:
    assert BASELINE_ANSWERS_PATH.exists(), f"Missing baseline answers at {BASELINE_ANSWERS_PATH}"
    answers = json.loads(BASELINE_ANSWERS_PATH.read_text(encoding="utf-8"))
    results = score_all(answers)
    assert set(results.keys()) == {c.case_id for c in CASES}
    failures = {k: v for k, v in results.items() if v}
    assert failures == {}

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(BASELINE_ANSWERS_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{len(CASES)}/{len(CASES)} passed" in proc.stdout
