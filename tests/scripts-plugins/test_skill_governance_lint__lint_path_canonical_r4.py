"""lint-path-canonical.py のパス正本ルール (CONVENTIONS.md §8) を網羅検証する (scripts4 系列)。

対象 script:
  plugins/skill-governance-lint/scripts/lint-path-canonical.py

純ローカル lint (network=false, write-scope=none) のため外部 stub は不要。全 fixture は
tmp_path 配下に置き repo を汚さない。検証対象の分岐:
  - parse_name / parse_kind / parse_source: 有/無/クォート除去
  - check_skill_md:
      * ファイル不在
      * ルール1 ディレクトリ名 != name
      * ルール2 python3 パス (canonical 許可形 / .claude/skills 違反 / その他無視)
      * ルール3 ref-* の source 必須 (有=OK / 無=違反 / 非ref は対象外)
      * ルール4 ハードコード (xl-skills / owner: team-skills / owner: solo_operator)
      * 複数違反の累積
  - main:
      * --skill-md 単体 / --skills-dir glob / 両方
      * 引数なし → skill targets 空でも stale-root scan は実行され
        (既定 --scripts-dir = 本スクリプト同階層, clean) return 0
      * 全合格 → return 0 + ok メッセージ
      * 違反あり → return 1 + stderr に findings
      * subprocess 経由 (__main__ ガード + exit code 契約)

他ディレクトリ (tests/scripts3 等) の同名衝突を避けるため _r4 サフィックス + plugin 接頭辞。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-path-canonical.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_path_canonical_r4_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _mk_skill(root: Path, dir_name: str, body: str) -> Path:
    """tmp_path 配下に <dir_name>/SKILL.md を作り、その Path を返す。"""
    d = root / dir_name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(body, encoding="utf-8")
    return p


# 全ルール通過する最小 frontmatter (dir 名と name 一致 / kind=run なので source 不要)
def _good_body(name: str) -> str:
    return f"---\nname: {name}\nkind: run\n---\n\n# {name}\n本文。\n"


# ---------------------------------------------------------------------------
# parse_name / parse_kind / parse_source
# ---------------------------------------------------------------------------
def test_parse_name_present_and_absent(MOD):
    assert MOD.parse_name("---\nname: run-foo\n---\n") == "run-foo"
    assert MOD.parse_name("no name here\n") is None


def test_parse_kind_present_and_absent(MOD):
    assert MOD.parse_kind("---\nkind: ref\n---\n") == "ref"
    assert MOD.parse_kind("---\nname: x\n---\n") is None


def test_parse_source_strips_quotes(MOD):
    assert MOD.parse_source('source: "doc/21"\n') == "doc/21"
    assert MOD.parse_source("source: 'plugins/x'\n") == "plugins/x"
    assert MOD.parse_source("source: bare-value\n") == "bare-value"
    assert MOD.parse_source("no source line\n") is None


# ---------------------------------------------------------------------------
# check_skill_md — ファイル不在
# ---------------------------------------------------------------------------
def test_check_missing_file(MOD, tmp_path):
    missing = tmp_path / "ghost" / "SKILL.md"
    errs = MOD.check_skill_md(missing)
    assert errs == [f"not found: {missing}"]


# ---------------------------------------------------------------------------
# check_skill_md — ルール1: ディレクトリ名 == name
# ---------------------------------------------------------------------------
def test_check_clean_skill_no_errors(MOD, tmp_path):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-foo"))
    assert MOD.check_skill_md(p) == []


def test_check_name_directory_mismatch(MOD, tmp_path):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-bar"))
    errs = MOD.check_skill_md(p)
    assert any("name 'run-bar' != directory 'run-foo'" in e for e in errs)


def test_check_name_absent_does_not_trip_rule1(MOD, tmp_path):
    # name 行が無ければルール1 はスキップ (name は None)
    p = _mk_skill(tmp_path, "run-foo", "---\nkind: run\n---\n# body\n")
    assert not any("!= directory" in e for e in MOD.check_skill_md(p))


# ---------------------------------------------------------------------------
# check_skill_md — ルール2: python3 呼び出しパス
# ---------------------------------------------------------------------------
def test_check_py3_canonical_plugins_path_ok(MOD, tmp_path):
    body = _good_body("run-foo") + "\n`python3 plugins/x/scripts/do.py`\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    assert not any("non-canonical" in e for e in MOD.check_skill_md(p))


def test_check_py3_relative_scripts_path_ok(MOD, tmp_path):
    body = _good_body("run-foo") + "\npython3 ./scripts/run.py\npython3 scripts/run.py\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    assert not any("non-canonical" in e for e in MOD.check_skill_md(p))


def test_check_py3_skills_subpath_ok(MOD, tmp_path):
    # "skills/" を含むパスは許可 (skill 自身の scripts/)
    body = _good_body("run-foo") + "\npython3 some/skills/run-x/scripts/a.py\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    assert not any("non-canonical" in e for e in MOD.check_skill_md(p))


def test_check_py3_claude_skills_path_is_currently_dead_branch(MOD, tmp_path):
    """GENUINE FINDING: ルール2 の `.claude/skills/` 違反枝 (script L81-83) は到達不能。

    判定順は `or "skills/" in script_path` (L78) が先に評価され continue するため、
    `.claude/skills/...` を含むパスは必ず "skills/" を含み、`.claude/skills/` 違反 append に
    到達しない (dead code)。本テストは実装の現挙動 = フラグされない を固定する
    (回帰検知)。意図どおりに違反検出したい場合は script 側の判定順序修正が必要。"""
    body = _good_body("run-foo") + "\npython3 .claude/skills/run-x/scripts/a.py\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    errs = MOD.check_skill_md(p)
    assert not any("non-canonical python3 path" in e for e in errs)


def test_check_py3_claude_non_skills_path_not_flagged(MOD, tmp_path):
    """dead-branch 認定の裏付け: `.claude/` 配下でも `.claude/skills/` 部分文字列を持たない
    パス (例 `.claude/agents/.../scripts/a.py`) は、L78 の "skills/" 一致もせず L81 の
    `.claude/skills/` 一致もしないため違反対象外。違反枝 (L81-83) に到達する入力は、
    `.claude/skills/` を含む = 必ず "skills/" を含む → L78 で continue、の一通りしかなく、
    結局どの入力でも append されない (= 到達不能) ことを示す。"""
    body = _good_body("run-foo") + "\npython3 .claude/agents/run-x/scripts/a.py\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    errs = MOD.check_skill_md(p)
    assert not any("non-canonical python3 path" in e for e in errs)


def test_check_py3_other_path_ignored(MOD, tmp_path):
    # canonical でも .claude/skills でもない単発パスは (このルールでは) 黙認される
    body = _good_body("run-foo") + "\npython3 tools/random.py\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    assert not any("non-canonical" in e for e in MOD.check_skill_md(p))


# ---------------------------------------------------------------------------
# check_skill_md — ルール3: ref-* は source 必須
# ---------------------------------------------------------------------------
def test_check_ref_without_source_violation(MOD, tmp_path):
    body = "---\nname: ref-x\nkind: ref\n---\n# body\n"
    p = _mk_skill(tmp_path, "ref-x", body)
    errs = MOD.check_skill_md(p)
    assert "ref-* skill missing 'source:' field (doc/21)" in errs


def test_check_ref_with_source_ok(MOD, tmp_path):
    body = "---\nname: ref-x\nkind: ref\nsource: doc/21\n---\n# body\n"
    p = _mk_skill(tmp_path, "ref-x", body)
    assert not any("missing 'source:'" in e for e in MOD.check_skill_md(p))


def test_check_non_ref_kind_skips_source_rule(MOD, tmp_path):
    # kind=run は source 無しでもルール3 対象外
    p = _mk_skill(tmp_path, "run-x", _good_body("run-x"))
    assert not any("missing 'source:'" in e for e in MOD.check_skill_md(p))


# ---------------------------------------------------------------------------
# check_skill_md — ルール4: ハードコード検出
# ---------------------------------------------------------------------------
def test_check_hardcode_project_name(MOD, tmp_path):
    body = _good_body("run-foo") + "\nパスは xl-skills/plugins を参照。\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    errs = MOD.check_skill_md(p)
    assert any("specific project name 'xl-skills'" in e for e in errs)


def test_check_hardcode_owner_team_skills(MOD, tmp_path):
    body = "---\nname: run-foo\nkind: run\nowner: team-skills\n---\n# body\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    errs = MOD.check_skill_md(p)
    assert any("hardcoded owner 'team-skills'" in e for e in errs)


def test_check_hardcode_owner_solo_operator(MOD, tmp_path):
    body = "---\nname: run-foo\nkind: run\nowner: solo_operator\n---\n# body\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    errs = MOD.check_skill_md(p)
    assert any("hardcoded owner 'solo_operator'" in e for e in errs)


def test_check_owner_templated_not_flagged(MOD, tmp_path):
    # {{owner}} はハードコードでないので検出されない
    body = "---\nname: run-foo\nkind: run\nowner: {{owner}}\n---\n# body\n"
    p = _mk_skill(tmp_path, "run-foo", body)
    assert not any("hardcoded owner" in e for e in MOD.check_skill_md(p))


def test_check_multiple_violations_accumulate(MOD, tmp_path):
    # name 不一致 + ref source 欠落 + ハードコード を同時に出す
    body = "---\nname: ref-mismatch\nkind: ref\nowner: team-skills\n---\nxl-skills here\n"
    p = _mk_skill(tmp_path, "ref-foo", body)
    errs = MOD.check_skill_md(p)
    joined = "\n".join(errs)
    assert "!= directory 'ref-foo'" in joined
    assert "missing 'source:'" in joined
    assert "'team-skills'" in joined
    assert "'xl-skills'" in joined
    assert len(errs) >= 4


# ---------------------------------------------------------------------------
# main (in-process)
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-path-canonical.py", *args])


def test_main_no_args_runs_stale_scan_and_returns_0(MOD, monkeypatch, capsys):
    # 旧 API は引数なし → print_help + return 2 (fail-open) だったが、現実装は
    # skill targets 空でも stale-root scan を必ず実行する。既定 --scripts-dir は
    # 本スクリプト同階層 (clean) なので return 0 + "ok: 0 skill(s)" メッセージ。
    _argv(monkeypatch)
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "ok: 0 skill(s)" in out
    assert "stale-root scan" in out


def test_main_skill_md_ok(MOD, tmp_path, monkeypatch, capsys):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-foo"))
    clean = tmp_path / "clean-scripts"
    clean.mkdir()
    _argv(monkeypatch, "--skill-md", str(p), "--scripts-dir", str(clean))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "ok: 1 skill(s)" in out
    assert "pass path-canonical lint" in out


def test_main_skill_md_violation_returns_1(MOD, tmp_path, monkeypatch, capsys):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-bar"))
    _argv(monkeypatch, "--skill-md", str(p))
    assert MOD.main() == 1
    cap = capsys.readouterr()
    assert str(p) in cap.err
    assert "!= directory" in cap.err


def test_main_skills_dir_glob_mixed(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "skills"
    _mk_skill(base, "run-ok", _good_body("run-ok"))
    _mk_skill(base, "run-bad", _good_body("run-other"))
    _argv(monkeypatch, "--skills-dir", str(base))
    # 1 件違反 → return 1
    assert MOD.main() == 1
    cap = capsys.readouterr()
    assert "run-bad" in cap.err
    # 合格した run-ok は stderr に出ない
    assert "run-ok" not in cap.err


def test_main_skills_dir_all_ok(MOD, tmp_path, monkeypatch, capsys):
    base = tmp_path / "skills"
    _mk_skill(base, "run-a", _good_body("run-a"))
    _mk_skill(base, "run-b", _good_body("run-b"))
    clean = tmp_path / "clean-scripts"
    clean.mkdir()
    _argv(monkeypatch, "--skills-dir", str(base), "--scripts-dir", str(clean))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "ok: 2 skill(s)" in out
    assert "pass path-canonical lint" in out


def test_main_both_targets_combined(MOD, tmp_path, monkeypatch, capsys):
    single = _mk_skill(tmp_path / "single", "run-z", _good_body("run-z"))
    base = tmp_path / "skills"
    _mk_skill(base, "run-a", _good_body("run-a"))
    clean = tmp_path / "clean-scripts"
    clean.mkdir()
    _argv(monkeypatch, "--skill-md", str(single), "--skills-dir", str(base),
          "--scripts-dir", str(clean))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "ok: 2 skill(s)" in out
    assert "pass path-canonical lint" in out


# ---------------------------------------------------------------------------
# main (subprocess) — __main__ ガード + exit code 契約
# ---------------------------------------------------------------------------
def test_subprocess_ok(tmp_path):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-foo"))
    r = _run(["--skill-md", str(p)])
    assert r.returncode == 0
    assert "pass path-canonical lint" in r.stdout


def test_subprocess_violation_exit1(tmp_path):
    p = _mk_skill(tmp_path, "run-foo", _good_body("run-bar"))
    r = _run(["--skill-md", str(p)])
    assert r.returncode == 1
    assert "!= directory" in r.stderr


def test_subprocess_no_args_runs_stale_scan_exit0():
    # 旧 API: 引数なし → exit 2 (print_help)。現実装: skill targets 空でも
    # 既定 --scripts-dir (本スクリプト同階層, clean) に対し stale-root scan を
    # 実行し exit 0 + "ok: 0 skill(s)" を返す。
    r = _run([])
    assert r.returncode == 0, r.stderr
    assert "ok: 0 skill(s)" in r.stdout
