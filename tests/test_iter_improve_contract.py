"""run-skill-iter-improve の契約テスト。

検査対象:
  1. schemas/interrogation-log.schema.json (D11 審問ログ契約) の正負検証。
     独立判定の発火条件 (|score_delta|>10 または評価経路接触) と
     「緩め判定 / 緩め禁止抵触 → 破棄必須」の機械強制を固定する。
  2. SKILL.md frontmatter 契約: validate-frontmatter.py 通過 +
     feedback_contract.criteria が feedback_contract_ssot.validate_criteria を通過。
  3. 本文が参照する SSOT (convergence-policy loop_bounds.iter_improve /
     ENGINE_SKILLS / goal-spec forbidden_loosening) の実在 parity (dangling 参照防止)。
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import feedback_contract_ssot as FC  # noqa: E402

SKILL_DIR = ROOT / "plugins/harness-creator/skills/run-skill-iter-improve"
SCHEMA_PATH = SKILL_DIR / "schemas/interrogation-log.schema.json"
SKILL_MD = SKILL_DIR / "SKILL.md"
GOAL_SPEC_SCHEMA = (
    ROOT / "plugins/harness-creator/skills/run-goal-elicit/schemas/goal-spec.schema.json"
)
CONVERGENCE_POLICY = (
    ROOT
    / "plugins/harness-creator/skills/run-elegant-review/references/convergence-policy.json"
)
VALIDATE_FRONTMATTER = (
    ROOT / "plugins/skill-governance-lint/scripts/validate-frontmatter.py"
)


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema)


def _base_entry() -> dict:
    """全 required を満たす最小正例 (通常 iter: 急変なし・評価経路非接触)。"""
    return {
        "iter": 1,
        "proposed_changes": [
            {
                "path": "plugins/x/skills/y/SKILL.md",
                "summary": "writer-prompt に用語リスト規約を追加",
                "touches_evaluation_path": False,
            }
        ],
        "self_interrogation": {
            "is_generator_improvement": True,
            "rationale": "成果物生成側の規約強化で評価経路に触れない",
        },
        "forbidden_loosening_check": {"violated": False, "matched_rule": None},
        "score_delta": 3.0,
        "independent_check": {
            "required": False,
            "verdict": None,
            "agent_independent": False,
        },
        "discarded": False,
    }


def _is_valid(validator, entry) -> bool:
    return not list(validator.iter_errors(entry))


# --- 正例 ------------------------------------------------------------------


def test_normal_iter_passes(validator):
    assert _is_valid(validator, _base_entry())


def test_score_surge_with_independent_check_passes(validator):
    e = _base_entry()
    e["score_delta"] = 15.0
    e["independent_check"] = {
        "required": True,
        "verdict": "generator",
        "agent_independent": True,
    }
    assert _is_valid(validator, e)


def test_eval_path_touch_with_independent_check_passes(validator):
    e = _base_entry()
    e["proposed_changes"][0]["touches_evaluation_path"] = True
    e["independent_check"] = {
        "required": True,
        "verdict": "generator",
        "agent_independent": True,
    }
    assert _is_valid(validator, e)


def test_loosening_verdict_discarded_passes(validator):
    e = _base_entry()
    e["score_delta"] = 20.0
    e["independent_check"] = {
        "required": True,
        "verdict": "loosening",
        "agent_independent": True,
    }
    e["discarded"] = True
    assert _is_valid(validator, e)


def test_forbidden_violation_discarded_passes(validator):
    e = _base_entry()
    e["forbidden_loosening_check"] = {
        "violated": True,
        "matched_rule": "採点 mode を lenient に固定する",
    }
    e["discarded"] = True
    assert _is_valid(validator, e)


# --- 負例: 独立判定の発火条件 (|score_delta|>10 or 評価経路接触) ------------


def test_score_surge_without_independent_check_fails(validator):
    e = _base_entry()
    e["score_delta"] = 15.0  # +10pt 超なのに required=False のまま
    assert not _is_valid(validator, e)


def test_score_drop_without_independent_check_fails(validator):
    e = _base_entry()
    e["score_delta"] = -12.0  # 対称: -10pt 超の急降下
    assert not _is_valid(validator, e)


def test_boundary_10pt_does_not_require_check(validator):
    e = _base_entry()
    e["score_delta"] = 10.0  # 「超」なので 10.0 ちょうどは発火しない
    assert _is_valid(validator, e)


def test_eval_path_touch_without_independent_check_fails(validator):
    e = _base_entry()
    # score 急変なし・自己申告 Yes でも、評価経路接触は客観条件として独立判定必須
    e["proposed_changes"][0]["touches_evaluation_path"] = True
    assert not _is_valid(validator, e)


def test_required_true_with_null_verdict_fails(validator):
    e = _base_entry()
    e["independent_check"] = {
        "required": True,  # 必要と判定したのに未実施 (verdict null)
        "verdict": None,
        "agent_independent": False,
    }
    assert not _is_valid(validator, e)


def test_verdict_without_agent_independence_fails(validator):
    e = _base_entry()
    e["score_delta"] = 15.0
    e["independent_check"] = {
        "required": True,
        "verdict": "generator",
        "agent_independent": False,  # 別個体性なしの判定は無効 (D11)
    }
    assert not _is_valid(validator, e)


# --- 負例: 破棄強制 (INVARIANT 1/8) ----------------------------------------


def test_loosening_verdict_not_discarded_fails(validator):
    e = _base_entry()
    e["score_delta"] = 20.0
    e["independent_check"] = {
        "required": True,
        "verdict": "loosening",
        "agent_independent": True,
    }
    e["discarded"] = False  # 外部判定「緩め」を無視して採用するのは違反
    assert not _is_valid(validator, e)


def test_forbidden_violation_not_discarded_fails(validator):
    e = _base_entry()
    e["forbidden_loosening_check"] = {
        "violated": True,
        "matched_rule": "threshold を下げる",
    }
    e["discarded"] = False
    assert not _is_valid(validator, e)


# --- 負例: 構造契約 ----------------------------------------------------------


@pytest.mark.parametrize("missing", sorted(_base_entry().keys()))
def test_missing_required_key_fails(validator, missing):
    e = _base_entry()
    del e[missing]
    assert not _is_valid(validator, e)


def test_additional_property_fails(validator):
    e = _base_entry()
    e["note"] = "additionalProperties false"
    assert not _is_valid(validator, e)


def test_invalid_verdict_enum_fails(validator):
    e = _base_entry()
    e["independent_check"] = {
        "required": True,
        "verdict": "maybe",
        "agent_independent": True,
    }
    assert not _is_valid(validator, e)


def test_empty_proposed_changes_fails(validator):
    e = _base_entry()
    e["proposed_changes"] = []
    assert not _is_valid(validator, e)


def test_iter_zero_fails(validator):
    # GOAL DECLARATION (iter 0) は goal-spec 側の記録であり審問ログは 1 始まり
    e = _base_entry()
    e["iter"] = 0
    assert not _is_valid(validator, e)


# --- SKILL.md frontmatter 契約 ----------------------------------------------


def _frontmatter() -> dict:
    text = SKILL_MD.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def test_validate_frontmatter_passes():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE_FRONTMATTER), str(SKILL_MD)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_feedback_contract_criteria_pass_ssot():
    fm = _frontmatter()
    criteria = fm["feedback_contract"]["criteria"]
    assert FC.validate_criteria(criteria) == []
    # criteria は genuine 導出 (fallback 同語反復の焼き込みでない)
    assert not any(FC.is_fallback_text(c["text"]) for c in criteria)


def test_common_core_keys_present():
    fm = _frontmatter()
    for key in ("name", "description", "kind", "version", "owner"):
        assert fm.get(key), f"commonCore 必須キー欠落: {key}"
    assert fm["kind"] == "run"
    assert fm["name"] == "run-skill-iter-improve"


# --- SSOT parity (dangling 参照防止) -----------------------------------------


def test_loop_bounds_iter_improve_params_exist():
    policy = json.loads(CONVERGENCE_POLICY.read_text(encoding="utf-8"))
    params = policy["loop_bounds"]["iter_improve"]["params"]
    for key in (
        "max_iter",
        "batch_per_iter_max",
        "parallel_agents_default",
        "score_threshold_default",
    ):
        assert key in params, f"loop_bounds.iter_improve.params.{key} 不在"
    # 本文はパラメータ名参照のみ (生値の二重宣言禁止) — 参照文字列の実在を固定
    body = SKILL_MD.read_text(encoding="utf-8")
    assert "loop_bounds.iter_improve" in body


def test_engine_closure_includes_self():
    # INVARIANT 7: 本 skill はエンジン閉包に属し、自己適用時は被験体コピー必須
    assert "run-skill-iter-improve" in FC.ENGINE_SKILLS
    assert FC.requires_subject_copy("harness-creator", "run-skill-iter-improve") is True
    assert FC.requires_subject_copy("harness-creator", "run-skill-rename") is False


def test_goal_spec_has_forbidden_loosening_field():
    # D3: 緩め禁止リストは goal-spec 拡張 field へ格納 (goal-declaration.md が参照)
    schema = json.loads(GOAL_SPEC_SCHEMA.read_text(encoding="utf-8"))
    assert "forbidden_loosening" in schema["properties"]
    assert "forbidden_loosening" not in schema.get("required", [])
