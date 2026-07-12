"""Genuine functional tests for run-build-skill/scripts/render-frontmatter.py.

Covers the constrained {{var}} / {{var | default("...")}} renderer, value
normalization, default parsing, truthiness helper, the OS-preamble dynamic
context contract, brief->mapping projection, generated steps/checks/gotchas/
variable-contract builders, and the feedback-contract mapping (fallback +
brief-driven). main() is exercised via subprocess on real templates and on each
argument-validation error path (exit 2). This script declares network: false
and write-scope: none, so no external I/O occurs; --out writes only under
tmp_path.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
SCRIPT = RUN_BUILD / "scripts" / "render-frontmatter.py"
TEMPLATES = RUN_BUILD / "templates"


def _load():
    spec = importlib.util.spec_from_file_location("render_frontmatter", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


# ── render ───────────────────────────────────────────────────────────────
def test_render_substitutes_present_value():
    assert mod.render("hi {{name}}", {"name": "bob"}) == "hi bob"


def test_render_uses_default_when_missing():
    assert mod.render('x {{k | default("D")}}', {}) == "x D"


def test_render_empty_value_falls_back_to_default():
    assert mod.render('x {{k | default("D")}}', {"k": ""}) == "x D"


def test_render_missing_without_default_yields_empty():
    assert mod.render("[{{nope}}]", {}) == "[]"


def test_render_list_value_is_bracketed():
    assert mod.render("{{xs}}", {"xs": ["a", "b"]}) == "[a, b]"


def test_render_empty_list_uses_default():
    # empty list is "falsy" so the default branch applies
    assert mod.render("{{xs | default([])}}", {"xs": []}) == "[]"


# ── _normalize_value ─────────────────────────────────────────────────────
def test_normalize_value_variants():
    assert mod._normalize_value(["a", "b"]) == "[a, b]"
    assert mod._normalize_value([]) == "[]"
    assert mod._normalize_value(None) == ""
    assert mod._normalize_value(5) == "5"
    assert mod._normalize_value("plain") == "plain"


# ── _parse_default ───────────────────────────────────────────────────────
def test_parse_default_strips_quotes():
    assert mod._parse_default('"hi"') == "hi"
    assert mod._parse_default("'hi'") == "hi"


def test_parse_default_keeps_collection_literals():
    assert mod._parse_default("[]") == "[]"
    assert mod._parse_default("{}") == "{}"


def test_parse_default_none_is_empty():
    assert mod._parse_default(None) == ""


# ── is_true ──────────────────────────────────────────────────────────────
def test_is_true_bool_and_strings():
    assert mod.is_true(True) is True
    assert mod.is_true(False) is False
    assert mod.is_true("true") is True
    assert mod.is_true("True") is True
    assert mod.is_true("false") is False
    assert mod.is_true("garbage") is False


# ── apply_dynamic_context_contract ───────────────────────────────────────
def test_dynamic_context_no_preamble_when_not_required():
    src = "---\nname: x\n---\nbody\n"
    assert mod.apply_dynamic_context_contract(src, {"cross_platform": "false"}) == src


def test_dynamic_context_injects_preamble_and_frontmatter_keys():
    src = "---\nname: x\n---\nbody\n"
    out = mod.apply_dynamic_context_contract(src, {"cross_platform": "true"})
    assert mod.OS_PREAMBLE in out
    assert "cross_platform: true" in out
    assert "os_preamble_required: true" in out
    assert 'os=unknown' in out


def test_dynamic_context_no_frontmatter_prepends_preamble():
    out = mod.apply_dynamic_context_contract("plain body\n", {"os_preamble_required": "true"})
    assert out.startswith(mod.OS_PREAMBLE)
    assert "plain body" in out


# ── _feedback_contract_mapping ───────────────────────────────────────────
def test_feedback_contract_fallback_from_skill_name():
    m = mod._feedback_contract_mapping({"skill_name": "run-foo"})
    assert m["feedback_contract_max_iterations"] == 3
    assert "run-foo の完了チェックリスト" in m["feedback_contract_inner_criteria_text"]
    assert "run-elegant-review の4条件" in m["feedback_contract_outer_criteria_text"]


def test_feedback_contract_inner_from_deterministic_checks():
    m = mod._feedback_contract_mapping(
        {"skill_name": "run-foo", "deterministic_checks": ["lint A", "lint B"]}
    )
    assert m["feedback_contract_inner_criteria_text"] == "lint A / lint B"


def test_feedback_contract_explicit_criteria_override():
    m = mod._feedback_contract_mapping(
        {
            "skill_name": "run-foo",
            "feedback_contract": {
                "max_iterations": 7,
                "criteria": [
                    {"id": "IN1", "loop_scope": "inner", "text": "INNER X"},
                    {"id": "OUT1", "loop_scope": "outer", "text": "OUTER Y"},
                ],
            },
        }
    )
    assert m["feedback_contract_max_iterations"] == 7
    assert m["feedback_contract_inner_criteria_text"] == "INNER X"
    assert m["feedback_contract_outer_criteria_text"] == "OUTER Y"


# ── generated builders ───────────────────────────────────────────────────
def test_generated_steps_appends_optional_sections():
    base = mod._generated_steps([], [], [], [])
    assert base.startswith("1. 入力 brief")
    rich = mod._generated_steps(["chk"], ["cand"], ["pat"], ["evt"])
    assert "決定論的検査を script" in rich
    assert "配置判断を" in rich
    assert "採用パターンを適用" in rich
    assert "Hook 配線案" in rich


def test_generated_checks_includes_reuse_and_checks():
    out = mod._generated_checks(["chk1"], ["reuseX"])
    assert "validate-frontmatter.py" in out
    assert "決定論的検査: chk1" in out
    assert "横展開候補: reuseX" in out


def test_generated_gotchas_conditional_lines():
    base = mod._generated_gotchas([], [])
    assert "TODO" in base
    extra = mod._generated_gotchas(["pat"], ["axis"])
    assert "negative cases" in extra
    assert "variant_axes" in extra


def test_variable_contract_lists_items():
    out = mod._variable_contract(["av"], ["ti"], ["ng"])
    assert "変数化対象: av" in out
    assert "入力変数: ti" in out
    assert "非対象: ng" in out


# ── brief_mapping ────────────────────────────────────────────────────────
def test_brief_mapping_projects_fields(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps(
            {
                "skill_name": "run-demo",
                "kind": "run",
                "output_contract": "demo を作る",
                "trigger_conditions": ["条件1", "条件2"],
                "key_constraints": ["制約A", "制約B"],
                "deterministic_checks": ["lint X"],
                "additional_resources": [
                    {"path": "references/a.md", "when_to_read": "詳細時"}
                ],
            }
        ),
        encoding="utf-8",
    )
    m = mod.brief_mapping(brief)
    assert m["name"] == "run-demo"
    assert m["kind"] == "run"
    assert m["output_contract"] == "demo を作る"
    assert m["trigger1"] == "条件1"
    assert m["trigger2"] == "条件2"
    assert "1. 制約A" in m["key_constraints"]
    assert "2. 制約B" in m["key_constraints"]
    assert "- `references/a.md`: 詳細時" in m["additional_resources"]
    # feedback contract mapping merged in
    assert m["feedback_contract_inner_criteria_text"] == "lint X"


def test_brief_mapping_defaults_for_sparse_brief(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "run-x"}), encoding="utf-8")
    m = mod.brief_mapping(brief)
    assert m["trigger1"] == "ユーザーが依頼した"
    assert m["trigger2"] == "ワークフローで必要になった"
    assert m["verb"] == "実行する"
    assert m["key_constraints"].startswith("1. 未設定")


# ── CLI main via subprocess ──────────────────────────────────────────────
def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_cli_renders_run_template():
    proc = _run(
        "--name", "run-demo", "--kind", "run", "--template", str(TEMPLATES / "run.md")
    )
    assert proc.returncode == 0, proc.stderr
    # placeholders must be fully resolved
    assert "{{" not in proc.stdout
    assert "run-demo" in proc.stdout


def test_cli_template_not_found_exit_2():
    proc = _run("--name", "run-x", "--kind", "run", "--template", "/no/such.md")
    assert proc.returncode == 2
    assert "template not found" in proc.stderr


def test_cli_name_kind_mismatch_exit_2():
    proc = _run(
        "--name", "ref-x", "--kind", "run", "--template", str(TEMPLATES / "run.md")
    )
    assert proc.returncode == 2
    assert "name/kind mismatch" in proc.stderr


def test_cli_template_kind_mismatch_exit_2():
    proc = _run(
        "--name", "run-x", "--kind", "run", "--template", str(TEMPLATES / "ref.md")
    )
    assert proc.returncode == 2
    assert "template/kind mismatch" in proc.stderr


def test_cli_brief_not_found_exit_2():
    proc = _run(
        "--name", "run-x", "--kind", "run",
        "--template", str(TEMPLATES / "run.md"),
        "--brief", "/no/such/brief.json",
    )
    assert proc.returncode == 2
    assert "brief not found" in proc.stderr


def test_cli_wrap_requires_base_skill(tmp_path):
    brief = tmp_path / "b.json"
    brief.write_text(json.dumps({"skill_name": "wrap-x", "kind": "wrap"}), encoding="utf-8")
    proc = _run(
        "--name", "wrap-x", "--kind", "wrap",
        "--template", str(TEMPLATES / "wrap.md"),
        "--brief", str(brief),
    )
    assert proc.returncode == 2
    assert "wrap requires base_skill" in proc.stderr


def test_cli_delegate_requires_delegate_agent(tmp_path):
    brief = tmp_path / "b.json"
    brief.write_text(
        json.dumps({"skill_name": "delegate-x", "kind": "delegate"}), encoding="utf-8"
    )
    proc = _run(
        "--name", "delegate-x", "--kind", "delegate",
        "--template", str(TEMPLATES / "delegate.md"),
        "--brief", str(brief),
    )
    assert proc.returncode == 2
    assert "delegate requires delegate_agent" in proc.stderr


def test_cli_brief_kind_mismatch_exit_2(tmp_path):
    brief = tmp_path / "b.json"
    brief.write_text(json.dumps({"skill_name": "run-x", "kind": "ref"}), encoding="utf-8")
    proc = _run(
        "--name", "run-x", "--kind", "run",
        "--template", str(TEMPLATES / "run.md"),
        "--brief", str(brief),
    )
    assert proc.returncode == 2
    assert "brief/kind mismatch" in proc.stderr


def test_cli_pair_and_rubric_refs_substituted():
    proc = _run(
        "--name", "assign-x", "--kind", "assign",
        "--template", str(TEMPLATES / "assign-generator.md"),
        "--pair", "assign-x-evaluator",
        "--rubric-refs", "r1,r2",
    )
    assert proc.returncode == 0, proc.stderr
    assert "assign-x-evaluator" in proc.stdout
    assert "{{" not in proc.stdout


def test_cli_writes_out_file(tmp_path):
    out = tmp_path / "deep" / "SKILL.md"
    proc = _run(
        "--name", "run-demo", "--kind", "run",
        "--template", str(TEMPLATES / "run.md"),
        "--out", str(out),
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "{{" not in text
    assert "run-demo" in text
