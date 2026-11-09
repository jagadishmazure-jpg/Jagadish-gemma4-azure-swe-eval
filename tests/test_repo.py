"""Verification is strict: fresh checkout, tests reset, issue test + hidden regression suite."""

import pytest

from sweval.repo import apply_edits, git, materialize, reference_patch, verify
from sweval.tasks import get


def test_materialize_commits_a_clean_buggy_tree(tmp_path):
    d = materialize(get("units-kg-to-lb"), tmp_path / "r")
    assert git(d, "status", "--porcelain").stdout == ""
    assert "kg * KG_PER_LB" in (d / "freightkit/units.py").read_text()


def test_apply_edits_requires_exactly_one_match(tmp_path):
    (tmp_path / "f.py").write_text("a = 1\na = 1\n")
    with pytest.raises(ValueError):
        apply_edits(tmp_path, [("f.py", "a = 1", "a = 2")])
    with pytest.raises(ValueError):
        apply_edits(tmp_path, [("f.py", "b = 1", "b = 2")])


def test_empty_patch_is_unresolved_and_garbage_does_not_apply():
    t = get("units-kg-to-lb")
    assert verify(t, "")["resolved"] is False
    v = verify(t, "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-nope\n+yes\n")
    assert v == {**v, "applied": False, "resolved": False}


def test_constant_hack_passes_the_issue_test_but_fails_the_regression_suite(tmp_path):
    """The shortcut a small model really took: change the shared constant instead of the formula."""
    t = get("units-kg-to-lb")
    d = materialize(t, tmp_path / "r")
    f = d / "freightkit/units.py"
    f.write_text(f.read_text().replace("KG_PER_LB = 0.45359237", "KG_PER_LB = 2.2046226"))
    v = verify(t, git(d, "diff", "HEAD").stdout)
    assert v["applied"] and v["resolved"] and not v["regression_ok"]


def test_editing_tests_is_detected_and_undone(tmp_path):
    t = get("units-kg-to-lb")
    d = materialize(t, tmp_path / "r")
    f = d / "tests/test_basics.py"
    f.write_text(f.read_text().replace("assert round(units.kg_to_lb(1), 3) == 2.205", "assert True"))
    v = verify(t, git(d, "diff", "HEAD").stdout)
    assert v["touched_tests"] and v["applied"] and not v["resolved"] and not v["visible_suite_ok"]


def test_reference_patch_is_a_git_diff_of_the_fix():
    p = reference_patch(get("units-kg-to-lb"))
    assert p.startswith("diff --git a/freightkit/units.py") and "+    return kg / KG_PER_LB" in p
