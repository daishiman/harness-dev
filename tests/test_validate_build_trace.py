"""validate-build-trace.py の feedback_contract 検査と manifest self-test を実証する。

評価フィードバックループ配線で追加された _validate_feedback_contract の核契約を固める:
  - loop 実行系 (run/wrap/delegate) は criteria を必須とし inner+outer を各1件以上課す
  - ref/assign は N/A escape (feedback_contract 不要、あっても配列形式のみ確認)
  - id は ^(IN|OUT|C)[0-9]+$ / verify_by は固定 enum に強制 (build-flags と同型)
これらは「per-skill 評価基準の漏れ防止」というユーザー要望の機械的担保点。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-build-trace.py"
)
SPEC = importlib.util.spec_from_file_location("validate_build_trace", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _valid_run_contract():
    """run kind の最小・正しい feedback_contract (inner+outer を含む)。"""
    return {
        "skill_kind": "run",
        "feedback_contract": {
            "criteria": [
                {
                    "id": "IN1",
                    "loop_scope": "inner",
                    "text": "ゴールシーク内ループで checklist を満たす",
                    "verify_by": "lint",
                },
                {
                    "id": "OUT1",
                    "loop_scope": "outer",
                    "text": "ハーネス全体で4条件 PASS",
                    "verify_by": "elegant-review",
                },
            ]
        },
    }


# --- 正常系 ---

def test_run_kind_valid_contract_has_no_errors():
    assert MOD._validate_feedback_contract(_valid_run_contract()) == []


def test_ref_kind_without_contract_is_na_escape():
    # ref は read-only 評価器: feedback_contract が無くてもエラーにしない。
    assert MOD._validate_feedback_contract({"skill_kind": "ref"}) == []


def test_loop_kind_skip_reason_does_not_escape_empty_criteria():
    # loop 実行系の skip_reason escape は封鎖 (FEEDBACK_SKIP_KINDS=ref/assign 限定。
    # lint-feedback-contract.py と対称)。
    data = {
        "skill_kind": "wrap",
        "feedback_contract": {"skip_reason": "委譲先で評価するため本体は N/A", "criteria": []},
    }
    errs = MOD._validate_feedback_contract(data)
    assert errs and any("skip_reason escape は" in e for e in errs)


def test_assign_kind_skip_reason_with_empty_criteria_is_na_escape():
    # ref/assign は kind 自体が escape 対象: skip_reason + 空 criteria でもエラーなし。
    data = {
        "skill_kind": "assign",
        "feedback_contract": {"skip_reason": "read-only 評価器のため N/A", "criteria": []},
    }
    assert MOD._validate_feedback_contract(data) == []


def test_unknown_kind_legacy_trace_is_not_checked():
    # kind 不明の旧トレースは破壊回避のため検査しない。
    assert MOD._validate_feedback_contract({}) == []


# --- 異常系: 漏れ / 形式違反を確実に検出する ---

def test_run_kind_missing_contract_is_error():
    errs = MOD._validate_feedback_contract({"skill_kind": "run"})
    assert errs and any("feedback_contract is required" in e for e in errs)


def test_run_kind_missing_outer_scope_is_error():
    data = _valid_run_contract()
    # outer を削って inner のみにする → outer 欠落を検出すべき。
    data["feedback_contract"]["criteria"] = [
        data["feedback_contract"]["criteria"][0]
    ]
    errs = MOD._validate_feedback_contract(data)
    assert any("outer" in e for e in errs)


def test_run_kind_bad_id_pattern_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][0]["id"] = "X9"  # IN|OUT|C 以外
    errs = MOD._validate_feedback_contract(data)
    assert any("must match" in e and "X9" in e for e in errs)


def test_run_kind_bad_verify_by_enum_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][0]["verify_by"] = "magic"
    errs = MOD._validate_feedback_contract(data)
    assert any("verify_by" in e and "magic" in e for e in errs)


def test_run_kind_duplicate_id_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][1]["id"] = "IN1"  # 重複
    errs = MOD._validate_feedback_contract(data)
    assert any("duplicated" in e for e in errs)


def test_ref_kind_non_list_criteria_is_error():
    data = {"skill_kind": "ref", "feedback_contract": {"criteria": "oops"}}
    errs = MOD._validate_feedback_contract(data)
    assert any("must be array" in e for e in errs)


# --- requirement_coverage (RTM): 要望被覆の機械検査 ---
#
# doc_coverage(参照知識)と対になる「ユーザー要望の被覆」。brief の非空要求フィールド
# 全てが mapped / not_applicable+reason で被覆されることを exit 1 検査する。
# 旧 trace は skip、brief 参照があるのに coverage 無しは WARN (段階導入)。

import json


def _brief_dict():
    """最小・現実的な brief。被覆対象は trigger_conditions / output_contract /
    key_constraints / goal / boundary の5フィールド (識別系は除外セット)。"""
    return {
        "skill_name": "run-x",
        "prefix": "run",
        "kind": "run",
        "hierarchy_level": "L1",
        "trigger_conditions": ["契約書を作りたいとき", "台帳から量産したいとき"],
        "output_contract": "生成物が黄色二系統で出力される",
        "key_constraints": ["トークンは Keychain のみ", "誤値より空欄優先"],
        "goal": "G を達成する",
        "boundary": "同定と補完のみ。与信判断は対象外",
    }


def _full_coverage():
    return [
        {"requirement_id": "trigger_conditions", "disposition": "mapped",
         "mapped_to": "SKILL.md description trigger句"},
        {"requirement_id": "output_contract", "disposition": "mapped",
         "mapped_to": "OUT1"},
        {"requirement_id": "key_constraints[0]", "disposition": "mapped",
         "mapped_to": "IN1"},
        {"requirement_id": "key_constraints[1]", "disposition": "not_applicable",
         "reason": "本 build では Notion 書込を行わないため対象外"},
        {"requirement_id": "goal", "disposition": "mapped",
         "mapped_to": "SKILL.md ゴールシーク実行節"},
        {"requirement_id": "boundary", "disposition": "mapped",
         "mapped_to": "SKILL.md 境界節"},
    ]


def _rtm_trace(tmp_path, coverage):
    """brief を tmp に書き、それを参照する trace dict と trace_path を返す。"""
    brief_p = tmp_path / "skill-brief.json"
    brief_p.write_text(json.dumps(_brief_dict()), encoding="utf-8")
    trace = {"brief_path": "skill-brief.json"}
    if coverage is not None:
        trace["requirement_coverage"] = coverage
    return trace, tmp_path / "skill-build-trace.json"


def test_requirement_coverage_full_passes(tmp_path):
    trace, tp = _rtm_trace(tmp_path, _full_coverage())
    assert MOD._validate_requirement_coverage(trace, tp) == []


def test_requirement_coverage_missing_field_fails(tmp_path):
    # boundary の被覆を落とす → 欠落フィールドとして検出すべき。
    cov = [c for c in _full_coverage() if c["requirement_id"] != "boundary"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert errs and any("missing=['boundary']" in e for e in errs)


def test_requirement_coverage_absent_old_trace_skips(tmp_path, capsys):
    # brief 参照も coverage も無い旧 trace: 検査せず WARN も出さない。
    errs = MOD._validate_requirement_coverage({}, tmp_path / "t.json")
    assert errs == []
    assert "WARN" not in capsys.readouterr().err


def test_requirement_coverage_absent_with_brief_ref_warns(tmp_path, capsys):
    # brief 情報 (source_docs) があるのに coverage 無し → WARN のみ (FAIL しない)。
    trace = {"source_docs": ["eval-log/skill-brief.json"]}
    errs = MOD._validate_requirement_coverage(trace, tmp_path / "t.json")
    assert errs == []
    assert "requirement_coverage" in capsys.readouterr().err


def test_requirement_coverage_unknown_field_fails(tmp_path):
    cov = _full_coverage() + [
        {"requirement_id": "nonexistent_field", "disposition": "mapped",
         "mapped_to": "x"}
    ]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("not found in brief" in e and "nonexistent_field" in e for e in errs)


def test_requirement_coverage_index_out_of_range_fails(tmp_path):
    cov = _full_coverage() + [
        {"requirement_id": "key_constraints[9]", "disposition": "mapped",
         "mapped_to": "x"}
    ]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("key_constraints[9]" in e and "not found" in e for e in errs)


def test_requirement_coverage_mapped_requires_mapped_to(tmp_path):
    cov = _full_coverage()
    del cov[1]["mapped_to"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("mapped_to is required" in e for e in errs)


def test_requirement_coverage_na_requires_reason(tmp_path):
    cov = _full_coverage()
    del cov[3]["reason"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("reason is required" in e for e in errs)


def test_requirement_coverage_bad_disposition_fails(tmp_path):
    cov = _full_coverage()
    cov[0]["disposition"] = "deferred"
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("disposition='deferred'" in e for e in errs)


def test_requirement_coverage_duplicate_id_fails(tmp_path):
    cov = _full_coverage() + [_full_coverage()[0]]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("duplicated" in e for e in errs)


def test_requirement_coverage_unresolvable_brief_warns_structural_only(tmp_path, capsys):
    # brief ファイルが無い場合は構造検査のみ (WARN)。cwd 依存で trace 資産を壊さない。
    trace = {
        "brief_path": "no-such-brief.json",
        "requirement_coverage": _full_coverage(),
    }
    errs = MOD._validate_requirement_coverage(trace, tmp_path / "t.json")
    assert errs == []
    assert "brief を解決できない" in capsys.readouterr().err


def test_requirement_coverage_brief_detected_from_source_docs(tmp_path):
    # brief_path 無しでも source_docs の skill-brief*.json から突合先を推定する。
    brief_p = tmp_path / "skill-brief.json"
    brief_p.write_text(json.dumps(_brief_dict()), encoding="utf-8")
    trace = {
        "source_docs": ["skill-brief.json"],
        "requirement_coverage": _full_coverage(),
    }
    assert MOD._validate_requirement_coverage(trace, tmp_path / "t.json") == []


def test_requirement_coverage_non_array_fails(tmp_path):
    trace, tp = _rtm_trace(tmp_path, None)
    trace["requirement_coverage"] = {"oops": True}
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert errs == ["requirement_coverage must be array"]


# --- C09: prompt_provenance バイパス不能性 (_validate_prompt_provenance) ---

def _required_pgm():
    """agent/prompt を実生成する build (resolved_policy=required) の最小 model。"""
    return {"prompt_generation_model": {"policy_resolution": {"resolved_policy": "required"}}}


def _valid_provenance():
    return {
        "prompt_creator_invocation": True,
        "source_contract_ref": "references/subagent-hybrid-format.md",
        "content_lint": {"mode": "agent", "status": "PASS"},
    }


def test_provenance_valid_required_build_has_no_errors():
    data = _required_pgm()
    data["prompt_provenance"] = _valid_provenance()
    assert MOD._validate_prompt_provenance(data) == []


def test_provenance_absent_on_required_build_fails():
    # policy=required なのに prompt_provenance 欠落 → バイパス試行を検出
    errs = MOD._validate_prompt_provenance(_required_pgm())
    assert errs and any("prompt_provenance is required" in e for e in errs)


def test_provenance_absent_on_optional_build_is_ok():
    # policy=optional の従来 build は後方互換で prompt_provenance 不要
    # (kind 未解決/非必須 kind のみ。run/assign は _validate_prompt_generation_model が弾く)。
    data = {"prompt_generation_model": {"policy_resolution": {"resolved_policy": "optional"}}}
    assert MOD._validate_prompt_provenance(data) == []


def test_pgm_run_assign_optional_downgrade_with_prompts_fails():
    # C09-1 (精緻化): 生成物 (per_responsibility 非空) があるのに resolved_policy=optional へ
    # 降格するのは prompt_provenance 必須化の迂回 (bypass) なので fail-closed にする。
    for kind in ("run", "assign"):
        data = {
            "variant_support": {"prefix": kind},
            "prompt_generation_model": {
                "policy_resolution": {
                    "resolved_policy": "optional",
                    "resolved_via": "brief override",
                },
                "per_responsibility": [
                    {"id": "R1", "path_convention": "skill-local-v1",
                     "layer_yaml_path": "plugins/x/skills/run-y/prompts/R1.md",
                     "lint_status": "PASS"}
                ],
            },
        }
        errs = MOD._validate_prompt_generation_model(data)
        assert any("resolved_policy=optional contradicts" in e for e in errs)
        assert MOD._validate_prompt_provenance(data) == []


def test_pgm_run_assign_optional_without_prompts_is_ok():
    # 精緻化: 本 build が prompt を生成しない run/assign (per_responsibility 空=共有 prompt 消費等)
    # は optional で宣言してよい。生成物がないため provenance 迂回にならない (例: run-company-master-build)。
    for kind in ("run", "assign"):
        data = {
            "variant_support": {"prefix": kind},
            "prompt_generation_model": {
                "policy_resolution": {
                    "resolved_policy": "optional",
                    "resolved_via": "上流/他skillが生成した共有 prompt を消費するため本 build は生成なし",
                },
                "per_responsibility": [],
            },
        }
        errs = MOD._validate_prompt_generation_model(data)
        assert not any("resolved_policy=optional contradicts" in e for e in errs)


def test_pgm_run_assign_skip_always_fails():
    # skip は生成物有無に関わらず run/assign では不可 (生成なしでも optional で宣言する)。
    for kind in ("run", "assign"):
        data = {
            "variant_support": {"prefix": kind},
            "prompt_generation_model": {
                "policy_resolution": {"resolved_policy": "skip", "resolved_via": "x"},
                "per_responsibility": [],
            },
        }
        errs = MOD._validate_prompt_generation_model(data)
        assert any("resolved_policy=skip contradicts" in e for e in errs)


def test_provenance_invocation_false_is_bypass_fail():
    # 単独生成 (prompt-creator 非経由) を宣言する trace は常に FAIL
    data = _required_pgm()
    prov = _valid_provenance()
    prov["prompt_creator_invocation"] = False
    data["prompt_provenance"] = prov
    errs = MOD._validate_prompt_provenance(data)
    assert errs and any("bypass detected" in e for e in errs)


def test_provenance_unknown_contract_ref_fails():
    data = _required_pgm()
    prov = _valid_provenance()
    prov["source_contract_ref"] = "references/some-other-doc.md"
    data["prompt_provenance"] = prov
    errs = MOD._validate_prompt_provenance(data)
    assert errs and any("must reference a 7層契約" in e for e in errs)


def test_provenance_content_lint_not_pass_fails():
    data = _required_pgm()
    prov = _valid_provenance()
    prov["content_lint"] = {"mode": "agent", "status": "FAIL"}
    data["prompt_provenance"] = prov
    errs = MOD._validate_prompt_provenance(data)
    assert errs and any("content_lint.status" in e for e in errs)


def test_provenance_content_lint_bad_mode_fails():
    data = _required_pgm()
    prov = _valid_provenance()
    prov["content_lint"] = {"mode": "schema", "status": "PASS"}
    data["prompt_provenance"] = prov
    errs = MOD._validate_prompt_provenance(data)
    assert errs and any("content_lint.mode invalid" in e for e in errs)


def _load_full_valid_trace():
    """CI が検証する実 trace (全必須トップフィールドを備える) を読み、E2E 受入の土台にする。"""
    import json
    return json.loads((ROOT / "eval-log" / "skill-build-trace.json").read_text(encoding="utf-8"))


def test_e2e_bypass_trace_exits_1(tmp_path):
    """受入例: prompt-creator 非経由 (invocation=false) の生成物 trace が CLI で exit1 になる。"""
    import json
    trace = _load_full_valid_trace()
    trace.setdefault("prompt_generation_model", {}).setdefault(
        "policy_resolution", {}
    )["resolved_policy"] = "required"
    trace["prompt_provenance"] = {
        "prompt_creator_invocation": False,  # ← バイパス試行
        "source_contract_ref": "references/subagent-hybrid-format.md",
        "content_lint": {"mode": "agent", "status": "PASS"},
    }
    p = tmp_path / "bypass-trace.json"
    p.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(p)], capture_output=True, text=True)
    assert proc.returncode == 1
    assert "bypass detected" in proc.stderr


# --- manifest 検証経路 (--self-test) が緑であること ---

def test_self_test_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
