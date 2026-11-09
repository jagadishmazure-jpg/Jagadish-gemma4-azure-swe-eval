"""The declarative agent pack: validated before it is zipped, and it ships the measured prompt."""

import shutil
import zipfile

import pack
import pytest

from sweval.agent import PROMPTS


@pytest.fixture
def tmp_pack(tmp_path):
    d = tmp_path / "agent_pack"
    shutil.copytree(pack.PACK, d)
    return d


def test_committed_pack_is_valid_and_uses_one_model():
    info = pack.validate()
    assert info["model"] == "gemma-4-e2b-it" and "agent.yaml" in info["files"] and info["agents"] == 1


def test_pack_ships_the_exact_prompt_and_budgets_that_were_measured():
    agent = pack.load_agent(pack.PACK / "agent.yaml", pack.PACK)
    assert agent["instruction"] == (PROMPTS / "system.md").read_text()
    assert agent["generate_content_config"]["temperature"] == 0.0
    import yaml

    from sweval.agent import LIMITS
    cfg = yaml.safe_load((pack.PACK / "eval_config.yaml").read_text())
    assert cfg["max_tool_calls"] == LIMITS["max_tool_calls"] and cfg["max_turns"] == LIMITS["max_turns"]


@pytest.mark.parametrize("breakage,message", [
    (lambda d: (d / "agent.yaml").unlink(), "agent.yaml must be at the root"),
    (lambda d: (d / "run.sh").write_text("echo"), "file type not allowed"),
    (lambda d: (d / "link.md").symlink_to(d / "prompts/system.md"), "symlink"),
    (lambda d: (d / "agent.yaml").write_text((d / "agent.yaml").read_text().replace(
        "prompts/system.md", "../../etc/hosts")), "leaves the pack"),
    (lambda d: (d / "agent.yaml").write_text((d / "agent.yaml").read_text() + "  - name: browse_web\n"),
     "unknown tools"),
    (lambda d: (d / "skills/fix_issue/SKILL.md").write_text("---\nname: other\n---\n"), "front matter name"),
])
def test_validator_rejects_broken_packs(tmp_pack, breakage, message):
    breakage(tmp_pack)
    with pytest.raises(pack.PackError, match=message):
        pack.validate(tmp_pack)


def test_adapter_rank_is_capped(tmp_pack):
    a = tmp_pack / "adapters/lora"
    a.mkdir(parents=True)
    (a / "adapter_config.json").write_text('{"r": 256}')
    (a / "adapter_model.safetensors").write_bytes(b"0")
    (tmp_pack / "agent.yaml").write_text((tmp_pack / "agent.yaml").read_text() + "adapter: lora\n")
    with pytest.raises(pack.PackError, match="rank above 128"):
        pack.validate(tmp_pack)


def test_zip_is_deterministic(tmp_path):
    a = pack.build(out=tmp_path / "a.zip").read_bytes()
    b = pack.build(out=tmp_path / "b.zip").read_bytes()
    assert a == b and zipfile.ZipFile(tmp_path / "a.zip").namelist()[0] == "agent.yaml"
