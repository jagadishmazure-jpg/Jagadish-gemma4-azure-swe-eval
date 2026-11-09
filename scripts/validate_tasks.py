"""Check every task: the bug applies once, the issue's hidden test FAILS on the buggy repo and PASSES with
the reference patch, and the hidden regression suite and the visible tests pass after the reference patch.
Also reports how many planted bugs the visible tests and the regression suite would catch on their own.
    python scripts/validate_tasks.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sweval.repo import reference_patch, verify  # noqa: E402
from sweval.tasks import TASKS  # noqa: E402

CAUGHT = {"visible": 0, "regression": 0}


def check(task: dict) -> list[str]:
    bad = []
    before = verify(task, "")
    if before["resolved"]:
        bad.append("hidden tests already pass on the buggy repo")
    CAUGHT["visible"] += not before["visible_suite_ok"]
    CAUGHT["regression"] += not before["regression_ok"]
    after = verify(task, reference_patch(task))
    if not after["resolved"]:
        bad.append("reference patch does not resolve: " + after["output"])
    if not after["visible_suite_ok"]:
        bad.append("visible tests fail after the reference patch")
    if not after["regression_ok"]:
        bad.append("regression suite fails after the reference patch")
    return bad


def main() -> int:
    failures = 0
    for t in TASKS:
        problems = check(t)
        failures += bool(problems)
        print(("FAIL " if problems else "ok   ") + t["id"] + ("" if not problems else ": " + "; ".join(problems)))
    print(f"{len(TASKS) - failures}/{len(TASKS)} tasks valid")
    print(f"bugs caught without the issue test: visible tests {CAUGHT['visible']}/{len(TASKS)}, "
          f"regression suite {CAUGHT['regression']}/{len(TASKS)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
