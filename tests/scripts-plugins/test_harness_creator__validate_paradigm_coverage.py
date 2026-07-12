"""validate-paradigm-coverage.py の純関数 + main CLI 契約を network 無しで網羅する。

このスクリプトは network/secret を一切持たない (network: false / write-scope: none) ため、
全分岐を実入力で genuine に到達できる:

  - validate_structured_json: 正常 (全 30 paradigm + variable_abstraction) /
    invalid json / paradigm_findings 欠落・非リスト / item 非 object /
    paradigm_id 非 int / 欠落 id / meta 不一致 (name/category/agent) /
    observations 空・非リスト / issues 非リスト・非 object /
    issue condition・severity・description・recommended_intervention 不正 /
    variable_abstraction 非リスト・非 object・key 欠落・template でない
  - extract_text: lower-case 化
  - markdown 経路: 全 30 paradigm トークン網羅 OK / 欠落で MISSING
  - main: usage error (引数なし) / json OK / json fail / md OK / md missing

importlib.util.spec_from_file_location で実ファイルパスから直接ロードし純関数を呼ぶ。
main は subprocess(sys.executable) で起動し exit code / stdout / stderr を assert する。
tmp_path のみ使用し repo を汚さない。
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
    / "run-elegant-review"
    / "scripts"
    / "validate-paradigm-coverage.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_paradigm_coverage_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

def _full_findings() -> dict:
    """全 30 paradigm を EXPECTED_META 通りに埋めた合格 findings.json を組む。"""
    findings = []
    for pid in range(1, 31):
        name, category, agent = MOD.EXPECTED_META[pid]
        findings.append(
            {
                "paradigm_id": pid,
                "paradigm_name": name,
                "category": category,
                "agent": agent,
                "observations": [f"observation for paradigm {pid}"],
                "condition_matrix": {
                    "C1": {"verdict": "PASS", "evidence": [f"C1 checked {pid}"]},
                    "C2": {"verdict": "PASS", "evidence": [f"C2 checked {pid}"]},
                    "C3": {"verdict": "PASS", "evidence": [f"C3 checked {pid}"]},
                    "C4": {"verdict": "PASS", "evidence": [f"C4 checked {pid}"]},
                },
                "issues": [
                    {
                        "condition": "C1",
                        "severity": "high",
                        "description": f"issue desc {pid}",
                        "recommended_intervention": f"fix {pid}",
                    }
                ],
            }
        )
    return {
        "paradigm_findings": findings,
        # coverage.used は finding の paradigm_name から動的導出する。
        # validator L166-167 は finding ごとに EXPECTED_META[pid][0] (== paradigm_name)
        # が used に含まれることを要求するため、findings を単一ソースにして突合ズレを防ぐ。
        # 30 名は全 distinct なので len(used)==30 / skipped=[] で 30 網羅を満たす。
        "thought_method_coverage": {
            "total": 30,
            "used": [f["paradigm_name"] for f in findings],
            "skipped_with_reason": [],
        },
        "variable_abstraction": [
            {
                "concrete_value": "harness-creator",
                "variable_name": "{{plugin_name}}",
                "source_trace": "SKILL.md L1",
            }
        ],
    }


def _full_markdown() -> str:
    """全 30 paradigm の受理トークンを少なくとも1つずつ含む markdown 本文。"""
    lines = ["# elegant review"]
    for pid, tokens in MOD.PARADIGMS.items():
        # 最初のトークンを使う (ja or en)。lower-case 一致なので大文字混入も確認したい
        lines.append(f"## paradigm {pid}: {tokens[0]} の観点")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# extract_text
# --------------------------------------------------------------------------

def test_extract_text_lowercases(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("Critical THINKING MECE", encoding="utf-8")
    assert MOD.extract_text(p) == "critical thinking mece"


# --------------------------------------------------------------------------
# validate_structured_json: 正常系
# --------------------------------------------------------------------------

def test_structured_json_full_passes(tmp_path):
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(_full_findings(), ensure_ascii=False), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is True
    assert errors == []


def test_structured_json_empty_variable_abstraction_list_ok(tmp_path):
    # variable_abstraction は空リストでも (is list なので) OK
    data = _full_findings()
    data["variable_abstraction"] = []
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is True, errors


# --------------------------------------------------------------------------
# validate_structured_json: invalid json / 構造欠落
# --------------------------------------------------------------------------

def test_structured_json_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert errors == ["invalid json"]


def test_structured_json_missing_paradigm_findings_key(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"variable_abstraction": []}), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert errors == ["missing paradigm_findings"]


def test_structured_json_paradigm_findings_not_list(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"paradigm_findings": {"x": 1}}), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert errors == ["missing paradigm_findings"]


# --------------------------------------------------------------------------
# validate_structured_json: item レベルの異常
# --------------------------------------------------------------------------

def test_structured_json_item_not_object(tmp_path):
    data = _full_findings()
    data["paradigm_findings"].append("not-an-object")
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("is not an object" in e for e in errors)


def test_structured_json_paradigm_id_not_int(tmp_path):
    data = _full_findings()
    # 1件 paradigm_id を文字列に壊す → not int + missing id 31番扱いでなく当該欠落
    data["paradigm_findings"][0]["paradigm_id"] = "1"
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("paradigm_id is not int" in e for e in errors)
    # by_id に入らないので id=1 が missing にもなる
    assert any("missing paradigm_findings ids" in e for e in errors)


def test_structured_json_missing_some_ids(tmp_path):
    data = _full_findings()
    # 末尾2件を削除 → id 29,30 が欠落
    data["paradigm_findings"] = data["paradigm_findings"][:-2]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    miss = [e for e in errors if "missing paradigm_findings ids" in e]
    assert miss and "29" in miss[0] and "30" in miss[0]


# --------------------------------------------------------------------------
# validate_structured_json: meta 不一致
# --------------------------------------------------------------------------

def test_structured_json_meta_name_mismatch(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["paradigm_name"] = "WRONG"
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("expected paradigm_name=critical" in e for e in errors)


def test_structured_json_meta_category_and_agent_mismatch(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["category"] = "Z-wrong"
    data["paradigm_findings"][0]["agent"] = "wrong-agent"
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("expected category=A-logical" in e for e in errors)
    assert any("expected agent=elegant-logical-structural-analyst" in e for e in errors)


# --------------------------------------------------------------------------
# validate_structured_json: observations / issues 異常
# --------------------------------------------------------------------------

def test_structured_json_observations_empty(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["observations"] = ["   ", ""]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("observations must contain non-empty text" in e for e in errors)


def test_structured_json_observations_not_list(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["observations"] = "single string"
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("observations must contain non-empty text" in e for e in errors)


def test_structured_json_missing_condition_matrix_fails(tmp_path):
    data = _full_findings()
    del data["paradigm_findings"][0]["condition_matrix"]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("condition_matrix must cover C1-C4" in e for e in errors)


def test_structured_json_condition_matrix_empty_evidence_fails(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["condition_matrix"]["C2"]["evidence"] = []
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("condition_matrix.C2.evidence" in e for e in errors)


def test_structured_json_issues_not_list(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = {"condition": "C1"}
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("issues must be a list" in e for e in errors)


def test_structured_json_issue_not_object(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = ["plain-string-issue"]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("issue 0: not an object" in e for e in errors)


def test_structured_json_issue_invalid_condition_severity(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = [
        {
            "condition": "C9",  # 不正
            "severity": "fatal",  # 不正
            "description": "d",
            "recommended_intervention": "r",
        }
    ]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("invalid condition" in e for e in errors)
    assert any("invalid severity" in e for e in errors)


def test_structured_json_issue_missing_desc_and_intervention(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = [
        {
            "condition": "C1",
            "severity": "low",
            "description": "   ",  # 空白のみ
            # recommended_intervention 欠落
        }
    ]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("missing description" in e for e in errors)
    assert any("missing recommended_intervention" in e for e in errors)


def test_structured_json_empty_issues_list_is_ok(tmp_path):
    # issues は空リストでも is list なので OK (各 issue ループは回らない)
    data = _full_findings()
    for f in data["paradigm_findings"]:
        f["issues"] = []
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is True, errors


# --------------------------------------------------------------------------
# validate_structured_json: variable_abstraction 異常
# --------------------------------------------------------------------------

def test_structured_json_variable_abstraction_not_list(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = {"x": 1}
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("variable_abstraction must be a list" in e for e in errors)


def test_structured_json_variable_abstraction_item_not_object(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = ["not-an-object"]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("variable_abstraction[0] must be object" in e for e in errors)


def test_structured_json_variable_abstraction_missing_keys(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = [{"variable_name": "{{x}}"}]  # concrete_value/source_trace 欠落
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("missing concrete_value" in e for e in errors)
    assert any("missing source_trace" in e for e in errors)


def test_structured_json_variable_abstraction_not_template(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = [
        {
            "concrete_value": "v",
            "variable_name": "plain_name",  # {{ で始まらない
            "source_trace": "t",
        }
    ]
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("must be template variable" in e for e in errors)


# --------------------------------------------------------------------------
# markdown 経路 (純ロジックを main 経由でなく直接の text 走査では公開関数が無いため
# main を subprocess で叩いて契約として確認する。下の main セクションで網羅)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# main via subprocess
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_main_usage_error_no_args(tmp_path):
    r = _run([], tmp_path)
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_main_json_ok(tmp_path):
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(_full_findings(), ensure_ascii=False), encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "all 30 paradigms covered with structured findings" in r.stdout


def test_main_json_failure_exit1_emits_errors(tmp_path):
    data = _full_findings()
    data["paradigm_findings"] = data["paradigm_findings"][:-1]  # 1件欠落
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 1
    assert "missing paradigm_findings ids" in r.stderr


def test_main_markdown_ok_all_covered(tmp_path):
    p = tmp_path / "review.md"
    p.write_text(_full_markdown(), encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "all 30 paradigms covered" in r.stdout


def test_main_markdown_missing_paradigms_exit1(tmp_path):
    # 一切 paradigm トークンを含まない本文 → 30件全 missing
    p = tmp_path / "review.md"
    p.write_text("# empty review\nnothing relevant here\n", encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 1
    assert "MISSING paradigms (30/30)" in r.stderr


def test_main_markdown_partial_missing(tmp_path):
    # 1つだけ欠落させる: 全トークンを入れた上で paradigm 7 (mece) を除外
    lines = []
    for pid, tokens in MOD.PARADIGMS.items():
        if pid == 7:
            continue
        lines.append(tokens[0])
    p = tmp_path / "review.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 1
    assert "MISSING paradigms (1/30): [7]" in r.stderr


def test_main_non_json_suffix_treated_as_markdown(tmp_path):
    # .txt も markdown 経路 (suffix != .json) として扱われる
    p = tmp_path / "review.txt"
    p.write_text(_full_markdown(), encoding="utf-8")
    r = _run([str(p)], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "all 30 paradigms covered" in r.stdout
