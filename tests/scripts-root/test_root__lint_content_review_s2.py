"""scripts/lint-content-review.py の main() / _git_changed_skills / 未網羅分岐の
genuine な機能テスト (network 不要)。

tests/scripts-root/test_root__lint_content_review.py が純関数 (_check_verdict 等) を
網羅しているのに対し、本ファイルは未到達だった main() の全 exit path
(no target / OK / FAIL)、フィルタ (EXEMPT_KINDS=ref 除外 / 削除 SKILL.md 除外)、
_git_changed_skills の git diff -z パースと、git の失敗を exit 2 にすること、
_check_verdict の残りの schema 分岐 (feedback_loop 各型 / iterations 型 /
skill_md_sha256 欠落 / criteria 空) を網羅する。

すべて tmp_path に閉じた fixture を monkeypatch で module 定数 (ROOT/PLUGINS_DIR/
EVAL_LOG) に差し込み、in-process で main() を呼ぶ (--cov=scripts に直接計上)。
実 repo / 実 eval-log は読み書きしない。
"""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-content-review.py"

_SPEC = importlib.util.spec_from_file_location("lint_content_review_s2", SCRIPT)
LCR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LCR)


# ---------- helpers ----------------------------------------------------------

def _good_verdict(plugin, skill, sha, review_kind="elegance"):
    return {
        "target": {"plugin": plugin, "skill": skill, "skill_md_sha256": sha},
        "review_kind": review_kind,
        "verdict": "PASS",
        "reviewer": "tester",
        "reviewed_at": "2026-06-24T00:00:00Z",
        "iterations": 1,
        "feedback_loop": {
            "criteria_evaluated": ["IN1", "OUT1"],
            "iteration_limit": 3,
            "iteration": 1,
            "loop_scope": "both",
            "positive_feedback": ["good"],
            "negative_feedback": [],
            "next_action": "none",
            "hook_trigger": "Stop",
        },
    }


def _write_skill(plugins_dir, plugin, skill, kind="run"):
    md = plugins_dir / plugin / "skills" / skill / "SKILL.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(f"---\nname: {skill}\nkind: {kind}\n---\nbody\n", encoding="utf-8")
    return md, hashlib.sha256(md.read_bytes()).hexdigest()


def _write_verdicts(eval_log, plugin, skill, sha):
    """両 REQUIRED_VERDICTS を PASS で書く。"""
    rdir = eval_log / plugin / skill / "content-review"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "elegance-verdict.json").write_text(
        json.dumps(_good_verdict(plugin, skill, sha, "elegance")), encoding="utf-8")
    (rdir / "rubric-verdict.json").write_text(
        json.dumps(_good_verdict(plugin, skill, sha, "rubric")), encoding="utf-8")
    return rdir


@pytest.fixture
def env(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    eval_log = tmp_path / "eval-log"
    plugins.mkdir()
    eval_log.mkdir()
    monkeypatch.setattr(LCR, "ROOT", tmp_path)
    monkeypatch.setattr(LCR, "PLUGINS_DIR", plugins)
    monkeypatch.setattr(LCR, "EVAL_LOG", eval_log)
    return {"tmp": tmp_path, "plugins": plugins, "eval_log": eval_log}


def _run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["lint-content-review.py", *argv])
    return LCR.main()


# ---------- main() --all : OK path -------------------------------------------

def test_main_all_ok_when_verdicts_present(env, monkeypatch, capsys):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    _write_verdicts(env["eval_log"], "p1", "run-x", sha)
    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 skill(s) verified" in out


# ---------- main() --all : FAIL path (missing verdicts) ----------------------

def test_main_all_fail_when_verdicts_missing(env, monkeypatch, capsys):
    _write_skill(env["plugins"], "p1", "run-x")  # no verdicts written
    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 1
    assert "violation(s)" in out
    # 両 REQUIRED_VERDICTS が missing なので 2 件
    assert "elegance-verdict.json missing" in out
    assert "rubric-verdict.json missing" in out
    assert "run-elegant-review" in out  # Fix ガイダンス出力


# ---------- main() --all : no target ----------------------------------------

