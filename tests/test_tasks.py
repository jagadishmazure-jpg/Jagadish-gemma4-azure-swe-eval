"""The task suite: well-formed, deterministic split, and each bug is real and fixable."""

import re

import pytest

from sweval.repo import FIXTURE, reference_patch, verify
from sweval.tasks import TASKS, get, split


def test_suite_size_kinds_and_unique_ids():
    ids = [t["id"] for t in TASKS]
    assert len(ids) == 39 and len(set(ids)) == 39
    assert {t["kind"] for t in TASKS} == {"named", "symptom", "multi"}


def test_split_is_deterministic_and_mostly_test():
    s = [split(t["id"]) for t in TASKS]
    assert s == [split(t["id"]) for t in TASKS]
    assert s.count("dev") == 7 and s.count("test") == 32


def test_every_bug_edit_matches_exactly_once_in_the_clean_package():
    for t in TASKS:
        for rel, before, _after in t["edits"]:
            assert (FIXTURE / rel).read_text().count(before) == 1, t["id"]


def test_reference_patches_touch_only_library_code():
    for t in TASKS[:12]:
        files = re.findall(r"^\+\+\+ b/(\S+)", reference_patch(t), re.M)
        assert files and all(f.startswith("freightkit/") for f in files), t["id"]


def test_issue_text_never_contains_the_fixed_code():
    for t in TASKS:
        for _rel, before, _after in t["edits"]:
            line = max(before.strip().splitlines(), key=len).strip()
            assert len(line) < 12 or line not in t["issue"], t["id"]


def test_hidden_tests_only_import_the_package_and_stdlib():
    for t in TASKS:
        mods = set(re.findall(r"^(?:from|import) (\w+)", t["tests"], re.M))
        assert mods <= {"datetime", "decimal", "pytest", "freightkit"}, t["id"]


def test_unknown_task_raises():
    with pytest.raises(KeyError):
        get("no-such-task")


@pytest.mark.parametrize("tid", ["units-lb-to-kg", "dock-before-open", "rates-remote-fee-discounted"])
def test_bug_is_caught_and_reference_fix_passes(tid):
    t = get(tid)
    assert not verify(t, "")["resolved"]
    v = verify(t, reference_patch(t))
    assert v["resolved"] and v["regression_ok"] and v["visible_suite_ok"]
