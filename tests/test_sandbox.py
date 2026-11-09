"""The agent's tools: confined to the workspace, budgeted, and safe without a shell."""

import json
from unittest import mock

import pytest

from sweval import sandbox
from sweval.sandbox import check_allowlisted


def call(ws, tool, **args):
    return json.loads(ws.call(tool, args))


@pytest.mark.parametrize("path", ["../outside.txt", "freightkit/../../x", "/workspace/../../etc/passwd"])
def test_paths_cannot_leave_the_workspace(workspace, path):
    assert "outside the workspace" in call(workspace, "read_file", filepath=path)["error"]


def test_workspace_prefix_and_absolute_paths_map_inside(workspace):
    a = call(workspace, "read_file", filepath="/workspace/freightkit/units.py", start_line=3, end_line=3)
    assert a["content"] == "3: KG_PER_LB = 0.45359237"


@pytest.mark.parametrize("cmd,reason", [
    ("ls; rm -rf /", "shell operators"), ("curl http://x", "not allowed"),
    ("python -c 'print(1)'", "python -m pytest"), ("git checkout .", "read-only git"), ("sed -i s/a/b/ f.py", "sed -i")])
def test_allowlist_refuses_risky_commands(cmd, reason):
    assert reason in check_allowlisted(cmd)


def test_allowlist_permits_read_and_test_commands():
    for cmd in ("python -m pytest -q", "grep -rn KG freightkit", "git diff", "ls tests"):
        assert check_allowlisted(cmd) is None, cmd


def test_fallback_mode_runs_tests_without_a_shell(workspace):
    with mock.patch.object(sandbox, "BWRAP", False):
        out = call(workspace, "run_command", command="python -m pytest -q tests")
        assert out["exit_code"] == 1 and "FAILED tests/test_basics.py::test_units" in out["output"]
        assert "not allowed" in call(workspace, "run_command", command="rm -rf freightkit")["error"]
    assert (workspace.root / "freightkit/units.py").exists()


@pytest.mark.skipif(not sandbox.BWRAP, reason="bubblewrap not available on this machine")
def test_bwrap_mode_hides_the_host_blocks_network_and_keeps_writes_in_the_workspace(workspace):
    out = call(workspace, "run_command", command="ls /home; touch /etc/x; python -c 'import socket; "
                                                  "socket.create_connection((\"1.1.1.1\", 53), 2)'")
    assert "No such file" in out["output"] and "Read-only" in out["output"] and "Error" in out["output"]


def test_tool_budget_is_enforced_but_status_and_submit_are_free(workspace):
    for _ in range(5):
        call(workspace, "read_file", filepath="README.md", start_line=1, end_line=1)
    assert "budget" in call(workspace, "read_file", filepath="README.md")["error"]
    assert call(workspace, "get_status")["tool_calls_left"] == 0
    assert call(workspace, "submit_patch")["submitted"] and workspace.submitted


def test_edit_file_needs_exactly_one_match(workspace):
    assert "not found" in call(workspace, "edit_file", filepath="freightkit/units.py", old_string="nope",
                               new_string="x")["error"]
    assert "matches 2 places" in call(workspace, "edit_file", filepath="freightkit/units.py",
                                      old_string="KG_PER_LB\n", new_string="X\n")["error"]
    ok = call(workspace, "edit_file", filepath="freightkit/units.py", old_string="kg * KG_PER_LB",
              new_string="kg / KG_PER_LB")
    assert ok == {"replaced": 1} and "+    return kg / KG_PER_LB" in workspace.diff()


def test_read_file_numbers_lines_and_caps_the_range(workspace):
    (workspace.root / "long.txt").write_text("\n".join(f"line {i}" for i in range(1, 201)))
    out = call(workspace, "read_file", filepath="long.txt", start_line=10, end_line=200)
    assert out["lines"] == "10-89 of 200" and out["content"].startswith("10: line 10") and out["is_truncated"]


def test_new_files_appear_in_the_patch(workspace):
    call(workspace, "write_file", filepath="freightkit/extra.py", content="X = 1\n")
    assert "+++ b/freightkit/extra.py" in workspace.diff()


def test_unknown_tools_and_bad_arguments_return_errors_not_exceptions(workspace):
    assert "unknown tool" in call(workspace, "grep", pattern="x")["error"]
    assert "bad arguments" in call(workspace, "read_file", path="x")["error"]
    assert [e["ok"] for e in workspace.log] == [False, False]


def test_long_output_is_truncated():
    assert len(sandbox.cap("x" * 5000)) <= sandbox.OUTPUT_CAP and "truncated" in sandbox.cap("x" * 5000)
