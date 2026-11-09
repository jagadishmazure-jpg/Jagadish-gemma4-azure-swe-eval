# Interview points

Short, defensible answers backed by this repository's measured runs (synthetic tasks, 39 issues).

## What did you build?

A small but complete coding-agent evaluation: a fictional freight company's Python package, 39 planted
bugs with issue text and hidden tests, a sandboxed tool layer, an agent loop for any chat model, and a
verifier that re-applies every patch to a fresh checkout. Gemma 4 E2B (4-bit) ran it on an 8-core CPU.

## What does the agent loop actually add?

Measured, not assumed. With the same model and instructions, the loop resolved
43.6%<!-- m:configs/gemma4-e2b.workflow/resolved/rate --> and one shot with the whole source in view resolved
28.2%<!-- m:configs/gemma4-e2b.oneshot/resolved/rate --> (paired exact McNemar p =
0.146<!-- m:paired/agent_vs_oneshot/mcnemar_p -->). Running the tests was the strongest signal: tasks where the
agent ran them were resolved 57.1%<!-- m:configs/gemma4-e2b.workflow/resolved_when_ran_tests/rate --> of the time,
against 9.1%<!-- m:configs/gemma4-e2b.workflow/resolved_when_no_tests/rate --> without (an association, not a
controlled effect: harder tasks may also be the ones where it gave up early).

## How do you know a fix is real?

Three checks on a fresh checkout: the issue's hidden test, a hidden regression suite over the whole
package, and the visible tests, with any test edits reset first. The regression suite is there because
the model really did "fix" a conversion by changing a shared constant. An issue-test-only grader would
have reported 48.7%<!-- m:configs/gemma4-e2b.workflow/issue_test_only/rate --> instead of
43.6%<!-- m:configs/gemma4-e2b.workflow/resolved/rate -->. Reference patches must score 100% and empty patches 0%,
or CI fails.

## How did the small models fail?

Gemma 4 E2B: wrong fixes, submitting with no change, replies without a tool call, and calling a `grep`
tool that does not exist (21<!-- m:configs/gemma4-e2b.workflow/unknown_tool_calls --> times) instead of
`run_command`. Qwen2.5 1.5B resolved 0.0%<!-- m:configs/qwen2.5-1.5b.workflow/resolved/rate -->: it mostly ran
commands and then submitted without editing
({{configs/qwen2.5-1.5b.workflow/failures/no_patch:submitted_empty|int}} of 39).

## What about the prompt?

The workflow prompt (run tests, grep, read narrowly, smallest edit, re-test) against a one-line prompt
on the same loop: 43.6%<!-- m:configs/gemma4-e2b.workflow/resolved/rate --> against
20.5%<!-- m:configs/gemma4-e2b.basic/resolved/rate --> (p = 0.0352<!-- m:paired/workflow_vs_basic/mcnemar_p -->).

## How is it kept safe?

Safety lives in the tools, not the prompt: commands in bubblewrap with no network, no home directory and
read-only system directories; workspace-only writes; path checks; budgets; and no tool that can push,
merge or deploy. A test makes the model obey an injected instruction and shows the tools still hold.

## Why CPU and 4-bit?

To get real Gemma 4 numbers without a GPU, and because a private, cheap model is the realistic option
for many teams. The cost is speed (median 65.1<!-- m:configs/gemma4-e2b.workflow/cost/seconds_p50 --> s per task on a
shared machine) and probably some accuracy. The written Azure pipeline runs E4B on a T4 at $0.526 per
hour (dated 2026-11-09) with the same agent and verifier.

## What would you do next?

Mine tasks from real fix commits, add code-search tools (neighbours, similar code, call graph), try
native tool calling and larger Gemma 4 sizes on the GPU, and keep the same verifier and paired tests so
every change is a measured difference.
