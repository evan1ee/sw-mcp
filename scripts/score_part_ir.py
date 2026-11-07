"""Score an agent's answers to the IR authoring prompts.

Usage: ``uv run python scripts/score_part_ir.py --prompts`` lists the prompts;
``uv run python scripts/score_part_ir.py answers.json`` scores a file that maps each case id to
a graph, or to null when the agent refused. The pass rate samples one agent's behaviour; it is
not a reliability claim.
"""

import json
import sys
from pathlib import Path

from cad_application.authoring_eval.cases import CASES
from cad_application.authoring_eval.checker import score_all
from cad_application.authoring_eval.references import REFERENCE_ANSWERS

USAGE = "usage: score_part_ir.py (--prompts | --baseline | answers.json)\n"


def main(argv: list[str]) -> int:
    if argv == ["--prompts"]:
        for case in CASES:
            sys.stdout.write(f"{case.case_id}\t{case.prompt}\n")
        return 0
    if len(argv) != 1:
        sys.stderr.write(USAGE)
        return 2
    if argv == ["--baseline"]:
        answers = REFERENCE_ANSWERS
    else:
        answers = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    results = score_all(answers)
    for case_id, problems in results.items():
        sys.stdout.write(f"{'PASS' if not problems else 'FAIL'} {case_id}\n")
        for problem in problems:
            sys.stdout.write(f"     {problem}\n")
    passed = sum(1 for problems in results.values() if not problems)
    sys.stdout.write(f"{passed}/{len(results)} passed\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
