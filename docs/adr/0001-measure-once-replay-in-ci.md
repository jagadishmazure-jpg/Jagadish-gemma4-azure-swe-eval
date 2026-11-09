# ADR 0001: Measure once on CPU, replay the scoring in CI

**Status:** accepted

**Context.** Running a 2B-parameter model through 39 tasks and four configurations takes hours on CPU.
CI cannot do that on every push, and should not need model weights.

**Decision.** Agent runs are measured once with `scripts/run_agent.py` and committed as trajectories.
CI does not trust the recorded verdicts: `scripts/run_eval.py --check` re-applies every committed patch
to a fresh checkout, runs the hidden tests, recomputes every metric, and fails if anything differs from
`results/`. A hash manifest pins the trajectories.

**Consequences.** Scoring is fully reproducible and cheap. The agent's behaviour itself is not
re-measured in CI; re-measuring needs `scripts/fetch_models.sh` and a few hours of CPU.
