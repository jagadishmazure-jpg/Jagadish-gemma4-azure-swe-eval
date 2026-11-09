"""Build a task's repository, apply a patch, and run the hidden tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "freightkit"
HIDDEN = "tests/test_issue.py"
REGRESSION = "tests/test_regression_hidden.py"
GIT_ENV = {"GIT_AUTHOR_NAME": "sweval", "GIT_AUTHOR_EMAIL": "sweval@example.invalid",
           "GIT_COMMITTER_NAME": "sweval", "GIT_COMMITTER_EMAIL": "sweval@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def git(cwd: Path, *args: str, input: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(["git", *args], cwd=cwd, input=input, capture_output=True, text=True, env=env)


def apply_edits(root: Path, edits: list[tuple[str, str, str]]) -> None:
    for rel, before, after in edits:
        p = root / rel
        src = p.read_text()
        if src.count(before) != 1:
            raise ValueError(f"{rel}: expected exactly one match for {before[:40]!r}, found {src.count(before)}")
        p.write_text(src.replace(before, after))


def materialize(task: dict, dest: Path, buggy: bool = True) -> Path:
    """Copy the fixture to dest, plant the bug, and commit (a clean git baseline)."""
    shutil.copytree(FIXTURE, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if buggy:
        apply_edits(dest, task["edits"])
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "baseline")
    return dest


def reference_patch(task: dict) -> str:
    """The fix as a git diff (clean minus buggy), the patch a perfect agent would submit."""
    with tempfile.TemporaryDirectory() as tmp:
        d = materialize(task, Path(tmp) / "repo")
        for rel, before, after in task["edits"]:
            p = d / rel
            p.write_text(p.read_text().replace(after, before, 1) if after else p.read_text())
        if any(not after for _, _, after in task["edits"]):  # deletions: rebuild from the clean fixture
            for rel, _, _ in task["edits"]:
                shutil.copy(FIXTURE / rel, d / rel)
        return git(d, "diff", "HEAD").stdout


def run_pytest(cwd: Path, *targets: str, timeout: int = 120) -> tuple[bool, str]:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
           "PYTHONPATH": str(cwd)}
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets], cwd=cwd,
                           capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


def verify(task: dict, patch: str) -> dict:
    """Fresh buggy checkout + patch; test files reset to the baseline; hidden tests added and run.

    hidden_ok: the issue's own test passes (FAIL_TO_PASS). regression_ok: the hidden whole-package suite
    passes (PASS_TO_PASS). visible_suite_ok: the tests the agent could see still pass.
    """
    from sweval.regression import SUITE

    with tempfile.TemporaryDirectory() as tmp:
        d = materialize(task, Path(tmp) / "repo")
        applied = True
        if patch.strip():
            r = git(d, "apply", "--whitespace=nowarn", "-", input=patch if patch.endswith("\n") else patch + "\n")
            applied = r.returncode == 0
        touched_tests = any(line.startswith(("+++ b/tests/", "--- a/tests/")) for line in patch.splitlines())
        git(d, "checkout", "HEAD", "--", "tests")
        git(d, "clean", "-fdq", "tests")
        (d / HIDDEN).write_text(task["tests"])
        (d / REGRESSION).write_text(SUITE)
        if not applied:
            return {"applied": False, "resolved": False, "regression_ok": False, "visible_suite_ok": False,
                    "touched_tests": touched_tests, "output": "patch did not apply"}
        hidden_ok, out = run_pytest(d, HIDDEN)
        regression_ok, _ = run_pytest(d, REGRESSION)
        visible_ok, _ = run_pytest(d, "tests", "--ignore", HIDDEN, "--ignore", REGRESSION)
    return {"applied": True, "resolved": hidden_ok, "regression_ok": regression_ok, "visible_suite_ok": visible_ok,
            "touched_tests": touched_tests, "output": out[-600:]}
