"""Run one agent configuration on the task suite and append trajectories to data/runs/<config>.jsonl.

    python scripts/run_agent.py --config gemma4-e2b.workflow [--split test] [--limit N] [--threads 8]

Resumable: tasks already in the file are skipped. Needs llama-cpp-python==0.3.36 and the GGUF files
from scripts/fetch_models.sh. Run it detached (nohup) and watch the log; a full split takes about an
hour per configuration on 8 CPU cores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sweval.agent import CONFIGS, LIMITS, run_baseline, run_llm, run_oneshot  # noqa: E402
from sweval.tasks import TASKS, split  # noqa: E402

RUNS = ROOT / "data" / "runs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, choices=[*CONFIGS, "oracle", "noop"])
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--models-dir", type=Path, default=ROOT / "models")
    ap.add_argument("--endpoint", help="OpenAI-compatible base URL (cloud pipeline) instead of llama.cpp")
    a = ap.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"{a.config}.jsonl"
    done = {json.loads(line)["id"] for line in out.read_text().splitlines()} if out.exists() else set()
    tasks = [t for t in TASKS if a.split == "all" or split(t["id"]) == a.split]
    tasks = [t for t in tasks if t["id"] not in done][: a.limit or None]
    llm = None
    if a.config in CONFIGS and a.endpoint:
        from sweval.llm_http import HttpLLM

        llm = HttpLLM(a.endpoint, "google/gemma-4-E4B-it" if "e4b" in a.config else CONFIGS[a.config]["model"])
    elif a.config in CONFIGS:
        from llama_cpp import Llama

        spec = json.loads((ROOT / "scripts/models.json").read_text())
        f = next(m["file"] for m in spec["gguf"] if m["label"] == CONFIGS[a.config]["model"])
        llm = Llama(str(a.models_dir / f), n_ctx=LIMITS["n_ctx"], n_threads=a.threads, seed=0, verbose=False)
    with out.open("a", encoding="utf-8") as fh:
        for t in tasks:
            if llm is None:
                r = run_baseline(t, a.config)
            elif CONFIGS[a.config].get("mode") == "oneshot":
                r = run_oneshot(t, llm, a.config)
            else:
                r = run_llm(t, llm, a.config)
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(t["id"], r["stop"], r["tool_calls"], r["seconds"], flush=True)
    print("done", a.config, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
