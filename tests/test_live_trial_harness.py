"""run-skill-live-trial harness の機械検証 (tmux 非依存)。

- live-trial-status: transcript JSONL の 4 状態分類 + interrupt 例外 + subagents bytes 合算
- live-trial-poll: 終端 4 分岐 (DONE/STALL/GATE/HARD_CAP) + state-file JSON 永続化
- live-trial-verdict: schema 自己検証 / skill_dir_tree_sha 決定論 / proof 機械 gate /
  nudge 降格 / denylist 拒否
- live-trial-backend/boot/send: オフライン検査 (tmux 呼出は BLOCKED/fallback 側のみ)

合成 fixture は references/transcript-jsonl.md の実測スキーマに従う。
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial" / "scripts"
SCHEMA = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
    / "schemas" / "live-trial-verdict.schema.json"
)


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), SCRIPTS / f"{stem}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


status_mod = _load("live-trial-status")
poll_mod = _load("live-trial-poll")
verdict_mod = _load("live-trial-verdict")
backend_mod = _load("live-trial-backend")
boot_mod = _load("live-trial-boot")
send_mod = _load("live-trial-send")


# ---- 合成 transcript fixture -------------------------------------------------

def _write_jsonl(path: Path, entries: list[dict]) -> Path:
    for i, e in enumerate(entries):
        e.setdefault("timestamp", f"2026-07-02T00:00:{i:02d}Z")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return path


def _prompt(text="run the task"):
    return {"type": "user", "message": {"content": text}}


def _turn_end():
    return {"type": "system", "subtype": "turn_duration"}


def _tool_use(tid, name):
    return {"type": "assistant", "message": {
        "model": "claude-opus-4-8",
        "content": [{"type": "tool_use", "id": tid, "name": name}]}}


def _tool_result(tid):
    return {"type": "user", "message": {
        "content": [{"type": "tool_result", "tool_use_id": tid}]}}


FIXTURES = {
    "waiting": [_prompt(), _tool_use("t1", "AskUserQuestion")],
    "busy_tool": [_prompt(), _tool_use("t2", "Bash")],
    "busy_gen": [_prompt()],
    "idle": [_prompt(), _tool_use("t3", "Bash"), _tool_result("t3"), _turn_end()],
}


# ---- live-trial-status: 4 状態分類 -------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("waiting", "WAITING_USER_INPUT"),
    ("busy_tool", "BUSY_TOOL_RUNNING"),
    ("busy_gen", "BUSY_GENERATING"),
    ("idle", "IDLE_TURN_COMPLETE"),
])
def test_status_four_states(tmp_path, name, expected):
    p = _write_jsonl(tmp_path / f"{name}.jsonl", [dict(e) for e in FIXTURES[name]])
    result = status_mod.classify(p)
    assert result["state"] == expected


def test_status_interrupt_is_turn_end(tmp_path):
    entries = [_prompt(), {"type": "user",
                           "message": {"content": "[Request interrupted by user]"}}]
    p = _write_jsonl(tmp_path / "int.jsonl", entries)
    assert status_mod.classify(p)["state"] == "IDLE_TURN_COMPLETE"


def test_status_missing_or_empty_returns_none(tmp_path):
    assert status_mod.classify(tmp_path / "nope.jsonl") is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert status_mod.classify(empty) is None
    # 全行 parse 不能も None (TUI fallback へ)
    garbage = tmp_path / "garbage.jsonl"
    garbage.write_text("not json at all\n", encoding="utf-8")
    assert status_mod.classify(garbage) is None


def test_status_subagent_bytes_aggregated(tmp_path):
    """fork 内長時間実行の STALL 誤報対策: subagents/*.jsonl bytes を合算する。"""
    p = _write_jsonl(tmp_path / "s.jsonl", [_prompt()])
    base = status_mod.transcript_bytes(p)
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    (sub / "a.jsonl").write_text("x" * 100, encoding="utf-8")
    assert status_mod.transcript_bytes(p) == base + 100


def test_status_cli_exit3_on_missing(tmp_path, capsys):
    assert status_mod.main([str(tmp_path / "none.jsonl")]) == 3
    p = _write_jsonl(tmp_path / "idle.jsonl", [dict(e) for e in FIXTURES["idle"]])
    assert status_mod.main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "STATE:IDLE_TURN_COMPLETE" in out and "BYTES:" in out


# ---- live-trial-poll: 終端 4 分岐 + state-file --------------------------------

def _poll_env(monkeypatch, tmp_path, session_id="u-1", **env):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setenv("SESSION_ID", session_id)
    defaults = {"INTERVAL": "0", "STABLE_TICKS": "2",
                "STALL_LIMIT": "600", "HARD_CAP": "7200"}
    defaults.update({k: str(v) for k, v in env.items()})
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    return projects


def test_poll_done(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    rc = poll_mod.main([str(marker), "lt-test"])
    assert rc == poll_mod.EXIT_DONE
    assert "via jsonl" in capsys.readouterr().out


def test_poll_gate_after_two_ticks_and_resets(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["waiting"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file),
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_GATE
    assert "AskUserQuestion" in capsys.readouterr().out
    # 応答後の再 poll が即 GATE 再発しないよう gate_ticks=0 で永続化される
    assert json.loads(state_file.read_text())["gate_ticks"] == 0


def test_poll_stall_no_artifact(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", STALL_LIMIT="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_STALL
    assert "成果物なし" in capsys.readouterr().out


def test_poll_hard_cap(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", HARD_CAP="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_HARD_CAP
    out = capsys.readouterr().out
    assert "HARD_CAP" in out


def test_poll_state_file_persists_counters(monkeypatch, tmp_path):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file), "--max-ticks", "2",
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_TICK_BUDGET
    st = json.loads(state_file.read_text())
    assert st["elapsed"] == 1  # 呼び越しで 0 に戻らない (STALL/HARD_CAP 実効の前提)
    assert st["prev"].startswith("jsonl:")
    # 同一 state-file の再呼びで elapsed が引き継がれ DONE に到達する
    # (trial 完了を模して jsonl を idle へ更新 — busy のままだと DONE 条件を満たさない)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    monkeypatch.setenv("INTERVAL", "0")
    monkeypatch.setenv("STABLE_TICKS", "1")
    rc2 = poll_mod.main(["--state-file", str(state_file),
                         str(marker), "lt-test"])
    assert rc2 == poll_mod.EXIT_DONE
    assert json.loads(state_file.read_text())["elapsed"] >= 1


def test_poll_corrupt_state_file_recovers(monkeypatch, tmp_path):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    state_file = tmp_path / "state.json"
    state_file.write_text("{broken", encoding="utf-8")
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text("{}", encoding="utf-8")
    assert poll_mod.main(["--state-file", str(state_file),
                          str(marker), "lt-test"]) == poll_mod.EXIT_DONE


# ---- live-trial-verdict: schema / tree sha / gate ----------------------------

def _fake_skill_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fake-skill"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: fake\n---\nbody\n", encoding="utf-8")
    (d / "scripts" / "a.py").write_text("print('a')\n", encoding="utf-8")
    return d


def _run_verdict(tmp_path, transcript: Path, extra: list[str]) -> tuple[int, Path]:
    workdir = tmp_path / "workdir"
    skill_dir = _fake_skill_dir(tmp_path)
    argv = [
        "--workdir", str(workdir),
        "--target-skill", "some-plugin:run-something",
        "--skill-dir", str(skill_dir),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
        "--poll-exit", "DONE",
    ] + extra
    rc = verdict_mod.main(argv)
    return rc, workdir / "verdict.json"


@pytest.fixture()
def transcript(tmp_path):
    entries = [dict(_prompt()), dict(_tool_use("t9", "Bash")),
               dict(_tool_result("t9")), dict(_turn_end())]
    entries[1]["version"] = "2.1.173"
    return _write_jsonl(tmp_path / "src" / "u-9.jsonl", entries)


def test_verdict_pass_and_schema_valid(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    assert verdict_mod.validate_schema(doc, schema) == []
    assert doc["overall"]["verdict"] == "PASS"
    assert doc["actual_model"] == ["claude-opus-4-8"]
    assert doc["environment"]["claude_version"] == "2.1.173"
    assert doc["environment"]["transcript_layer"] == "jsonl"
    assert doc["transcript_sha256"] and len(doc["transcript_sha256"]) == 64
    assert (tmp_path / "workdir" / "transcript.jsonl").is_file()


def test_verdict_goal_fail_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "FAIL", "--blocker", "成果物が目的を満たさない"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "goal-proxy" in doc["downgrade_reason"]


def test_verdict_nudge_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--nudge-count", "1"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "自走未達" in doc["downgrade_reason"]


def test_verdict_proof_model_gate(tmp_path, transcript):
    # transcript の actual は claude-opus-4-8 — requested と不一致なら proof は FAIL
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--proof",
                            "--requested-model", "claude-sonnet-5"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "FAIL"
    assert "proof" in doc["downgrade_reason"]
    # 一致すれば PASS
    rc2, out2 = _run_verdict(tmp_path, transcript,
                             ["--goal-result", "PASS", "--proof",
                              "--requested-model", "claude-opus-4-8"])
    assert json.loads(out2.read_text())["overall"]["verdict"] == "PASS"


def test_verdict_blocked_fail_closed(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--blocked"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "BLOCKED"
    assert doc["overall"]["goal_fit"] == "NOT_EVALUATED"
    assert doc["goal_verdict"]["blockers"]  # 未実施の blocker が自動記録される


def test_verdict_denylist_rejected(tmp_path, transcript, capsys):
    workdir = tmp_path / "wd"
    rc = verdict_mod.main([
        "--workdir", str(workdir),
        "--target-skill", "harness-creator:run-skill-live-trial",
        "--skill-dir", str(_fake_skill_dir(tmp_path)),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
    ])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err


def test_tree_sha_deterministic_and_content_sensitive(tmp_path):
    d1 = _fake_skill_dir(tmp_path / "a")
    d2 = _fake_skill_dir(tmp_path / "b")
    sha1 = verdict_mod.skill_dir_tree_sha(d1)
    assert sha1 == verdict_mod.skill_dir_tree_sha(d1)  # 決定論
    assert sha1 == verdict_mod.skill_dir_tree_sha(d2)  # 同内容 → 同 sha
    (d2 / "scripts" / "a.py").write_text("print('b')\n", encoding="utf-8")
    assert sha1 != verdict_mod.skill_dir_tree_sha(d2)  # 内容変更で変わる


def test_schema_rejects_additional_properties(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    doc["extra_key"] = 1
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("additionalProperties" in e for e in errs)
    del doc["extra_key"]
    del doc["timeline"]
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("timeline" in e for e in errs)


# ---- backend / boot / send: オフライン検査 ------------------------------------

def test_backend_denylist_and_session_names():
    assert backend_mod.deny_target_skill("run-skill-live-trial")
    assert backend_mod.deny_target_skill("harness-creator:run-skill-iter-improve")
    assert not backend_mod.deny_target_skill("harness-creator:run-goal-seek")
    assert backend_mod.valid_session_name("lt-20260702T000000-x")
    assert not backend_mod.valid_session_name("../evil")
    assert not backend_mod.valid_session_name("a/b")


def test_backend_blocked_without_tmux(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    with pytest.raises(SystemExit) as exc:
        backend_mod.require_tmux()
    assert exc.value.code == 3


def test_backend_self_test_cli():
    assert backend_mod.main(["--self-test"]) == 0
    assert backend_mod.main(["deny-check", "harness-creator:run-goal-seek"]) == 0
    assert backend_mod.main(["deny-check", "run-skill-live-trial"]) == 2


def test_boot_denylist_and_validation(tmp_path, capsys):
    assert boot_mod.main(["--self-test"]) == 0
    rc = boot_mod.main(["lt-x", str(tmp_path),
                        "--target-skill", "run-skill-iter-improve"])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err
    assert boot_mod.main(["../evil", str(tmp_path)]) == 2
    assert boot_mod.main(["lt-x", str(tmp_path / "missing")]) == 2
    assert boot_mod.main(["lt-x", str(tmp_path), "--model", "bad model;rm"]) == 2


def test_send_usage_errors(tmp_path, capsys):
    assert send_mod.main(["../evil", str(tmp_path / "task.md")]) == 2
    assert send_mod.main(["lt-x", str(tmp_path / "missing.md")]) == 2


def test_send_jsonl_accept_detection(tmp_path):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    task = tmp_path / "task.md"
    task.write_text("do it", encoding="utf-8")
    line = json.dumps({"type": "user", "message": {"content": f"読んで実行: {task}"}})
    (projects / "u-2.jsonl").write_text(line + "\n", encoding="utf-8")
    assert send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-2", str(task))
    assert not send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-404", str(task))


# ---- fake backend による tmux 経路の網羅 (実 tmux 非依存) ----------------------

class FakeSendBackend:
    """live-trial-send.main が触る backend 面だけを実装する fake。"""

    def __init__(self, cap=""):
        self.cap = cap
        self.enters = 0
        self.pasted = ""

    def valid_session_name(self, s):
        return backend_mod.valid_session_name(s)

    def require_tmux(self):
        pass

    def paste_file(self, _session, path):
        self.pasted = Path(path).read_text(encoding="utf-8")

    def send_keys(self, _session, *_keys):
        self.enters += 1

    def capture_pane(self, _session, scrollback=False):
        return self.cap


def test_send_started_via_tui_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="✻ … (5s · 120 tokens)")
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0
    # 指示行はファイル経由 (paste) で送られ、taskfile の絶対パスを含む
    assert str(task.resolve()) in fb.pasted


def test_send_unconfirmed_retries_then_warn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="")  # 着手マーカーなし
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 1
    assert fb.enters == 3  # Enter 再送は 3 回で打ち切り
    assert "WARN" in capsys.readouterr().out


def test_send_jsonl_primary_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    line = json.dumps({"type": "user",
                       "message": {"content": f"読んで実行: {task.resolve()}"}})
    (projects / "u-3.jsonl").write_text(line + "\n", encoding="utf-8")
    monkeypatch.setenv("SESSION_ID", "u-3")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    fb = FakeSendBackend(cap="")  # TUI は無反応でも jsonl 一次判定で確定する
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0


class FakeBootBackend:
    """live-trial-boot.boot が触る backend 面だけを実装する fake。"""

    def __init__(self, captures, cmds):
        self.captures = captures
        self.cmds = cmds
        self.tick = 0
        self.killed = []
        self.sent = ""

    def new_session(self, _s, _c):
        pass

    def send_line(self, _s, text):
        self.sent = text

    def capture_pane(self, _s, scrollback=False):
        return self.captures[min(self.tick, len(self.captures) - 1)]

    def pane_current_command(self, _s):
        v = self.cmds[min(self.tick, len(self.cmds) - 1)]
        self.tick += 1
        return v

    def kill_session(self, s):
        self.killed.append(s)


def test_boot_ready_line_contract(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["... bypass permissions ..."], ["2.1.173"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "claude-opus-4-8", "u-1",
                       timeout=5, grace=1)
    assert rc == 0
    out = capsys.readouterr().out
    # SESSION_ID: は行末固定 (parse 互換) / MODEL: は requested の echo
    assert "READY: lt-x" in out
    assert out.strip().endswith("SESSION_ID:u-1")
    assert "MODEL:claude-opus-4-8" in out
    assert "--model claude-opus-4-8" in fb.sent


def test_boot_fail_when_claude_dies(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["zsh: command not found: claude"], ["zsh"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=5, grace=0)
    assert rc == 1
    assert "BOOT_FAIL" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]  # 失敗経路でも session を掃除する


def test_boot_timeout_no_ready(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["still starting"], ["2.1.173"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=2, grace=1)
    assert rc == 1
    assert "TIMEOUT" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]


def test_backend_tmux_wrappers_with_fake_subprocess(monkeypatch, tmp_path):
    calls = []

    class CP:
        returncode = 0
        stdout = "lt-a\nlt-b\nother\n"
        stderr = ""

    def fake_run(args, capture_output=True, text=True, check=False):
        calls.append(list(args))
        return CP()

    monkeypatch.setattr(backend_mod.shutil, "which", lambda _c: "/usr/bin/tmux")
    monkeypatch.setattr(backend_mod.subprocess, "run", fake_run)

    backend_mod.new_session("lt-x", str(tmp_path))
    backend_mod.send_line("lt-x", "hello")
    backend_mod.paste_text("lt-x", "task body\nwith newline")
    assert backend_mod.capture_pane("lt-x", scrollback=True) == CP.stdout
    assert backend_mod.has_session("lt-x")
    assert backend_mod.pane_current_command("lt-x") == "lt-a"
    assert backend_mod.reap("lt-") == ["lt-a", "lt-b"]
    kill_calls = [c for c in calls if c[:2] == ["tmux", "kill-session"]]
    assert len(kill_calls) >= 3  # new_session 前掃除 + reap 2 件
    # paste はファイル経由 (load-buffer → paste-buffer)
    flat = [c[1] for c in calls]
    assert "load-buffer" in flat and "paste-buffer" in flat
    # CLI dispatch も同じ境界を通る
    assert backend_mod.main(["new-session", "lt-y", str(tmp_path)]) == 0
    assert backend_mod.main(["send-line", "lt-y", "hi"]) == 0
    assert backend_mod.main(["capture-pane", "lt-y", "--scrollback"]) == 0
    assert backend_mod.main(["has-session", "lt-y"]) == 0
    assert backend_mod.main(["kill-session", "lt-y"]) == 0
    assert backend_mod.main(["reap"]) == 0
    assert backend_mod.main(["require"]) == 0
    assert backend_mod.main(["kill-session", "../evil"]) == 2  # session 名検証は CLI 層でも効く