def test_main_all_no_target_when_empty(env, monkeypatch, capsys):
    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 0
    assert "no target skill" in out


def test_main_all_ref_kind_exempted(env, monkeypatch, capsys):
    # kind: ref は EXEMPT_KINDS で除外 -> verdict 無くても no target
    _write_skill(env["plugins"], "p1", "ref-x", kind="ref")
    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 0
    assert "no target skill" in out


def test_main_all_mixed_ref_and_run(env, monkeypatch, capsys):
    # ref は除外、run のみ検査対象。run に verdict あれば 1 verified。
    _write_skill(env["plugins"], "p1", "ref-y", kind="ref")
    _, sha = _write_skill(env["plugins"], "p1", "run-y")
    _write_verdicts(env["eval_log"], "p1", "run-y", sha)
    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 skill(s) verified" in out


# ---------- main() --changed-only : git diff parse + filter ------------------

def test_main_changed_only_parses_diff(env, monkeypatch, capsys):
    _, sha = _write_skill(env["plugins"], "p1", "run-c")
    _write_verdicts(env["eval_log"], "p1", "run-c", sha)

    def fake_diff(cmd, cwd, text):
        return "plugins/p1/skills/run-c/SKILL.md\0README.md\0"  # git diff -z は NUL 区切り

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    rc = _run_main(monkeypatch, "--changed-only")
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 skill(s) verified" in out


def test_main_changed_only_git_error_is_an_input_error(env, monkeypatch, capsys):
    # git diff の失敗を「対象なし」(rc0) にすると、base を誤っただけで違反が隠れる (fail-open)。
    def boom(cmd, cwd, text):
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(LCR.subprocess, "check_output", boom)
    rc = _run_main(monkeypatch, "--changed-only")
    captured = capsys.readouterr()
    assert rc == 2
    assert "no target skill" not in captured.out
    assert "git diff origin/main...HEAD failed" in captured.err


def test_main_changed_only_ignores_non_skill_paths(env, monkeypatch, capsys):
    # SKILL.md でないパスのみ -> マッチ無し -> no target
    def fake_diff(cmd, cwd, text):
        return "scripts/foo.py\0plugins/p1/skills/run-c/references/x.md\0"

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    rc = _run_main(monkeypatch, "--changed-only")
    assert rc == 0
    assert "no target skill" in capsys.readouterr().out


# ---------- _git_changed_skills 直呼び ---------------------------------------

def test_git_changed_skills_parses_pairs(env, monkeypatch):
    def fake_diff(cmd, cwd, text):
        return (
            "plugins/alpha/skills/run-a/SKILL.md\0"
            "plugins/beta/skills/run-b/SKILL.md\0"
            "plugins/alpha/skills/run-a/references/r.md\0"  # not SKILL.md
        )

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    out = LCR._git_changed_skills("origin/main")
    assert out == {("alpha", "run-a"), ("beta", "run-b")}


# ---------- main(): deleted SKILL.md in changed set is skipped ---------------

def test_main_changed_only_deleted_skill_skipped(env, monkeypatch, capsys):
    # git diff が削除された SKILL.md を返すが実ファイルは無い -> filter で除外
    def fake_diff(cmd, cwd, text):
        return "plugins/p1/skills/gone/SKILL.md\0"

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    rc = _run_main(monkeypatch, "--changed-only")
    assert rc == 0
    assert "no target skill" in capsys.readouterr().out


# ---------- _check_verdict 残り schema 分岐 ----------------------------------

def _verdict_path(env, plugin="p1", skill="run-x"):
    p = env["eval_log"] / plugin / skill / "content-review"
    p.mkdir(parents=True, exist_ok=True)
    return p / "elegance-verdict.json"


