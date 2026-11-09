# Data card: the Tallowmere Freight issue suite

**Synthetic.** Tallowmere Freight is a fictional road-freight company. Its Python package
`freightkit` (seven modules: units, text, rates, manifest, dock, tracking, and the package file) was
written for this repository. No real code, issues, people or companies are included.

## What a task is

Each of the 39 tasks plants one bug (or a small multi-file change) in the clean package and gives:

- **issue text** written the way a user or colleague would report it. 13 name the function
  (`named`), 23 only describe the symptom (`symptom`), and 3 need edits in more than one place (`multi`).
- **a hidden test** for that issue (the FAIL_TO_PASS test), which fails on the buggy code and passes
  with the reference fix.
- **the reference fix**, the exact reverse of the planted edit.

Every task is checked by `scripts/validate_tasks.py` in CI: the edit matches once, the hidden test
fails before and passes after, and the hidden regression suite and the visible tests pass after.

## The hidden regression suite

`sweval/regression.py` holds 12 behaviour tests over the whole package (round trips, edge cases, error
handling), written against the clean package. The agent never sees them. They play the role of
PASS_TO_PASS tests: a patch that fixes the issue by breaking something else does not count. The
visible tests (6, in the package's own `tests/`) catch 8<!-- m:suite/bugs_caught_by_visible_tests --> of the 39
planted bugs; the regression suite catches 38<!-- m:suite/bugs_caught_by_regression_suite -->.

## Split

A task is `dev` when the SHA-256 of its id is divisible by 4 (7 tasks), otherwise `test` (32). Only
dev tasks were looked at while writing the agent prompt. Results are reported for both.

## Measured trajectories

`data/runs/<config>.jsonl` holds one line per task per configuration: stop reason, turns, tool calls,
invalid replies, tokens, seconds, the patch, and the trace of tool calls (arguments cut to 120
characters). Model replies and patches pass through a brand scrubber (real names become fixed
fictional names) before anything is stored or scored, and the brand check runs over every file,
data included. A SHA-256 manifest (`data/manifest.json`) pins every file.

## Limits

- 39 small tasks in one small code base. Real repositories are larger, with more files to search and
  longer tests. Treat the results as a regression check for this setup, not a benchmark score.
- All bugs are single-concept and planted by hand, so they are easier to localise than real bugs.
- Times were measured on a shared 8-core machine with other jobs running; they show relative cost.
