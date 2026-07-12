"""scripts/gate-phase0.py の genuine 機能テスト。

純関数 (check_effect / check_resource_map / check_duplicate_scripts /
check_hardcode_paths) を tmp_path 上に構築した擬似 Skill ツリーで実入力により
呼び、PASS / FAIL の errs リストを実出力で assert する。main() は subprocess
(--skills-dir を tmp_path に向ける) で全 PASS (exit 0) / 違反 (exit 1) /
skills-dir 不在 (exit 2) / --help を検証する。外部 I/O (network/keychain) なし。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gate-phase0.py"

SPEC = importlib.util.spec_from_file_location("gate_phase0_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _skill(base: Path, name: str, body: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


FM_WITH_EFFECT = "---\nname: run-x\neffect: read-only\n---\nbody\n"


# --- check_effect ------------------------------------------------------------

def test_check_effect_present_no_error(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT)
    assert MOD.check_effect(d) == []


def test_check_effect_missing_field_reports(tmp_path):
    d = _skill(tmp_path, "run-x", "---\nname: run-x\n---\nbody\n")
    errs = MOD.check_effect(d)
    assert len(errs) == 1
    assert "(a)" in errs[0]
    assert "effect:" in errs[0]


def test_check_effect_no_skill_md(tmp_path):
    d = tmp_path / "run-empty"
    d.mkdir()
    errs = MOD.check_effect(d)
    assert errs == ["run-empty: SKILL.md not found"]


def test_check_effect_no_frontmatter_fence_no_error(tmp_path):
    # frontmatter が無い (--- で始まらない) -> frontmatter チェックをスキップ -> errs 空
    d = _skill(tmp_path, "run-x", "no frontmatter here\n")
    assert MOD.check_effect(d) == []


def test_check_effect_incomplete_fence_no_error(tmp_path):
    # 開始 --- のみで終端が無い -> split で 3 分割できず errs 空
    d = _skill(tmp_path, "run-x", "---\nname: run-x\neffect missing colon\n")
    assert MOD.check_effect(d) == []


def test_check_effect_only_in_body_not_frontmatter_reports(tmp_path):
    # effect: が本文にあっても frontmatter には無い -> 違反
    body = "---\nname: run-x\n---\neffect: read-only (body だけ)\n"
    d = _skill(tmp_path, "run-x", body)
    errs = MOD.check_effect(d)
    assert len(errs) == 1
    assert "(a)" in errs[0]


# --- check_resource_map ------------------------------------------------------

def test_check_resource_map_no_refs_dir_no_error(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT)
    assert MOD.check_resource_map(d) == []


def test_check_resource_map_under_threshold_no_error(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT)
    refs = d / "references"
    refs.mkdir()
    (refs / "a.md").write_text("a", encoding="utf-8")
    (refs / "b.md").write_text("b", encoding="utf-8")  # 2 ファイル < 3
    assert MOD.check_resource_map(d) == []


def test_check_resource_map_three_files_without_map_reports(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT)
    refs = d / "references"
    refs.mkdir()
    for n in ("a.md", "b.md", "c.md"):
        (refs / n).write_text("x", encoding="utf-8")
    errs = MOD.check_resource_map(d)
    assert len(errs) == 1
    assert "(b)" in errs[0]
    assert "resource-map.yaml が不在" in errs[0]


def test_check_resource_map_three_files_with_map_ok(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT)
    refs = d / "references"
    refs.mkdir()
    for n in ("a.md", "b.md"):
        (refs / n).write_text("x", encoding="utf-8")
    (refs / "resource-map.yaml").write_text("map", encoding="utf-8")  # 計 3 だが map あり
    assert MOD.check_resource_map(d) == []


# --- check_duplicate_scripts -------------------------------------------------

def test_check_duplicate_scripts_no_scripts_dir_no_error(tmp_path):
    assert MOD.check_duplicate_scripts(tmp_path) == []


def test_check_duplicate_scripts_valid_symlink_no_error(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    target = tmp_path / "real.py"
    target.write_text("x", encoding="utf-8")
    (scripts / "link.py").symlink_to(target)  # 解決可能な symlink
    assert MOD.check_duplicate_scripts(tmp_path) == []


def test_check_duplicate_scripts_broken_symlink_reports(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "dead.py").symlink_to(tmp_path / "does-not-exist.py")  # broken
    errs = MOD.check_duplicate_scripts(tmp_path)
    assert len(errs) == 1
    assert "(c)" in errs[0]
    assert "broken symlink" in errs[0]


# --- check_hardcode_paths ----------------------------------------------------

def test_check_hardcode_paths_no_skill_md(tmp_path):
    d = tmp_path / "run-x"
    d.mkdir()
    assert MOD.check_hardcode_paths(d) == []


def test_check_hardcode_paths_clean_no_error(tmp_path):
    d = _skill(tmp_path, "run-x", FM_WITH_EFFECT + "no hardcoded paths here\n")
    assert MOD.check_hardcode_paths(d) == []


def test_check_hardcode_paths_detects_mkdir_reference(tmp_path):
    body = FM_WITH_EFFECT + "Run: mkdir -p .claude/skills/run-other\n"
    d = _skill(tmp_path, "run-x", body)
    errs = MOD.check_hardcode_paths(d)
    assert len(errs) == 1
    assert "(d)" in errs[0]
    assert "ハードコード参照が残存" in errs[0]


def test_check_hardcode_paths_detects_git_mv_and_counts(tmp_path):
    body = (
        FM_WITH_EFFECT
        + "git mv old .claude/skills/run-a\n"
        + "cp x .claude/skills/run-b\n"
    )
    d = _skill(tmp_path, "run-x", body)
    errs = MOD.check_hardcode_paths(d)
    assert len(errs) == 1
    assert "(2 箇所)" in errs[0]


def test_check_hardcode_paths_fallback_pattern_allowed(tmp_path):
    # [ -f ".claude/skills/..." ] のような fallback 探索 (mkdir/git mv/ls/grep/cp 動詞でない)
    # は許容され違反にならない
    body = FM_WITH_EFFECT + 'if [ -f ".claude/skills/run-x/SKILL.md" ]; then echo ok; fi\n'
    d = _skill(tmp_path, "run-x", body)
    assert MOD.check_hardcode_paths(d) == []


# --- main(): subprocess (--skills-dir を tmp に向ける) -----------------------

def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def test_main_all_pass_exit_0(tmp_path):
    skills = tmp_path / "skills"
    _skill(skills, "run-clean", FM_WITH_EFFECT)
    proc = _run(["--skills-dir", str(skills)])
    assert proc.returncode == 0, proc.stderr
    assert "GATE-PHASE0: PASS" in proc.stdout
    assert "(1 skills checked)" in proc.stdout


def test_main_violation_exit_1(tmp_path):
    skills = tmp_path / "skills"
    # effect: 欠如 -> (a) 違反
    _skill(skills, "run-bad", "---\nname: run-bad\n---\nbody\n")
    proc = _run(["--skills-dir", str(skills)])
    assert proc.returncode == 1
    assert "GATE-PHASE0: FAIL" in proc.stderr
    assert "(a)" in proc.stderr


def test_main_skills_dir_not_found_exit_2(tmp_path):
    proc = _run(["--skills-dir", str(tmp_path / "absent")])
    assert proc.returncode == 2
    assert "skills directory not found" in proc.stderr


def test_main_skips_non_dir_entries(tmp_path):
    skills = tmp_path / "skills"
    _skill(skills, "run-clean", FM_WITH_EFFECT)
    (skills / "stray.txt").write_text("ignored", encoding="utf-8")  # ファイルは無視
    proc = _run(["--skills-dir", str(skills)])
    assert proc.returncode == 0
    assert "(1 skills checked)" in proc.stdout


def test_main_multiple_skills_aggregates_violations(tmp_path):
    skills = tmp_path / "skills"
    _skill(skills, "run-ok", FM_WITH_EFFECT)
    _skill(skills, "run-noeffect", "---\nname: run-noeffect\n---\nbody\n")
    refs = (skills / "run-noeffect" / "references")
    refs.mkdir()
    for n in ("a.md", "b.md", "c.md"):
        (refs / n).write_text("x", encoding="utf-8")  # (b) 違反も追加
    proc = _run(["--skills-dir", str(skills)])
    assert proc.returncode == 1
    assert "(a)" in proc.stderr
    assert "(b)" in proc.stderr


# --- main(): in-process 駆動 (main 本体 lines 92-129 を genuine にカバー) -----

def test_main_inprocess_pass_returns_0(tmp_path, monkeypatch, capsys):
    skills = tmp_path / "skills"
    _skill(skills, "run-clean", FM_WITH_EFFECT)
    monkeypatch.chdir(tmp_path)  # repo_root=tmp_path, scripts/ 不在 -> (c) PASS
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py", "--skills-dir", str(skills)])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "GATE-PHASE0: PASS" in out
    assert "(1 skills checked)" in out


def test_main_inprocess_violation_returns_1(tmp_path, monkeypatch, capsys):
    skills = tmp_path / "skills"
    _skill(skills, "run-bad", "---\nname: run-bad\n---\nbody\n")  # effect 欠如
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py", "--skills-dir", str(skills)])
    rc = MOD.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "GATE-PHASE0: FAIL" in err
    assert "(a)" in err


def test_main_inprocess_missing_skills_dir_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["gate-phase0.py", "--skills-dir", str(tmp_path / "absent")]
    )
    rc = MOD.main()
    assert rc == 2
    assert "skills directory not found" in capsys.readouterr().err


def test_main_inprocess_default_skills_dir_when_missing_returns_2(tmp_path, monkeypatch, capsys):
    # --skills-dir なし & cwd=tmp_path -> default plugins/harness-creator/skills 不在 -> 2
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py"])
    rc = MOD.main()
    assert rc == 2
    assert "skills directory not found" in capsys.readouterr().err


def test_main_inprocess_flag_without_value_uses_default(tmp_path, monkeypatch, capsys):
    # --skills-dir が末尾で値なし -> override されず default にフォールバック (cwd 起点)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py", "--skills-dir"])
    rc = MOD.main()
    # default plugins/harness-creator/skills は tmp_path 配下に無い -> 2
    assert rc == 2


def test_main_inprocess_skips_non_dir_entries(tmp_path, monkeypatch, capsys):
    # skills-base 直下のファイル (非ディレクトリ) はループ内で continue される
    skills = tmp_path / "skills"
    _skill(skills, "run-clean", FM_WITH_EFFECT)
    (skills / "stray.txt").write_text("ignored", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py", "--skills-dir", str(skills)])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "(1 skills checked)" in out  # stray.txt は数えない


def test_main_inprocess_detects_broken_symlink_in_repo_scripts(tmp_path, monkeypatch, capsys):
    # repo_root/scripts に broken symlink -> (c) 違反で exit 1
    skills = tmp_path / "skills"
    _skill(skills, "run-clean", FM_WITH_EFFECT)
    rscripts = tmp_path / "scripts"
    rscripts.mkdir()
    (rscripts / "dead.py").symlink_to(tmp_path / "missing.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate-phase0.py", "--skills-dir", str(skills)])
    rc = MOD.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "(c)" in err
    assert "broken symlink" in err
