"""Score agent trajectories by re-running the hidden tests on every submitted patch.

Nothing here trusts the agent's own account: each patch is applied to a fresh buggy checkout, the
test folder is reset, the hidden test for the issue is added, and pytest decides. A task counts as
resolved when the issue's hidden test passes AND the hidden whole-package regression suite passes AND the
visible suite still passes. "issue_test_only" is what a weaker grader (issue test alone) would report.
"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sweval.agent import CONFIGS, LIMITS
from sweval.metrics import mcnemar_exact, percentile, rate
from sweval.repo import verify
from sweval.tasks import TASKS, get, split

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs"
KNOWN_TOOLS = {"run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"}
ORDER = ["oracle", "noop", "gemma4-e2b.workflow", "gemma4-e2b.basic", "gemma4-e2b.oneshot",
         "qwen2.5-1.5b.workflow", "gemma4-e4b.workflow"]
PAIRS = {"workflow_vs_basic": ("gemma4-e2b.workflow", "gemma4-e2b.basic"),
         "agent_vs_oneshot": ("gemma4-e2b.workflow", "gemma4-e2b.oneshot"),
         "gemma_vs_qwen": ("gemma4-e2b.workflow", "qwen2.5-1.5b.workflow")}


def load_runs(runs_dir: Path = RUNS) -> dict[str, list[dict]]:
    out = {}
    for p in sorted(runs_dir.glob("*.jsonl")):
        rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        out[p.stem] = sorted(rows, key=lambda r: r["id"])
    return out


def ran_tests(run: dict) -> bool:
    return any(t.get("tool") == "run_command" and "pytest" in t.get("args", {}).get("command", "")
               for t in run["trace"])


def solved(v: dict) -> bool:
    return v["resolved"] and v["regression_ok"] and v["visible_suite_ok"]


def failure(run: dict, v: dict) -> str | None:
    """One primary reason per unresolved task, checked in this order."""
    if solved(v):
        return None
    if not run["patch"].strip():
        return {"no_tool_call": "no_patch:stopped_replying_with_tools", "max_turns": "no_patch:out_of_turns",
                "context_full": "no_patch:context_full"}.get(run["stop"], "no_patch:submitted_empty")
    if not v["applied"]:
        return "patch_did_not_apply"
    if v["resolved"]:
        return "issue_test_passes_but_broke_other_behaviour"
    if v["touched_tests"]:
        return "wrong_fix_and_edited_tests"
    return "wrong_fix"


def summarize(name: str, runs: list[dict], verdicts: list[dict]) -> dict:
    ok = [solved(v) for v in verdicts]
    by_kind, by_split = {}, {}
    for kind in ("named", "symptom", "multi"):
        idx = [i for i, r in enumerate(runs) if get(r["id"])["kind"] == kind]
        if idx:
            by_kind[kind] = rate(sum(ok[i] for i in idx), len(idx))
    for s in ("dev", "test"):
        idx = [i for i, r in enumerate(runs) if split(r["id"]) == s]
        if idx:
            by_split[s] = rate(sum(ok[i] for i in idx), len(idx))
    tools = Counter(t["tool"] for r in runs for t in r["trace"] if t.get("tool"))
    tested = [i for i, r in enumerate(runs) if ran_tests(r)]
    untested = [i for i in range(len(runs)) if i not in tested]
    n = len(runs)
    m = {"n": n, "resolved": rate(sum(ok), n), "by_kind": by_kind, "by_split": by_split,
         "patch_nonempty": rate(sum(bool(r["patch"].strip()) for r in runs), n),
         "patch_applied": rate(sum(v["applied"] and bool(r["patch"].strip()) for r, v in zip(runs, verdicts)), n),
         "issue_test_only": rate(sum(v["resolved"] for v in verdicts), n),
         "regressions": sum(v["resolved"] and not (v["regression_ok"] and v["visible_suite_ok"]) for v in verdicts),
         "touched_tests": sum(v["touched_tests"] for v in verdicts),
         "stop": dict(sorted(Counter(r["stop"] for r in runs).items())),
         "failures": dict(sorted(Counter(f for r, v in zip(runs, verdicts) if (f := failure(r, v))).items())),
         "tool_use": dict(sorted(tools.items())),
         "unknown_tool_calls": sum(c for t, c in tools.items() if t not in KNOWN_TOOLS),
         "failed_tool_calls": sum(1 for r in runs for t in r["trace"] if t.get("tool") and not t.get("ok", True)),
         "invalid_replies": sum(r["invalid_replies"] for r in runs),
         "ran_tests": rate(len(tested), n)}
    if tested:
        m["resolved_when_ran_tests"] = rate(sum(ok[i] for i in tested), len(tested))
    if untested:
        m["resolved_when_no_tests"] = rate(sum(ok[i] for i in untested), len(untested))
    if any(r["seconds"] for r in runs):
        m["cost"] = {"tool_calls_p50": percentile([r["tool_calls"] for r in runs], 50),
                     "turns_p50": percentile([r["turns"] for r in runs], 50),
                     "prompt_tokens_p50": percentile([r["prompt_tokens"] for r in runs], 50),
                     "completion_tokens_p50": percentile([r["completion_tokens"] for r in runs], 50),
                     "seconds_p50": round(percentile([r["seconds"] for r in runs], 50), 1),
                     "seconds_p90": round(percentile([r["seconds"] for r in runs], 90), 1),
                     "cpu_minutes_total": round(sum(r["seconds"] for r in runs) / 60, 1)}
        secs = [r["seconds"] for r, o in zip(runs, ok) if o]
        if secs:
            m["cost"]["seconds_p50_resolved"] = round(percentile(secs, 50), 1)
    m["model"] = runs[0]["model"] if runs else "-"
    m["mode"] = CONFIGS.get(name, {}).get("mode", "agent" if name in CONFIGS else "baseline")
    return m


def paired(a: dict[str, bool], b: dict[str, bool]) -> dict:
    ids = sorted(set(a) & set(b))
    only_a = sum(a[i] and not b[i] for i in ids)
    only_b = sum(b[i] and not a[i] for i in ids)
    return {"n": len(ids), "both": sum(a[i] and b[i] for i in ids), "only_first": only_a, "only_second": only_b,
            "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4)}


def evaluate(runs_dir: Path = RUNS, workers: int = 4) -> dict:
    runs = load_runs(runs_dir)
    jobs = [(name, r) for name, rows in runs.items() for r in rows]
    with ThreadPoolExecutor(workers) as ex:
        verdicts = list(ex.map(lambda j: verify(get(j[1]["id"]), j[1]["patch"]), jobs))
    by_cfg: dict[str, list] = {}
    for (name, r), v in zip(jobs, verdicts):
        by_cfg.setdefault(name, []).append((r, v))
    configs, done = {}, {}
    for name in sorted(by_cfg, key=lambda c: ORDER.index(c) if c in ORDER else len(ORDER)):
        rows = by_cfg[name]
        configs[name] = summarize(name, [r for r, _ in rows], [v for _, v in rows])
        done[name] = {r["id"]: solved(v) for r, v in rows}
    noop = [v for (name, _), v in zip(jobs, verdicts) if name == "noop"]
    kinds = Counter(t["kind"] for t in TASKS)
    splits = Counter(split(t["id"]) for t in TASKS)
    return {"suite": {"tasks": len(TASKS), "by_kind": dict(sorted(kinds.items())), "by_split": dict(sorted(splits.items())),
                      "files": len(list((ROOT / "fixtures/freightkit/freightkit").glob("*.py"))),
                      "bugs_caught_by_visible_tests": sum(not v["visible_suite_ok"] for v in noop),
                      "bugs_caught_by_regression_suite": sum(not v["regression_ok"] for v in noop)},
            "limits": LIMITS,
            "configs": configs,
            "paired": {k: paired(done[a], done[b]) for k, (a, b) in PAIRS.items() if a in done and b in done},
            "per_task": {t["id"]: {c: s[t["id"]] for c, s in done.items() if t["id"] in s} for t in TASKS}}
