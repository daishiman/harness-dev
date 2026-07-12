"""scripts/lint-content-review.py の main() / _git_changed_skills / 未網羅分岐の
genuine な機能テスト (network 不要)。

tests/scripts-root/test_root__lint_content_review.py が純関数 (_check_verdict 等) を
網羅しているのに対し、本ファイルは未到達だった main() の全 exit path
(no target / OK / FAIL)、フィルタ (EXEMPT_KINDS=ref 除外 / 削除 SKILL.md 除外)、
_git_changed_skills の git diff パースと CalledProcessError フォールバック、
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
        return "plugins/p1/skills/run-c/SKILL.md\nREADME.md\n"

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    rc = _run_main(monkeypatch, "--changed-only")
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 skill(s) verified" in out


def test_main_changed_only_git_error_returns_no_target(env, monkeypatch, capsys):
    def boom(cmd, cwd, text):
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(LCR.subprocess, "check_output", boom)
    rc = _run_main(monkeypatch, "--changed-only")
    out = capsys.readouterr().out
    assert rc == 0
    assert "no target skill" in out


def test_main_changed_only_ignores_non_skill_paths(env, monkeypatch, capsys):
    # SKILL.md でないパスのみ -> マッチ無し -> no target
    def fake_diff(cmd, cwd, text):
        return "scripts/foo.py\nplugins/p1/skills/run-c/references/x.md\n"

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    rc = _run_main(monkeypatch, "--changed-only")
    assert rc == 0
    assert "no target skill" in capsys.readouterr().out


# ---------- _git_changed_skills 直呼び ---------------------------------------

def test_git_changed_skills_parses_pairs(env, monkeypatch):
    def fake_diff(cmd, cwd, text):
        return (
            "plugins/alpha/skills/run-a/SKILL.md\n"
            "plugins/beta/skills/run-b/SKILL.md\n"
            "plugins/alpha/skills/run-a/references/r.md\n"  # not SKILL.md
        )

    monkeypatch.setattr(LCR.subprocess, "check_output", fake_diff)
    out = LCR._git_changed_skills("origin/main")
    assert out == {("alpha", "run-a"), ("beta", "run-b")}


# ---------- main(): deleted SKILL.md in changed set is skipped ---------------

def test_main_changed_only_deleted_skill_skipped(env, monkeypatch, capsys):
    # git diff が削除された SKILL.md を返すが実ファイルは無い -> filter で除外
    def fake_diff(cmd, cwd, text):
        return "plugins/p1/skills/gone/SKILL.md\n"

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
