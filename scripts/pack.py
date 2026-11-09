"""Validate agent_pack/ and build a deterministic dist/agent_pack.zip.

    python scripts/pack.py            # validate and build
    python scripts/pack.py --check    # validate only (CI)

Rules checked: agent.yaml at the root; only text, config and safetensors files; no symlinks and no
paths that leave the pack; every !include resolves inside the pack; tools come from the known set;
every skill has a SKILL.md whose front matter names it; one model for every agent; LoRA adapters (if
any) have rank 128 or less; total size under 3 GiB.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "agent_pack"
ALLOWED_EXT = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
TOOLS = {"run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch",
         "get_code_neighbors", "search_similar_code", "get_code_subgraph"}
MAX_BYTES = 3 * 1024**3


class PackError(ValueError):
    pass


def loader(base: Path, pack: Path):
    class L(yaml.SafeLoader):
        pass

    def include(ld, node):
        rel = ld.construct_scalar(node)
        target = (base / rel).resolve()
        if ".." in Path(rel).parts or pack.resolve() not in target.parents:
            raise PackError(f"!include leaves the pack: {rel}")
        if not target.is_file():
            raise PackError(f"!include not found: {rel}")
        if target.suffix in (".yaml", ".yml"):
            return yaml.load(target.read_text(), Loader=loader(target.parent, pack))
        return target.read_text()

    L.add_constructor("!include", include)
    return L


def load_agent(path: Path, pack: Path) -> dict:
    return yaml.load(path.read_text(), Loader=loader(path.parent, pack))


def validate(pack: Path = PACK) -> dict:
    if not (pack / "agent.yaml").is_file():
        raise PackError("agent.yaml must be at the root")
    total, files = 0, []
    for p in sorted(pack.rglob("*")):
        if p.is_symlink():
            raise PackError(f"symlink not allowed: {p.relative_to(pack)}")
        if p.is_file():
            if p.suffix not in ALLOWED_EXT:
                raise PackError(f"file type not allowed: {p.relative_to(pack)}")
            total += p.stat().st_size
            files.append(str(p.relative_to(pack)))
    if total > MAX_BYTES:
        raise PackError("pack larger than 3 GiB")
    agents = [load_agent(pack / "agent.yaml", pack)]
    for sub in sorted((pack / "sub_agents").glob("*.yaml")) if (pack / "sub_agents").is_dir() else []:
        agents.append(load_agent(sub, pack))
    models = {a.get("model") for a in agents}
    if len(models) != 1 or None in models:
        raise PackError(f"every agent must name the same model, found {models}")
    for a in agents:
        if not isinstance(a.get("instruction"), str) or not a["instruction"].strip():
            raise PackError(f"agent {a.get('name')} has no instruction")
        unknown = {t["name"] for t in a.get("tools", [])} - TOOLS
        if unknown:
            raise PackError(f"unknown tools: {sorted(unknown)}")
        adapter = a.get("adapter")
        if adapter:
            cfg = pack / "adapters" / adapter / "adapter_config.json"
            if not cfg.is_file() or not (cfg.parent / "adapter_model.safetensors").is_file():
                raise PackError(f"adapter {adapter} is incomplete")
            if json.loads(cfg.read_text()).get("r", 0) > 128:
                raise PackError(f"adapter {adapter} rank above 128")
    for skill in sorted((pack / "skills").iterdir()) if (pack / "skills").is_dir() else []:
        doc = skill / "SKILL.md"
        if not doc.is_file():
            raise PackError(f"skill {skill.name} has no SKILL.md")
        text = doc.read_text()
        if not text.startswith("---\n"):
            raise PackError(f"skill {skill.name}: SKILL.md needs YAML front matter")
        meta = yaml.safe_load(text.split("---\n")[1])
        if meta.get("name") != skill.name:
            raise PackError(f"skill {skill.name}: front matter name is {meta.get('name')!r}")
    return {"files": files, "bytes": total, "model": models.pop(), "agents": len(agents)}


def build(pack: Path = PACK, out: Path = ROOT / "dist" / "agent_pack.zip") -> Path:
    info = validate(pack)
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in info["files"]:
            zi = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, (pack / rel).read_bytes())
    return out


def main() -> int:
    try:
        info = validate()
    except PackError as e:
        print("INVALID:", e)
        return 1
    print(f"valid: {len(info['files'])} files, {info['bytes']} bytes, model {info['model']}")
    if "--check" not in sys.argv:
        print("built", build().relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
