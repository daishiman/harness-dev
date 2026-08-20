"""Phase 3 usable-first artifact delivery regression contracts.

These tests intentionally exercise the public workflow manifests and generated
goal-seek prose.  The invariant is chronological: an actual artifact is created,
class-specific mechanical guards pass, the artifact is presented, the user makes
a choice, and only then may a semantic evaluator or improver start.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _manifest(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _phase_index(manifest: dict, phase_id: str) -> int:
    return [phase["id"] for phase in manifest["phases"]].index(phase_id)


def test_all_owned_workflows_publish_the_same_delivery_event_order():
    paths = (
        "plugins/harness-creator/skills/run-build-skill/workflow-manifest.json",
        "plugins/slide-report-generator/skills/run-slide-report-generate/workflow-manifest.json",
        "plugins/prompt-creator/skills/run-prompt-create/workflow-manifest.json",
    )
    expected_states = [
        "artifact_created",
        "minimal_guard_passed",
        "artifact_presented",
        "user_choice_recorded",
        "semantic_evaluator_started",
        "handoff_complete",
    ]
    for path in paths:
        contract = _manifest(path)["artifact_delivery_contract"]
        machine = contract["state_machine"]
        assert machine["states"] == expected_states, path
        assert machine["accept_contexts"] == {"evaluator": 0, "improver": 0}, path
        assert contract["release"] == "explicit-only", path
        assert contract["exhaustive"] == "explicit-only", path


def test_harness_creator_presents_before_choice_and_optional_30_method_review():
    manifest = _manifest(
        "plugins/harness-creator/skills/run-build-skill/workflow-manifest.json"
    )
    ids = [
        "usable-draft-proof",
        "artifact-present-handoff",
        "diagnostic-choice",
        "initial-draft-review",
        "bounded-improvement",
    ]
    assert [_phase_index(manifest, value) for value in ids] == sorted(
        _phase_index(manifest, value) for value in ids
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert phases["initial-draft-review"]["default_on"] is False
    assert "diagnostic-choice" in phases["initial-draft-review"]["dependsOn"]
    assert "explicit" in phases["initial-draft-review"]["trigger"].lower()
    assert phases["diagnostic-choice"]["accept_as_is_evaluator_contexts"] == 0


def test_slide_heavy_review_is_post_choice_and_not_a_handoff_dependency():
    manifest = _manifest(
        "plugins/slide-report-generator/skills/run-slide-report-generate/workflow-manifest.json"
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert phases["R4-artifact-present-handoff"]["dependsOn"] == [
        "R3-generate-minimal-guard"
    ]
    assert phases["R5-diagnostic-choice"]["dependsOn"] == [
        "R4-artifact-present-handoff"
    ]
    review = phases["R6-selected-semantic-review"]
    assert review["dependsOn"] == ["R5-diagnostic-choice"]
    assert review["default_on"] is False
    assert review["evaluator_contexts_when_accept_as_is"] == 0
    assert review["improver_contexts_when_accept_as_is"] == 0
    assert review["max_iterations"] == 3
    assert review["thought_method_count"] == 30
    assert review["agent_roster_count"] == 15


def test_prompt_handoff_does_not_depend_on_semantic_or_governance_review():
    manifest = _manifest(
        "plugins/prompt-creator/skills/run-prompt-create/workflow-manifest.json"
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert phases["artifact-present-handoff"]["dependsOn"] == ["p0-lint"]
    assert phases["diagnostic-choice"]["dependsOn"] == [
        "artifact-present-handoff"
    ]
    assert phases["design-evaluate"]["dependsOn"] == ["diagnostic-choice"]
    assert phases["design-evaluate"]["default_on"] is False
    assert phases["elegant-review"]["post_choice_only"] is True
    assert phases["governance"]["post_choice_only"] is True
    assert phases["diagnostic-choice"]["accept_as_is_evaluator_contexts"] == 0
    assert phases["diagnostic-choice"]["accept_as_is_improver_contexts"] == 0


def test_goal_seek_ssot_and_generated_combinator_share_delivery_invariant():
    ssot = (
        ROOT / "plugins/harness-creator/skills/run-goal-seek/SKILL.md"
    ).read_text(encoding="utf-8")
    script_path = (
        ROOT
        / "plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py"
    )
    spec = importlib.util.spec_from_file_location("phase3_render_combinators", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    generated = module.GOAL_SEEK_WIRING_SECTION
    event_sequence = (
        "`artifact_created` → `minimal_guard_passed` → `artifact_presented` → "
        "`user_choice_recorded` → `semantic_evaluator_started`"
    )
    for text in (ssot, generated):
        assert event_sequence in text
        assert "evaluator_contexts=0" in text
        assert "improver_contexts=0" in text


def test_slide_postgen_hook_prompts_presentation_and_choice_not_auto_evaluator(
    monkeypatch, tmp_path
):
    script = ROOT / "plugins/slide-report-generator/hooks/hook-postgen-eval.py"
    spec = importlib.util.spec_from_file_location("phase3_postgen_hook", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    artifact = tmp_path / "index.html"
    artifact.write_text("<!doctype html><html><body>draft</body></html>", encoding="utf-8")
    context, guard_status = module.build_context("slide", str(tmp_path))
    assert guard_status == "pass"
    assert "artifact_presented" in context
    assert "user_choice_recorded" in context
    assert "deck-evaluator" not in context
    assert "30 種思考法" not in context
    assert "accept-as-is / light / standard / detailed" in context
    assert "focused" not in context
    assert "release" not in context.split("user_choice_recorded:", 1)[1].splitlines()[0]


def test_slide_hook_is_subprocess_free_minimal_guard_only():
    source = (
        ROOT / "plugins/slide-report-generator/hooks/hook-postgen-eval.py"
    ).read_text(encoding="utf-8")
    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert "def run_svg_diagram_lint" not in source
    assert "def run_information_lint" not in source
    assert "def run_slide_layout_gate" not in source


def test_slide_runtime_docs_composition_and_workflow_share_post_choice_contract():
    plugin = ROOT / "plugins/slide-report-generator"
    readme = (plugin / "README.md").read_text(encoding="utf-8")
    reference = (plugin / "references/post-generation-evaluation.md").read_text(
        encoding="utf-8"
    )
    skill = (plugin / "skills/run-slide-report-generate/SKILL.md").read_text(
        encoding="utf-8"
    )
    resource_map = (
        plugin / "skills/run-slide-report-generate/references/resource-map.yaml"
    ).read_text(encoding="utf-8")
    composition = (plugin / "plugin-composition.yaml").read_text(encoding="utf-8")
    manifest = _manifest(
        "plugins/slide-report-generator/skills/run-slide-report-generate/workflow-manifest.json"
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}

    assert "最小guard・成果物提示・利用者選択を促すadvisory" in readme
    assert "生成後評価の自動起動" not in readme
    assert "利用者選択後のみ" in reference
    assert "自動起動(フック)" not in reference
    assert "hook-postgen-eval が生成検知時に機械実行" not in skill
    assert "両者とも `hook-postgen-eval` が生成検知時に機械実行" not in skill
    assert "hook-postgen-eval も消費" not in resource_map
    assert (
        'from: "hook:PostToolUse/hook-postgen-eval", to: agents/deck-evaluator'
        not in composition
    )
    assert (
        "from: skills/run-slide-report-generate, to: agents/deck-evaluator,"
        in composition
    )
    choice = phases["R5-diagnostic-choice"]
    assert choice["choices"] == ["accept-as-is", "light", "standard", "detailed"]
    assert choice["release_event"] == "explicit-only"
    assert choice["exhaustive_event"] == "explicit-only"
    review = phases["R6-selected-semantic-review"]
    assert review["condition"] == "user_choice_recorded in [light,standard,detailed]"
    post_choice_resources = {
        "ref-deck-evaluation-rubric",
        "ref-ui-quality-checklist",
        "ref-report-quality-checklist",
        "vendor-evaluate-deck",
        "glue-validate-svg-diagram",
        "glue-validate-diagram-information",
        "glue-validate-slide-layout",
        "glue-validate-report-layout",
    }
    minimal = phases["R3-generate-minimal-guard"]
    assert post_choice_resources.isdisjoint(minimal["resourceIds"])
    assert post_choice_resources <= set(review["resourceIds"])
    resources = {resource["id"]: resource for resource in manifest["resources"]}
    for resource_id in post_choice_resources:
        assert resources[resource_id]["phaseIds"] == ["R6-selected-semantic-review"]


def test_slide_minimal_guard_rejects_secret_corruption_and_symlink(tmp_path):
    script = ROOT / "plugins/slide-report-generator/hooks/hook-postgen-eval.py"
    spec = importlib.util.spec_from_file_location("phase3_postgen_hook_negative", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    artifact = tmp_path / "index.html"
    artifact.write_text(
        '<html><body>api_key="abcdefghijklmnop"</body></html>', encoding="utf-8"
    )
    status, failures = module.run_minimal_artifact_guard("slide", str(tmp_path))
    assert status == "fail" and "possible embedded secret" in failures

    artifact.write_bytes(b"<html>\x00</html>")
    status, failures = module.run_minimal_artifact_guard("slide", str(tmp_path))
    assert status == "fail" and any("corrupt" in item for item in failures)

    artifact.unlink()
    target = tmp_path / "outside.html"
    target.write_text("<html><body>outside</body></html>", encoding="utf-8")
    artifact.symlink_to(target)
    status, failures = module.run_minimal_artifact_guard("slide", str(tmp_path))
    assert status == "fail" and any("symlink" in item for item in failures)
