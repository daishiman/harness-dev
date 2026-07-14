"""Genuine functional tests for
plugins/harness-creator/skills/run-build-skill/scripts/lint-prompt-placement.py.

このスクリプトは plugins/*/skills/*/prompts/* が prompt-placement-convention に
準拠していること (a) ファイル名 regex (skill-local-v1, validate-build-trace の
SSOT を shim 経由 import) と (b) run/assign の責務プロンプトが空殻リダイレクトでない
ことを機械検証する純ローカル lint (network/keychain なし)。

カバレッジ方針:
- 純関数 (_skill_kind_of / _split_frontmatter / _is_redirect_shell) を実値検証。
- `scan(repo_root)` を tmp_path に合格 fixture / 各違反 fixture を生成して genuine 検査
  (PROMPT-FILENAME-FORMAT と PROMPT-REDIRECT-INVERSION の双方、kind による
  skip 分岐、plugins 不在の早期 return)。
- `_self_test` (--self-test) の PASS 経路と main() の usage / PASS / 違反検出経路を
  argv 差し替えで駆動。リポジトリ実体に対する main() (root 走査) も非破壊で確認。
- すべての fixture は tmp_path 配下に限定し repo を汚さない。

ファイル名は他ディレクトリと衝突しないよう `_r4` を付して新規作成。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "scripts" / "lint-prompt-placement.py")

_SPEC = importlib.util.spec_from_file_location("lint_prompt_placement_s4", SCRIPT)
LPP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LPP)


# 7 層相当の十分長い本文 (12 実質行以上 → 空殻でないとみなされる)
def _long_body(n=20):
    return "\n".join(f"行{i} これは実質的な 7 層本文の一部です。" for i in range(n))


def _frontmatter(**kv):
    lines = "\n".join(f"{k}: {v}" for k, v in kv.items())
    return f"---\n{lines}\n---\n"


# ===================== _skill_kind_of =====================

def test_skill_kind_of_extracts_run():
    rel = "plugins/p/skills/run-foo/prompts/R1.md"
    assert LPP._skill_kind_of(rel) == "run"


def test_skill_kind_of_extracts_each_kind():
    for kind in ("run", "assign", "ref", "wrap", "delegate"):
        rel = f"plugins/p/skills/{kind}-bar-baz/prompts/R1.md"
        assert LPP._skill_kind_of(rel) == kind


def test_skill_kind_of_returns_none_for_unknown():
    assert LPP._skill_kind_of("plugins/p/skills/foo-bar/prompts/R1.md") is None
    assert LPP._skill_kind_of("totally/unrelated/path.md") is None


# ===================== _split_frontmatter =====================

def test_split_frontmatter_separates_fm_and_body():
    text = "---\nkey: val\n---\nbody line 1\nbody line 2"
    fm, body = LPP._split_frontmatter(text)
    assert "key: val" in fm
    assert body == "body line 1\nbody line 2"


def test_split_frontmatter_no_fm_returns_full_body():
    text = "no frontmatter here\nsecond line"
    fm, body = LPP._split_frontmatter(text)
    assert fm == ""
    assert body == text


def test_split_frontmatter_unterminated_fm():
    # 開始 --- はあるが終端 --- が無い → fm="" body=全文
    text = "---\nkey: val\nnever closes"
    fm, body = LPP._split_frontmatter(text)
    assert fm == ""
    assert body == text


def test_split_frontmatter_fm_at_eof_no_trailing_newline():
    # 終端 --- の後に改行が無いケース (nl == -1 経路) → body=""
    text = "---\nkey: val\n---"
    fm, body = LPP._split_frontmatter(text)
    assert "key: val" in fm
    assert body == ""


# ===================== _is_redirect_shell =====================

def test_is_redirect_shell_moved_to_in_frontmatter():
    text = _frontmatter(moved_to="agents/x.md") + "\n# Prompt\n" + _long_body()
    assert LPP._is_redirect_shell(text) is True


def test_is_redirect_shell_redirect_phrase_and_agents_ref():
    text = "# Prompt (リダイレクト)\n本文は agents/x.md を参照。\n" + _long_body()
    assert LPP._is_redirect_shell(text) is True


def test_is_redirect_shell_too_short_body():
    # 実質本文 < 12 行 → 空殻判定
    text = _frontmatter(responsibility_id="R1") + "\n短い\n本文のみ\n"
    assert LPP._is_redirect_shell(text) is True


def test_is_redirect_shell_full_body_is_ok():
    text = _frontmatter(responsibility_id="R1") + "\n" + _long_body()
    assert LPP._is_redirect_shell(text) is False


def test_is_redirect_shell_agents_ref_without_redirect_phrase_not_shell():
    # 'リダイレクト' が無ければ agents/ 言及だけでは shell にならない (本文が十分長い場合)
    text = _long_body() + "\nなお agents/ に補助あり。"
    assert LPP._is_redirect_shell(text) is False


# ===================== scan (fixture repo) =====================

def _make_prompt(repo_root: Path, plugin: str, skill: str, fname: str, content: str):
    d = repo_root / "plugins" / plugin / "skills" / skill / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_text(content, encoding="utf-8")
    return d / fname


def test_scan_no_plugins_dir_returns_empty(tmp_path):
    # plugins/ ディレクトリが無ければ即 [] (base.exists() False 経路)
    assert LPP.scan(tmp_path) == []


def test_scan_clean_repo_has_no_violations(tmp_path):
    body = _frontmatter(responsibility_id="R1") + "\n" + _long_body()
    _make_prompt(tmp_path, "myplugin", "run-foo", "R1.md", body)
    _make_prompt(tmp_path, "myplugin", "assign-bar", "R2-eval.md", body)
    assert LPP.scan(tmp_path) == []


def test_scan_accepts_planner_responsibility_filename(tmp_path):
    body = _frontmatter(responsibility_id="R2b-readiness") + "\n" + _long_body()
    _make_prompt(tmp_path, "myplugin", "run-foo", "R2b-readiness.md", body)
    assert LPP.scan(tmp_path) == []


def test_scan_flags_bad_filename(tmp_path):
    # ファイル名が R<id> 形式でない → PROMPT-FILENAME-FORMAT
    body = _frontmatter(responsibility_id="R1") + "\n" + _long_body()
    _make_prompt(tmp_path, "myplugin", "run-foo", "main.md", body)
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-FILENAME-FORMAT" in v for v in viols)
    assert any("main.md" in v for v in viols)


def test_scan_rejects_invalid_planner_responsibility_filename(tmp_path):
    body = _frontmatter(responsibility_id="R2B-readiness") + "\n" + _long_body()
    _make_prompt(tmp_path, "myplugin", "run-foo", "R2B-readiness.md", body)
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-FILENAME-FORMAT" in v for v in viols)


def test_scan_flags_redirect_inversion_for_run_kind(tmp_path):
    # run の R-id プロンプトが空殻リダイレクト → PROMPT-REDIRECT-INVERSION
    shell = _frontmatter(moved_to="agents/x.md") + "\n# Prompt\nstub"
    _make_prompt(tmp_path, "myplugin", "run-foo", "R1.md", shell)
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-REDIRECT-INVERSION" in v for v in viols)
    assert any("kind=run" in v for v in viols)


def test_scan_flags_inversion_for_assign_kind(tmp_path):
    shell = _frontmatter(responsibility_id="R1") + "\n短い本文\n"
    _make_prompt(tmp_path, "myplugin", "assign-bar", "R1.md", shell)
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-REDIRECT-INVERSION" in v and "kind=assign" in v for v in viols)


def test_scan_skips_inversion_for_ref_kind(tmp_path):
    # ref は INVERSION 検査の対象外 → 空殻でも通る (ファイル名は合格させる)
    shell = _frontmatter(responsibility_id="R1") + "\nごく短い本文\n"
    _make_prompt(tmp_path, "myplugin", "ref-meta", "R1.md", shell)
    viols = LPP.scan(tmp_path)
    assert not any("PROMPT-REDIRECT-INVERSION" in v for v in viols)


def test_scan_skips_non_md_yaml_suffix_for_inversion(tmp_path):
    # run でも .md/.yaml 以外の suffix は INVERSION 検査外。
    # (ただしファイル名 regex には通らないので FILENAME 違反だけが出る想定)
    _make_prompt(tmp_path, "myplugin", "run-foo", "R1.txt", "stub")
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-FILENAME-FORMAT" in v for v in viols)
    assert not any("PROMPT-REDIRECT-INVERSION" in v for v in viols)


def test_scan_ignores_directories(tmp_path):
    # prompts/ 配下のサブディレクトリ (is_file False 経路) はスキップ
    d = tmp_path / "plugins" / "p" / "skills" / "run-foo" / "prompts" / "subdir"
    d.mkdir(parents=True)
    body = _frontmatter(responsibility_id="R1") + "\n" + _long_body()
    _make_prompt(tmp_path, "p", "run-foo", "R1.md", body)
    assert LPP.scan(tmp_path) == []


def test_scan_yaml_inversion(tmp_path):
    # .yaml の run プロンプトでも空殻なら INVERSION (suffix in (.md,.yaml))
    shell = _frontmatter(moved_to="agents/y.yaml") + "\nstub"
    _make_prompt(tmp_path, "p", "run-foo", "R3.yaml", shell)
    viols = LPP.scan(tmp_path)
    assert any("PROMPT-REDIRECT-INVERSION" in v for v in viols)


# ===================== _self_test =====================

def test_self_test_passes(capsys):
    rc = LPP._self_test()
    out = capsys.readouterr().out
    assert rc == 0
    assert "self-test: PASS" in out


# ===================== main() =====================

def test_main_self_test_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lint-prompt-placement.py", "--self-test"])
    assert LPP.main() == 0
    assert "self-test: PASS" in capsys.readouterr().out


def test_main_usage_on_unknown_arg(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lint-prompt-placement.py", "--bogus"])
    assert LPP.main() == 2
    assert "usage:" in capsys.readouterr().err


def test_main_pass_when_no_violations(monkeypatch, capsys):
    # scan を空にして PASS 経路を駆動 (repo 実体に依存しない)
    monkeypatch.setattr(LPP, "scan", lambda root: [])
    monkeypatch.setattr(sys, "argv", ["lint-prompt-placement.py"])
    assert LPP.main() == 0
    assert "ok:" in capsys.readouterr().out


def test_main_reports_violations(monkeypatch, capsys):
    monkeypatch.setattr(
        LPP, "scan",
        lambda root: ["PROMPT-FILENAME-FORMAT x (bad)",
                      "PROMPT-REDIRECT-INVERSION y (kind=run)"])
    monkeypatch.setattr(sys, "argv", ["lint-prompt-placement.py"])
    assert LPP.main() == 1
    out = capsys.readouterr().out
    assert "violations" in out
    assert "total: 2 violation(s)" in out


def test_main_against_real_repo_is_nondestructive(monkeypatch, capsys):
    # 実 repo に対する main() (no-arg) を駆動。リポジトリの実状態に依存するが、
    # exit は 0 か 1 のいずれか (例外を投げないこと) を保証する非破壊スモーク。
    monkeypatch.setattr(sys, "argv", ["lint-prompt-placement.py"])
    rc = LPP.main()
    assert rc in (0, 1)


def test_repo_root_points_to_repo():
    # _repo_root() が plugins/ を持つディレクトリを指すこと
    root = LPP._repo_root()
    assert (root / "plugins").exists()


def test_subprocess_self_test_smoke():
    # CLI 起動 (__main__ / SystemExit 経路) を subprocess で genuine に確認
    import subprocess
    r = subprocess.run([sys.executable, str(SCRIPT), "--self-test"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "self-test: PASS" in r.stdout
