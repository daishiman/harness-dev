"""skill-governance-lint scripts の回帰テスト (elegant-review Phase 3 バッチC)。

対象:
  - MD-208: lint-skill-completeness.py の *_refs fail-open 修復 (dangling 参照検出)
  - LS-211: run kind の manifest カテゴリ (段階導入: 既定 warn / env で error)
  - LS-215: lint-path-canonical.py の削除済み 'creator-kit' 残存参照検出
"""
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
COMPLETENESS = SCRIPTS / "lint-skill-completeness.py"
PATH_CANONICAL = SCRIPTS / "lint-path-canonical.py"


def run_cmd(*args, env=None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=merged,
    )


def make_skill(base: Path, name: str, frontmatter: str) -> Path:
    skill = base / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\n{frontmatter}---\n\n# {name}\n", encoding="utf-8"
    )
    return skill


# ── MD-208: dangling *_refs 検出 ───────────────────────────────────────────


def test_completeness_dangling_refs_detected(tmp_path):
    skill = make_skill(
        tmp_path,
        "run-demo",
        "prefix: run\n"
        "responsibility_refs:\n"
        "  - prompts/missing.md\n"
        "completeness_exempt:\n"
        '  - "manifest: テスト用免除"\n',
    )
    result = run_cmd(COMPLETENESS, skill)
    assert result.returncode == 1
    assert "解決不可" in result.stderr
    assert "prompts/missing.md" in result.stderr


def test_completeness_resolvable_refs_pass(tmp_path):
    skill = make_skill(
        tmp_path,
        "run-demo",
        "prefix: run\n"
        "responsibility_refs:\n"
        "  - prompts/r1-demo.md\n"
        "completeness_exempt:\n"
        '  - "manifest: テスト用免除"\n',
    )
    (skill / "prompts").mkdir()
    (skill / "prompts" / "r1-demo.md").write_text("# r1\n", encoding="utf-8")
    result = run_cmd(COMPLETENESS, skill)
    assert result.returncode == 0, result.stderr


# ── LS-211: manifest カテゴリ (段階導入) ──────────────────────────────────


def test_completeness_manifest_missing_warns_by_default(tmp_path):
    skill = make_skill(
        tmp_path,
        "run-demo",
        "prefix: run\nprompt_creator_policy: skip\n",
    )
    result = run_cmd(COMPLETENESS, skill, env={"LINT_COMPLETENESS_STRICT_MANIFEST": "0"})
    assert result.returncode == 0, result.stderr
    assert "[Warn]LS-211" in result.stderr

    strict = run_cmd(COMPLETENESS, skill, env={"LINT_COMPLETENESS_STRICT_MANIFEST": "1"})
    assert strict.returncode == 1
    assert "workflow-manifest.json" in strict.stderr


def test_completeness_manifest_satisfied_by_file(tmp_path):
    skill = make_skill(
        tmp_path,
        "run-demo",
        "prefix: run\nprompt_creator_policy: skip\n",
    )
    (skill / "workflow-manifest.json").write_text("{}\n", encoding="utf-8")
    result = run_cmd(COMPLETENESS, skill, env={"LINT_COMPLETENESS_STRICT_MANIFEST": "1"})
    assert result.returncode == 0, result.stderr


# ── LS-215: 削除済み creator-kit 残存参照検出 ─────────────────────────────


def test_path_canonical_detects_stale_creator_kit_ref(tmp_path):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "run-demo", "kind: run\n")
    bad_scripts = tmp_path / "scripts"
    bad_scripts.mkdir()
    (bad_scripts / "bad-lint.py").write_text(
        'ROOT = __import__("pathlib").Path(".")\n'
        'TARGET = ROOT / "creator-kit" / "skills"\n',
        encoding="utf-8",
    )
    result = run_cmd(
        PATH_CANONICAL, "--skills-dir", skills_dir, "--scripts-dir", bad_scripts
    )
    assert result.returncode == 1
    assert "creator-kit" in result.stderr
    assert "残存参照" in result.stderr


def test_path_canonical_clean_scripts_dir_passes(tmp_path):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "run-demo", "kind: run\n")
    clean_scripts = tmp_path / "scripts"
    clean_scripts.mkdir()
    (clean_scripts / "good-lint.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = run_cmd(
        PATH_CANONICAL, "--skills-dir", skills_dir, "--scripts-dir", clean_scripts
    )
    assert result.returncode == 0, result.stderr
