# ADR 0003: Score with the issue's test AND a hidden regression suite

**Status:** accepted

**Context.** In an early trajectory the model "fixed" a wrong conversion by changing the shared
constant instead of the formula. The issue's own test passed, the visible tests passed, and another
function silently broke.

**Decision.** Every patch is also run against a hidden 12-test behaviour suite for the whole package
(PASS_TO_PASS style). A task is resolved only when the issue test, the regression suite and the visible
tests all pass. The report also shows what an issue-test-only grader would have said.

**Consequences.** Lower but honest numbers, and the gap between the two graders is itself a measured
result.
