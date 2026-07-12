from __future__ import annotations

# /// script
# name: test-run-blueprint-apply-criteria-coverage
# purpose: run-blueprint-apply の feedback_contract criteria (IN1/OUT1) を実ゲート起動で被覆検証する。
#   skill-local に criteria id を紐付けて LLM-coverage の被覆源を genuine に成立させる。
# inputs:
#   - scripts/doc-emit.py --check-apply (IN1 決定論ゲート / OUT1 接地・追跡性の受入検証)
#   - SKILL.md + prompts/R1-ground.md (IN1 C02 receipt受理 / network 0 境界)
# outputs:
#   - pytest assertions (実 exit code)
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]  # skills/run-blueprint-apply/tests -> plugin root
DOC_EMIT = PLUGIN_ROOT / "scripts" / "doc-emit.py"
SKILL_ROOT = PLUGIN_ROOT / "skills" / "run-blueprint-apply"


def _check_apply(apply_path, blueprint_path):
    return subprocess.run(
        [sys.executable, str(DOC_EMIT), "--check-apply", str(apply_path), "--blueprint", str(blueprint_path)],
        capture_output=True, text=True,
    )


def _write(p, obj):
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_in1_check_apply_gate_exit0_on_valid_and_exit1_on_invalid(tmp_path):
    """IN1: doc-emit.py --check-apply が exit0 (全項目 kind=inference・分類 adopt|avoid|differentiate・
    evidence_refs の blueprint 実在 anchor 解決率 100%・kind=fact 新規レコード 0) を確認する。

    valid apply-recommendation で exit0、契約違反 (kind=fact / anchor 未解決) で exit1 を実起動で要求する。
    """
    blueprint = _write(tmp_path / "blueprint.json", {"anchors": ["hero", "nav"]})
    valid = _write(tmp_path / "valid.json", [{
        "kind": "inference", "category": "adopt", "claim": "採用する",
        "own_context_ref": "our-stack",
        "confidence": {"level": "high", "rationale": "observed"},
        "evidence_refs": ["hero"],
    }])
    assert _check_apply(valid, blueprint).returncode == 0
    invalid = _write(tmp_path / "invalid.json", [{"kind": "fact", "category": "copy", "evidence_refs": ["missing"]}])
    assert _check_apply(invalid, blueprint).returncode == 1


def test_in1_receipt_and_network_boundaries_are_fail_closed():
    """IN1: 機械shape gate以外の受理条件も、R1と最小権限frontmatterへ固定されている。"""
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    ground = (SKILL_ROOT / "prompts" / "R1-ground.md").read_text(encoding="utf-8")

    assert "mcp_tools: []" in skill
    assert "external_systems: []" in skill
    assert "verdict=PASS" in ground
    assert "draft_hash" in ground
    assert "不在/FAIL/hash 不一致" in ground
    assert "対象 origin へ一切アクセスしない (network 0)" in ground


def test_out1_recommendations_grounded_and_traceable(tmp_path):
    """OUT1: apply-recommendations が自社コンテキストへ接地した採用/回避/差別化になっており、
    blueprint 外の無根拠主張 0 件で、独立レビューアが evidence_refs+confidence から各判断を追跡できる
    ことを受入検証する。

    adopt/avoid/differentiate 三分類がそれぞれ evidence_refs (blueprint anchor 解決) と confidence を
    携えて通過し、blueprint anchor 外を参照する主張は落とされる (fail-closed) ことを実起動で確認する。
    """
    blueprint = _write(tmp_path / "blueprint.json", {"anchors": ["hero", "pricing", "footer"]})
    grounded = _write(tmp_path / "grounded.json", [
        {"kind": "inference", "category": "adopt", "claim": "採用", "own_context_ref": "our-stack",
         "confidence": {"level": "high", "rationale": "既存資産と適合"}, "evidence_refs": ["hero"]},
        {"kind": "inference", "category": "avoid", "claim": "回避", "own_context_ref": "our-stack",
         "confidence": {"level": "medium", "rationale": "運用コスト過大"}, "evidence_refs": ["pricing"]},
        {"kind": "inference", "category": "differentiate", "claim": "差別化", "own_context_ref": "our-stack",
         "confidence": {"level": "medium", "rationale": "独自価値"}, "evidence_refs": ["footer"]},
    ])
    assert _check_apply(grounded, blueprint).returncode == 0
    # blueprint anchor 外を参照する = 無根拠主張は追跡不能ゆえ落とす。
    unfounded = _write(tmp_path / "unfounded.json", [
        {"kind": "inference", "category": "adopt", "claim": "根拠なし", "own_context_ref": "our-stack",
         "confidence": {"level": "low", "rationale": "推測"}, "evidence_refs": ["not-in-blueprint"]},
    ])
    assert _check_apply(unfounded, blueprint).returncode == 1
