"""check-review-trigger.py (Stop hook) の確実起動ロジックと安全弁を実証する。

ユーザー要望「Claude Code 実行完了をフックで捉え評価を確実に起動」の核は
decision:block。ただし無限ループ防止/自己ブロック回避/opt-out の三安全弁が
正しく効くことが同じくらい重要。本テストはその両面を固める:
  - _unevaluated_or_stale: verdict 欠落 or SHA 不一致 (stale) を pending に挙げ、
    harness-creator 自身は Stop block 対象から除外する。
  - _enqueue: 同一 changed_skills セットは冪等スキップ (queue 肥大防止)。
  - main(): pending があれば decision:block を出すが、stop_hook_active 継続中 /
    env opt-out 時は block しない。
"""
import hashlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-elegant-review"
    / "scripts"
    / "check-review-trigger.py"
)
SPEC = importlib.util.spec_from_file_location("check_review_trigger", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- パス判定の純関数 ---

def test_is_skill_md_matches_only_skill_md():
    assert MOD._is_skill_md("plugins/demo/skills/run-x/SKILL.md")
    assert not MOD._is_skill_md("plugins/demo/skills/run-x/scripts/foo.py")
    assert not MOD._is_skill_md("plugins/demo/agents/prompts/a.md")


def test_parse_plugin_skill_extracts_pair():
    assert MOD._parse_plugin_skill("plugins/demo/skills/run-x/SKILL.md") == ("demo", "run-x")
    assert MOD._parse_plugin_skill("not/a/path") == (None, None)


def test_semantic_changed_paths_filters_eval_artifacts():
    paths = [
        "plugins/demo/skills/run-x/SKILL.md",
        "plugins/demo/skills/run-x/rubric.json",
        "plugins/demo/skills/run-x/workflow-manifest.json",
        "README.md",  # 除外される
        "plugins/demo/skills/run-x/scripts/foo.py",  # 除外される
    ]
    got = MOD._semantic_changed_paths(paths)
    assert "plugins/demo/skills/run-x/SKILL.md" in got
    assert "plugins/demo/skills/run-x/rubric.json" in got
    assert "plugins/demo/skills/run-x/workflow-manifest.json" in got
    assert "README.md" not in got
    assert all("foo.py" not in g for g in got)


# --- queue 冪等性 ---

def test_enqueue_is_idempotent_on_same_set(tmp_path):
    q = str(tmp_path / "eval-log" / "review-queue.jsonl")
    assert MOD._enqueue(q, "first", ["demo/run-x"]) is True
    # 同一 changed_skills セットの 2 回目は追記しない。
    assert MOD._enqueue(q, "second", ["demo/run-x"]) is False
    # 異なるセットなら追記する。
    assert MOD._enqueue(q, "third", ["demo/run-y"]) is True
    lines = [l for l in Path(q).read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2


# --- stale 検出 (評価が確実に再起動する保証の核) ---

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
    pending = MOD._unevaluated_or_stale(str(tmp_path), [rel])
    assert pending == ["demo/run-x"]


def test_not_pending_when_verdict_sha_matches(tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x", body="# fresh\n")
    sha = hashlib.sha256(b"# fresh\n").hexdigest()
    _write_verdicts(tmp_path, "demo", "run-x", sha)
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == []


def test_pending_when_verdict_sha_is_stale(tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x", body="# changed\n")
    _write_verdicts(tmp_path, "demo", "run-x", "deadbeef")  # 古い SHA
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == ["demo/run-x"]


def test_harness_creator_self_is_excluded(tmp_path):
    rel = _make_skill(tmp_path, "harness-creator", "run-build-skill")
    # verdict 欠落でも harness-creator 自身は Stop block 対象から外れる。
    assert MOD._unevaluated_or_stale(str(tmp_path), [rel]) == []


def test_pending_review_targets_exempt_true_returns_self_only(tmp_path):
    self_rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill")
    other_rel = _make_skill(tmp_path, "demo", "run-x")
    got = MOD._pending_review_targets(str(tmp_path), [self_rel, other_rel], exempt=True)
    assert got == [f"{MOD.SELF_EXCLUDED_PLUGIN}/run-build-skill"]


def test_pending_review_targets_exempt_true_empty_when_verdict_fresh(tmp_path):
    body = "# fresh\n"
    self_rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill", body=body)
    sha = hashlib.sha256(body.encode()).hexdigest()
    _write_verdicts(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill", sha)
    assert MOD._pending_review_targets(str(tmp_path), [self_rel], exempt=True) == []


# --- main(): decision:block と安全弁 ---

def _run_main(monkeypatch, root: Path, changed_rel: list[str], stdin_obj: dict):
    monkeypatch.setattr(MOD, "_git_repo_root", lambda: str(root))
    monkeypatch.setattr(MOD, "_changed_paths", lambda: list(changed_rel))
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(json.dumps(stdin_obj)))
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = MOD.main()
    return rc, buf.getvalue()


def test_main_blocks_when_pending(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "run-elegant-review" in payload["reason"]


def test_main_does_not_block_when_stop_hook_active(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    rc, out = _run_main(
        monkeypatch, tmp_path, [rel],
        {"hook_event_name": "Stop", "stop_hook_active": True},
    )
    assert rc == 0
    assert '"decision": "block"' not in out and '"decision":"block"' not in out


def test_main_opt_out_env_disables_block(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, "demo", "run-x")
    monkeypatch.setenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", "1")
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    assert "block" not in out


# --- self-plugin 通知 (block しない・完全無音の解消) ---

def test_main_notifies_self_pending_without_block(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill")
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "Stop"})
    assert rc == 0
    payload = json.loads(out)
    assert "decision" not in payload  # block はしない
    assert payload["notice"] == "self-plugin content-review pending"
    assert f"{MOD.SELF_EXCLUDED_PLUGIN}/run-build-skill" in payload["pending_skills"]
    assert "lint-content-review" in payload["reason"]


def test_main_block_takes_precedence_over_self_notice(monkeypatch, tmp_path):
    # 他プラグイン pending が残る場合は decision:block を単独 JSON で出す
    # (self 通知が混ざると decision JSON の parse を壊すため、block が先に return)。
    self_rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill")
    other_rel = _make_skill(tmp_path, "demo", "run-x")
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    rc, out = _run_main(monkeypatch, tmp_path, [self_rel, other_rel], {"hook_event_name": "Stop"})
    assert rc == 0
    payload = json.loads(out)  # 単独で parse 可能な decision JSON
    assert payload["decision"] == "block"
    assert "notice" not in payload


def test_main_self_notice_not_emitted_on_non_stop_event(monkeypatch, tmp_path):
    rel = _make_skill(tmp_path, MOD.SELF_EXCLUDED_PLUGIN, "run-build-skill")
    monkeypatch.delenv("HARNESS_CREATOR_NO_REVIEW_BLOCK", raising=False)
    rc, out = _run_main(monkeypatch, tmp_path, [rel], {"hook_event_name": "PostToolUse"})
    assert rc == 0
    assert "notice" not in out
