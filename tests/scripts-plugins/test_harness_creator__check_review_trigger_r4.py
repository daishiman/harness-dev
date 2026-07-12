"""check-review-trigger.py (run-elegant-review の Stop hook) を genuine に網羅する。

このスクリプトは git を read-only で参照し、変更量/評価対象 artifact から
  - 出力1: 変更件数 >= THRESHOLD なら run-elegant-review を stdout 推奨
  - 出力2: queue (eval-log/review-queue.jsonl) へ append-only で評価要求を記録
  - 出力3: 未評価 or stale な変更 skill が残れば decision:block で Stop を差し戻す
を行う。exit code は常に 0(継続/停止は stdout JSON の decision で表現)。

network/keychain は無いが subprocess(git) と stdin を叩くため、本テストは:
  - 純関数 (_is_skill_md / _parse_plugin_skill / _semantic_changed_paths /
    _sha256_file / _verdict_recorded_sha / _last_queue_changed_set /
    _enqueue / _unevaluated_or_stale) を実ファイル import で直接検証。
  - git 依存 (_git_repo_root / _changed_paths) は monkeypatch で subprocess.run を
    stub し、正常 (porcelain/rename/diff)・非ゼロ・例外・タイムアウト経路を網羅。
  - main() は stdin / _changed_paths / _git_repo_root を差し替え、decision:block と
    三安全弁 (stop_hook_active / opt-out env / harness-creator 自己除外) を in-process で確認。

tests/test_check_review_trigger.py と衝突しないモジュール名 (_r4) を使う。
"""
import hashlib
import importlib.util
import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-elegant-review"
    / "scripts"
    / "check-review-trigger.py"
)
_SPEC = importlib.util.spec_from_file_location("check_review_trigger_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# _read_stdin_json: 空 / 正常 / 不正 JSON
# --------------------------------------------------------------------------

def _set_stdin(monkeypatch, text):
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(text))


def test_read_stdin_json_empty_returns_empty_dict(monkeypatch):
    _set_stdin(monkeypatch, "   \n  ")
    assert MOD._read_stdin_json() == {}


def test_read_stdin_json_parses_valid(monkeypatch):
    _set_stdin(monkeypatch, json.dumps({"session_id": "s1", "stop_hook_active": True}))
    got = MOD._read_stdin_json()
    assert got["session_id"] == "s1" and got["stop_hook_active"] is True


def test_read_stdin_json_invalid_returns_empty_dict(monkeypatch):
    _set_stdin(monkeypatch, "{not json")
    assert MOD._read_stdin_json() == {}


# --------------------------------------------------------------------------
# _git_repo_root: 正常 / 非ゼロ returncode / 例外
#   新仕様: git 失敗時は cwd を返さず、CLAUDE_PLUGIN_ROOT があればそれ、無ければ None。
#   (旧仕様の os.getcwd() fallback は無関係なユーザ cwd に queue を生成する副作用漏れ
#    だったため撤廃。queue 書込先安全化。)
# --------------------------------------------------------------------------

def _fake_proc(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr="")


def test_git_repo_root_returns_toplevel(monkeypatch):
    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: _fake_proc("/repo/root\n", 0))
    assert MOD._git_repo_root() == "/repo/root"


def test_git_repo_root_none_on_nonzero_without_plugin_root(monkeypatch):
    """git 非ゼロ かつ CLAUDE_PLUGIN_ROOT 未設定 → None (cwd を汚さない)。"""
    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: _fake_proc("", 128))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    assert MOD._git_repo_root() is None


def test_git_repo_root_none_on_exception_without_plugin_root(monkeypatch):
    """git 例外 かつ CLAUDE_PLUGIN_ROOT 未設定 → None。"""
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(MOD.subprocess, "run", boom)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    assert MOD._git_repo_root() is None


def test_git_repo_root_uses_plugin_root_when_git_fails(monkeypatch, tmp_path):
    """git 失敗時に CLAUDE_PLUGIN_ROOT が実在ディレクトリなら self-relative root を返す。"""
    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: _fake_proc("", 128))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
    assert MOD._git_repo_root() == str(tmp_path)


# --------------------------------------------------------------------------
# _changed_paths: porcelain (通常/rename/quoted/空行) + diff の合流, 例外耐性
# --------------------------------------------------------------------------

