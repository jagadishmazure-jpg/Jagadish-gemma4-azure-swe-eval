"""The cloud client speaks the OpenAI-compatible chat API that vLLM serves (tested on a local fake)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from sweval.llm_http import HttpLLM


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.last = body
        out = json.dumps({"choices": [{"message": {"content": "ok"}}],
                          "usage": {"prompt_tokens": 7, "completion_tokens": 1}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def test_chat_completion_round_trip_on_a_local_server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        llm = HttpLLM(f"http://127.0.0.1:{srv.server_port}/v1", "google/gemma-4-E4B-it")
        r = llm.create_chat_completion([{"role": "user", "content": "hi"}], max_tokens=9)
        assert r["choices"][0]["message"]["content"] == "ok" and r["usage"]["prompt_tokens"] == 7
        assert Handler.last["model"] == "google/gemma-4-E4B-it" and Handler.last["max_tokens"] == 9
        assert Handler.last["temperature"] == 0
    finally:
        srv.shutdown()


def test_only_local_or_https_endpoints_and_a_conservative_token_estimate():
    with pytest.raises(ValueError):
        HttpLLM("http://10.0.0.5:8000/v1", "m")
    assert len(HttpLLM("https://example.invalid/v1", "m").tokenize(b"x" * 700)) == 201
