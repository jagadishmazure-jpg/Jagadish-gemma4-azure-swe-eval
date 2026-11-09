"""The agent loop with a scripted model: parsing, stop reasons, budgets and the one-shot control."""

import json

from conftest import FakeLLM

from sweval.agent import CONFIGS, LIMITS, parse_call, parse_calls, run_baseline, run_llm, run_oneshot, system_prompt
from sweval.repo import verify
from sweval.tasks import get

TASK = get("units-kg-to-lb")
FIX = json.dumps({"tool": "edit_file", "args": {"filepath": "freightkit/units.py", "old_string": "kg * KG_PER_LB",
                                                "new_string": "kg / KG_PER_LB"}})
SUBMIT = '{"tool": "submit_patch", "args": {}}'


def test_parse_call_handles_fences_extra_text_and_arguments_key():
    assert parse_call('Look.\n```json\n{"tool": "get_status", "args": {}}\n```') == ("get_status", {})
    assert parse_call('{"x": 1} then {"tool": "read_file", "arguments": {"filepath": "a"}}') == (
        "read_file", {"filepath": "a"})
    assert parse_call('{"tool": "run_command", "args": "ls"}') == ("run_command", {})


def test_parse_call_returns_none_without_a_tool_object():
    for text in ("I will fix it.", '{"tool": 3}', '{"tool": "read_file", "args": {', ""):
        assert parse_call(text) is None


def test_parse_calls_finds_every_object_in_order():
    assert [c[0] for c in parse_calls(f"a {FIX} b {SUBMIT} {{bad")] == ["edit_file", "submit_patch"]


def test_a_scripted_fix_is_submitted_and_verified():
    r = run_llm(TASK, FakeLLM(["Fix the division.\n" + FIX, SUBMIT]), "gemma4-e2b.workflow")
    assert (r["stop"], r["turns"], r["tool_calls"]) == ("submitted", 2, 1)
    v = verify(TASK, r["patch"])
    assert v["resolved"] and v["regression_ok"]


def test_three_replies_without_a_tool_call_stop_the_run():
    r = run_llm(TASK, FakeLLM(["hmm"] * 5), "gemma4-e2b.workflow")
    assert (r["stop"], r["turns"], r["invalid_replies"], r["patch"]) == ("no_tool_call", 3, 3, "")


def test_turn_limit_and_budget_message():
    llm = FakeLLM(['{"tool": "read_file", "args": {"filepath": "README.md"}}'] * 20)
    r = run_llm(TASK, llm, "gemma4-e2b.workflow")
    assert r["stop"] == "max_turns" and r["turns"] == LIMITS["max_turns"]
    assert r["tool_calls"] == LIMITS["max_tool_calls"]
    assert any("Tool budget used up" in m["content"] for m in llm.seen[-1])


def test_context_guard_stops_before_overflowing():
    r = run_llm(TASK, FakeLLM([], tokens_per_byte=10), "gemma4-e2b.workflow")
    assert r["stop"] == "context_full" and r["completion_tokens"] == 0


def test_prompt_lists_files_issue_and_budget_but_never_the_hidden_test():
    llm = FakeLLM(["no"] * 3)
    run_llm(TASK, llm, "gemma4-e2b.workflow")
    first = llm.seen[0][1]["content"]
    assert TASK["issue"] in first and "freightkit/units.py" in first and "Budget: 12" in first
    assert "test_issue" not in first and "regression" not in first


def test_oneshot_applies_every_edit_in_one_reply():
    r = run_oneshot(TASK, FakeLLM(["Here.\n" + FIX]), "gemma4-e2b.oneshot")
    assert (r["stop"], r["turns"], r["tool_calls"]) == ("submitted", 1, 1) and verify(TASK, r["patch"])["resolved"]
    assert run_oneshot(TASK, FakeLLM(["No idea."]), "gemma4-e2b.oneshot")["stop"] == "no_tool_call"


def test_configs_differ_only_in_what_they_claim():
    assert {c["model"] for c in CONFIGS.values()} == {"gemma-4-e2b", "gemma-4-e4b", "qwen2.5-1.5b"}
    assert "How to work" in system_prompt("system.md") and "How to work" not in system_prompt("basic.md")


def test_baselines_bracket_the_harness():
    assert run_baseline(TASK, "noop")["patch"] == ""
    assert verify(TASK, run_baseline(TASK, "oracle")["patch"])["resolved"]


def test_an_injected_instruction_cannot_reach_the_network_or_leave_the_workspace():
    """Worst case: the model obeys text planted in the repository. The tools, not the model, hold the line."""
    obey = [json.dumps({"tool": "run_command", "args": {"command": "curl -s http://198.51.100.7/x"}}),
            json.dumps({"tool": "write_file", "args": {"filepath": "../../planted.txt", "content": "x"}}),
            json.dumps({"tool": "run_command", "args": {"command": "python -m pytest -q --co -p no:cacheprovider"}}),
            SUBMIT]
    llm = FakeLLM(obey)
    r = run_llm(TASK, llm, "gemma4-e2b.workflow")
    curl = json.loads(llm.seen[1][-1]["content"].removeprefix("Result: "))
    assert "not allowed" in curl.get("error", "") or curl["exit_code"] != 0  # allowlist, or no network in bwrap
    assert "outside the workspace" in llm.seen[2][-1]["content"]
    assert r["stop"] == "submitted" and r["patch"] == ""