def test_changed_paths_parses_porcelain_and_diff(monkeypatch):
    porcelain = (
        " M plugins/demo/skills/run-x/SKILL.md\n"
        "?? newfile.txt\n"
        'R  "old name.md" -> "plugins/demo/skills/run-x/rubric.json"\n'
        "\n"  # 空行は無視される
    )
    diff = "plugins/demo/skills/run-x/workflow-manifest.json\nplugins/demo/skills/run-x/SKILL.md\n"

    calls = {"n": 0}

    def fake_run(cmd, **kw):
        # 第1呼: status --porcelain, 第2呼: diff --name-only HEAD
        if "status" in cmd:
            return _fake_proc(porcelain, 0)
        return _fake_proc(diff, 0)

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    paths = MOD._changed_paths()
    assert "plugins/demo/skills/run-x/SKILL.md" in paths
    assert "newfile.txt" in paths
    # rename は新しいパス(矢印の右側・引用符除去)を採用する。
    assert "plugins/demo/skills/run-x/rubric.json" in paths
    assert "plugins/demo/skills/run-x/workflow-manifest.json" in paths
    # 重複排除されソート済み。
    assert paths == sorted(set(paths))


def test_changed_paths_handles_nonzero_and_exception(monkeypatch):
    def fake_run(cmd, **kw):
        if "status" in cmd:
            return _fake_proc("ignored\n", 1)  # 非ゼロは無視
        raise RuntimeError("git diff exploded")  # 例外も握りつぶす

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    assert MOD._changed_paths() == []


def test_changed_paths_porcelain_exception_swallowed(monkeypatch):
    # status 自体が例外を投げても diff 側の結果は拾える (両 try は独立)。
    def fake_run(cmd, **kw):
        if "status" in cmd:
            raise RuntimeError("git status exploded")
        return _fake_proc("only/from/diff.py\n", 0)

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    assert MOD._changed_paths() == ["only/from/diff.py"]


# --------------------------------------------------------------------------
# 純関数: パス判定
# --------------------------------------------------------------------------

def test_is_skill_md():
    assert MOD._is_skill_md("plugins/demo/skills/run-x/SKILL.md")
    assert MOD._is_skill_md("plugins\\demo\\skills\\run-x\\SKILL.md")  # backslash 正規化
    assert not MOD._is_skill_md("plugins/demo/skills/run-x/scripts/foo.py")
    assert not MOD._is_skill_md("docs/skills/run-x/SKILL.md")  # plugins/ 始まりでない


def test_parse_plugin_skill():
    assert MOD._parse_plugin_skill("plugins/demo/skills/run-x/SKILL.md") == ("demo", "run-x")
    assert MOD._parse_plugin_skill("plugins\\p\\skills\\s\\SKILL.md") == ("p", "s")
    assert MOD._parse_plugin_skill("nope/no/path") == (None, None)


def test_semantic_changed_paths_filters_and_dedups():
    paths = [
        "plugins/demo/skills/run-x/SKILL.md",
        "plugins/demo/skills/run-x/SKILL.md",  # 重複
        "plugins/demo/skills/run-x/references/rubric.json",
        "plugins/demo/skills/run-x/workflow-manifest.json",
        "README.md",
        "plugins/demo/skills/run-x/scripts/foo.py",
    ]
    got = MOD._semantic_changed_paths(paths)
    assert got == sorted(set(got))
    assert "README.md" not in got
    assert all("foo.py" not in g for g in got)
    assert "plugins/demo/skills/run-x/references/rubric.json" in got
    assert "plugins/demo/skills/run-x/workflow-manifest.json" in got
    assert got.count("plugins/demo/skills/run-x/SKILL.md") == 1


# --------------------------------------------------------------------------
# _sha256_file: 存在 / 欠落
# --------------------------------------------------------------------------

