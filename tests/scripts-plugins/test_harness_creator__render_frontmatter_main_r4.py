"""Genuine functional tests (scripts4) for
plugins/harness-creator/skills/run-build-skill/scripts/render-frontmatter.py.

既存の tests/scripts-plugins/test_harness_creator__render_frontmatter.py は純関数中心で
main() (344-458) が丸ごと未到達 (71%)。本ファイルは main() の各分岐を sys.argv 駆動で
in-process カバーし、加えて純関数の未到達枝 (outer criteria 上書き / _parse_default の
quote 剥がし / apply_dynamic_context_contract の closing 無し) を埋める。

network なし。すべての I/O は tmp_path に限定し repo を汚さない。テンプレートは
run-build-skill/templates/ の実ファイルを使う (genuine レンダリング)。

他ディレクトリ test と basename 衝突しないよう `_main_r4` サフィックスを付す。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
SCRIPT = RUN_BUILD / "scripts" / "render-frontmatter.py"
TEMPLATES = RUN_BUILD / "templates"

_SPEC = importlib.util.spec_from_file_location("render_frontmatter_main_r4", SCRIPT)
RF = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RF)


# ============================================================
# 純関数の未到達枝
# ============================================================

def test_feedback_contract_outer_criteria_override():
    """criteria に outer scope があれば outer を上書き (line ~71-77)。"""
    data = {
        "skill_name": "run-x",
        "feedback_contract": {
            "max_iterations": 7,
            "criteria": [
                {"loop_scope": "inner", "text": "内側基準テキスト"},
                {"loop_scope": "outer", "text": "外側基準テキスト"},
                {"loop_scope": "bogus", "text": "無視される"},
                "not-a-dict",
            ],
        },
    }
    out = RF._feedback_contract_mapping(data)
    assert out["feedback_contract_max_iterations"] == 7
    assert out["feedback_contract_inner_criteria_text"] == "内側基準テキスト"
    assert out["feedback_contract_outer_criteria_text"] == "外側基準テキスト"


def test_feedback_contract_fallback_uses_deterministic_checks():
    data = {"skill_name": "run-y", "deterministic_checks": ["lintA 通過", "schemaB 検証"]}
    out = RF._feedback_contract_mapping(data)
    assert out["feedback_contract_inner_criteria_text"] == "lintA 通過 / schemaB 検証"
    # outer は goal ベース fallback
    assert "run-elegant-review の4条件" in out["feedback_contract_outer_criteria_text"]


def test_feedback_contract_fallback_no_checks():
    data = {"skill_name": "run-z"}
    out = RF._feedback_contract_mapping(data)
    assert "完了チェックリスト" in out["feedback_contract_inner_criteria_text"]


def test_parse_default_strips_quotes():
    # line ~91-95: クォート除去
    assert RF._parse_default('"hello"') == "hello"
    assert RF._parse_default("'world'") == "world"
    assert RF._parse_default("[]") == "[]"
    assert RF._parse_default("{}") == "{}"
    assert RF._parse_default("bare") == "bare"
    assert RF._parse_default(None) == ""


def test_apply_dynamic_context_contract_no_closing_frontmatter():
    """frontmatter 開始のみで closing --- 無し → OS_PREAMBLE を前置 (line ~134)。"""
    content = "---\nname: x\nno closing fence here"
    out = RF.apply_dynamic_context_contract(content, {"cross_platform": True})
    assert out.startswith(RF.OS_PREAMBLE)


def test_apply_dynamic_context_contract_disabled_returns_unchanged():
    content = "---\nname: x\n---\nbody"
    assert RF.apply_dynamic_context_contract(content, {}) == content


def test_apply_dynamic_context_contract_no_frontmatter_prefixes_preamble():
    content = "plain body no frontmatter"
    out = RF.apply_dynamic_context_contract(content, {"os_preamble_required": "true"})
    assert out.startswith(RF.OS_PREAMBLE)
    assert "plain body" in out


def test_apply_dynamic_context_contract_injects_into_frontmatter_and_body():
    content = "---\nname: x\n---\n\n# Heading\nbody text\n"
    out = RF.apply_dynamic_context_contract(content, {"cross_platform": True})
    # frontmatter に cross_platform / os_preamble_required が追記
    fm = out.split("---", 2)[1]
    assert "cross_platform: true" in fm
    assert "os_preamble_required: true" in fm
    # body 冒頭に OS preamble + os=unknown fallback
    assert RF.OS_PREAMBLE in out
    assert 'os=unknown' in out


def test_is_true_variants():
    assert RF.is_true(True) is True
    assert RF.is_true(False) is False
    assert RF.is_true("true") is True
    assert RF.is_true("TRUE") is True
    assert RF.is_true("no") is False
    assert RF.is_true(1) is False  # bool でなく str("1") != "true"


def test_normalize_value_list_and_none():
    assert RF._normalize_value([]) == "[]"
    assert RF._normalize_value(["a", "b"]) == "[a, b]"
    assert RF._normalize_value(None) == ""
    assert RF._normalize_value(5) == "5"


def test_render_uses_default_when_missing():
    tmpl = '{{present}} / {{absent | default("DEF")}} / {{empty | default([])}}'
    out = RF.render(tmpl, {"present": "P", "empty": []})
    assert out == "P / DEF / []"


# ============================================================
# main(): argv 駆動ヘルパ
# ============================================================

def _run_main(monkeypatch, argv, capsys=None):
    monkeypatch.setattr(sys, "argv", ["render-frontmatter.py", *argv])
    return RF.main()


def test_main_template_not_found(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, ["--name", "run-x", "--kind", "run",
                                 "--template", str(tmp_path / "nope.md")])
    assert rc == 2
    assert "template not found" in capsys.readouterr().err


def test_main_name_kind_mismatch(monkeypatch, capsys):
    # name prefix 'ref' != kind 'run'
    rc = _run_main(monkeypatch, ["--name", "ref-thing", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md")])
    assert rc == 2
    assert "name/kind mismatch" in capsys.readouterr().err


def test_main_template_kind_mismatch(monkeypatch, capsys):
    # ref.md は kind=run に対して不正テンプレート
    rc = _run_main(monkeypatch, ["--name", "run-x", "--kind", "run",
                                 "--template", str(TEMPLATES / "ref.md")])
    assert rc == 2
    assert "template/kind mismatch" in capsys.readouterr().err


def test_main_render_run_to_stdout(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ["--name", "run-demo", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "name: run-demo" in out
    # placeholder が全部展開され {{ }} が残らない
    assert "{{" not in out
    # feedback_contract criteria の inner/outer が埋まる (fallback)
    assert "完了チェックリスト" in out or "loop_scope: inner" in out


def test_main_render_ref_kind(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ["--name", "ref-thing", "--kind", "ref",
                                 "--template", str(TEMPLATES / "ref.md")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "name: ref-thing" in out
    assert "{{" not in out


def test_main_writes_to_out_file(monkeypatch, tmp_path):
    outp = tmp_path / "sub" / "SKILL.md"
    rc = _run_main(monkeypatch, ["--name", "run-w", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--out", str(outp)])
    assert rc == 0
    assert outp.exists()
    text = outp.read_text(encoding="utf-8")
    assert "name: run-w" in text and "{{" not in text


def test_main_brief_not_found(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, ["--name", "run-b", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--brief", str(tmp_path / "missing.json")])
    assert rc == 2
    assert "brief not found" in capsys.readouterr().err


def test_main_brief_kind_mismatch(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "run-b", "kind": "ref"}), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "run-b", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--brief", str(brief)])
    assert rc == 2
    assert "brief/kind mismatch" in capsys.readouterr().err


def test_main_brief_overrides_render(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({
        "skill_name": "run-real",
        "kind": "run",
        "trigger_conditions": ["特定条件で発火", "別の発火条件"],
        "output_contract": "JSON を 1 件返す",
        "deterministic_checks": ["lintQ"],
        "feedback_contract": {"max_iterations": 5,
                              "criteria": [{"loop_scope": "outer", "text": "外側OK"}]},
    }), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "run-real", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--brief", str(brief)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "特定条件で発火" in out
    assert "別の発火条件" in out
    # criteria outer 上書きが反映
    assert "外側OK" in out
    # inner は deterministic_checks fallback
    assert "lintQ" in out


def test_main_wrap_requires_base_skill(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "wrap-x", "kind": "wrap"}), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "wrap-x", "--kind", "wrap",
                                 "--template", str(TEMPLATES / "wrap.md"),
                                 "--brief", str(brief)])
    assert rc == 2
    assert "wrap requires base_skill" in capsys.readouterr().err


def test_main_wrap_with_base_skill_ok(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "wrap-x", "kind": "wrap",
                                 "base_skill": "run-existing"}), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "wrap-x", "--kind", "wrap",
                                 "--template", str(TEMPLATES / "wrap.md"),
                                 "--brief", str(brief)])
    assert rc == 0
    assert "{{" not in capsys.readouterr().out


def test_main_delegate_requires_delegate_agent(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "delegate-x", "kind": "delegate"}), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "delegate-x", "--kind", "delegate",
                                 "--template", str(TEMPLATES / "delegate.md"),
                                 "--brief", str(brief)])
    assert rc == 2
    assert "delegate requires delegate_agent" in capsys.readouterr().err


def test_main_pair_override(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ["--name", "assign-x", "--kind", "assign",
                                 "--template", str(TEMPLATES / "assign-evaluator.md"),
                                 "--pair", "run-x-generator"])
    assert rc == 0
    # pair 指定で generator/evaluator が埋まる; テンプレに pair 変数があれば反映
    assert "{{" not in capsys.readouterr().out


def test_main_rubric_refs_split(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ["--name", "run-r", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--rubric-refs", "ref-a, ref-b ,"])
    assert rc == 0
    out = capsys.readouterr().out
    # rubric_refs リストが [ref-a, ref-b] として展開され upstream-rubric=ref-a
    assert "ref-a" in out and "ref-b" in out


def test_main_cross_platform_brief_injects_preamble(monkeypatch, tmp_path, capsys):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"skill_name": "run-cp", "kind": "run",
                                 "cross_platform": True}), encoding="utf-8")
    rc = _run_main(monkeypatch, ["--name", "run-cp", "--kind", "run",
                                 "--template", str(TEMPLATES / "run.md"),
                                 "--brief", str(brief)])
    assert rc == 0
    out = capsys.readouterr().out
    assert RF.OS_PREAMBLE in out


# ============================================================
# brief_mapping: 直接呼んで生成系・additional_resources を網羅
# ============================================================

def test_brief_mapping_additional_resources_and_generated(tmp_path):
    brief = tmp_path / "b.json"
    brief.write_text(json.dumps({
        "skill_name": "run-g",
        "kind": "run",
        "trigger_conditions": ["t1", "t2", "t3"],
        "key_constraints": ["制約1", "制約2"],
        "additional_resources": [
            {"path": "doc/x.md", "when_to_read": "設計時"},
            {"path": "doc/y.md"},
            {"no_path": "skip"},
        ],
        "deterministic_checks": ["chk1"],
        "placement_candidates": ["Skill", "Hook"],
        "pattern_refs": ["pat1"],
        "variant_axes": ["axis1"],
        "reuse_targets": ["reuseA"],
        "hook_events": ["PostToolUse"],
    }), encoding="utf-8")
    m = RF.brief_mapping(brief)
    assert m["name"] == "run-g" and m["kind"] == "run"
    assert m["trigger1"] == "t1" and m["trigger3"] == "t3"
    assert "1. 制約1" in m["key_constraints"] and "2. 制約2" in m["key_constraints"]
    # additional_resources は path 行のみ; when_to_read 有/無 両方
    assert "- `doc/x.md`: 設計時" in m["additional_resources"]
    assert "- `doc/y.md`" in m["additional_resources"]
    assert "skip" not in m["additional_resources"]
    # generated_steps に placement/deterministic/pattern/hook が反映
    assert "配置判断" in m["generated_steps"]
    assert "決定論的検査" in m["generated_steps"]
    assert "採用パターン" in m["generated_steps"]
    assert "Hook 配線案" in m["generated_steps"]
    # generated_checks に reuse_targets
    assert "横展開候補" in m["generated_checks"]
    # generated_gotchas に pattern/variant 注意
    assert "negative cases" in m["generated_gotchas"]
    assert "variant_axes" in m["generated_gotchas"]


def test_brief_mapping_defaults_when_minimal(tmp_path):
    brief = tmp_path / "b.json"
    brief.write_text(json.dumps({"skill_name": "run-min"}), encoding="utf-8")
    m = RF.brief_mapping(brief)
    assert m["trigger1"] == "ユーザーが依頼した"
    assert m["trigger2"] == "ワークフローで必要になった"
    assert m["trigger3"] == ""
    assert m["key_constraints"].startswith("1. 未設定")
    assert m["additional_resources"] == ""


def test_generated_helpers_empty_inputs():
    assert "入力 brief と境界" in RF._generated_steps([], [], [], [])
    assert "validate-frontmatter.py" in RF._generated_checks([], [])
    assert "固有名詞" in RF._generated_gotchas([], [])
    assert "パラメーター名" in RF._variable_contract([], [], [])


def test_variable_contract_with_items():
    out = RF._variable_contract(["AV"], ["TI"], ["NG"])
    assert "変数化対象: AV" in out
    assert "入力変数: TI" in out
    assert "非対象: NG" in out
