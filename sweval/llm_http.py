"""Talk to an OpenAI-compatible chat endpoint (for example vLLM serving Gemma 4 on a GPU node) with the
same two methods the agent uses from llama.cpp: create_chat_completion and tokenize.

Used by the Azure ML pipeline (infra/aml/pipeline.yml); locally the agent runs on llama.cpp instead.
Standard library only, so the cloud job needs no extra client package.
"""

from __future__ import annotations

import json
import urllib.request


class HttpLLM:
    def __init__(self, base_url: str, model: str, timeout: int = 300):
        if not base_url.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise ValueError("endpoint must be local or HTTPS")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def create_chat_completion(self, messages: list[dict], temperature: float = 0, max_tokens: int = 256,
                               seed: int = 0) -> dict:
        body = json.dumps({"model": self.model, "messages": messages, "temperature": temperature,
                           "max_tokens": max_tokens, "seed": seed}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        return {"choices": [{"message": {"content": data["choices"][0]["message"].get("content") or ""}}],
                "usage": {"prompt_tokens": data["usage"]["prompt_tokens"],
                          "completion_tokens": data["usage"]["completion_tokens"]}}

    def tokenize(self, text: bytes) -> list[int]:
        """Rough count (about 3.5 bytes per token) used only for the context-window guard."""
        return [0] * (len(text) * 2 // 7 + 1)
