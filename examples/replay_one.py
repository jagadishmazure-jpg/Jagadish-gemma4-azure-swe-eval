"""Replay one measured trajectory: the issue, the agent's tool calls, its patch, and a fresh verdict.

    python examples/replay_one.py [task-id] [config]

The verdict is recomputed now (patch applied to a fresh buggy checkout, the issue's hidden test and the
hidden regression suite added, pytest run),
so this shows exactly how the evaluation scores the agent. No model weights are needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sweval.repo import verify  # noqa: E402
from sweval.tasks import get  # noqa: E402


def main(task_id: str = "rates-remote-fee-discounted", config: str = "gemma4-e2b.workflow") -> int:
    rows = [json.loads(line) for line in (ROOT / "data/runs" / f"{config}.jsonl").read_text().splitlines()]
    run = next(r for r in rows if r["id"] == task_id)
    task = get(task_id)
    print(f"Issue ({task['kind']}): {task['issue']}\n")
    print(f"Agent {config}: stop={run['stop']}, turns={run['turns']}, tool calls={run['tool_calls']}")
    for t in run["trace"]:
        if t.get("tool"):
            first = next(iter(t["args"].values()), "")
            print(f"  turn {t['turn']:2d}  {t['tool']:<12s} {first[:60]!r}  ok={t['ok']}")
        else:
            print(f"  turn {t['turn']:2d}  (reply without a tool call)")
    print("\nPatch:")
    print("\n".join(line for line in run["patch"].splitlines()
                    if not line.startswith(("diff ", "index ", "--- ", "+++ "))))
    v = verify(task, run["patch"])
    print(f"\nVerdict: applied={v['applied']} issue_test_passed={v['resolved']} "
          f"regression_suite_passed={v['regression_ok']} visible_suite_ok={v['visible_suite_ok']} "
          f"touched_tests={v['touched_tests']}")
    print("Resolved:", v["resolved"] and v["regression_ok"] and v["visible_suite_ok"])
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
