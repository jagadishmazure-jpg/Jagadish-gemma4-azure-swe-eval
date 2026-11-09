"""Scoring: failure taxonomy, paired tests, the gate, and the committed results replay exactly."""

import json

import pytest
import run_eval

from sweval.evaluate import failure, paired, summarize
from sweval.metrics import mcnemar_exact, rate, wilson

V_OK = {"applied": True, "resolved": True, "regression_ok": True, "visible_suite_ok": True, "touched_tests": False}


def run(patch="x", stop="submitted", **kw):
    return {"id": "units-kg-to-lb", "patch": patch, "stop": stop, "trace": [], "model": "m", "invalid_replies": 0,
            "tool_calls": 1, "turns": 1, "prompt_tokens": 1, "completion_tokens": 1, "seconds": 1.0, **kw}


@pytest.mark.parametrize("r,v,reason", [
    (run(), V_OK, None),
    (run(patch="", stop="no_tool_call"), {**V_OK, "resolved": False}, "no_patch:stopped_replying_with_tools"),
    (run(patch="", stop="max_turns"), {**V_OK, "resolved": False}, "no_patch:out_of_turns"),
    (run(), {**V_OK, "applied": False, "resolved": False}, "patch_did_not_apply"),
    (run(), {**V_OK, "regression_ok": False}, "issue_test_passes_but_broke_other_behaviour"),
    (run(), {**V_OK, "resolved": False, "touched_tests": True}, "wrong_fix_and_edited_tests"),
    (run(), {**V_OK, "resolved": False}, "wrong_fix"),
])
def test_failure_taxonomy(r, v, reason):
    assert failure(r, v) == reason


def test_summary_counts_weak_grader_overcount_and_test_running():
    runs = [run(trace=[{"tool": "run_command", "args": {"command": "python -m pytest -q"}, "ok": True}]),
            run(trace=[{"tool": "grep", "args": {}, "ok": False}])]
    m = summarize("gemma4-e2b.workflow", runs, [V_OK, {**V_OK, "regression_ok": False}])
    assert m["resolved"]["k"] == 1 and m["issue_test_only"]["k"] == 2 and m["regressions"] == 1
    assert m["unknown_tool_calls"] == 1 and m["failed_tool_calls"] == 1 and m["ran_tests"]["k"] == 1


def test_paired_counts_discordant_tasks():
    p = paired({"a": True, "b": True, "c": False}, {"a": True, "b": False, "c": False, "d": True})
    assert (p["n"], p["both"], p["only_first"], p["only_second"]) == (3, 1, 1, 0)


def test_metric_helpers():
    assert wilson(0, 10)[0] == 0 and wilson(10, 10)[1] == 1
    assert mcnemar_exact(0, 0) == 1.0 and mcnemar_exact(0, 6) == pytest.approx(0.03125)
    assert rate(3, 4)["rate"] == 0.75


def test_gate_catches_a_broken_harness(metrics):
    broken = json.loads(json.dumps(metrics))
    broken["configs"]["noop"]["resolved"]["rate"] = 0.1
    assert any("empty patch" in b for b in run_eval.gate(broken))
    assert run_eval.gate(metrics) == []


def test_committed_results_replay_exactly(metrics):
    from sweval.evaluate import evaluate

    fresh = evaluate()
    assert run_eval.dump(fresh) == run_eval.dump(metrics)
    assert (run_eval.OUT / "report.md").read_text() == run_eval.report(fresh)
