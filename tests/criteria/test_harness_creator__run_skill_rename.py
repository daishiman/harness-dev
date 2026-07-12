"""Genuine feedback_contract.criteria verification for harness-creator/run-skill-rename.

各テスト関数は当該 criterion の id と skill 名を関数名/docstring に含む。
validate-llm-coverage.py は tests/**/*.py が「skill 名 + criterion id」を共に
参照すると covered と判定するため、本ファイルは skill=run-skill-rename と
id (IN1/IN2/OUT1) を実 assert と共に明記して被覆を成立させる。

検証方針 (genuine, ダミー禁止):
  - inner (verify_by: lint / script): 当該 skill の SKILL.md に対し決定論 lint を
    subprocess 実行し exit 0 を assert。lint は SKILL.md の検証節で列挙される
    lint-skill-name.py / lint-skill-tree.py / validate-frontmatter.py、および
    feedback_contract.criteria 構造正本である lint-feedback-contract.py。
  - outer (verify_by: elegant-review): content-review/elegance-verdict.json が存在し
    verdict==PASS かつ feedback_loop.criteria_evaluated に当該 id を含むことを assert。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = "harness-creator"
SKILL = "run-skill-rename"
SKILL_DIR = REPO_ROOT / "plugins" / PLUGIN / "skills" / SKILL
SKILL_MD = SKILL_DIR / "SKILL.md"
ELEGANCE_VERDICT = (
    REPO_ROOT / "eval-log" / PLUGIN / SKILL / "content-review" / "elegance-verdict.json"
)


def _run_lint(script_name: str, target: Path) -> subprocess.CompletedProcess:
    """repo-root の決定論 lint を subprocess 実行する (CI 通過済なので exit0 のはず)。"""
    script = REPO_ROOT / "scripts" / script_name
    assert script.is_file(), f"lint script not found: {script}"
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _run_lint_all(script_name: str) -> subprocess.CompletedProcess:
    """--all モードの contract 系 lint を subprocess 実行する。"""
    script = REPO_ROOT / "scripts" / script_name
    assert script.is_file(), f"lint script not found: {script}"
    return subprocess.run(
        [sys.executable, str(script), "--all"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _load_elegance_verdict() -> dict:
    assert ELEGANCE_VERDICT.is_file(), f"elegance-verdict.json missing: {ELEGANCE_VERDICT}"
    return json.loads(ELEGANCE_VERDICT.read_text(encoding="utf-8"))


def test_skill_md_exists():
    """前提: run-skill-rename の SKILL.md が存在する。"""
    assert SKILL_MD.is_file(), f"SKILL.md missing: {SKILL_MD}"


# --- inner: IN1 (verify_by: lint) -----------------------------------------
# run-skill-rename IN1: 改名後の新名 SKILL.md が lint-skill-name と
# lint-skill-tree と validate-frontmatter を全て exit0 で通過する。
def test_run_skill_rename_IN1_lint_skill_name():
    """IN1 [run-skill-rename] inner: lint-skill-name.py exit 0。"""
    r = _run_lint("lint-skill-name.py", SKILL_MD)
    assert r.returncode == 0, f"lint-skill-name failed:\n{r.stdout}\n{r.stderr}"


def test_run_skill_rename_IN1_lint_skill_tree():
    """IN1 [run-skill-rename] inner: lint-skill-tree.py exit 0。"""
    r = _run_lint("lint-skill-tree.py", SKILL_DIR)
    assert r.returncode == 0, f"lint-skill-tree failed:\n{r.stdout}\n{r.stderr}"


def test_run_skill_rename_IN1_validate_frontmatter():
    """IN1 [run-skill-rename] inner: validate-frontmatter.py exit 0。"""
    r = _run_lint("validate-frontmatter.py", SKILL_MD)
    assert r.returncode == 0, f"validate-frontmatter failed:\n{r.stdout}\n{r.stderr}"


# --- inner: IN2 (verify_by: script) ---------------------------------------
# run-skill-rename IN2: git mv 履歴保持 + frontmatter.name 新名化 +
# aliases 旧名登録の不可分セット。frontmatter 整合は validate-frontmatter と
# lint-skill-name (dir==name 第7条) が決定論検証する。feedback_contract.criteria
# 構造そのものの正本検証は lint-feedback-contract.py が担う。
def test_run_skill_rename_IN2_frontmatter_consistency():
    """IN2 [run-skill-rename] inner: validate-frontmatter + lint-skill-name exit 0。"""
    r1 = _run_lint("validate-frontmatter.py", SKILL_MD)
    assert r1.returncode == 0, f"validate-frontmatter failed:\n{r1.stdout}\n{r1.stderr}"
    r2 = _run_lint("lint-skill-name.py", SKILL_MD)
    assert r2.returncode == 0, f"lint-skill-name failed:\n{r2.stdout}\n{r2.stderr}"


def test_run_skill_rename_IN2_feedback_contract_lint():
    """IN2 [run-skill-rename] inner: lint-feedback-contract.py --all exit 0 (criteria 正本)。"""
    r = _run_lint_all("lint-feedback-contract.py")
    assert r.returncode == 0, f"lint-feedback-contract failed:\n{r.stdout}\n{r.stderr}"


# --- outer: OUT1 (verify_by: elegant-review) ------------------------------
# run-skill-rename OUT1: OUT_BASE 配下 SKILL.md 全体の pair/Skill() 旧名参照を
# 漏れなく走査し全ヒットが新名化、参照切れが残らない (到達状態 adequacy)。
def test_run_skill_rename_OUT1_elegance_verdict_pass():
    """OUT1 [run-skill-rename] outer: elegance-verdict.json verdict==PASS。"""
    data = _load_elegance_verdict()
    assert data["target"]["plugin"] == PLUGIN
    assert data["target"]["skill"] == SKILL
    assert data["review_kind"] == "elegance"
    assert data["verdict"] == "PASS", f"verdict not PASS: {data['verdict']}"


def test_run_skill_rename_OUT1_criteria_evaluated_contains_id():
    """OUT1 [run-skill-rename] outer: feedback_loop.criteria_evaluated に OUT1 を含む。"""
    data = _load_elegance_verdict()
    evaluated = data["feedback_loop"]["criteria_evaluated"]
    assert "OUT1" in evaluated, f"OUT1 not in criteria_evaluated: {evaluated}"
