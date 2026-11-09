# ADR 0005: A plain JSON tool protocol, the same locally and in the cloud

**Status:** accepted

**Context.** llama.cpp and vLLM each have their own tool-calling formats and parsers, and small models
follow them unevenly.

**Decision.** The model replies with one short sentence and one JSON object `{"tool": ..., "args": ...}`.
The parser takes the first object with a `tool` key and tolerates code fences and surrounding text.
Replies without a tool call get one reminder; three in a row end the run.

**Consequences.** The same protocol works with any chat model and both back ends, so local and cloud
numbers stay comparable. Native tool calling might do better and is listed as planned.