def test_sha256_file_reads_and_missing(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    assert MOD._sha256_file(str(f)) == hashlib.sha256(b"hello").hexdigest()
    assert MOD._sha256_file(str(tmp_path / "nope.txt")) is None


# --------------------------------------------------------------------------
# _last_queue_changed_set / _verdict_recorded_sha: 読み取り経路
# --------------------------------------------------------------------------

def test_last_queue_changed_set_none_when_missing(tmp_path):
    assert MOD._last_queue_changed_set(str(tmp_path / "q.jsonl")) is None


def test_last_queue_changed_set_empty_file_returns_none(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text("\n\n", encoding="utf-8")
    assert MOD._last_queue_changed_set(str(q)) is None


def test_last_queue_changed_set_reads_last_line(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text(
        json.dumps({"changed_skills": ["a/b"]}) + "\n"
        + json.dumps({"changed_skills": ["c/d", "e/f"]}) + "\n",
        encoding="utf-8",
    )
    assert MOD._last_queue_changed_set(str(q)) == {"c/d", "e/f"}


def test_last_queue_changed_set_corrupt_returns_none(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text("{bad json}\n", encoding="utf-8")
    assert MOD._last_queue_changed_set(str(q)) is None


def test_verdict_recorded_sha_missing_and_present(tmp_path):
    # 欠落
    assert MOD._verdict_recorded_sha(str(tmp_path), "demo", "run-x", "rubric-verdict.json") == (None, False)
    # 存在 + sha
    base = tmp_path / "eval-log" / "demo" / "run-x" / "content-review"
    base.mkdir(parents=True)
    (base / "rubric-verdict.json").write_text(
        json.dumps({"target": {"skill_md_sha256": "abc123"}}), encoding="utf-8"
    )
    assert MOD._verdict_recorded_sha(str(tmp_path), "demo", "run-x", "rubric-verdict.json") == ("abc123", True)


def test_verdict_recorded_sha_corrupt_json(tmp_path):
    base = tmp_path / "eval-log" / "demo" / "run-x" / "content-review"
    base.mkdir(parents=True)
    (base / "rubric-verdict.json").write_text("{broken", encoding="utf-8")
    assert MOD._verdict_recorded_sha(str(tmp_path), "demo", "run-x", "rubric-verdict.json") == (None, False)


# --------------------------------------------------------------------------
# _enqueue: 新規追記 / 冪等スキップ / makedirs / 失敗経路
# --------------------------------------------------------------------------

def test_enqueue_writes_then_idempotent(tmp_path):
    q = str(tmp_path / "eval-log" / "review-queue.jsonl")
    assert MOD._enqueue(q, "reason1", ["demo/run-x"]) is True
    assert MOD._enqueue(q, "reason2", ["demo/run-x"]) is False  # 同一セット
    assert MOD._enqueue(q, "reason3", ["demo/run-y"]) is True  # 異なるセット
    lines = [l for l in Path(q).read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["reason"] == "reason1"
    assert rec["trigger"] == "Stop"
    assert "requested_at" in rec


def test_enqueue_failure_returns_false(monkeypatch, tmp_path):
    q = str(tmp_path / "eval-log" / "review-queue.jsonl")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(MOD.os, "makedirs", boom)
    assert MOD._enqueue(q, "x", ["demo/run-x"]) is False


# --------------------------------------------------------------------------
# _unevaluated_or_stale: 欠落 / 一致 / stale / self除外 / 非SKILL.md skip
# --------------------------------------------------------------------------

def _make_skill(root: Path, plugin: str, skill: str, body: str = "# skill\n") -> str:
    rel = f"plugins/{plugin}/skills/{skill}/SKILL.md"
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return rel


def _write_verdicts(root: Path, plugin: str, skill: str, sha: str):
    base = root / "eval-log" / plugin / skill / "content-review"
    base.mkdir(parents=True, exist_ok=True)
    for fname in MOD.REQUIRED_VERDICTS:
        (base / fname).write_text(
            json.dumps({"target": {"skill_md_sha256": sha}, "verdict": "PASS"}),
            encoding="utf-8",
        )


def test_unevaluated_when_verdict_missing(tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == ["demo/run-x"]


def test_not_pending_when_sha_matches(tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x", body="# fresh\n")
    sha = hashlib.sha256(b"# fresh\n").hexdigest()
    _write_verdicts(tmp_path, "demo", "run-x", sha)
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == []


def test_pending_when_sha_is_stale(tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x", body="# changed\n")
    _write_verdicts(tmp_path, "demo", "run-x", "deadbeef")
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == ["demo/run-x"]


def test_self_excluded_plugin_skipped(tmp_path):
    rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill")
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == []


def test_non_skill_md_paths_skipped(tmp_path):
    # SKILL.md でないパス (rubric.json) は _unevaluated_or_stale 内で skip される。
    assert MOD._unevaluated_or_stale(str(tmp_path), ["plugins/demo/skills/run-x/rubric.json"]) == []


# --------------------------------------------------------------------------
# main(): 統合経路。stdin / git stub を差し替える
# --------------------------------------------------------------------------

def _run_main(monkeypatch, root, changed_rel, stdin_obj, env=None):
    monkeypatch.setattr(MOD, "_git_repo_root", lambda: str(root))
    monkeypatch.setattr(MOD, "_changed_paths", lambda: list(changed_rel))
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(json.dumps(stdin_obj)))
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    if env:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = MOD.main()
    return rc, buf.getvalue()


def test_main_blocks_when_pending(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "run-elegant-review" in payload["reason"]
    # queue にも記録されている (semantic を含むため)。
    q = tmp_path / "eval-log" / "review-queue.jsonl"
    assert q.exists()


def test_main_does_not_block_when_stop_hook_active(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    rc, out = _run_main(
        monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop", "stop_hook_active": True}
    )
    assert rc == 0
    assert "block" not in out


def test_main_opt_out_env_disables_block(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    rc, out = _run_main(
        monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"},
        env={"HARNESS_CREATOR_NO_REVIEW_BLOCK": "1"},
    )
    assert rc == 0
    assert "block" not in out


def test_main_no_block_when_all_fresh_emits_nothing(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x", body="# fresh\n")
    sha = hashlib.sha256(b"# fresh\n").hexdigest()
    _write_verdicts(tmp_path, "demo", "run-x", sha)
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    # pending なし & 件数 < THRESHOLD → 出力1 も出ない。
    assert out.strip() == ""


def test_main_recommendation_when_over_threshold(monkeypatch, tmp_path):
    # 評価対象でない無関係ファイルを 20 件超 → 出力1 (recommendation) のみ。
    changed = [f"src/file_{i}.py" for i in range(MOD.THRESHOLD + 3)]
    rc, out = _run_main(monkeypatch, tmp_path, changed, {"hook_event_name": "Stop"})
    assert rc == 0
    payload = json.loads(out)
    assert payload["recommendation"] == "run-elegant-review"
    assert payload["changed_files"] == MOD.THRESHOLD + 3
    assert payload["threshold"] == MOD.THRESHOLD
    # queue 化もされている (件数 >= THRESHOLD)。reason は件数ベース。
    q = tmp_path / "eval-log" / "review-queue.jsonl"
    rec = json.loads(q.read_text(encoding="utf-8").splitlines()[-1])
    assert str(MOD.THRESHOLD) in rec["reason"]


def test_main_semantic_under_threshold_enqueues_only(monkeypatch, tmp_path):
    # 評価対象 1 件のみ・件数 < THRESHOLD だが harness-creator 自身 → block されず queue だけ。
    rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-x")
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    assert "block" not in out
    q = tmp_path / "eval-log" / "review-queue.jsonl"
    rec = json.loads(q.read_text(encoding="utf-8").splitlines()[-1])
    assert "評価対象 artifact" in rec["reason"]


def test_main_empty_stdin_treated_as_stop(monkeypatch, tmp_path):
    # 空 stdin (inp == {}) は is_stop_event=True 扱いで block 判定が走る。
    rel = _make_skill(tmp_path, "demo", "run-x")
    monkeypatch.setattr(MOD, "_git_repo_root", lambda: str(tmp_path))
    monkeypatch.setattr(MOD, "_changed_paths", lambda: [rel])
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(""))
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = MOD.main()
    assert rc == 0
    assert json.loads(buf.getvalue())["decision"] == "block"


def test_main_non_stop_event_skips_block(monkeypatch, tmp_path):
    # 非 Stop イベント (例: PreToolUse) では block 判定を行わない。
    rel = _make_skill(tmp_path, "demo", "run-x")
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "PreToolUse"})
    assert rc == 0
    assert "block" not in out


def test_main_many_pending_truncates_list(monkeypatch, tmp_path):
    # pending が 8 件超なら reason に省略記号 (" …") が付く。
    rels = []
    for i in range(10):
        rels.append(_make_skill(tmp_path, "demo", f"run-{i}"))
    rc, out = _run_main(monkeypatch, tmp_path, rels, {"hook_event_name": "Stop"})
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "10 件" in payload["reason"]
    assert "…" in payload["reason"]


def test_main_swallows_internal_exception(monkeypatch, tmp_path):
    # main 内部で例外が起きても exit 0 を保つ (Stop hook は落とさない)。
    monkeypatch.setattr(MOD, "_changed_paths", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO("{}"))
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# CLI: subprocess で __main__ 経路 (exit 常に 0) を確認
# --------------------------------------------------------------------------

def test_cli_exit_zero_with_empty_stdin():
    import sys as _sys

    proc = subprocess.run(
        [_sys.executable, str(SCRIPT)],
        input="",
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    # Stop hook は常に exit 0。
    assert proc.returncode == 0
