"""A tool-using coding agent driven by a small open model (llama.cpp on CPU), and two baselines.

Protocol: each model turn must contain one tool call as JSON, {"tool": "...", "args": {...}}, optionally
inside a ```json block. The harness runs the tool and returns the result as the next user message.
The episode ends on submit_patch, when the tool or turn budget runs out, when the context window would
overflow, or after three turns in a row without a valid tool call. The workspace diff is graded either way.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from pathlib import Path

from .repo import materialize, reference_patch
from .sandbox import Workspace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_brands import scrub  # noqa: E402

PROMPTS = ROOT / "agent_pack" / "prompts"
TOOLS_DOC = """Tools (call exactly one per turn):
- run_command(command): run a shell command in the repository root (60 s limit, output capped)
- read_file(filepath, start_line, end_line): read lines of a file (80 lines max per call)
- edit_file(filepath, old_string, new_string): replace old_string (must match exactly once)
- write_file(filepath, content): create or overwrite a file
- get_status(): budget left and files changed
- submit_patch(): finish and submit your changes

Reply format: one short sentence of thought, then one JSON object on its own, for example
{"tool": "read_file", "args": {"filepath": "freightkit/rates.py", "start_line": 1, "end_line": 40}}"""

CONFIGS = {
    "gemma4-e2b.basic": {"model": "gemma-4-e2b", "prompt": "basic.md"},
    "gemma4-e2b.workflow": {"model": "gemma-4-e2b", "prompt": "system.md"},
    "qwen2.5-1.5b.workflow": {"model": "qwen2.5-1.5b", "prompt": "system.md"},
    # Non-agentic control: one reply with the whole package in the prompt, no tools, no test feedback.
    "gemma4-e2b.oneshot": {"model": "gemma-4-e2b", "prompt": "system.md", "mode": "oneshot"},
    # Cloud only (written, not run): the same prompt on Gemma 4 E4B served by vLLM.
    "gemma4-e4b.workflow": {"model": "gemma-4-e4b", "prompt": "system.md"},
}
LIMITS = {"max_turns": 14, "max_tool_calls": 12, "max_new_tokens": 256, "n_ctx": 8192, "no_call_streak": 3}


def system_prompt(name: str) -> str:
    return (PROMPTS / name).read_text().strip() + "\n\n" + TOOLS_DOC


def first_message(task: dict, root: Path) -> str:
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                   if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts)
    return (f"Issue {task['id']}:\n{task['issue']}\n\nRepository files:\n" + "\n".join(files)
            + f"\n\nBudget: {LIMITS['max_tool_calls']} tool calls.")


def parse_call(text: str) -> tuple[str, dict] | None:
    """Find the first JSON object with a "tool" key. Tolerates code fences and text around it."""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            args = obj.get("args", obj.get("arguments", {}))
            return obj["tool"], args if isinstance(args, dict) else {}
    return None


def run_llm(task: dict, llm, config: str) -> dict:
    cfg = CONFIGS[config]
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        root = materialize(task, Path(tmp) / "repo")
        ws = Workspace(root, max_tool_calls=LIMITS["max_tool_calls"])
        msgs = [{"role": "system", "content": system_prompt(cfg["prompt"])},
                {"role": "user", "content": first_message(task, root)}]
        turns, streak, stop, prompt_tokens, completion_tokens, invalid = 0, 0, "max_turns", 0, 0, 0
        trace = []
        while turns < LIMITS["max_turns"]:
            turns += 1
            if len(llm.tokenize(json.dumps(msgs).encode())) + LIMITS["max_new_tokens"] > LIMITS["n_ctx"]:
                stop = "context_full"
                break
            r = llm.create_chat_completion(messages=msgs, temperature=0, max_tokens=LIMITS["max_new_tokens"], seed=0)
            reply = scrub(r["choices"][0]["message"]["content"] or "")[0]
            prompt_tokens += r["usage"]["prompt_tokens"]
            completion_tokens += r["usage"]["completion_tokens"]
            msgs.append({"role": "assistant", "content": reply})
            call = parse_call(reply)
            if call is None:
                streak += 1
                invalid += 1
                trace.append({"turn": turns, "tool": None, "reply_chars": len(reply)})
                if streak >= LIMITS["no_call_streak"]:
                    stop = "no_tool_call"
                    break
                msgs.append({"role": "user", "content": "No tool call found. Reply with one JSON tool call."})
                continue
            streak = 0
            tool, args = call
            result = ws.call(tool, args)
            trace.append({"turn": turns, "tool": tool, "args": {k: str(v)[:120] for k, v in args.items()},
                          "ok": ws.log[-1]["ok"]})
            if ws.submitted:
                stop = "submitted"
                break
            if ws.calls >= ws.max_tool_calls and tool not in ("get_status", "submit_patch"):
                msgs.append({"role": "user", "content": f"Result: {result}\nTool budget used up. Call submit_patch."})
            else:
                msgs.append({"role": "user", "content": f"Result: {result}"})
        patch = scrub(ws.diff())[0]
    return {"id": task["id"], "config": config, "model": cfg["model"], "stop": stop, "turns": turns,
            "tool_calls": ws.calls, "invalid_replies": invalid, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "seconds": round(time.perf_counter() - t0, 1),
            "patch": patch, "trace": trace}


def run_baseline(task: dict, kind: str) -> dict:
    """oracle: submits the reference fix (checks the harness end to end). noop: submits nothing."""
    patch = reference_patch(task) if kind == "oracle" else ""
    return {"id": task["id"], "config": kind, "model": "-", "stop": "submitted", "turns": 1, "tool_calls": 0,
            "invalid_replies": 0, "prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0,
            "patch": patch, "trace": []}


ONESHOT_DOC = """Reply with one short sentence, then one or more JSON edit calls, each on its own, like
{"tool": "edit_file", "args": {"filepath": "freightkit/units.py", "old_string": "...", "new_string": "..."}}
You get no tool results and no second turn: the edits are applied and submitted as they are."""


def parse_calls(text: str) -> list[tuple[str, dict]]:
    """Every JSON object with a "tool" key, in order (non-overlapping)."""
    dec, out, pos = json.JSONDecoder(), [], 0
    while (i := text.find("{", pos)) != -1:
        try:
            obj, end = dec.raw_decode(text[i:])
        except json.JSONDecodeError:
            pos = i + 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            args = obj.get("args", obj.get("arguments", {}))
            out.append((obj["tool"], args if isinstance(args, dict) else {}))
        pos = i + end
    return out


def run_oneshot(task: dict, llm, config: str) -> dict:
    """Control without the agent loop: same model, whole package source in the prompt, one reply."""
    cfg = CONFIGS[config]
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        root = materialize(task, Path(tmp) / "repo")
        ws = Workspace(root, max_tool_calls=LIMITS["max_tool_calls"])
        sources = "\n\n".join(f"### {p.relative_to(root)}\n{p.read_text()}"
                               for p in sorted((root / "freightkit").glob("*.py")))
        msgs = [{"role": "system", "content": (PROMPTS / cfg["prompt"]).read_text().strip() + "\n\n" + ONESHOT_DOC},
                {"role": "user", "content": f"Issue {task['id']}:\n{task['issue']}\n\nSource:\n{sources}"}]
        r = llm.create_chat_completion(messages=msgs, temperature=0, max_tokens=2 * LIMITS["max_new_tokens"], seed=0)
        reply = scrub(r["choices"][0]["message"]["content"] or "")[0]
        calls = [c for c in parse_calls(reply) if c[0] == "edit_file"]
        trace = []
        for tool, args in calls:
            ws.call(tool, args)
            trace.append({"turn": 1, "tool": tool, "args": {k: str(v)[:120] for k, v in args.items()},
                          "ok": ws.log[-1]["ok"]})
        ws.call("submit_patch", {})
        patch = scrub(ws.diff())[0]
    return {"id": task["id"], "config": config, "model": cfg["model"],
            "stop": "submitted" if calls else "no_tool_call", "turns": 1, "tool_calls": len(calls),
            "invalid_replies": 0 if calls else 1, "prompt_tokens": r["usage"]["prompt_tokens"],
            "completion_tokens": r["usage"]["completion_tokens"], "seconds": round(time.perf_counter() - t0, 1),
            "patch": patch, "trace": trace}
