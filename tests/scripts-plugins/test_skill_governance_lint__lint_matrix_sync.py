"""lint-matrix-sync.py の突合ロジック + main CLI 契約を network 無しで網羅する。

このスクリプトは lint-matrix.json (lint 集合の単一正本、finding LS-02/LS-07:
lint 集合3箇所分散の突合機械層) と3消費面 (run-build-skill SKILL.md Step4 /
run-skill-create workflow-manifest p0-lint.commands / CI workflow) の集合整合を
検査する。本テストは:
  - _extract_step4_scripts: Step4 セクション限定抽出 / Step4 不在 / 他セクション非混入
  - _extract_p0_scripts: 正常抽出 / JSON 破損 / p0-lint 不在
  - check_matrix: 整合 PASS / SKILL.md 側未宣言 / manifest 側不在 / CI 実行行不在 /
    コメント行のみの CI 言及を実配線と誤認しない (偽陽性封鎖) /
    ci 欠落 + ci_exclusion_reason 空の FAIL
  - main: 実 repo ファイルで exit0 / --self-test exit0 / 引数無し usage exit2
を tmp_path 上の合成 fixture と実入力で genuine に assert する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-matrix-sync.py"
REAL_MATRIX = ROOT / "plugins" / "harness-creator" / "references" / "lint-matrix.json"

_SPEC = importlib.util.spec_from_file_location("lint_matrix_sync_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


SKILL_MD = (
    "## Key Rules\n\n### Step 3: prep\n\n```bash\npython3 lint-other.py x\n```\n\n"
    "### Step 4: 命名・構造 Lint (phase: scripts)\n\n> note\n\n```bash\n"
    "python3 lint-a.py x\npython3 validate-b.py y\n```\n\n### Step 5: next\n"
)
MANIFEST = {"phases": [{"id": "p0-lint", "commands": ["python3 lint-a.py --skills-dir d"]}]}
CI_YML = "      - name: a\n        run: python3 lint-a.py\n"
MATRIX = {
    "consumers": {
        "build-preflight": "SKILL.md",
        "p0-gate": "manifest.json",
        "ci": ["ci.yml"],
    },
    "lints": [
        {"id": "a", "script": "lint-a.py", "contexts": ["build-preflight", "p0-gate", "ci"]},
        {
            "id": "b",
            "script": "validate-b.py",
            "contexts": ["build-preflight"],
            "ci_exclusion_reason": "既知債務",
        },
    ],
}


def _write_all(root: Path, matrix=None, skill_md=SKILL_MD, manifest=MANIFEST, ci=CI_YML):
    (root / "SKILL.md").write_text(skill_md, encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "ci.yml").write_text(ci, encoding="utf-8")
    mp = root / "lint-matrix.json"
    mp.write_text(json.dumps(matrix or MATRIX), encoding="utf-8")
    return mp


def test_extract_step4_scripts_scopes_to_step4_section_only():
    names = MOD._extract_step4_scripts(SKILL_MD)
    assert names == {"lint-a.py", "validate-b.py"}
    assert "lint-other.py" not in names


def test_extract_step4_scripts_returns_empty_without_step4():
    assert MOD._extract_step4_scripts("## x\n```bash\npython3 lint-a.py\n```\n") == set()


def test_extract_p0_scripts_reads_commands():
    names, errs = MOD._extract_p0_scripts(json.dumps(MANIFEST))
    assert names == {"lint-a.py"} and errs == []


def test_extract_p0_scripts_reports_parse_error():
    names, errs = MOD._extract_p0_scripts("{broken")
    assert names == set() and errs


def test_check_matrix_passes_when_consistent(tmp_path):
    mp = _write_all(tmp_path)
    assert MOD.check_matrix(mp, tmp_path) == []


def test_check_matrix_fails_on_undeclared_script_in_skill_md(tmp_path):
    rogue = SKILL_MD.replace(
        "python3 validate-b.py y\n", "python3 validate-b.py y\npython3 lint-rogue.py z\n"
    )
    mp = _write_all(tmp_path, skill_md=rogue)
    errs = MOD.check_matrix(mp, tmp_path)
    assert any("lint-rogue.py" in e and "未宣言" in e for e in errs)


def test_check_matrix_fails_on_declared_script_missing_from_manifest_and_ci(tmp_path):
    matrix = json.loads(json.dumps(MATRIX))
    matrix["lints"].append({"id": "c", "script": "lint-c.py", "contexts": ["p0-gate", "ci"]})
    mp = _write_all(tmp_path, matrix=matrix)
    errs = MOD.check_matrix(mp, tmp_path)
    assert any("lint-c.py" in e and "p0-lint.commands に不在" in e for e in errs)
    assert any("lint-c.py" in e and "実行行に不在" in e for e in errs)


def test_check_matrix_ignores_comment_only_ci_mentions(tmp_path):
    """コメント行にしか script 名が無い場合は CI 配線とみなさない (偽陽性封鎖)。"""
    matrix = json.loads(json.dumps(MATRIX))
    matrix["lints"][1] = {
        "id": "b",
        "script": "validate-b.py",
        "contexts": ["build-preflight", "ci"],
    }
    ci = CI_YML + "      # SSOT: validate-b.py の定数を参照\n"
    mp = _write_all(tmp_path, matrix=matrix, ci=ci)
    errs = MOD.check_matrix(mp, tmp_path)
    assert any("validate-b.py" in e and "実行行に不在" in e for e in errs)


def test_check_matrix_requires_exclusion_reason_when_ci_absent(tmp_path):
    matrix = json.loads(json.dumps(MATRIX))
    matrix["lints"][1] = {"id": "b", "script": "validate-b.py", "contexts": ["build-preflight"]}
    mp = _write_all(tmp_path, matrix=matrix)
    errs = MOD.check_matrix(mp, tmp_path)
    assert any("ci_exclusion_reason" in e for e in errs)


def test_main_real_repo_matrix_is_consistent():
    """実 repo の lint-matrix.json と3消費面が整合している (回帰ゲート)。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(REAL_MATRIX.relative_to(ROOT))],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "整合" in proc.stdout


def test_main_self_test_ok():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True
    )
    assert proc.returncode == 0 and "ok" in proc.stdout


def test_main_usage_without_args():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 2


def test_main_violation_exit1(tmp_path):
    matrix = json.loads(json.dumps(MATRIX))
    matrix["lints"][1] = {"id": "b", "script": "validate-b.py", "contexts": ["build-preflight"]}
    mp = _write_all(tmp_path, matrix=matrix)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(mp)], capture_output=True, text=True, cwd=tmp_path
    )
    assert proc.returncode == 1 and "FAIL" in proc.stderr
