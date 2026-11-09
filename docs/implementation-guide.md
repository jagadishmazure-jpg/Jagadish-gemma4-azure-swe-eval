# Implementation guide: evaluating a coding agent on your own code base

This guide is for a team that wants to know whether a small open model can fix real issues in its own
repositories, and what the agent loop adds, before buying GPU time or wiring an agent into its workflow.

## 1. Build a task suite from your own code

1. Pick a package with a fast test suite (seconds, not minutes).
2. Write tasks the way `sweval/tasks.py` does: an issue in plain words, a planted edit (`correct ->
   buggy`, matching exactly once), and a hidden test. Mix three kinds: issues that name the function,
   issues that only describe the symptom, and changes that touch more than one place.
3. Better still, mine closed issues and their fixing commits: the parent commit is the buggy state, the
   fix's diff is the reference, and the tests added in the fix are the hidden test.
4. Run `python scripts/validate_tasks.py`. Every task must fail before and pass after.

## 2. Add a hidden regression suite

The issue's test alone over-counts. Write behaviour tests for the whole package (or reuse your full
suite, minus the tests changed by the fix) and run them on every patch, as `sweval/regression.py` does.
Report both numbers; the gap shows how often the agent "fixes" an issue by breaking something else.

## 3. Lock down the tools first

Keep `sweval/sandbox.py`'s rules when you adapt it:

- paths resolve inside the workspace or the call fails;
- commands run without network and without the host's home directory or other repositories;
- budgets on turns, tool calls, output size and time;
- no tool that pushes, merges or deploys. The agent hands back a patch; people review it.

Write the prompt-injection test before you trust any model with the tools.

## 4. Measure, with controls

- `oracle` (reference patches) must score 100% and `noop` (empty patch) 0%, or the harness is broken.
- A one-shot control with the same model shows what the loop adds.
- Change one thing at a time (prompt, model, budget) and compare on the same tasks with a paired test
  (exact McNemar), not two separate percentages.
- Split tasks into dev and test, and only look at dev while you tune the prompt.

```bash
python scripts/run_agent.py --config gemma4-e2b.workflow --split dev   # iterate on the prompt
nohup python scripts/run_agent.py --config gemma4-e2b.workflow > run.log 2>&1 &   # full run, detached
python scripts/run_eval.py
```

## 5. Replay in CI

Commit trajectories, pin them with `scripts/manifest.py`, and let CI recompute every verdict with
`scripts/run_eval.py --check`. Set the gate floors once from the measured run.

## 6. Move to a GPU when the numbers justify it

`infra/` provisions an Azure ML workspace (Microsoft Foundry hub type) and a GPU cluster that scales
to zero; `infra/aml/pipeline.yml` serves a larger Gemma 4 model with vLLM on the node and runs the same
agent and verifier through `--endpoint`. Read `docs/deployment.md` for the cost and the approval steps.

## 7. Package the agent declaratively

`agent_pack/` holds the agent as configuration only: `agent.yaml` (ADK Agent Config format) pulls in
the measured prompt and sampling settings, with a skill file and per-task budgets. `scripts/pack.py`
validates it (allowed file types, no symlinks or paths that leave the pack, includes resolve, known
tools, one model, adapter rank limit) and builds a deterministic zip. Keep the pack's prompt the same
file the evaluation used, so what you ship is what you measured.
