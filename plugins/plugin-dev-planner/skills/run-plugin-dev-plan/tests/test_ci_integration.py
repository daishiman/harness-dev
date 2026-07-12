"""dogfooding: plugin-dev-planner 自身の CI/governance 配線が存在することを固定する。

本 plugin は『生成 plan に harness-creator 規律を課す』(layer a) だけでなく、自分自身も
その規律で CI 検証される (layer b = 自己適用) ことを保証する。CI 配線が静かに外れたら
本テストが落ちて気づける。標準 install (repo 外) では .github/workflows/ が無いため
skip する (単独 install 移植性を壊さない)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[5]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _read_or_skip(name: str) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        pytest.skip(f"{path} 不在 (repo 外の標準 install) — CI 配線テストは repo 文脈のみ")
    return path.read_text(encoding="utf-8")


def test_creator_kit_ci_discovers_all_plugin_test_files():
    """per-plugin pytest が plugins/** の test files を深さ非依存に収集する。

    固定 glob (plugins/*/tests, plugins/*/skills/*/tests) だけだと、scripts/tests や
    hooks/tests に加え、scripts/test_*.py / hooks/*_test.py のような tests/ 外 colocated
    test files も取りこぼすため、探索はファイル名ベースにする。
    """
    ci = _read_or_skip("harness-creator-kit-ci.yml")
    required = [
        'fnmatch.fnmatch(filename, "test_*.py")',
        'fnmatch.fnmatch(filename, "*_test.py")',
        'if "tests" in parts:',
        '"-m", "pytest", *args, "-q"',
        "no plugin test files discovered under plugins/**/{test_*.py,*_test.py}",
    ]
    missing = [text for text in required if text not in ci]
    assert missing == [], (
        "harness-creator-kit-ci.yml の per-plugin pytest が plugins/** の test files を "
        f"収集していない。欠落: {missing}"
    )


def test_governance_check_has_plugin_dev_planner_conformance():
    """governance-check.yml に plugin-dev-planner の conformance lint block がある (A4-10)。"""
    gov = _read_or_skip("governance-check.yml")
    required = [
        "validate-frontmatter.py --skills-dir plugins/plugin-dev-planner/skills",
        "lint-skill-name.py --skills-dir plugins/plugin-dev-planner/skills",
        "lint-skill-description.py --skills-dir plugins/plugin-dev-planner/skills",
        "lint-skill-completeness.py --skills-dir plugins/plugin-dev-planner/skills",
    ]
    missing = [r for r in required if r not in gov]
    assert missing == [], f"governance-check.yml に plugin-dev-planner conformance 配線が欠落: {missing}"


def test_governance_check_has_harness_coverage_selfcheck():
    """governance-check.yml に harness-coverage 12軸自己適用 (C3・dogfooding) の配線がある。

    『生成 plan に課すハーネス規律を自分自身へも適用する』layer b の CI 配線が静かに外れたら
    本テストが落ちて気づける (self-application の断線検出)。
    """
    gov = _read_or_skip("governance-check.yml")
    assert "check-harness-coverage-selfcheck.py" in gov, (
        "governance-check.yml に plugin-dev-planner の harness-coverage 自己適用 step が欠落"
    )


def test_evals_surfaces_each_have_enforced_by():
    """EVALS.surfaces の各面に enforced_by 宣言がある (宣言 surface の被覆漏れ防止・A2-4)。"""
    evals = json.loads((PLUGIN_ROOT / "EVALS.json").read_text(encoding="utf-8"))
    enforced = evals.get("surfaces_enforced_by", {})
    missing = [s for s in evals["surfaces"] if not str(enforced.get(s, "")).strip()]
    assert missing == [], f"enforced_by 宣言が欠落した surface: {missing}"


def test_handoff_gate_green_from_skill_dir_cwd():
    """CI が cd する skill dir cwd から handoff gate (旧 cwd 依存) が exit0 になることを
    subprocess で実証する。配線『文字列の存在』だけでなく『配線したゲートが CI cwd で緑』を
    検査し、wiring と実挙動の乖離を防ぐ (harness-creator-kit-ci は各 plugin/skill dir へ cd して pytest)。
    """
    import subprocess
    import sys

    skill_dir = PLUGIN_ROOT / "skills" / "run-plugin-dev-plan"
    handoff_rel = "examples/sample-plan/handoff-run-plugin-dev-plan.json"
    if not (skill_dir / handoff_rel).is_file():
        pytest.skip("sample handoff 不在")
    result = subprocess.run(
        [sys.executable, "scripts/check-build-handoff.py", handoff_rel],
        cwd=str(skill_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"skill dir cwd から handoff gate が FAIL (cwd 依存の回帰): {result.stderr}"
    )