def test_check_verdict_target_not_object(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["target"] = "not-an-object"
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: target must be object"


def test_check_verdict_skill_md_sha256_missing(env):
    _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", "irrelevant")
    del data["target"]["skill_md_sha256"]
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: target.skill_md_sha256 missing"


def test_check_verdict_iterations_not_int(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["iterations"] = "1"
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: iterations must be integer"


def test_check_verdict_feedback_loop_not_object(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"] = []
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop must be object"


def test_check_verdict_criteria_empty(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["criteria_evaluated"] = []
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.criteria_evaluated must be non-empty array"


def test_check_verdict_iteration_limit_not_int(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["iteration_limit"] = "3"
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.iteration_limit must be integer"


def test_check_verdict_iteration_not_int(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["iteration"] = None
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.iteration must be integer"


def test_check_verdict_loop_scope_invalid(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["loop_scope"] = "sideways"
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.loop_scope invalid"


def test_check_verdict_positive_feedback_not_array(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["positive_feedback"] = "good"
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.positive_feedback must be array"


def test_check_verdict_negative_feedback_not_array(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["negative_feedback"] = {}
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.negative_feedback must be array"


def test_check_verdict_hook_trigger_blank(env):
    _, sha = _write_skill(env["plugins"], "p1", "run-x")
    data = _good_verdict("p1", "run-x", sha)
    data["feedback_loop"]["hook_trigger"] = "   "
    path = _verdict_path(env)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert LCR._check_verdict(path, "p1", "run-x", "elegance-verdict.json") == \
        "schema: feedback_loop.hook_trigger missing"


# ---------- _expected_criteria_ids: build-trace 後方互換 ---------------------

def test_expected_criteria_ids_from_skill_local_build_trace(env):
    # frontmatter に criteria 無し -> skill-local build trace を best-effort で読む
    _write_skill(env["plugins"], "p1", "run-x")
    trace = env["eval_log"] / "p1" / "run-x" / "skill-build-trace.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(json.dumps({
        "feedback_contract": {"criteria": [
            {"id": "IN1"}, {"id": "OUT1"}, {"id": "C1"},
        ]}
    }), encoding="utf-8")
    assert LCR._expected_criteria_ids("p1", "run-x") == {"IN1", "OUT1", "C1"}


def test_expected_criteria_ids_global_build_trace_skill_name_filter(env):
    # global trace の skill_name が一致しなければスキップ -> 空集合
    _write_skill(env["plugins"], "p1", "run-x")
    gtrace = env["eval_log"] / "skill-build-trace.json"
    gtrace.write_text(json.dumps({
        "skill_name": "other-skill",
        "feedback_contract": {"criteria": [{"id": "IN9"}]},
    }), encoding="utf-8")
    assert LCR._expected_criteria_ids("p1", "run-x") == set()


def test_expected_criteria_ids_global_build_trace_match(env):
    _write_skill(env["plugins"], "p1", "run-x")
    gtrace = env["eval_log"] / "skill-build-trace.json"
    gtrace.write_text(json.dumps({
        "skill_name": "run-x",
        "feedback_contract": {"criteria": [{"id": "IN5"}]},
    }), encoding="utf-8")
    assert LCR._expected_criteria_ids("p1", "run-x") == {"IN5"}


def test_expected_criteria_ids_none_anywhere(env):
    _write_skill(env["plugins"], "p1", "run-x")
    assert LCR._expected_criteria_ids("p1", "run-x") == set()


# ---------- _all_skills 分岐 (plugin非dir / skills無し) ----------------------

def test_all_skills_ignores_non_dir_plugin_entry(env):
    # plugins/ 直下に file があっても無視される (is_dir false branch)
    (env["plugins"] / "stray.txt").write_text("x", encoding="utf-8")
    _write_skill(env["plugins"], "p1", "run-x")
    assert LCR._all_skills() == {("p1", "run-x")}


def test_all_skills_plugin_without_skills_dir(env):
    # skills ディレクトリの無い plugin は無視 (sk_dir.is_dir false branch)
    (env["plugins"] / "p-empty").mkdir()
    _write_skill(env["plugins"], "p1", "run-x")
    assert LCR._all_skills() == {("p1", "run-x")}


# ---------- _read_kind OSError 経路 -----------------------------------------

def test_read_kind_unreadable_returns_none(env, monkeypatch):
    md, _ = _write_skill(env["plugins"], "p1", "run-x")
    real_read_text = Path.read_text

    def selective(self, *a, **k):
        # 対象 SKILL.md のみ OSError、他 (coverage 等) は素通し
        if self == md:
            raise OSError("permission denied")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", selective)
    assert LCR._read_kind("p1", "run-x") is None


# ---------- _expected_criteria_ids: build-trace feedback_contract 非 dict ----

def test_expected_criteria_ids_build_trace_fc_not_dict(env):
    _write_skill(env["plugins"], "p1", "run-x")
    trace = env["eval_log"] / "p1" / "run-x" / "skill-build-trace.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(json.dumps({"feedback_contract": "not-a-dict"}), encoding="utf-8")
    assert LCR._expected_criteria_ids("p1", "run-x") == set()


# ---------- main(): argparse mutually exclusive enforcement ------------------

def test_main_requires_a_mode():
    r = subprocess.run(
        ["python3", str(SCRIPT)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
    assert "one of the arguments" in r.stderr or "required" in r.stderr


# ---------- 形の崩れた verdict があっても --all は残りの skill を検査する ----------

def test_main_all_reports_a_malformed_verdict_and_keeps_checking(env, monkeypatch, capsys):
    # 独立レビューの再現: verdict が null だと traceback (rc1) で止まり、ほかの skill の違反を報告しなかった
    _, sha_a = _write_skill(env["plugins"], "p1", "run-a")
    rdir = _write_verdicts(env["eval_log"], "p1", "run-a", sha_a)
    (rdir / "elegance-verdict.json").write_text("null", encoding="utf-8")
    _write_skill(env["plugins"], "p1", "run-b")  # verdict なし
    _, sha_c = _write_skill(env["plugins"], "p1", "run-c")
    _write_verdicts(env["eval_log"], "p1", "run-c", sha_c)

    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 1
    assert "3 violation(s)" in out
    assert "p1/run-a: elegance-verdict.json schema: verdict must be a JSON object, got null" in out
    assert "p1/run-b: elegance-verdict.json missing" in out
    assert "p1/run-b: rubric-verdict.json missing" in out
    assert "run-c" not in out  # 正しい skill は違反にならない


def test_main_all_turns_an_unexpected_error_into_a_violation(env, monkeypatch, capsys):
    # 想定していない形 (UTF-8 でない SKILL.md) で検査が例外を出しても、その skill の違反にして続ける
    md, _ = _write_skill(env["plugins"], "p1", "run-a")
    md.write_bytes(b"---\nkind: run\n---\n\xff\n")
    sha_a = hashlib.sha256(md.read_bytes()).hexdigest()
    _write_verdicts(env["eval_log"], "p1", "run-a", sha_a)
    _write_skill(env["plugins"], "p1", "run-b")  # verdict なし

    rc = _run_main(monkeypatch, "--all")
    out = capsys.readouterr().out
    assert rc == 1
    assert "p1/run-a: elegance-verdict.json check-error: could not finish the check (UnicodeDecodeError" in out
    assert "p1/run-b: elegance-verdict.json missing" in out


def test_guarded_returns_the_check_result_or_a_check_error():
    assert LCR._guarded(lambda value: value, None) is None
    assert LCR._guarded(lambda value: value, "stale-sha: x") == "stale-sha: x"
    assert LCR._guarded(lambda: 1 // 0) == (
        "check-error: could not finish the check (ZeroDivisionError: integer division or modulo by zero)"
    )


# ---------- --changed-only: git の失敗は exit 2、path は -z で受ける ----------

def test_main_changed_only_without_git_is_an_input_error(env, monkeypatch, capsys):
    def no_git(cmd, cwd, text):
        raise FileNotFoundError(2, "No such file or directory", "git")

    monkeypatch.setattr(LCR.subprocess, "check_output", no_git)
    rc = _run_main(monkeypatch, "--changed-only")
    captured = capsys.readouterr()
    assert rc == 2
    assert "no target skill" not in captured.out
    assert "FileNotFoundError" in captured.err


def test_main_changed_only_outside_a_repository_is_an_input_error(env, monkeypatch, capsys):
    # ROOT が git repo でないとき (実 git を呼ぶ)。上の階層の repo を拾わないよう ceiling を置く
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(env["tmp"].parent))
    rc = _run_main(monkeypatch, "--changed-only", "--base", "HEAD")
    captured = capsys.readouterr()
    assert rc == 2
    assert "no target skill" not in captured.out
    assert "git diff HEAD...HEAD failed (CalledProcessError" in captured.err


def test_git_changed_paths_asks_git_for_nul_separated_paths(env, monkeypatch):
    seen = {}

    def fake_diff(cmd, cwd, text):
        seen["cmd"] = cmd
        return "plugins/p1/skills/run-a/references/日本語.md\0plugins/p1/skills/run-a/SKILL.md\0"

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    assert LCR._git_changed_paths("origin/main") == {("p1", "run-a"): {"references/日本語.md", "SKILL.md"}}
    assert seen["cmd"] == ["git", "diff", "--name-only", "-z", "origin/main...HEAD"]


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True,
    )


def test_changed_only_picks_up_a_non_ascii_reference_change(env, monkeypatch):
    # 独立レビューの再現: core.quotePath=true (git の既定) だと references/日本語.md の変更が
    # "plugins/..." と引用符つきで出て ^plugins/ に当たらず、--changed-only が取りこぼして rc0 だった
    repo = env["tmp"]
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(repo.parent))
    _, sha = _write_skill(env["plugins"], "p1", "run-a")
    ref = env["plugins"] / "p1" / "skills" / "run-a" / "references" / "日本語.md"
    ref.parent.mkdir()
    ref.write_text("before\n", encoding="utf-8")
    digest = LCR._skill_dir_digest("p1", "run-a")
    rdir = env["eval_log"] / "p1" / "run-a" / "content-review"
    rdir.mkdir(parents=True)
    for kind in ("elegance", "rubric"):
        verdict = _good_verdict("p1", "run-a", sha, kind)
        verdict["target"]["skill_dir_digest"] = digest
        (rdir / f"{kind}-verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "core.quotePath", "true")  # 利用者の global 設定に左右されないよう既定値に固定
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "tag", "base")
    ref.write_text("after\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "change the reference")

    assert LCR._git_changed_paths("base") == {("p1", "run-a"): {"references/日本語.md"}}
    assert LCR._git_changed_skills("base") == {("p1", "run-a")}
    rc = _run_main(monkeypatch, "--changed-only", "--base", "base")
    assert rc == 1  # 変えた reference が digest に当たり stale-dir-digest になる


@pytest.mark.parametrize("content", ["null", "{not json", '{"target": []}', '["target"]'])
def test_changed_only_checks_a_skill_whose_verdict_is_malformed(env, monkeypatch, content):
    # 形の崩れた verdict を「digest なし」と読んで --changed-only の対象から外すと、壊れた記録が素通りする
    _write_skill(env["plugins"], "p1", "run-a")
    rdir = env["eval_log"] / "p1" / "run-a" / "content-review"
    rdir.mkdir(parents=True)
    (rdir / "elegance-verdict.json").write_text(content, encoding="utf-8")
    monkeypatch.setattr(LCR, "_git_changed_paths", lambda base: {("p1", "run-a"): {"references/x.md"}})
    assert LCR._has_dir_digest("p1", "run-a") is True
    assert LCR._git_changed_skills("origin/main") == {("p1", "run-a")}


# ---------- _expected_criteria_ids: 形の崩れた build trace ----------

@pytest.mark.parametrize("trace", [[], ["run-x"], {"skill_name": ["run-x"], "feedback_contract": {"criteria": [{"id": "IN9"}]}}])
def test_expected_criteria_ids_skips_a_malformed_global_build_trace(env, trace):
    # 再現: eval-log/skill-build-trace.json が [] だと data.get で AttributeError、
    # skill_name が配列だと set の in で unhashable だった。後方互換の best-effort 入力なので読み飛ばす
    _write_skill(env["plugins"], "p1", "run-x")
    (env["eval_log"] / "skill-build-trace.json").write_text(json.dumps(trace), encoding="utf-8")
    assert LCR._expected_criteria_ids("p1", "run-x") == set()
