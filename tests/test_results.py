"""What was measured: every config ran every task, the controls bracket the harness, docs match."""

import json
import subprocess
import sys

from conftest import ROOT

from sweval.tasks import TASKS

LLM_CONFIGS = ("gemma4-e2b.workflow", "gemma4-e2b.basic", "gemma4-e2b.oneshot", "qwen2.5-1.5b.workflow")


def test_every_measured_config_ran_every_task_once(metrics):
    for c in ("oracle", "noop", *LLM_CONFIGS):
        assert metrics["configs"][c]["n"] == len(TASKS), c
    ids = sorted(t["id"] for t in TASKS)
    for c in LLM_CONFIGS:
        rows = [json.loads(x) for x in (ROOT / f"data/runs/{c}.jsonl").read_text().splitlines()]
        assert sorted(r["id"] for r in rows) == ids, c


def test_controls_bracket_the_harness(metrics):
    assert metrics["configs"]["oracle"]["resolved"]["rate"] == 1.0
    assert metrics["configs"]["noop"]["resolved"]["rate"] == 0.0


def test_no_trajectory_touched_paths_outside_the_workspace():
    for p in (ROOT / "data/runs").glob("*.jsonl"):
        for line in p.read_text().splitlines():
            for t in json.loads(line)["trace"]:
                cmd = t.get("args", {}).get("command", "") + t.get("args", {}).get("filepath", "")
                assert "/home" not in cmd and "~" not in cmd and "/etc/" not in cmd, (p.name, cmd)


def test_measured_files_match_the_manifest():
    r = subprocess.run([sys.executable, "scripts/manifest.py", "--check"], cwd=ROOT, capture_output=True, text=True,
                       check=False)
    assert r.returncode == 0, r.stdout


def test_models_file_pins_every_model():
    spec = json.loads((ROOT / "scripts/models.json").read_text())
    for m in spec["gguf"]:
        assert "/resolve/main/" not in m["url"] and len(m["sha256"]) == 64 and m["license"] == "Apache-2.0"


def test_numbers_in_the_docs_match_the_results():
    r = subprocess.run([sys.executable, "scripts/check_numbers.py"], cwd=ROOT, capture_output=True, text=True,
                       check=False)
    assert r.returncode == 0, r.stdout


def test_documented_example_output_is_current():
    r = subprocess.run([sys.executable, "scripts/render_docs.py", "--check"], cwd=ROOT, capture_output=True,
                       text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
