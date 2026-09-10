"""Runtime profile と run-intake-revise の依存契約回帰テスト。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REVISE_DIR = PLUGIN_ROOT / "skills" / "run-intake-revise"
INTAKE_DIR = PLUGIN_ROOT / "skills" / "run-skill-intake"


def test_revise_manifest_dependencies_are_closed_and_resources_exist() -> None:
    manifest = json.loads(
        (REVISE_DIR / "workflow-manifest.json").read_text(encoding="utf-8")
    )
    phases = manifest["phases"]
    phase_ids = {phase["id"] for phase in phases}
    assert len(phase_ids) == len(phases)

    resource_by_id = {resource["id"]: resource for resource in manifest["resources"]}
    for phase in phases:
        assert set(phase.get("dependsOn", [])) <= phase_ids
        assert set(phase.get("resourceIds", [])) <= resource_by_id.keys()

    for resource in resource_by_id.values():
        assert (REVISE_DIR / resource["path"]).resolve().is_file(), resource


def test_revise_uses_existing_question_bank_script_without_dangling_agent() -> None:
    manifest = json.loads(
        (REVISE_DIR / "workflow-manifest.json").read_text(encoding="utf-8")
    )
    phase = next(item for item in manifest["phases"] if item["id"] == "P8-self-update")
    assert phase["exitHook"] == "update-question-bank"
    assert phase["resourceIds"] == ["script-update-question-bank"]
    assert phase["success_outcomes"] == [
        {"decision": "approved", "result": "apply_exit_0"},
        {
            "decision": "declined",
            "result": "stop_success",
            "record": "question-bank-update.json.status=skipped; skip_reason=question_bank_update_declined",
        },
    ]

    forbidden = "skill-intake-self" + "-updater"
    texts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".json", ".yaml", ".yml", ".py"}
    )
    assert forbidden not in texts
    assert "update_question_bank.py" in texts
    assert "--apply" in texts
    assert "dry-run" in texts


def test_revise_exit_61_is_consistent_across_manifest_skill_and_prompt() -> None:
    manifest = json.loads(
        (REVISE_DIR / "workflow-manifest.json").read_text(encoding="utf-8")
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert phases["P7-log"]["fatal_exit_codes"] == [2, 61]
    assert phases["P8-self-update"]["fatal_exit_codes"] == [61]

    skill_text = (REVISE_DIR / "SKILL.md").read_text(encoding="utf-8")
    prompt_text = (REVISE_DIR / "prompts" / "R1-main.md").read_text(encoding="utf-8")
    for text in (skill_text, prompt_text):
        assert "exit 61" in text
        assert "revision-log" in text
        assert "update_question_bank.py" in text
        assert "P7/P8" in text


def test_self_update_components_resolve_and_renderer_keeps_legacy_fallback() -> None:
    canonical_map = json.loads(
        (PLUGIN_ROOT / "references" / "section_canonical_map.json").read_text(
            encoding="utf-8"
        )
    )
    section = next(
        item
        for item in canonical_map["sections"]
        if item["section_key"] == "10_self_updater"
    )
    assert section["responsible_components"] == [
        "skill:run-skill-intake",
        "script:plugins/skill-intake/scripts/measure_value_realized.py",
        "script:plugins/skill-intake/scripts/update_question_bank.py",
    ]

    repo_root = PLUGIN_ROOT.parents[1]
    for ref in section["responsible_components"]:
        kind, value = ref.split(":", 1)
        if kind == "skill":
            target = PLUGIN_ROOT / "skills" / value / "SKILL.md"
        else:
            target = repo_root / value
        assert target.is_file(), ref

    module_path = PLUGIN_ROOT / "scripts" / "render_v2_adapter.py"
    spec = importlib.util.spec_from_file_location("skill_intake_render_v2", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.responsible_components(section) == section["responsible_components"]
    assert module.responsible_components(
        {"responsible_subagent": ["legacy-one"]}
    ) == ["agent:legacy-one"]


def test_skill_intake_phase9_resolves_inline_self_update_scripts() -> None:
    manifest = json.loads(
        (INTAKE_DIR / "workflow-manifest.json").read_text(encoding="utf-8")
    )
    phase = next(item for item in manifest["phases"] if item["id"] == "P9-finalize")
    assert "entryHook" not in phase
    assert phase["exitHook"] == "measure-and-preview-self-update-inline"
    assert phase["resourceIds"] == [
        "ref-handoff-contract",
        "script-measure-value-realized",
        "script-update-question-bank",
    ]

    resources = {item["id"]: item for item in manifest["resources"]}
    for resource_id in phase["resourceIds"]:
        resource = resources[resource_id]
        assert (INTAKE_DIR / resource["path"]).resolve().is_file(), resource_id

    phase11 = next(item for item in manifest["phases"] if item["id"] == "P11-next-action")
    assert phase11["exitHook"] == "validate-task-graph-progress"
    assert phase11["resourceIds"] == ["script-validate-task-graph-progress"]
    verifier = resources["script-validate-task-graph-progress"]
    assert (INTAKE_DIR / verifier["path"]).resolve().is_file()


def test_skill_intake_manifest_delegate_and_dependency_closure() -> None:
    manifest = json.loads((INTAKE_DIR / "workflow-manifest.json").read_text(encoding="utf-8"))
    phases = manifest["phases"]
    phase_ids = {phase["id"] for phase in phases}
    resources = {resource["id"]: resource for resource in manifest["resources"]}
    for phase in phases:
        assert set(phase.get("dependsOn", [])) <= phase_ids
        assert set(phase.get("resourceIds", [])) <= resources.keys()
        if phase["delegateType"] == "skill":
            delegate = PLUGIN_ROOT / "skills" / phase["delegateName"] / "SKILL.md"
        else:
            delegate = PLUGIN_ROOT / "agents" / f"{phase['delegateName']}.md"
        assert delegate.is_file(), phase["id"]
        if phase.get("exitHook"):
            assert any(resources[item]["kind"] == "script" for item in phase["resourceIds"])
        if phase.get("outputSchemaId"):
            assert phase["outputSchemaId"] in phase["resourceIds"]


def test_artifact_schema_accepts_component_or_legacy_subagent_producer() -> None:
    schema = json.loads(
        (PLUGIN_ROOT / "references" / "intake.schema.json").read_text(
            encoding="utf-8"
        )
    )
    artifact = schema["$defs"]["artifact_index"]["properties"]["artifacts"]["items"]
    assert artifact["required"] == ["path", "role_one_liner"]
    assert artifact["anyOf"] == [
        {"required": ["generator_component"]},
        {"required": ["generator_subagent"]},
    ]
    assert "runtime_ref" in artifact["properties"]
