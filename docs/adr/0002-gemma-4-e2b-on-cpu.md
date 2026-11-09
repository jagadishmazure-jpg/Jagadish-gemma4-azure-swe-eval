# ADR 0002: Gemma 4 E2B, 4-bit, on CPU with llama.cpp

**Status:** accepted

**Context.** The question is how far a small open model gets as a coding agent, and what the agent loop
adds. There is no GPU on the build machine.

**Decision.** Use the smallest Gemma 4 model, E2B, from the official quantization-aware Q4_0 GGUF
release, through llama-cpp-python on 8 CPU threads with an 8,192-token context. It runs at about 16
tokens per second for generation, and the prompt prefix cache keeps later turns fast. Qwen2.5 1.5B
Instruct (Q4_K_M) is the non-Gemma comparison. Gemma 4 E4B and larger run only in the written cloud
pipeline.

**Consequences.** Real Gemma 4 numbers without a GPU. Results are for 4-bit weights and greedy decoding;
the 16-bit model and larger sizes may do better.
