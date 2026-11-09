# ADR 0004: Safety lives in the tools, not the prompt

**Status:** accepted

**Context.** A small model will sometimes follow instructions found in files it reads, call tools that
do not exist, or try shell tricks.

**Decision.** Six tools only, none of which push, merge or deploy. Paths resolve inside the workspace.
Commands run in bubblewrap (read-only system directories, no network, no home directory, the workspace
the only writable place), or, without bubblewrap, from an allowlist without a shell. Budgets on turns,
tool calls, output size and time.

**Consequences.** A prompt-injection test passes even when the model obeys the injected text. The
agent cannot install packages or fetch anything, which is the point.
