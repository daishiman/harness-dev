"""lint-skill-dep-step7.py の doc/20 Step 7 依存制約 5 条件を実入力で網羅検証する。

対象 script:
  plugins/skill-governance-lint/scripts/lint-skill-dep-step7.py

検査する 5 条件 (check_skill):
  (1) wrap-* に base: フィールドがある
  (2) assign-*-evaluator に pair: フィールドがある
  (3) pair: の相手スキルが plugins/harness-creator/skills か .claude/skills に存在する
  (4) dangerous run-* (danger:true / effect:external-mutation) に
      disable-model-invocation:true がある
  (5) ref-* が disable-model-invocation:true かつ user-invocable:false かつ
      他スキルから inbound 参照されない ⇒ 到達不能エラー

方針:
  - 純関数 (parse_fm / _repo_root / skill_exists / _collect_inbound_refs /
    check_skill) を実ファイルから importlib でロードして直接呼ぶ。
  - tmp_path に .git マーカ付きの「擬似 repo」を組み立て、plugins/harness-creator/skills と
    .claude/skills 配下に合格 fixture / 各違反 fixture の SKILL.md を実際に書いて
    check_skill / _collect_inbound_refs を実入力で assert する。
  - main は in-process (monkeypatch sys.argv) で全分岐 (paths / --skills-dir /
    --allow-partial / not-a-dir / 引数無し usage / 違反 exit1 / 合格 exit0 /
    not found) を return code + stdout/stderr で被覆し、加えて subprocess で
    __main__ ガード (raise SystemExit) を実行する。
  - network / keychain / Notion 依存は無い純ローカル lint なので stub 不要。
    全 fixture は tmp_path 配下で repo を汚染しない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-lint"
    / "scripts"
    / "lint-skill-dep-step7.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("lint_skill_dep_step7_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _mk_repo(tmp_path: Path) -> Path:
    """tmp_path に .git マーカ付きの擬似 repo を作り、空の skills root を用意する。"""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "plugins" / "harness-creator" / "skills").mkdir(parents=True)
    (repo / ".claude" / "skills").mkdir(parents=True)
    return repo


def _mk_skill_md(
    repo: Path,
    name: str,
    frontmatter: str,
    *,
    root: str = "plugins/harness-creator",
) -> Path:
    """repo/<root>/skills/<name>/SKILL.md を書いてそのパスを返す。"""
    d = repo / root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(f"---\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_fm
# ---------------------------------------------------------------------------
def test_parse_fm_scalar_and_quotes(MOD):
    text = (
        "---\n"
        'name: "wrap-foo"\n'
        "base: 'some-base'\n"
        "danger: true\n"
        "# this is a comment line\n"
        "\n"  # 空行は skip
        "effect: external-mutation\n"
        "---\n\nbody\n"
    )
    fm = MOD.parse_fm(text)
    assert fm["name"] == "wrap-foo"  # ダブルクォート除去
    assert fm["base"] == "some-base"  # シングルクォート除去
    assert fm["danger"] == "true"
    assert fm["effect"] == "external-mutation"
    assert "#" not in fm  # コメント行は取り込まれない


def test_parse_fm_no_frontmatter(MOD):
    assert MOD.parse_fm("plain body, no fence") == {}


def test_parse_fm_unterminated(MOD):
    assert MOD.parse_fm("---\nname: x\n") == {}


def test_parse_fm_ignores_non_kv_lines(MOD):
    # フェンス内に key:value でない行があっても無視される
    text = "---\nname: ref-x\nthis is not a kv line\n---\n"
    fm = MOD.parse_fm(text)
    assert fm == {"name": "ref-x"}


# ---------------------------------------------------------------------------
# _repo_root
# ---------------------------------------------------------------------------
def test_repo_root_finds_git_dir(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "ref-x", "name: ref-x")
    assert MOD._repo_root(p) == repo.resolve()


def test_repo_root_fallback_when_no_git(MOD, tmp_path):
    # .git が無い場合は引数の親を返す (フォールバック経路)
    lone = tmp_path / "lonely" / "file.md"
    lone.parent.mkdir(parents=True)
    lone.write_text("x", encoding="utf-8")
    # tmp_path 配下に上位の .git が無いことを前提に、フォールバックが parent を返す
    result = MOD._repo_root(lone)
    assert isinstance(result, Path)
    # .git を持つ祖先があればそれ、無ければ file の親
    assert (result / ".git").exists() or result == lone.resolve().parent


# ---------------------------------------------------------------------------
# skill_exists
# ---------------------------------------------------------------------------
def test_skill_exists_under_creator_kit(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "run-target", "name: run-target")
    assert MOD.skill_exists("run-target", repo) is True


def test_skill_exists_under_dot_claude(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "run-claude", "name: run-claude", root=".claude")
    assert MOD.skill_exists("run-claude", repo) is True


def test_skill_exists_missing(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    assert MOD.skill_exists("nope", repo) is False


# ---------------------------------------------------------------------------
# _collect_inbound_refs
# ---------------------------------------------------------------------------
def test_collect_inbound_refs_from_list_and_scalar(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    # list 形式 reference_refs に ref-shared を含む
    _mk_skill_md(
        repo,
        "run-consumer",
        "name: run-consumer\nreference_refs:\n  - ../ref-shared/references/a.md\n",
    )
    # scalar 形式 script_refs に wrap-tool を含む
    _mk_skill_md(
        repo,
        "run-other",
        "name: run-other\nscript_refs: ../wrap-tool/scripts/run.py\n",
        root=".claude",
    )
    inbound = MOD._collect_inbound_refs(repo)
    assert "ref-shared" in inbound
    assert "wrap-tool" in inbound


def test_collect_inbound_refs_ignores_non_ref_keys(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    # base: は対象キーでないので拾わない
    _mk_skill_md(
        repo,
        "wrap-x",
        "name: wrap-x\nbase: ref-notcounted\n",
    )
    inbound = MOD._collect_inbound_refs(repo)
    assert "ref-notcounted" not in inbound


def test_collect_inbound_refs_skips_bad_frontmatter(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    # frontmatter が無い / 未終端の SKILL.md は安全に skip される
    d1 = repo / "plugins" / "harness-creator" / "skills" / "broken1"
    d1.mkdir(parents=True)
    (d1 / "SKILL.md").write_text("no frontmatter at all", encoding="utf-8")
    d2 = repo / "plugins" / "harness-creator" / "skills" / "broken2"
    d2.mkdir(parents=True)
    (d2 / "SKILL.md").write_text("---\nname: broken2\n", encoding="utf-8")
    # 例外を出さず空集合 (または他からの参照のみ)
    assert MOD._collect_inbound_refs(repo) == set()


def test_collect_inbound_refs_no_skills_root(MOD, tmp_path):
    # skills root ディレクトリが両方とも存在しない場合でも空集合を返す
    repo = tmp_path / "bare"
    (repo / ".git").mkdir(parents=True)
    assert MOD._collect_inbound_refs(repo) == set()


def test_collect_inbound_refs_swallows_read_oserror(MOD, tmp_path):
    # SKILL.md が読めない (ディレクトリとして存在) 場合 OSError を握りつぶし継続する
    repo = _mk_repo(tmp_path)
    # 正常に参照を持つスキル
    _mk_skill_md(
        repo,
        "run-consumer",
        "name: run-consumer\nreference_refs:\n  - ../ref-shared/references/a.md\n",
    )
    # SKILL.md をディレクトリとして作る -> read_text が IsADirectoryError(OSError)
    bad = repo / "plugins" / "harness-creator" / "skills" / "broken" / "SKILL.md"
    bad.mkdir(parents=True)
    inbound = MOD._collect_inbound_refs(repo)
    # OSError を吐かず、正常スキルからの参照は収集される
    assert "ref-shared" in inbound


# ---------------------------------------------------------------------------
# check_skill — 条件 (1) wrap-* base
# ---------------------------------------------------------------------------
def test_check_wrap_clean(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "wrap-foo", "name: wrap-foo\nbase: run-base")
    _mk_skill_md(repo, "run-base", "name: run-base")  # pair でないので存在不問だが置く
    assert MOD.check_skill(p, inbound_refs=set()) == []


def test_check_wrap_missing_base(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "wrap-foo", "name: wrap-foo")
    errs = MOD.check_skill(p, inbound_refs=set())
    assert len(errs) == 1
    assert "Step 7-1" in errs[0]
    assert "wrap-foo" in errs[0]


def test_check_wrap_missing_base_allow_partial(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "wrap-foo", "name: wrap-foo")
    assert MOD.check_skill(p, inbound_refs=set(), allow_partial=True) == []


# ---------------------------------------------------------------------------
# check_skill — 条件 (2)(3) evaluator pair
# ---------------------------------------------------------------------------
def test_check_evaluator_clean(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "assign-foo", "name: assign-foo")  # pair の相手 (存在する)
    p = _mk_skill_md(
        repo, "assign-foo-evaluator", "name: assign-foo-evaluator\npair: assign-foo"
    )
    assert MOD.check_skill(p, inbound_refs=set()) == []


def test_check_evaluator_missing_pair(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo, "assign-foo-evaluator", "name: assign-foo-evaluator"
    )
    errs = MOD.check_skill(p, inbound_refs=set())
    assert any("Step 7-2" in e for e in errs)


def test_check_evaluator_missing_pair_allow_partial(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "assign-foo-evaluator", "name: assign-foo-evaluator")
    assert MOD.check_skill(p, inbound_refs=set(), allow_partial=True) == []


def test_check_pair_target_not_found(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "assign-foo-evaluator",
        "name: assign-foo-evaluator\npair: assign-ghost",
    )
    errs = MOD.check_skill(p, inbound_refs=set())
    assert any("Step 7-3" in e for e in errs)
    assert any("assign-ghost" in e for e in errs)


def test_check_pair_present_but_partial_does_not_silence_pair_target(MOD, tmp_path):
    # allow_partial でも (3) pair 相手不在は依然エラー (skeleton 許容は 7-1/7-2 のみ)
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "assign-foo-evaluator",
        "name: assign-foo-evaluator\npair: assign-ghost",
    )
    errs = MOD.check_skill(p, inbound_refs=set(), allow_partial=True)
    assert any("Step 7-3" in e for e in errs)


# ---------------------------------------------------------------------------
# check_skill — 条件 (4) dangerous run-*
# ---------------------------------------------------------------------------
def test_check_dangerous_run_via_danger_flag(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "run-mutate", "name: run-mutate\ndanger: true")
    errs = MOD.check_skill(p, inbound_refs=set())
    assert any("Step 7-4" in e for e in errs)


def test_check_dangerous_run_via_effect(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo, "run-mutate", "name: run-mutate\neffect: external-mutation"
    )
    errs = MOD.check_skill(p, inbound_refs=set())
    assert any("Step 7-4" in e for e in errs)


def test_check_dangerous_run_satisfied_by_dmi(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "run-mutate",
        "name: run-mutate\ndanger: true\ndisable-model-invocation: true",
    )
    assert MOD.check_skill(p, inbound_refs=set()) == []


def test_check_safe_run_no_constraint(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "run-safe", "name: run-safe")
    assert MOD.check_skill(p, inbound_refs=set()) == []


# ---------------------------------------------------------------------------
# check_skill — 条件 (5) ref-* 到達可能性
# ---------------------------------------------------------------------------
def test_check_ref_unreachable(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "ref-lonely",
        "name: ref-lonely\ndisable-model-invocation: true\nuser-invocable: false",
    )
    errs = MOD.check_skill(p, inbound_refs=set())
    assert any("Step 7-5" in e for e in errs)
    assert any("unreachable" in e for e in errs)


def test_check_ref_reachable_via_user_invocable(MOD, tmp_path):
    # user-invocable のデフォルト true なら到達可能
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "ref-x",
        "name: ref-x\ndisable-model-invocation: true",
    )
    assert MOD.check_skill(p, inbound_refs=set()) == []


def test_check_ref_reachable_via_model_invocation(MOD, tmp_path):
    # disable-model-invocation のデフォルト false なら到達可能
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "ref-x",
        "name: ref-x\nuser-invocable: false",
    )
    assert MOD.check_skill(p, inbound_refs=set()) == []


def test_check_ref_reachable_via_inbound(MOD, tmp_path):
    # 両無効でも他スキルからの inbound 参照があれば到達可能
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(
        repo,
        "ref-shared",
        "name: ref-shared\ndisable-model-invocation: true\nuser-invocable: false",
    )
    assert MOD.check_skill(p, inbound_refs={"ref-shared"}) == []


def test_check_skill_collects_inbound_when_none(MOD, tmp_path):
    # inbound_refs=None の場合、check_skill 内部で _collect_inbound_refs を実行する経路
    repo = _mk_repo(tmp_path)
    # ref-shared を参照するスキルを置く -> inbound 集合に入り到達可能になる
    _mk_skill_md(
        repo,
        "run-consumer",
        "name: run-consumer\nreference_refs:\n  - ../ref-shared/references/a.md\n",
    )
    p = _mk_skill_md(
        repo,
        "ref-shared",
        "name: ref-shared\ndisable-model-invocation: true\nuser-invocable: false",
    )
    # inbound_refs を渡さない -> 内部収集で ref-shared が到達可能と判定される
    assert MOD.check_skill(p) == []


def test_check_skill_uses_parent_dir_name_when_no_name_field(MOD, tmp_path):
    # name: フィールドが無い場合は親ディレクトリ名を採用する
    repo = _mk_repo(tmp_path)
    d = repo / "plugins" / "harness-creator" / "skills" / "wrap-bydir"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nbase:\n---\n\nbody\n", encoding="utf-8")
    errs = MOD.check_skill(d / "SKILL.md", inbound_refs=set())
    # ディレクトリ名 wrap-bydir から wrap- 判定され base 欠落エラー
    assert any("wrap-bydir" in e and "Step 7-1" in e for e in errs)


# ---------------------------------------------------------------------------
# main (in-process) — 全分岐被覆
# ---------------------------------------------------------------------------
def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["lint-skill-dep-step7.py", *args])


def test_main_no_targets_usage(MOD, monkeypatch, capsys):
    _argv(monkeypatch)
    assert MOD.main() == 2
    assert "usage:" in capsys.readouterr().err


def test_main_skills_dir_not_a_directory(MOD, tmp_path, monkeypatch, capsys):
    _argv(monkeypatch, "--skills-dir", str(tmp_path / "missing"))
    assert MOD.main() == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_skills_dir_ok(MOD, tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    # 合格スキル群
    _mk_skill_md(repo, "run-base", "name: run-base")
    _mk_skill_md(repo, "wrap-foo", "name: wrap-foo\nbase: run-base")
    _mk_skill_md(repo, "assign-foo", "name: assign-foo")
    _mk_skill_md(
        repo, "assign-foo-evaluator", "name: assign-foo-evaluator\npair: assign-foo"
    )
    skills_dir = repo / "plugins" / "harness-creator" / "skills"
    _argv(monkeypatch, "--skills-dir", str(skills_dir))
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "Step 7 全5条件 PASS" in out
    assert "(partial allowed)" not in out


def test_main_skills_dir_findings_exit1(MOD, tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "wrap-bad", "name: wrap-bad")  # base 欠落
    skills_dir = repo / "plugins" / "harness-creator" / "skills"
    _argv(monkeypatch, "--skills-dir", str(skills_dir))
    assert MOD.main() == 1
    err = capsys.readouterr().err
    assert "wrap-bad" in err
    assert "Step 7-1" in err


def test_main_skills_dir_allow_partial_suffix(MOD, tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "wrap-skel", "name: wrap-skel")  # base 欠落だが partial 許容
    skills_dir = repo / "plugins" / "harness-creator" / "skills"
    _argv(monkeypatch, "--skills-dir", str(skills_dir), "--allow-partial")
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "(partial allowed)" in out


def test_main_positional_paths(MOD, tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    p = _mk_skill_md(repo, "run-safe", "name: run-safe")
    _argv(monkeypatch, str(p))
    assert MOD.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_main_positional_not_found(MOD, tmp_path, monkeypatch, capsys):
    # 存在しないパスは "not found" として all_errs に入り exit1
    repo = _mk_repo(tmp_path)
    # 少なくとも 1 つ実在 path も渡して inbound 収集の repo 解決を成立させる
    real = _mk_skill_md(repo, "run-safe", "name: run-safe")
    ghost = repo / "plugins" / "harness-creator" / "skills" / "ghost" / "SKILL.md"
    _argv(monkeypatch, str(ghost), str(real))
    assert MOD.main() == 1
    err = capsys.readouterr().err
    assert "not found" in err


# ---------------------------------------------------------------------------
# main / __main__ guard via subprocess
# ---------------------------------------------------------------------------
def test_subprocess_usage_exit2(MOD):
    r = _run([])
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_subprocess_skills_dir_ok(MOD, tmp_path):
    repo = _mk_repo(tmp_path)
    _mk_skill_md(repo, "run-safe", "name: run-safe")
    skills_dir = repo / "plugins" / "harness-creator" / "skills"
    r = _run(["--skills-dir", str(skills_dir)])
    assert r.returncode == 0
    assert "PASS" in r.stdout
