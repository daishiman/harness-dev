"""Latest elegant-review kit contract: 30 required, 9/9/12, single-writer, opt-in git."""

import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "plugins" / "harness-creator" / "skills" / "run-elegant-review"
COMMAND_PROMPTS = ROOT / "plugins" / "harness-creator" / "references" / "command-usage-prompts"


def _load_script(name: str):
    path = KIT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_thought_method_allocation_is_exact_9_9_12_and_why_belongs_to_agent4():
    catalog = yaml.safe_load((KIT / "references" / "thought-methods.yaml").read_text())
    assert catalog["logical_structural"]["count"] == 9
    assert catalog["meta_divergent"]["count"] == 9
    assert catalog["system_strategic"]["count"] == 12
    assert [m["id"] for m in catalog["logical_structural"]["methods"]] == [
        "critical", "deduction", "induction", "abduction", "vertical",
        "decomposition", "mece", "two-axis", "process",
    ]
    assert "why" in [m["id"] for m in catalog["system_strategic"]["methods"]]

    validator = _load_script("validate-paradigm-coverage.py")
    assert validator.EXPECTED_META[26] == (
        "why", "G-problem", "elegant-system-strategic-analyst"
    )


def test_phase2_prompt_goal_uses_the_canonical_9_9_12_lane_allocation():
    prompt = (KIT / "prompts" / "R2-phase2-parallel.md").read_text()
    assert "(9 / 10 / 11)" not in prompt
    assert "担当思考法 (9 / 9 / 12)" in prompt


def test_phase3_executor_permissions_cover_git_audit_without_recursive_agents():
    agent = (ROOT / "plugins" / "harness-creator" / "agents" / "elegant-improvement-executor.md").read_text()
    prompt = (KIT / "prompts" / "R3-phase3-execute.md").read_text()

    frontmatter = agent.split("---", 2)[1]
    assert "Bash(git diff *)" in frontmatter
    assert "Bash(git grep *)" in frontmatter
    assert "executor 自身は SubAgent を再帰起動しない" in prompt
    assert "並列化は orchestrator が所有" in prompt


def test_manifest_is_single_writer_and_git_is_explicit_opt_in_only():
    manifest = json.loads((KIT / "workflow-manifest.json").read_text())
    assert "skip_thought_methods" not in manifest["input_contract"]["options"]
    assert manifest["input_contract"]["options"]["commit_authorized"] == "bool (default false)"

    phase1, phase2, phase3 = manifest["phases"]
    assert phase1["output"]["materialized_by"] == "orchestrator"
    assert phase2["output"]["materialized_by"] == "orchestrator"
    assert phase2["failure_action"]["policy"] == "abort"
    assert [a["thought_methods_count"] for a in phase2["subagents"]] == [9, 9, 12]
    assert "commit_authorized=true" in " ".join(phase3["steps"])
    assert manifest["side_effect_boundaries"]["git"] == "patch-only unless commit_authorized=true"


def test_resource_map_paths_exist_and_list_all_runtime_scripts_and_schemas():
    resource_map = yaml.safe_load((KIT / "references" / "resource-map.yaml").read_text())
    entries = resource_map["resources"] + resource_map["related_artifacts"]
    mapped = {entry["file"] for entry in entries}
    for entry in entries:
        assert (KIT / "references" / entry["file"]).resolve().exists(), entry["file"]
    expected = {
        f"../scripts/{p.name}" for p in (KIT / "scripts").glob("*.py")
    } | {
        f"../schemas/{p.name}" for p in (KIT / "schemas").glob("*.json")
    } | {
        f"../templates/{p.name}" for p in (KIT / "templates").glob("*") if p.is_file()
    }
    assert expected <= mapped


def test_command_prompt_distribution_capability_table_is_explicit_and_truthful():
    readme = (COMMAND_PROMPTS / "README.md").read_text()
    assert "配布 capability 表" in readme
    assert "Claude Code" in readme
    assert "Agents" in readme
    assert "Codex" in readme
    assert "plugin skill 内 team orchestration" in readme
    assert "native agent surface なし" in readme
    assert "../native-surface-contract.md" in readme


def test_variable_abstraction_schema_matches_variable_template_contract():
    schema = json.loads((KIT / "schemas" / "findings.schema.json").read_text())
    item = schema["properties"]["variable_abstraction"]["items"]
    assert set(item["required"]) == {
        "concrete_value", "name", "meaning", "default", "required",
        "not_applicable_when", "source_trace",
    }
    assert item["properties"]["name"]["pattern"].startswith("^\\{\\{")


def test_findings_template_is_executable_under_the_latest_contract(tmp_path):
    validator = _load_script("validate-paradigm-coverage.py")
    template = json.loads((KIT / "templates" / "findings.json").read_text())

    assert template["run_status"] == "incomplete"
    assert len(template["paradigm_findings"]) == 30
    for finding in template["paradigm_findings"]:
        pid = finding["paradigm_id"]
        name, category, agent = validator.EXPECTED_META[pid]
        assert (finding["paradigm_name"], finding["category"], finding["agent"]) == (
            name,
            category,
            agent,
        )
        assert set(finding["condition_matrix"]) == {"C1", "C2", "C3", "C4"}

    variable_keys = {
        "concrete_value", "name", "meaning", "default", "required",
        "not_applicable_when", "source_trace",
    }
    assert all(set(item) == variable_keys for item in template["variable_abstraction"])

    candidate = tmp_path / "findings.json"
    candidate.write_text(json.dumps(template), encoding="utf-8")
    valid, errors = validator.validate_structured_json(candidate, strict_signal=True)
    assert valid, errors


def test_scorecard_rejects_condition_matrix_issue_mismatch(tmp_path):
    validator = _load_script("validate-paradigm-coverage.py")
    scorecard = _load_script("build-paradigm-scorecard.py")
    findings = []
    for pid, (name, category, agent) in validator.EXPECTED_META.items():
        findings.append({
            "paradigm_id": pid,
            "paradigm_name": name,
            "category": category,
            "agent": agent,
            "score": 1.0,
            "condition_matrix": {
                condition: {"verdict": "PASS", "evidence": ["checked"]}
                for condition in ("C1", "C2", "C3", "C4")
            },
            "issues": [],
        })
    findings[0]["issues"] = [{"condition": "C1"}]
    src = tmp_path / "findings.json"
    src.write_text(json.dumps({
        "paradigm_findings": findings,
        "thought_method_coverage": {
            "total": 30,
            "used": [x["paradigm_name"] for x in findings],
            "skipped_with_reason": [],
        },
    }))
    assert scorecard.main(["build-paradigm-scorecard.py", str(src)]) == 1
