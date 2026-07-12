"""validate-build-trace.py の genuine で網羅的な機能テスト (network 不要)。

対象: plugins/harness-creator/skills/run-build-skill/scripts/validate-build-trace.py

このスクリプトは 3 系統を持つ:
  1. 既存(後方互換)モード: skill-build-trace.json を ~25 個のセクションで検証する
     大型 validator (main() 末尾の長大な errs 蓄積ロジック)。
  2. 新モード: --manifest / --bundle / --self-test (CapabilityManifest を kind 別
     dispatch で検証し JSON {valid, kind, findings} を出力)。
  3. 純関数群: _validate_prompt_generation_model / _validate_feedback_contract /
     validate_manifest / _has_cycle / _load_frontmatter / _check_kind_* など。

方針:
  - 完全な「合格 trace」を _full_trace() で組み立て、各セクションを 1 つずつ壊して
    対応する err 文字列が出ることを assert する (genuine な分岐網羅)。
  - 純関数は実入力で直接呼び戻り値を assert。
  - main は subprocess(sys.executable) と in-process 両方で exit code / 出力を assert。
  - feedback_contract_ssot は実 SSOT を import するスクリプト挙動をそのまま使う
    (network / keychain / Notion なし。tmp_path に閉じてリポジトリを汚染しない)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-build-trace.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_build_trace_uut", SCRIPT)
M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(M)


# =====================================================================
# trace fixture builders
# =====================================================================

def _full_trace() -> dict:
    """全セクション合格の skill-build-trace (run kind, feedback_contract 付き)。"""
    build_flow = [
        {"step": s, "status": "PASS", "evidence": f"{s} done"}
        for s in M.REQUIRED_BUILD_STEPS
    ]
    doc_cov = [
        {"doc": d, "status": "PASS", "evidence": f"read {d}"}
        for d in M.REQUIRED_DOC_COVERAGE
    ]
    layers = [
        {
            "layer": L,
            "decision": "use",
            "reason": "needed",
            "placement_evidence": "evidence",
            "fallback": "none",
            "dependency_direction_ok": True,
            "macos_stdlib_ok": True,
            "deterministic": True,
        }
        for L in M.REQUIRED_LAYERS
    ]
    return {
        "skill_kind": "run",
        "source_docs": ["02-skill-structure"],
        "context_map_decision": {
            "map": "resource-map",
            "task_category": "baseline-skill-build",
            "selected_docs": ["02-skill-structure", "03-frontmatter"],
        },
        "design_model": {
            "intent": "x",
            "contract": "y",
            "boundary": "z",
            "execution": "e",
            "feedback": "f",
        },
        "build_flow_coverage": build_flow,
        "doc_coverage": doc_cov,
        "layer_decisions": layers,
        "variant_support": {
            "prefix": "run",
            "role_suffix": "build",
            "subagent": "none",
            "hook": "none",
        },
        "pattern_decisions": [
            {
                "decision": "use",
                "pattern_ref": "P1",
                "reason": "fit",
                "reuse_target": "existing",
            }
        ],
        "reproducibility_gates": {
            "lint": "PASS",
            "evaluator": "PASS",
            "elegant_review": "PASS",
            "governance": "N/A",
        },
        "script_execution_model": {
            "contexts": ["A", "B", "C", "D", "E"],
            "responsibility_matrix": "matrix",
            "priority_order": "order",
            "permission_boundary": "boundary",
            "scripts": [
                {
                    "path": "scripts/x.py",
                    "type": "validator",
                    "allowed_contexts": ["A", "B"],
                    "frontmatter_status": "PASS",
                }
            ],
        },
        "governance_model": {
            "rubric_version": "1.0.0",
            "rubric_hash": "abc",
            "proposal_required": "no",
            "impact_assessment": "low",
            "roles": {
                "proposer": "a",
                "reviewer": "b",
                "approver": "c",
                "tooling": "d",
            },
        },
        "dogfooding_model": {
            "artifact_type": "skill",
            "adapter": "skill-adapter",
            "forked_evaluator": "assign-skill-design-evaluator",
            "eval_log_path": "eval-log/x",
            "recursive_checks": ["check1"],
        },
        "rubric_composition_model": {"status": "N/A", "reason": "single rubric"},
        "paradigm_analogy_model": {"status": "N/A", "reason": "no analogy"},
        "output_routing_model": {"status": "N/A", "reason": "no routing"},
        "prompt_generation_model": {
            "policy_resolution": {
                "resolved_policy": "required",
                "resolved_via": "kind=run",
            },
            "per_responsibility": [
                {
                    "id": "R1",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),
                    "lint_status": "PASS",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
            "cross_ref": {
                "join_key": "responsibility.id",
                "prompt_creator_trace_path": "eval-log/pc.json",
            },
        },
        "prompt_provenance": {
            "prompt_creator_invocation": True,
            "source_contract_ref": "references/seven-layer-format.md",
            "content_lint": {"mode": "prompt", "status": "PASS"},
        },
        "feedback_contract": {
            "criteria": [
                {
                    "id": "IN1",
                    "loop_scope": "inner",
                    "text": "inner check",
                    "verify_by": "lint",
                },
                {
                    "id": "OUT1",
                    "loop_scope": "outer",
                    "text": "outer check",
                    "verify_by": "evaluator",
                },
            ]
        },
        "variable_contract": [
            {
                "name": "VAR",
                "meaning": "m",
                "default": "d",
                "required": True,
                "not_applicable_when": "never",
                "source_trace": "brief",
            }
        ],
    }


def _run_main_with_trace(tmp_path, trace, fname="skill-build-trace.json"):
    """trace を tmp に書いて in-process main() を駆動し (rc, captured) を返す。"""
    p = tmp_path / fname
    p.write_text(json.dumps(trace), encoding="utf-8")
    old = sys.argv
    sys.argv = ["validate-build-trace.py", str(p)]
    try:
        rc = M.main()
    finally:
        sys.argv = old
    return rc, p


def _run_main_argv(argv):
    old = sys.argv
    sys.argv = ["validate-build-trace.py"] + argv
    try:
        rc = M.main()
    finally:
        sys.argv = old
    return rc


# =====================================================================
# legacy trace mode: happy path
# =====================================================================

def test_full_trace_passes(tmp_path, capsys):
    rc, p = _run_main_with_trace(tmp_path, _full_trace())
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert f"ok: {p}" in out.out


# --- 各セクションの欠落/破壊で exit 1 と特定 err を assert -----------------

def test_missing_source_docs(tmp_path, capsys):
    t = _full_trace()
    del t["source_docs"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "source_docs must list" in capsys.readouterr().err


def test_source_docs_not_subset(tmp_path, capsys):
    t = _full_trace()
    t["source_docs"] = ["nonexistent-doc"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "must be a subset" in capsys.readouterr().err


def test_missing_context_map_decision(tmp_path, capsys):
    t = _full_trace()
    t["context_map_decision"] = "not-a-dict"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing context_map_decision" in capsys.readouterr().err


def test_context_map_missing_key(tmp_path, capsys):
    t = _full_trace()
    del t["context_map_decision"]["map"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "context_map_decision.map is empty" in capsys.readouterr().err


def test_missing_design_model(tmp_path, capsys):
    t = _full_trace()
    del t["design_model"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing design_model" in capsys.readouterr().err


def test_design_model_empty_key(tmp_path, capsys):
    t = _full_trace()
    t["design_model"]["intent"] = ""
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "design_model.intent is empty" in capsys.readouterr().err


def test_missing_build_step(tmp_path, capsys):
    t = _full_trace()
    t["build_flow_coverage"] = [
        i for i in t["build_flow_coverage"] if i["step"] != "naming"
    ]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing build_flow_coverage steps" in capsys.readouterr().err


def test_invalid_build_step_status(tmp_path, capsys):
    t = _full_trace()
    for item in t["build_flow_coverage"]:
        if item["step"] == "naming":
            item["status"] = "PASS"
            item["evidence"] = ""  # PASS requires evidence
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "invalid build_flow_coverage item: naming" in capsys.readouterr().err


def test_missing_doc_coverage(tmp_path, capsys):
    t = _full_trace()
    t["doc_coverage"] = [
        i for i in t["doc_coverage"] if i["doc"] != "03-frontmatter"
    ]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing doc_coverage items" in capsys.readouterr().err


def test_layer_invalid_decision(tmp_path, capsys):
    t = _full_trace()
    for item in t["layer_decisions"]:
        if item["layer"] == "Skill":
            item["decision"] = "maybe"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "layer_decisions.Skill invalid decision" in capsys.readouterr().err


def test_layer_missing_bool_key(tmp_path, capsys):
    t = _full_trace()
    for item in t["layer_decisions"]:
        if item["layer"] == "Hook":
            item["dependency_direction_ok"] = "yes"  # not bool
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "dependency_direction_ok must be boolean" in capsys.readouterr().err


def test_missing_layer(tmp_path, capsys):
    t = _full_trace()
    t["layer_decisions"] = [
        i for i in t["layer_decisions"] if i["layer"] != "MCP"
    ]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing layer_decisions" in capsys.readouterr().err


def test_missing_variant_support(tmp_path, capsys):
    t = _full_trace()
    del t["variant_support"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing variant_support" in capsys.readouterr().err


def test_variant_prefix_invalid(tmp_path, capsys):
    t = _full_trace()
    t["variant_support"]["prefix"] = "atomic"  # old spec value
    # skill_kind=run でも variant prefix が atomic → invalid。feedback は run なので
    # feedback_contract は inner+outer 揃っているため他で落ちない。
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "variant_support.prefix='atomic' not in" in capsys.readouterr().err


def test_variant_prefix_kind_crosscheck(tmp_path, capsys):
    """skill_path の SKILL.md frontmatter kind と prefix が食い違うと err。"""
    t = _full_trace()
    skill_dir = tmp_path / "genskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-x\nkind: assign\n---\nbody\n", encoding="utf-8"
    )
    t["skill_path"] = str(skill_dir)  # prefix=run but frontmatter kind=assign
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    err = capsys.readouterr().err
    assert "!= frontmatter.kind='assign'" in err


def test_missing_pattern_decisions(tmp_path, capsys):
    t = _full_trace()
    t["pattern_decisions"] = []
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing pattern_decisions" in capsys.readouterr().err


def test_pattern_decision_empty_field(tmp_path, capsys):
    t = _full_trace()
    t["pattern_decisions"][0]["reason"] = ""
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "pattern_decisions[0].reason is empty" in capsys.readouterr().err


def test_missing_reproducibility_gates(tmp_path, capsys):
    t = _full_trace()
    del t["reproducibility_gates"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing reproducibility_gates" in capsys.readouterr().err


def test_invalid_gate_status(tmp_path, capsys):
    t = _full_trace()
    t["reproducibility_gates"]["lint"] = "MAYBE"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "invalid gate status: lint" in capsys.readouterr().err


def test_missing_script_execution_model(tmp_path, capsys):
    t = _full_trace()
    del t["script_execution_model"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing script_execution_model" in capsys.readouterr().err


def test_script_contexts_missing(tmp_path, capsys):
    t = _full_trace()
    t["script_execution_model"]["contexts"] = ["A", "B"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "script_execution_model.contexts missing" in capsys.readouterr().err


def test_script_unknown_allowed_context(tmp_path, capsys):
    t = _full_trace()
    t["script_execution_model"]["scripts"][0]["allowed_contexts"] = ["A", "Z"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "allowed_contexts unknown" in capsys.readouterr().err


def test_missing_governance_model(tmp_path, capsys):
    t = _full_trace()
    del t["governance_model"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing governance_model" in capsys.readouterr().err


def test_governance_roles_missing(tmp_path, capsys):
    t = _full_trace()
    del t["governance_model"]["roles"]["approver"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "governance_model.roles missing" in capsys.readouterr().err


def test_governance_newly_failing_not_int(tmp_path, capsys):
    t = _full_trace()
    t["governance_model"]["newly_failing_count"] = "3"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "newly_failing_count must be integer" in capsys.readouterr().err


def test_missing_dogfooding_model(tmp_path, capsys):
    t = _full_trace()
    del t["dogfooding_model"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing dogfooding_model" in capsys.readouterr().err


def test_dogfooding_recursive_checks_empty(tmp_path, capsys):
    t = _full_trace()
    t["dogfooding_model"]["recursive_checks"] = []
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "recursive_checks must list" in capsys.readouterr().err


def test_optional_model_missing(tmp_path, capsys):
    t = _full_trace()
    del t["output_routing_model"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "missing output_routing_model" in capsys.readouterr().err


def test_optional_model_na_without_reason(tmp_path, capsys):
    t = _full_trace()
    t["paradigm_analogy_model"] = {"status": "N/A"}  # reason missing
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "paradigm_analogy_model.reason is required when N/A" in capsys.readouterr().err


def test_optional_model_pass_requires_keys(tmp_path, capsys):
    t = _full_trace()
    t["rubric_composition_model"] = {"status": "PASS"}  # keys missing
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    err = capsys.readouterr().err
    assert "rubric_composition_model.ordered_refs is empty" in err


def test_optional_model_bad_status(tmp_path, capsys):
    t = _full_trace()
    t["output_routing_model"] = {"status": "WHATEVER"}
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "output_routing_model.status must be PASS or N/A" in capsys.readouterr().err


def test_variable_contract_missing(tmp_path, capsys):
    t = _full_trace()
    t["variable_contract"] = []
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "variable_contract must list" in capsys.readouterr().err


def test_variable_contract_empty_field(tmp_path, capsys):
    t = _full_trace()
    t["variable_contract"][0]["meaning"] = ""
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "variable_contract[0].meaning is empty" in capsys.readouterr().err


# =====================================================================
# main() argv dispatch & file-level errors
# =====================================================================

def test_main_no_args_returns_2(capsys):
    rc = _run_main_argv([])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_file_not_found_returns_1(tmp_path, capsys):
    rc = _run_main_argv([str(tmp_path / "absent.json")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_main_empty_file_returns_1(tmp_path, capsys):
    p = tmp_path / "empty.json"
    p.write_text("   ", encoding="utf-8")
    rc = _run_main_argv([str(p)])
    assert rc == 1
    assert "is empty" in capsys.readouterr().err


def test_main_invalid_json_returns_2(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    rc = _run_main_argv([str(p)])
    assert rc == 2
    assert "invalid json" in capsys.readouterr().err


def test_main_too_many_args_returns_2(tmp_path, capsys):
    rc = _run_main_argv(["a.json", "b.json"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


def test_main_manifest_wrong_argc_returns_2(capsys):
    rc = _run_main_argv(["--manifest"])
    assert rc == 2
    assert "usage: --manifest" in capsys.readouterr().err


def test_main_bundle_wrong_argc_returns_2(capsys):
    rc = _run_main_argv(["--bundle"])
    assert rc == 2
    assert "usage: --bundle" in capsys.readouterr().err


# =====================================================================
# --self-test mode
# =====================================================================

def test_self_test_in_process(capsys):
    rc = _run_main_argv(["--self-test"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["self_test_pass"] is True
    assert len(payload["results"]) == 3


# =====================================================================
# --manifest mode (純関数 validate_manifest 経由)
# =====================================================================

def _valid_skill_manifest() -> dict:
    return {
        "name": "run-sample",
        "description": "サンプルスキルの発動条件宣言。テスト用 manifest 本文。",
        "kind": "skill",
        "version": "1.0.0",
        "owner": "team-test",
        "triggers": ["sample"],
        "contract": {"intent": "x", "interface": {}, "invariant": ["i1"]},
    }


def test_manifest_mode_valid_skill_md(tmp_path, capsys):
    md = tmp_path / "SKILL.md"
    fm = _valid_skill_manifest()
    lines = ["---"]
    lines.append(f"name: {fm['name']}")
    lines.append(f"description: {fm['description']}")
    lines.append(f"kind: {fm['kind']}")
    lines.append(f"version: {fm['version']}")
    lines.append(f"owner: {fm['owner']}")
    lines.append("triggers:")
    lines.append("  - sample")
    lines.append("contract:")
    lines.append("  intent: x")
    lines.append("  interface: {}")
    lines.append("  invariant:")
    lines.append("    - i1")
    lines.append("---")
    lines.append("body")
    md.write_text("\n".join(lines), encoding="utf-8")
    rc = _run_main_argv(["--manifest", str(md)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["valid"] is True
    assert out["kind"] == "skill"
    assert out["findings"] == []


def test_manifest_mode_file_not_found(tmp_path, capsys):
    rc = _run_main_argv(["--manifest", str(tmp_path / "absent.md")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["valid"] is False
    assert any("file not found" in f for f in out["findings"])


def test_manifest_mode_invalid_skill_missing_triggers(tmp_path, capsys):
    data = _valid_skill_manifest()
    del data["triggers"]
    p = tmp_path / "m.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rc = _run_main_argv(["--manifest", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("triggers" in f for f in out["findings"])


def test_manifest_json_invalid_json(tmp_path, capsys):
    p = tmp_path / "m.json"
    p.write_text("{bad", encoding="utf-8")
    rc = _run_main_argv(["--manifest", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("json parse error" in f for f in out["findings"])


def test_manifest_unsupported_extension(tmp_path, capsys):
    p = tmp_path / "m.txt"
    p.write_text("name: x", encoding="utf-8")
    rc = _run_main_argv(["--manifest", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("unsupported manifest extension" in f for f in out["findings"])


def test_manifest_yaml_root(tmp_path, capsys):
    data = _valid_skill_manifest()
    import yaml
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    rc = _run_main_argv(["--manifest", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["kind"] == "skill"


# =====================================================================
# --bundle mode
# =====================================================================

def test_bundle_mode_ok(tmp_path, capsys):
    # plugin root with real referenced capabilities
    plugin_root = tmp_path / "plugins" / "demo"
    (plugin_root / "skills" / "run-a").mkdir(parents=True)
    (plugin_root / "skills" / "run-a" / "SKILL.md").write_text("x", encoding="utf-8")
    bundle = {
        "name": "demo-bundle",
        "description": "デモ用 plugin-composition の検証バンドル本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team-test",
        "capabilities": [
            {"kind": "skill", "ref": "skills/run-a"},
            {"kind": "hook", "ref": "hook:virtual"},  # hook: は skip
        ],
    }
    bp = plugin_root / "plugin-composition.yaml"
    import yaml
    bp.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    rc = _run_main_argv(["--bundle", str(bp)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["valid"] is True


def test_bundle_mode_missing_ref(tmp_path, capsys):
    plugin_root = tmp_path / "plugins" / "demo"
    plugin_root.mkdir(parents=True)
    bundle = {
        "name": "demo-bundle",
        "description": "存在しない ref を持つ plugin-composition の失敗ケース本文。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team-test",
        "capabilities": [{"kind": "skill", "ref": "skills/missing"}],
    }
    import yaml
    bp = plugin_root / "plugin-composition.yaml"
    bp.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    rc = _run_main_argv(["--bundle", str(bp)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("ref not found: skills/missing" in f for f in out["findings"])


def test_bundle_mode_rejects_repo_relative_plugin_prefix(tmp_path, capsys):
    plugin_root = tmp_path / "plugins" / "demo"
    (plugin_root / "skills" / "run-a").mkdir(parents=True)
    (plugin_root / "skills" / "run-a" / "SKILL.md").write_text("x", encoding="utf-8")
    bundle = {
        "name": "demo-bundle",
        "description": "repo 相対 prefix を持つ plugin-composition の失敗ケース本文。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team-test",
        "capabilities": [{"kind": "skill", "ref": "plugins/demo/skills/run-a"}],
    }
    import yaml
    bp = plugin_root / "plugin-composition.yaml"
    bp.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    rc = _run_main_argv(["--bundle", str(bp)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("must be relative to plugin root" in f for f in out["findings"])


def test_bundle_mode_rejects_escape_and_absolute_refs(tmp_path, capsys):
    plugin_root = tmp_path / "plugins" / "demo"
    plugin_root.mkdir(parents=True)
    bundle = {
        "name": "demo-bundle",
        "description": "plugin root 外参照を持つ plugin-composition の失敗ケース本文。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team-test",
        "capabilities": [
            {"kind": "skill", "ref": "../other/skills/run-a"},
            {"kind": "command", "ref": "/tmp/commands/do.md"},
        ],
    }
    import yaml
    bp = plugin_root / "plugin-composition.yaml"
    bp.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    rc = _run_main_argv(["--bundle", str(bp)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("must not escape plugin root" in f for f in out["findings"])
    assert any("not absolute" in f for f in out["findings"])


def test_plugin_composition_dependency_endpoints_must_be_declared():
    data = {
        "name": "bundle-x",
        "description": "未宣言 endpoint を持つ plugin-composition 失敗ケース本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team",
        "capabilities": [{"kind": "skill", "ref": "skills/a"}],
        "dependencies": [{"from": "skills/a", "to": "skills/missing", "type": "calls"}],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("undeclared capability" in f for f in findings)


def test_plugin_composition_allows_deploys_dependency_type():
    data = {
        "name": "bundle-x",
        "description": "deploys edge を持つ plugin-composition 成功ケース本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team",
        "capabilities": [
            {"kind": "skill", "ref": "skills/a"},
            {"kind": "skill", "ref": "skills/b"},
        ],
        "dependencies": [{"from": "skills/a", "to": "skills/b", "type": "deploys"}],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is True, findings


def test_bundle_mode_ref_with_md_suffix(tmp_path, capsys):
    plugin_root = tmp_path / "plugins" / "demo"
    (plugin_root / "commands").mkdir(parents=True)
    (plugin_root / "commands" / "do.md").write_text("x", encoding="utf-8")
    bundle = {
        "name": "demo-bundle",
        "description": ".md 補完で解決される command ref を持つバンドル本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team-test",
        "capabilities": [{"kind": "command", "ref": "commands/do"}],
    }
    import yaml
    bp = plugin_root / "plugin-composition.yaml"
    bp.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    rc = _run_main_argv(["--bundle", str(bp)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out


def test_bundle_mode_load_error(tmp_path, capsys):
    rc = _run_main_argv(["--bundle", str(tmp_path / "absent.yaml")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("file not found" in f for f in out["findings"])


# =====================================================================
# validate_manifest 純関数: 各 kind dispatch
# =====================================================================

def test_validate_manifest_agent_ok():
    data = {
        "name": "agent-x",
        "description": "エージェントの最小妥当 manifest 本文記述テスト用。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "team",
        "tools": ["Read"],
        "isolation": "fork",
        "phase": "p1",
        "model": "opus",
    }
    valid, kind, findings = M.validate_manifest(data)
    assert valid is True, findings
    assert kind == "agent"


def test_validate_manifest_agent_bad_isolation():
    data = {
        "name": "agent-x",
        "description": "isolation が不正なエージェント失敗ケースの本文記述。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "team",
        "tools": ["Read"],
        "isolation": "weird",
        "phase": "p1",
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("isolation invalid" in f for f in findings)


def test_validate_manifest_hook_ok():
    data = {
        "name": "hook-x",
        "description": "フックの最小妥当 manifest 本文記述。十分な長さを確保。",
        "kind": "hook",
        "version": "1.0.0",
        "owner": "team",
        "event": "PreToolUse",
        "command": "scripts/h.py",
        "timeout_ms": 5000,
    }
    valid, kind, findings = M.validate_manifest(data)
    assert valid is True, findings
    assert kind == "hook"


def test_validate_manifest_hook_bad_event_and_timeout():
    data = {
        "name": "hook-x",
        "description": "イベントとタイムアウトが不正なフック失敗ケース本文記述。",
        "kind": "hook",
        "version": "1.0.0",
        "owner": "team",
        "event": "Nope",
        "command": "scripts/h.py",
        "timeout_ms": 999999,
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("hook.event" in f for f in findings)
    assert any("timeout_ms" in f for f in findings)


def test_validate_manifest_command_entrypoint_missing(tmp_path):
    data = {
        "name": "cmd-x",
        "description": "存在しない entrypoint を持つコマンド失敗ケース本文記述。",
        "kind": "command",
        "version": "1.0.0",
        "owner": "team",
        "argument-hint": "<arg>",
        "allowed-tools": ["Bash"],
        "entrypoint": "run-absent",
    }
    # manifest_path を plugins/<name>/commands/x.md に置いて plugin root を解決させる
    mpath = tmp_path / "plugins" / "demo" / "commands" / "x.md"
    mpath.parent.mkdir(parents=True)
    mpath.write_text("x", encoding="utf-8")
    valid, _, findings = M.validate_manifest(data, manifest_path=mpath)
    assert valid is False
    assert any("entrypoint" in f and "SKILL.md not found" in f for f in findings)


def test_validate_manifest_prompt_wrong_layer_count():
    data = {
        "name": "prompt-x",
        "description": "7層でないプロンプト失敗ケースの本文記述。十分な長さ。",
        "kind": "prompt",
        "version": "1.0.0",
        "owner": "team",
        "layers": [{"index": 1, "title": "t"}],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("exactly 7 items" in f for f in findings)


def test_validate_manifest_prompt_ok():
    data = {
        "name": "prompt-x",
        "description": "7層完備のプロンプト妥当ケースの本文記述。十分な長さ確保。",
        "kind": "prompt",
        "version": "1.0.0",
        "owner": "team",
        "layers": [{"index": i, "title": f"L{i}"} for i in range(1, 8)],
    }
    valid, kind, findings = M.validate_manifest(data)
    assert valid is True, findings
    assert kind == "prompt"


def test_validate_manifest_workflow_ok():
    data = {
        "name": "wf-x",
        "description": "ワークフローの最小妥当 manifest 本文記述。十分な長さ確保。",
        "kind": "workflow",
        "version": "1.0.0",
        "owner": "team",
        "phases": [{"id": "p1", "agents": ["assign-x"]}],
    }
    valid, kind, findings = M.validate_manifest(data)
    assert valid is True, findings
    assert kind == "workflow"


def test_validate_manifest_workflow_phase_missing_agents():
    data = {
        "name": "wf-x",
        "description": "agents 欠落 phase を持つワークフロー失敗ケースの本文記述。",
        "kind": "workflow",
        "version": "1.0.0",
        "owner": "team",
        "phases": [{"id": "p1"}],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("agents must be non-empty" in f for f in findings)


def test_validate_manifest_common_core_violations():
    data = {
        "name": "Bad_Name",  # uppercase/underscore
        "description": "短",  # too short (<10)
        "kind": "nonsense",  # invalid kind
        "version": "1.0",  # not semver
        "owner": "",  # empty
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    joined = " ".join(findings)
    assert "name=" in joined
    assert "description length" in joined
    assert "version=" in joined
    assert "owner" in joined


def test_validate_manifest_unknown_kind_dispatch():
    data = {
        "name": "x",
        "description": "妥当な共通核だが kind が dispatch 表に無いケースの本文記述。",
        "kind": "telemetry",  # not in _VALID_KINDS nor dispatch
        "version": "1.0.0",
        "owner": "team",
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("kind='telemetry'" in f for f in findings)


# =====================================================================
# _has_cycle / plugin-composition DAG
# =====================================================================

def test_has_cycle_true():
    assert M._has_cycle({"a": ["b"], "b": ["a"]}) is True


def test_has_cycle_false_dag():
    assert M._has_cycle({"a": ["b", "c"], "b": ["c"], "c": []}) is False


def test_has_cycle_self_loop():
    assert M._has_cycle({"a": ["a"]}) is True


def test_plugin_composition_cycle_detected():
    data = {
        "name": "bundle-x",
        "description": "依存に循環を持つ plugin-composition 失敗ケース本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team",
        "capabilities": [
            {"kind": "skill", "ref": "skills/a"},
            {"kind": "skill", "ref": "skills/b"},
        ],
        "dependencies": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "a"},
        ],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("contains cycle" in f for f in findings)


def test_plugin_composition_empty_capabilities():
    data = {
        "name": "bundle-x",
        "description": "capabilities が空の plugin-composition 失敗ケース本文記述。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team",
        "capabilities": [],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("must be non-empty array" in f for f in findings)


def test_plugin_composition_cap_missing_ref():
    data = {
        "name": "bundle-x",
        "description": "ref を欠く capability を持つ plugin-composition 失敗ケース本文。",
        "kind": "plugin-composition",
        "version": "1.0.0",
        "owner": "team",
        "capabilities": [{"kind": "skill"}],
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("ref missing" in f for f in findings)


# =====================================================================
# _load_frontmatter / _load_manifest
# =====================================================================

def test_load_frontmatter_no_delimiter():
    fm, err = M._load_frontmatter("no frontmatter here")
    assert fm is None
    assert "delimiter" in err


def test_load_frontmatter_no_closing():
    fm, err = M._load_frontmatter("---\nname: x\n(no close)")
    assert fm is None
    assert "closing" in err


def test_load_frontmatter_parses_mapping():
    fm, err = M._load_frontmatter("---\nname: run-x\nkind: skill\n---\nbody")
    assert err == ""
    assert fm["name"] == "run-x"
    assert fm["kind"] == "skill"


def test_load_manifest_yaml_not_mapping(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    data, err = M._load_manifest(p)
    assert data is None
    assert "must be a mapping" in err


def test_normalize_dates_recursive():
    import datetime
    obj = {"d": datetime.date(2026, 1, 2), "nested": [datetime.datetime(2026, 1, 2, 3, 4)]}
    out = M._normalize_dates(obj)
    assert out["d"] == "2026-01-02"
    assert out["nested"][0].startswith("2026-01-02")


# =====================================================================
# _validate_prompt_generation_model 純関数
# =====================================================================

def test_pgm_required_when_run_kind_missing():
    data = {"variant_support": {"prefix": "run"}}
    errs = M._validate_prompt_generation_model(data)
    assert any("prompt_generation_model is required" in e for e in errs)


def test_pgm_skip_kind_no_model_ok():
    data = {"variant_support": {"prefix": "ref"}}
    errs = M._validate_prompt_generation_model(data)
    assert errs == []


def test_pgm_resolved_policy_invalid():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "weird", "resolved_via": "x"},
            "per_responsibility": [],
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("resolved_policy invalid" in e for e in errs)


def test_pgm_skip_contradicts_run():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "skip", "resolved_via": "x"},
            "per_responsibility": [],
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("resolved_policy=skip contradicts" in e for e in errs)


def test_pgm_optional_contradicts_run_assign():
    # 精緻化: 生成物 (per_responsibility 非空) がある run/assign の optional 降格のみ禁止 (bypass)。
    for kind in ("run", "assign"):
        data = {
            "variant_support": {"prefix": kind},
            "prompt_generation_model": {
                "policy_resolution": {"resolved_policy": "optional", "resolved_via": "x"},
                "per_responsibility": [
                    {"id": "R1", "path_convention": "skill-local-v1",
                     "layer_yaml_path": "plugins/x/skills/run-y/prompts/R1.md",
                     "lint_status": "PASS"}
                ],
            },
        }
        errs = M._validate_prompt_generation_model(data)
        assert any("resolved_policy=optional contradicts" in e for e in errs)


def test_pgm_optional_without_prompts_ok_run_assign():
    # 精緻化: 生成物なし (per_responsibility 空=共有 prompt 消費) の run/assign は optional 許容。
    for kind in ("run", "assign"):
        data = {
            "variant_support": {"prefix": kind},
            "prompt_generation_model": {
                "policy_resolution": {"resolved_policy": "optional", "resolved_via": "shared prompt 消費"},
                "per_responsibility": [],
            },
        }
        errs = M._validate_prompt_generation_model(data)
        assert not any("resolved_policy=optional contradicts" in e for e in errs)


def test_pgm_required_contradicts_delegate():
    data = {
        "variant_support": {"prefix": "delegate"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "R1",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),
                    "lint_status": "PASS",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("resolved_policy=required contradicts" in e for e in errs)


def test_pgm_bad_id_and_path():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "BAD",  # not ^R[0-9]+$
                    "path_convention": "unknown-conv",
                    "layer_yaml_path": "wrong/path.md",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("must match ^R[0-9]+$" in e for e in errs)
    assert any("path_convention invalid" in e for e in errs)


def test_pgm_filename_id_mismatch():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "R2",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),  # stem R1 != id R2
                    "lint_status": "PASS",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("filename 'R1' != id 'R2'" in e for e in errs)


def test_pgm_lint_fail_requires_escalation():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "R1",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),
                    "lint_status": "FAIL",
                    "escalation": "none",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("requires escalation != none" in e for e in errs)


def test_pgm_anchor_missing_nonempty():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "R1",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),
                    "lint_status": "PASS",
                }
            ],
            "anchor_coverage": {"missing_anchors": ["A1"]},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("missing_anchors must be empty" in e for e in errs)


def test_pgm_cross_ref_bad_join_key():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [
                {
                    "id": "R1",
                    "path_convention": "skill-local-v1",
                    "layer_yaml_path": (
                        "plugins/harness-creator/skills/run-x/prompts/R1.md"
                    ),
                    "lint_status": "PASS",
                }
            ],
            "anchor_coverage": {"missing_anchors": []},
            "cross_ref": {"join_key": "wrong.key"},
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("join_key must be 'responsibility.id'" in e for e in errs)


def test_pgm_required_empty_per_resp():
    data = {
        "variant_support": {"prefix": "run"},
        "prompt_generation_model": {
            "policy_resolution": {"resolved_policy": "required", "resolved_via": "x"},
            "per_responsibility": [],
        },
    }
    errs = M._validate_prompt_generation_model(data)
    assert any("per_responsibility must not be empty" in e for e in errs)


# =====================================================================
# _validate_feedback_contract 純関数
# =====================================================================

def test_fc_run_missing_contract():
    data = {"skill_kind": "run"}
    errs = M._validate_feedback_contract(data)
    assert any("feedback_contract is required" in e for e in errs)


def test_fc_run_skip_reason_does_not_escape():
    # loop 実行系の skip_reason escape は FEEDBACK_SKIP_KINDS (ref/assign) 限定
    # (lint-feedback-contract.py と対称)。run の skip_reason は criteria 必須のまま。
    data = {"skill_kind": "run", "feedback_contract": {"skip_reason": "外部評価器に委譲"}}
    errs = M._validate_feedback_contract(data)
    assert errs and any("skip_reason escape は" in e for e in errs)


def test_fc_run_criteria_missing_inner():
    data = {
        "skill_kind": "run",
        "feedback_contract": {
            "criteria": [
                {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"}
            ]
        },
    }
    errs = M._validate_feedback_contract(data)
    assert any("include >=1 inner" in e for e in errs)


def test_fc_bad_id_and_verify_by():
    data = {
        "skill_kind": "run",
        "feedback_contract": {
            "criteria": [
                {"id": "X1", "loop_scope": "inner", "text": "t", "verify_by": "magic"},
                {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
            ]
        },
    }
    errs = M._validate_feedback_contract(data)
    assert any("must match" in e for e in errs)
    assert any("verify_by='magic' not in" in e for e in errs)


def test_fc_duplicate_id():
    data = {
        "skill_kind": "run",
        "feedback_contract": {
            "criteria": [
                {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
                {"id": "IN1", "loop_scope": "outer", "text": "t", "verify_by": "lint"},
            ]
        },
    }
    errs = M._validate_feedback_contract(data)
    assert any("duplicated" in e for e in errs)


def test_fc_ref_kind_with_bad_criteria_type():
    data = {"skill_kind": "ref", "feedback_contract": {"criteria": "not-a-list"}}
    errs = M._validate_feedback_contract(data)
    assert any("criteria must be array" in e for e in errs)


def test_fc_ref_kind_no_contract_ok():
    data = {"skill_kind": "ref"}
    errs = M._validate_feedback_contract(data)
    assert errs == []


def test_fc_unknown_kind_skips():
    data = {}  # kind unresolved -> skipped
    errs = M._validate_feedback_contract(data)
    assert errs == []


# =====================================================================
# subprocess entrypoint (exit code + coverage via sitecustomize)
# =====================================================================

def test_subprocess_self_test():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["self_test_pass"] is True


def test_subprocess_no_args_exit_2():
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_subprocess_valid_trace(tmp_path):
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(_full_trace()), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(p)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "ok:" in r.stdout


# =====================================================================
# 追加カバレッジ: 周辺分岐 (genuine な追加 assert)
# =====================================================================

def test_context_map_category_against_resource_map(tmp_path, capsys, monkeypatch):
    """context_map_decision.category が resource-map.yaml に無い値なら err。

    main() は cwd 相対の resource-map.yaml を探索するため、本物の
    plugins/harness-creator/.../resource-map.yaml が読めるよう cwd を ROOT にする。
    trace は tmp_path に置き、リポジトリは汚さない。
    """
    monkeypatch.chdir(ROOT)
    t = _full_trace()
    t["context_map_decision"]["category"] = "this-category-does-not-exist"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "not in resource-map.yaml" in capsys.readouterr().err


def test_context_map_category_known_passes(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    t = _full_trace()
    t["context_map_decision"]["category"] = "baseline-skill-build"
    rc, _ = _run_main_with_trace(tmp_path, t)
    out = capsys.readouterr()
    assert rc == 0, out.err


def test_script_item_not_object(tmp_path, capsys):
    t = _full_trace()
    t["script_execution_model"]["scripts"] = ["not-a-dict"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "scripts[0] must be object" in capsys.readouterr().err


def test_script_responsibility_matrix_empty(tmp_path, capsys):
    t = _full_trace()
    t["script_execution_model"]["responsibility_matrix"] = ""
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "responsibility_matrix is empty" in capsys.readouterr().err


def test_layer_missing_reason(tmp_path, capsys):
    t = _full_trace()
    for item in t["layer_decisions"]:
        if item["layer"] == "CLI":
            item["reason"] = ""
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "layer_decisions.CLI missing reason" in capsys.readouterr().err


def test_layer_deterministic_not_bool(tmp_path, capsys):
    t = _full_trace()
    for item in t["layer_decisions"]:
        if item["layer"] == "script":
            item["deterministic"] = "yes"
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "deterministic must be boolean" in capsys.readouterr().err


def test_pattern_decision_not_object(tmp_path, capsys):
    t = _full_trace()
    t["pattern_decisions"] = ["not-a-dict"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "pattern_decisions[0] must be object" in capsys.readouterr().err


def test_variable_contract_item_not_object(tmp_path, capsys):
    t = _full_trace()
    t["variable_contract"] = ["nope"]
    rc, _ = _run_main_with_trace(tmp_path, t)
    assert rc == 1
    assert "variable_contract[0] must be object" in capsys.readouterr().err


def test_prompt_layer_index_duplicate():
    data = {
        "name": "prompt-x",
        "description": "index 重複のプロンプト失敗ケースの本文記述。十分な長さ確保。",
        "kind": "prompt",
        "version": "1.0.0",
        "owner": "team",
        "layers": [{"index": 1, "title": "a"}] * 7,  # all index=1
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("index duplicated" in f for f in findings)


def test_agent_missing_tools():
    data = {
        "name": "agent-x",
        "description": "tools を欠くエージェント失敗ケースの本文記述。十分な長さ。",
        "kind": "agent",
        "version": "1.0.0",
        "owner": "team",
        "isolation": "fork",
        "phase": "p1",
    }
    valid, _, findings = M.validate_manifest(data)
    assert valid is False
    assert any("agent.tools must be non-empty" in f for f in findings)


def test_command_entrypoint_resolved_ok(tmp_path):
    """entrypoint が実在 SKILL.md を指すなら finding 無し。"""
    plugin_root = tmp_path / "plugins" / "demo"
    (plugin_root / "skills" / "run-target").mkdir(parents=True)
    (plugin_root / "skills" / "run-target" / "SKILL.md").write_text("x", encoding="utf-8")
    mpath = plugin_root / "commands" / "x.md"
    mpath.parent.mkdir(parents=True)
    mpath.write_text("x", encoding="utf-8")
    data = {
        "name": "cmd-x",
        "description": "entrypoint が実在する command 妥当ケースの本文記述。十分な長さ。",
        "kind": "command",
        "version": "1.0.0",
        "owner": "team",
        "argument-hint": "<arg>",
        "allowed-tools": ["Bash"],
        "entrypoint": "run-target",
    }
    valid, _, findings = M.validate_manifest(data, manifest_path=mpath)
    assert valid is True, findings


def test_resolve_plugin_root():
    p = Path("/x/plugins/demo/skills/run-a/SKILL.md")
    root = M._resolve_plugin_root(p)
    assert root is not None
    assert root.name == "demo"
