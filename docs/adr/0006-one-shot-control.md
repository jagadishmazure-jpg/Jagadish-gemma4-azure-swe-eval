# ADR 0006: Measure what the agent loop adds with a one-shot control

**Status:** accepted

**Context.** "Agentic" only matters if running tests, reading code and iterating beat simply asking the
model for a fix.

**Decision.** Run the same model with the same instructions in one shot: the whole package source (it
fits in the context) and the issue in one prompt, and one reply containing edit calls, with no tool
results and no test feedback. Compare with the agent loop on the same tasks with an exact McNemar test.
A prompt-only variant (basic instructions, same loop) separates the effect of the workflow prompt.

**Consequences.** The benefit of the agent loop is a measured number with an interval, not a claim.
The one-shot control sees all the code at once, which a real large repository would not allow, so it is
a generous baseline.
