"""Prove domain injection and rejection at the real review routing boundary."""
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[1]
ROOT = PLUGIN.parent.parent
SCRIPT = PLUGIN / "scripts/evaluate-design-rubric.py"
REGISTRY = "plugins/skill-governance-config/config/rubric-registry.json"
L1 = "plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/references/rubric.json"


def load_module(path):
    spec = importlib.util.spec_from_file_location("review_routing_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("skill", sorted(p.name for p in (PLUGIN / "skills").glob("run-ubm-*")))
def test_actual_entrypoints_inject_the_registered_domain(skill):
    source = PLUGIN / "skills" / skill / "SKILL.md"
    command = load_module(SCRIPT).evaluation_command(ROOT, source)
    refs = command[command.index("--rubric-refs") + 1:command.index("--target")]
    assert len(refs) == 3
    assert [json.loads(Path(p).read_text())["layer"] for p in refs] == ["L0", "L1", "L2"]
    assert refs[1] == str(ROOT / L1)
    fm = yaml.safe_load(source.read_text().split("---", 2)[1])
    assert fm["domain"] == "ubm-goal-setting"
    assert (source.parent / fm["rubric_refs"][0]).resolve() == ROOT / L1
    assert "../../references/content-review-rubric.md" in fm["reference_refs"]


@pytest.fixture
def routing_fixture(tmp_path):
    script = tmp_path / "plugins/ubm-goal-setting/scripts/evaluate-design-rubric.py"
    script.parent.mkdir(parents=True)
    script.write_bytes(SCRIPT.read_bytes())
    for relative in [REGISTRY, L1, "plugins/ubm-goal-setting/.claude-plugin/plugin.json"]:
        out = tmp_path / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((ROOT / relative).read_bytes())
    source = tmp_path / "plugins/ubm-goal-setting/skills/run-ubm-example/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("fixture\n")
    return load_module(script), tmp_path, source


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "wrong-owner", "wrong-domain", "wrong-layer", "wrong-policy"])
def test_invalid_registration_never_falls_back_to_l0(routing_fixture, corruption):
    module, root, source = routing_fixture
    path = root / REGISTRY
    registry = json.loads(path.read_text())
    entry = next(item for item in registry["rubrics"] if item["domain"] == "ubm-goal-setting")
    if corruption == "missing":
        registry["rubrics"].remove(entry)
    elif corruption == "duplicate":
        registry["rubrics"].append(entry.copy())
    elif corruption == "wrong-owner":
        alternate = root / "alternate.json"
        alternate.write_bytes((root / L1).read_bytes())
        entry["rubric"] = str(alternate)
    elif corruption == "wrong-policy":
        entry["conflict_policy"] = "error"
    else:
        l1 = json.loads((root / L1).read_text())
        l1["domain" if corruption == "wrong-domain" else "layer"] = "other-domain" if corruption == "wrong-domain" else "L0"
        (root / L1).write_text(json.dumps(l1))
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


def test_foreign_target_and_symlink_escape_are_rejected(routing_fixture):
    module, root, source = routing_fixture
    foreign = root / "plugins/another/skills/run-ubm-example/SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("foreign\n")
    with pytest.raises(ValueError):
        module.evaluation_command(root, foreign)
    source.unlink()
    source.symlink_to(foreign)
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


@pytest.mark.parametrize("ancestor", [False, True])
def test_owner_rubric_symlink_cannot_inject_foreign_rules(routing_fixture, ancestor):
    module, root, source = routing_fixture
    owner = root / L1
    foreign = root / "foreign"
    foreign.mkdir()
    replacement = foreign / "rubric.json"
    replacement.write_bytes(owner.read_bytes())
    owner.unlink()
    if ancestor:
        owner.parent.rmdir()
        owner.parent.symlink_to(foreign, target_is_directory=True)
    else:
        owner.symlink_to(replacement)
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


def test_same_id_delta_changes_only_background_check():
    composer = load_module(ROOT / "plugins/skill-governance-automation/scripts/compose-rubrics.py")
    l0 = ROOT / "plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"
    l2 = ROOT / "plugins/harness-creator/skills/assign-skill-design-evaluator/references/rubric.json"
    base = composer.compose([str(l0), str(l2)], "deep-merge", "most-specific-wins")
    actual = composer.compose([str(l0), str(ROOT / L1), str(l2)], "deep-merge", "most-specific-wins")
    before = {r["id"]: r for r in base["rules"]}
    after = {r["id"]: r for r in actual["rules"]}
    assert len(after) == len(actual["rules"]) == len(before)
    assert set(before) == set(after)
    for rid in before:
        if rid == "KL-002":
            assert before[rid]["check"] != after[rid]["check"]
            assert {k: v for k, v in before[rid].items() if k != "check"} == {
                k: v for k, v in after[rid].items() if k != "check"}
        else:
            assert before[rid] == after[rid]
    assert "All current entries" in after["KL-002"]["check"]
    assert "mere added length is insufficient" in after["KL-002"]["check"]
