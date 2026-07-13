"""auto-sync-on-session-start.py (C05) の機能テスト — 薄い SessionStart lifecycle hook。

conftest 非依存で module-level に importlib ロードする (hooks/ 配下を自己完結ロード)。
**C01 (sync-native-surfaces.py) は必ず fake runner / dummy script path で置換し、実 C01 を
一切走らせない・実書込ゼロ**。repo root / lock / guard / log path は tempdir へ向け、実
`.claude`・実 repo 状態・実 global config を絶対に触らない。

網羅: write 境界 (allow=.build のみ / forbid=.claude/.agents/.codex/.git/home/plugin source)・
pid/lock stale・lock 取得/steal/timeout/解放・reentrancy guard (session debounce + process
lock)・payload 堅牢性 (空/不正/非 dict)・repo root 解決順・C01 exit 0/1/2/3 と timeout と
script 不在の status 写像 (常に内部 status 保持・プロセスは exit 0)・structured log に
remediation が載る・stdout hook 契約 (warning 時のみ systemMessage/additionalContext・
公式 SessionStart fields のみ)・wrong repository no-write・main が常に 0 を返す。
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
sys.dont_write_bytecode = True


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), HOOKS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


mod = _load("auto-sync-on-session-start")

T0 = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
HOST = socket.gethostname()


# ─────────────────────────── helpers ───────────────────────────
def _dead_pid() -> int:
    for pid in range(999999, 990000, -1):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            continue
        except OSError:
            return pid
    return 999999


def _write_lock(path: Path, *, started_at: str, pid: int, host: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"started_at": started_at, "pid": pid, "host": host}) + "\n", encoding="utf-8")


def _c01_report(adapters, *, verdict="success", exit_code=0) -> str:
    return json.dumps({"mode": "apply", "adapters": adapters, "verdict": verdict, "exit_code": exit_code})


def _adapter(name, status, changed=0, exit=0):
    return {"name": name, "status": status, "changed": changed, "exit": exit}


def _report_synced():
    return _c01_report([_adapter("claude_symlinks", "synced", changed=2),
                        _adapter("claude_settings", "noop"),
                        _adapter("codex_parity", "checked")])


def _report_noop():
    return _c01_report([_adapter("claude_symlinks", "noop"),
                        _adapter("claude_settings", "noop"),
                        _adapter("codex_parity", "checked")])


def _report_all_skipped():
    return _c01_report([_adapter("claude_symlinks", "skipped_not_installed"),
                        _adapter("claude_settings", "skipped_not_installed"),
                        _adapter("codex_parity", "skipped_not_installed")])


class FakeRunner:
    """C01 subprocess の fake。返り値 (rc, stdout, stderr) を固定し、呼び出しを記録する。

    ``timeout_exc=True`` で TimeoutExpired を送出。``exc`` で任意例外を送出。
    """

    def __init__(self, rc=0, stdout="", stderr="", *, timeout_exc=False, exc=None):
        self.rc, self.stdout, self.stderr = rc, stdout, stderr
        self.timeout_exc, self.exc = timeout_exc, exc
        self.calls = []

    def __call__(self, argv, timeout):
        self.calls.append((list(argv), timeout))
        if self.exc is not None:
            raise self.exc
        if self.timeout_exc:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
        return self.rc, self.stdout, self.stderr


def mk_repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    manifest = repo.joinpath(*mod.HARNESS_MANIFEST_REL)
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "harness-creator"}) + "\n", encoding="utf-8")
    c01 = repo.joinpath(*mod.HARNESS_C01_REL)
    c01.parent.mkdir(parents=True, exist_ok=True)
    c01.write_text("# harness repository identity marker\n", encoding="utf-8")
    return repo


def mk_wrong_repo(tmp_path) -> Path:
    repo = tmp_path / "wrong-repo"
    repo.mkdir(parents=True)
    return repo


def dummy_c01(tmp_path) -> Path:
    """存在する (present=True) が実行はされない dummy C01 script。"""
    p = tmp_path / "c01.py"
    p.write_text("# dummy — never executed (runner is faked)\n", encoding="utf-8")
    return p


def run(repo, c01_script, runner, *, payload=None, now=T0, **kw):
    return mod.run_hook(
        payload if payload is not None else {"session_id": "s1", "source": "startup"},
        repo_root=repo, c01_script=c01_script, runner=runner, now=now, **kw,
    )


# ═══════════════════════ frontmatter / module ═══════════════════════
def test_frontmatter_has_all_required_keys():
    text = (HOOKS / "auto-sync-on-session-start.py").read_text(encoding="utf-8")
    required = ("name", "purpose", "inputs", "outputs", "contexts", "network", "write-scope", "dependencies")
    block = text.split("# /// script", 1)[1].split("# ///", 1)[0]
    for key in required:
        assert f"# {key}:" in block or f"# {key} :" in block, f"missing frontmatter key: {key}"


def test_frontmatter_requires_python():
    text = (HOOKS / "auto-sync-on-session-start.py").read_text(encoding="utf-8")
    assert "requires-python" in text


def test_module_exposes_all_statuses():
    assert mod.ALL_STATUSES == frozenset({
        "success", "noop", "skipped_not_installed", "skipped_wrong_repository",
        "warning_drift", "warning_conflict", "warning_invalid", "warning_timeout"})


def test_harness_repository_identity_requires_manifest_and_c01(tmp_path):
    repo = mk_repo(tmp_path)
    assert mod.is_harness_repository(repo)
    repo.joinpath(*mod.HARNESS_C01_REL).unlink()
    assert not mod.is_harness_repository(repo)


def test_harness_repository_identity_rejects_wrong_manifest_name(tmp_path):
    repo = mk_repo(tmp_path)
    repo.joinpath(*mod.HARNESS_MANIFEST_REL).write_text(
        json.dumps({"name": "unrelated"}), encoding="utf-8"
    )
    assert not mod.is_harness_repository(repo)


# ═══════════════════════ is_hook_write_allowed: allowed ═══════════════════════
def test_write_allowed_build_locks(tmp_path):
    assert mod.is_hook_write_allowed(tmp_path, tmp_path / ".build" / "locks" / "l.lock")


def test_write_allowed_build_state(tmp_path):
    assert mod.is_hook_write_allowed(tmp_path, tmp_path / ".build" / "state" / "g.json")


def test_write_allowed_build_logs(tmp_path):
    assert mod.is_hook_write_allowed(tmp_path, tmp_path / ".build" / "logs" / "l.jsonl")


def test_write_allowed_build_dir_itself(tmp_path):
    assert mod.is_hook_write_allowed(tmp_path, tmp_path / ".build")


# ═══════════════════════ is_hook_write_allowed: forbidden ═══════════════════════
def test_write_forbidden_claude_dir(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".claude" / "skills" / "s")


def test_write_forbidden_settings_json(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".claude" / "settings.json")


def test_write_forbidden_agents_skills(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".agents" / "skills" / "s")


def test_write_forbidden_agents_skills_beads(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".agents" / "skills" / "beads" / "x")


def test_write_forbidden_agents_marketplace(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".agents" / "plugins" / "marketplace.json")


def test_write_forbidden_codex(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".codex" / "config.toml")


def test_write_forbidden_git(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".git" / "config")


def test_write_forbidden_plugin_source(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / "plugins" / "p" / "skills" / "s")


def test_write_forbidden_home_claude(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, Path.home() / ".claude" / "settings.json")


def test_write_forbidden_home_codex(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, Path.home() / ".codex" / "config.toml")


def test_write_forbidden_repo_root_itself(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path)


def test_write_forbidden_outside_repo_abs(tmp_path):
    assert not mod.is_hook_write_allowed(tmp_path, Path("/etc/passwd"))


def test_write_forbidden_build_prefix_lookalike(tmp_path):
    # ".buildX" は ".build" 配下ではない (prefix 誤判定しない)。
    assert not mod.is_hook_write_allowed(tmp_path, tmp_path / ".buildX" / "f")


# ═══════════════════════ time helpers ═══════════════════════
def test_iso_roundtrip():
    assert mod._parse_iso(mod._iso(T0)) == T0


def test_iso_format():
    assert mod._iso(T0) == "2026-07-06T12:00:00Z"


def test_parse_iso_rejects_non_string():
    with pytest.raises(ValueError):
        mod._parse_iso(123)


def test_safe_json_valid():
    assert mod._safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_empty_none():
    assert mod._safe_json("") is None
    assert mod._safe_json("   ") is None


def test_safe_json_invalid_none():
    assert mod._safe_json("{ not json") is None
    assert mod._safe_json(123) is None


# ═══════════════════════ pid_alive ═══════════════════════
def test_pid_alive_self():
    assert mod.pid_alive(os.getpid()) is True


def test_pid_alive_dead():
    assert mod.pid_alive(_dead_pid()) is False


def test_pid_alive_invalid():
    assert mod.pid_alive(0) is False
    assert mod.pid_alive(-1) is False
    assert mod.pid_alive("x") is False


# ═══════════════════════ lock_is_stale ═══════════════════════
def test_lock_stale_none():
    assert mod.lock_is_stale(None, T0, 300) is True


def test_lock_stale_non_dict():
    assert mod.lock_is_stale("garbage", T0, 300) is True


def test_lock_stale_bad_started_at():
    assert mod.lock_is_stale({"started_at": "nope", "pid": 1, "host": HOST}, T0, 300) is True


def test_lock_stale_age_exceeds_ttl():
    old = mod._iso(T0 - timedelta(seconds=600))
    assert mod.lock_is_stale({"started_at": old, "pid": os.getpid(), "host": HOST}, T0, 300) is True


def test_lock_stale_dead_pid_same_host():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": _dead_pid(), "host": HOST}, T0, 300) is True


def test_lock_not_stale_live_same_host():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": os.getpid(), "host": HOST}, T0, 300) is False


def test_lock_not_stale_other_host_within_ttl():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": _dead_pid(), "host": "__other__"}, T0, 300) is False


# ═══════════════════════ acquire / release lock ═══════════════════════
def test_acquire_lock_when_free(tmp_path):
    lock = tmp_path / ".build" / "locks" / "l"
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) == "acquired"
    content = json.loads(lock.read_text())
    assert content["pid"] == os.getpid() and content["host"] == HOST


def test_acquire_lock_creates_parent(tmp_path):
    lock = tmp_path / ".build" / "locks" / "deep" / "l"
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) == "acquired"
    assert lock.exists()


def test_acquire_lock_steal_dead_pid(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=_dead_pid(), host=HOST)
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) == "stolen"
    assert json.loads(lock.read_text())["pid"] == os.getpid()


def test_acquire_lock_steal_old_ttl(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0 - timedelta(seconds=600)), pid=os.getpid(), host=HOST)
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) == "stolen"


def test_acquire_lock_steal_corrupt(tmp_path):
    lock = tmp_path / "l"
    lock.write_text("{ not json")
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) == "stolen"
    assert json.loads(lock.read_text())["pid"] == os.getpid()


def test_acquire_lock_none_when_live(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=os.getpid(), host=HOST)
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) is None
    assert json.loads(lock.read_text())["pid"] == os.getpid()  # 不変


def test_acquire_lock_no_steal_other_host(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=_dead_pid(), host="__other__")
    assert mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid) is None


def test_acquire_lock_no_residue_on_steal(tmp_path):
    d = tmp_path / "locks"
    d.mkdir()
    lock = d / "l"
    lock.write_text("{ corrupt")
    mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid)
    assert [q.name for q in d.iterdir()] == ["l"]


def test_release_lock_unlinks(tmp_path):
    lock = tmp_path / "l"
    lease = mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid)
    assert lease is not None
    assert mod.release_lock(lock, lease) is True
    assert not lock.exists()


def test_release_lock_missing_ok(tmp_path):
    assert mod.release_lock(tmp_path / "nope", "missing-owner") is False


def test_release_lock_refuses_foreign_owner(tmp_path):
    lock = tmp_path / "l"
    lease = mod.acquire_lock(lock, lock_ttl=300, now=T0, getpid=os.getpid)
    assert lease is not None
    assert mod.release_lock(lock, "foreign-owner") is False
    assert lock.exists()
    assert mod.release_lock(lock, lease) is True


def test_lock_payload_shape():
    p = mod._lock_payload(T0, os.getpid)
    assert p["started_at"] == "2026-07-06T12:00:00Z"
    assert p["pid"] == os.getpid() and p["host"] == HOST
    assert isinstance(p["owner_token"], str) and p["owner_token"]


def test_run_hook_lock_filesystem_error_is_structured_warning(monkeypatch, tmp_path):
    repo = mk_repo(tmp_path)

    def fail_lock(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(mod, "acquire_lock", fail_lock)
    result = run(repo, dummy_c01(tmp_path), FakeRunner(), now=T0)
    assert result["status"] == "warning_invalid"
    assert result["lock"] == "filesystem_error"
    assert "filesystem" in result["reason"]
    assert result["warning"] is not None


# ═══════════════════════ reentrancy guard ═══════════════════════
def test_read_guard_empty_missing(tmp_path):
    assert mod.read_guard(tmp_path / "nope.json") == {}


def test_read_guard_corrupt(tmp_path):
    p = tmp_path / "g.json"
    p.write_text("{ not json")
    assert mod.read_guard(p) == {}


def test_read_guard_non_dict(tmp_path):
    p = tmp_path / "g.json"
    p.write_text("[1, 2]")
    assert mod.read_guard(p) == {}


def test_guard_recently_ran_true():
    guard = {"s1": mod._iso(T0)}
    assert mod.guard_recently_ran(guard, "s1", T0 + timedelta(seconds=10), 900) is True


def test_guard_recently_ran_false_expired():
    guard = {"s1": mod._iso(T0)}
    assert mod.guard_recently_ran(guard, "s1", T0 + timedelta(seconds=1000), 900) is False


def test_guard_recently_ran_no_id():
    assert mod.guard_recently_ran({"": mod._iso(T0)}, "", T0, 900) is False


def test_guard_recently_ran_unknown_id():
    assert mod.guard_recently_ran({"s1": mod._iso(T0)}, "s2", T0, 900) is False


def test_guard_recently_ran_bad_ts():
    assert mod.guard_recently_ran({"s1": "garbage"}, "s1", T0, 900) is False


def test_write_guard_records(tmp_path):
    p = tmp_path / ".build" / "state" / "g.json"
    mod.write_guard(p, {}, "s1", T0, retention=86400)
    assert json.loads(p.read_text())["s1"] == mod._iso(T0)


def test_write_guard_prunes_old(tmp_path):
    p = tmp_path / "g.json"
    old_guard = {"old": mod._iso(T0 - timedelta(seconds=100000))}
    mod.write_guard(p, old_guard, "s1", T0, retention=86400)
    data = json.loads(p.read_text())
    assert "s1" in data and "old" not in data  # retention 超過を prune


def test_write_guard_no_id_noop(tmp_path):
    p = tmp_path / "g.json"
    mod.write_guard(p, {}, "", T0, retention=86400)
    assert not p.exists()  # session id 無しは書かない


def test_write_guard_keeps_recent_other_sessions(tmp_path):
    p = tmp_path / "g.json"
    guard = {"recent": mod._iso(T0 - timedelta(seconds=10))}
    mod.write_guard(p, guard, "s1", T0, retention=86400)
    data = json.loads(p.read_text())
    assert set(data) == {"recent", "s1"}


# ═══════════════════════ payload 解釈 ═══════════════════════
def test_parse_payload_valid():
    assert mod.parse_payload('{"session_id": "abc"}') == {"session_id": "abc"}


def test_parse_payload_empty():
    assert mod.parse_payload("") == {}


def test_parse_payload_whitespace():
    assert mod.parse_payload("   \n ") == {}


def test_parse_payload_invalid():
    assert mod.parse_payload("{ not json") == {}


def test_parse_payload_non_dict():
    assert mod.parse_payload("[1, 2, 3]") == {}
    assert mod.parse_payload("42") == {}


def test_session_id_variants():
    assert mod.session_id({"session_id": "a"}) == "a"
    assert mod.session_id({"sessionId": "b"}) == "b"
    assert mod.session_id({}) == ""
    assert mod.session_id({"session_id": 5}) == ""


def test_session_source_variants():
    assert mod.session_source({"source": "resume"}) == "resume"
    assert mod.session_source({}) == "unknown"
    assert mod.session_source({"source": ""}) == "unknown"


# ═══════════════════════ resolve_repo_root ═══════════════════════
def test_resolve_repo_root_argv_wins(tmp_path):
    got = mod.resolve_repo_root({"cwd": "/payload"}, str(tmp_path), env={"CLAUDE_PROJECT_DIR": "/env"})
    assert got == tmp_path.resolve()


def test_resolve_repo_root_env(tmp_path):
    got = mod.resolve_repo_root({"cwd": str(tmp_path / "payload")}, None, env={"CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert got == tmp_path.resolve()


def test_resolve_repo_root_payload_cwd(tmp_path):
    got = mod.resolve_repo_root({"cwd": str(tmp_path)}, None, env={})
    assert got == tmp_path.resolve()


def test_resolve_repo_root_payload_project_dir(tmp_path):
    got = mod.resolve_repo_root({"project_dir": str(tmp_path)}, None, env={})
    assert got == tmp_path.resolve()


def test_resolve_repo_root_fallback_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    got = mod.resolve_repo_root({}, None, env={})
    assert got == Path.cwd()


# ═══════════════════════ _default_c01_script ═══════════════════════
def test_default_c01_script_points_to_sibling_scripts():
    p = mod._default_c01_script()
    assert p.name == "sync-native-surfaces.py"
    assert p.parent.name == "scripts"


# ═══════════════════════ invoke_c01 ═══════════════════════
def test_invoke_c01_absent_present_false(tmp_path):
    r = mod.invoke_c01(tmp_path, tmp_path / "nope.py", timeout=1.0, runner=FakeRunner())
    assert r["present"] is False and r["returncode"] is None and r["timed_out"] is False


def test_invoke_c01_builds_argv(tmp_path):
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_noop())
    mod.invoke_c01(tmp_path / "repo", c01, timeout=7.0, runner=runner)
    argv, timeout = runner.calls[0]
    assert argv[0] == sys.executable
    assert str(c01) in argv
    assert "--repo-root" in argv and str(tmp_path / "repo") in argv
    assert "--apply" in argv and "--json" in argv
    assert timeout == 7.0


def test_invoke_c01_returns_rc_stdout(tmp_path):
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=1, stdout=_report_noop(), stderr="warn")
    r = mod.invoke_c01(tmp_path, c01, timeout=1.0, runner=runner)
    assert r["present"] is True and r["returncode"] == 1 and r["stderr"] == "warn"


def test_invoke_c01_timeout(tmp_path):
    c01 = dummy_c01(tmp_path)
    r = mod.invoke_c01(tmp_path, c01, timeout=1.0, runner=FakeRunner(timeout_exc=True))
    assert r["timed_out"] is True and r["present"] is True and r["returncode"] is None


def test_invoke_c01_verdict_extracted(tmp_path):
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_c01_report([_adapter("x", "noop")], verdict="success"))
    r = mod.invoke_c01(tmp_path, c01, timeout=1.0, runner=runner)
    assert r["verdict"] == "success"


def test_invoke_c01_called_once(tmp_path):
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_noop())
    mod.invoke_c01(tmp_path, c01, timeout=1.0, runner=runner)
    assert len(runner.calls) == 1


def test_invoke_c01_uses_module_runner_when_none(tmp_path, monkeypatch):
    c01 = dummy_c01(tmp_path)
    seen = {}

    def fake(argv, timeout):
        seen["argv"] = argv
        return 0, _report_noop(), ""

    monkeypatch.setattr(mod, "_run_c01", fake)
    r = mod.invoke_c01(tmp_path, c01, timeout=1.0)  # runner 省略 → module の _run_c01
    assert r["returncode"] == 0 and "argv" in seen


# ═══════════════════════ classify_c01 / _classify_exit0 ═══════════════════════
def test_classify_absent_skipped():
    assert mod.classify_c01({"present": False}) == "skipped_not_installed"


def test_classify_timeout():
    assert mod.classify_c01({"present": True, "timed_out": True}) == "warning_timeout"


def test_classify_exit1_drift():
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": 1, "stdout": ""}) == "warning_drift"


def test_classify_exit2_conflict():
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": 2, "stdout": ""}) == "warning_conflict"


def test_classify_exit3_invalid():
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": 3, "stdout": ""}) == "warning_invalid"


def test_classify_unknown_exit_invalid():
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": -9, "stdout": ""}) == "warning_invalid"
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": 7, "stdout": ""}) == "warning_invalid"
    assert mod.classify_c01({"present": True, "timed_out": False, "returncode": None, "stdout": ""}) == "warning_invalid"


def test_classify_exit0_synced_success():
    r = {"present": True, "timed_out": False, "returncode": 0, "stdout": _report_synced()}
    assert mod.classify_c01(r) == "success"


def test_classify_exit0_all_noop_noop():
    r = {"present": True, "timed_out": False, "returncode": 0, "stdout": _report_noop()}
    assert mod.classify_c01(r) == "noop"


def test_classify_exit0_all_skipped():
    r = {"present": True, "timed_out": False, "returncode": 0, "stdout": _report_all_skipped()}
    assert mod.classify_c01(r) == "skipped_not_installed"


def test_classify_exit0_unparseable_noop():
    r = {"present": True, "timed_out": False, "returncode": 0, "stdout": "not json"}
    assert mod.classify_c01(r) == "noop"


def test_classify_exit0_empty_adapters_noop():
    r = {"present": True, "timed_out": False, "returncode": 0, "stdout": _c01_report([])}
    assert mod.classify_c01(r) == "noop"


def test_classify_exit0_changed_field_success():
    # status が synced でなくとも changed>0 なら success。
    r = {"present": True, "timed_out": False, "returncode": 0,
         "stdout": _c01_report([_adapter("x", "drift", changed=3)])}
    assert mod.classify_c01(r) == "success"


def test_classify_exit0_mixed_skipped_and_noop_is_noop():
    r = {"present": True, "timed_out": False, "returncode": 0,
         "stdout": _c01_report([_adapter("a", "skipped_not_installed"), _adapter("b", "noop")])}
    assert mod.classify_c01(r) == "noop"


# ═══════════════════════ status_warning_remediation ═══════════════════════
def test_warning_none_for_success_noop_skipped(tmp_path):
    for s in ("success", "noop", "skipped_not_installed"):
        assert mod.status_warning_remediation(s, tmp_path) == (None, None)


def test_warning_drift_has_apply_cmd(tmp_path):
    w, r = mod.status_warning_remediation("warning_drift", tmp_path)
    assert w is not None and "--apply" in r and "sync-native-surfaces.py" in r


def test_warning_conflict_has_remediation(tmp_path):
    w, r = mod.status_warning_remediation("warning_conflict", tmp_path)
    assert w is not None and "conflict" in w and "--apply" in r


def test_warning_invalid_has_remediation(tmp_path):
    w, r = mod.status_warning_remediation("warning_invalid", tmp_path)
    assert w is not None and r is not None


def test_warning_timeout_has_remediation(tmp_path):
    w, r = mod.status_warning_remediation("warning_timeout", tmp_path)
    assert w is not None and "timeout" in w and "--apply" in r


def test_apply_cmd_includes_repo_root(tmp_path):
    assert str(tmp_path) in mod._apply_cmd(tmp_path)


# ═══════════════════════ run_hook: status 写像 (常に exit 0 側) ═══════════════════════
def test_run_hook_success(tmp_path):
    repo = mk_repo(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    res = run(repo, dummy_c01(tmp_path), runner)
    assert res["status"] == "success" and res["warning"] is None
    assert len(runner.calls) == 1  # C01 を 1 回だけ呼ぶ


def test_run_hook_noop(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_noop()))
    assert res["status"] == "noop" and res["warning"] is None


def test_run_hook_skipped_when_c01_absent(tmp_path):
    repo = mk_repo(tmp_path)
    runner = FakeRunner()
    res = run(repo, tmp_path / "nope.py", runner)
    assert res["status"] == "skipped_not_installed" and res["warning"] is None
    assert runner.calls == []  # 不在なら subprocess を呼ばない


def test_run_hook_drift(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=1, stdout=_report_noop()))
    assert res["status"] == "warning_drift" and res["remediation"] and "--apply" in res["remediation"]


def test_run_hook_conflict(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=2, stdout=""))
    assert res["status"] == "warning_conflict" and res["warning"] is not None


def test_run_hook_invalid(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=3, stdout=""))
    assert res["status"] == "warning_invalid" and res["warning"] is not None


def test_run_hook_timeout(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(timeout_exc=True))
    assert res["status"] == "warning_timeout" and res["remediation"] and "--apply" in res["remediation"]


def test_run_hook_c01_meta_recorded(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_synced()))
    assert res["c01"]["present"] is True and res["c01"]["returncode"] == 0 and res["c01"]["verdict"] == "success"


def test_run_hook_runner_exception_is_soft(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(exc=RuntimeError("boom")))
    # runner の予期せぬ例外は warning_invalid へ畳み、プロセスは壊さない。
    assert res["status"] == "warning_invalid" and "boom" in res["reason"]


# ═══════════════════════ run_hook: reentrancy ═══════════════════════
def test_run_hook_reentrancy_session_second_noop(tmp_path):
    repo = mk_repo(tmp_path)
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    r1 = run(repo, c01, runner, payload={"session_id": "sX", "source": "startup"}, now=T0)
    r2 = run(repo, c01, runner, payload={"session_id": "sX", "source": "resume"},
             now=T0 + timedelta(seconds=5))
    assert r1["status"] == "success"
    assert r2["status"] == "noop" and "reentrancy" in r2["reason"]
    assert len(runner.calls) == 1  # 2 回目は C01 を呼ばない


def test_run_hook_reentrancy_expired_reruns(tmp_path):
    repo = mk_repo(tmp_path)
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    run(repo, c01, runner, payload={"session_id": "sX"}, now=T0)
    r2 = run(repo, c01, runner, payload={"session_id": "sX"},
             now=T0 + timedelta(seconds=2000), debounce=900)
    assert r2["status"] == "success" and len(runner.calls) == 2  # 窓超過で再実行


def test_run_hook_reentrancy_lock_held_noop(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=os.getpid(), host=HOST)  # 生存 lock
    runner = FakeRunner(rc=0, stdout=_report_synced())
    res = run(repo, dummy_c01(tmp_path), runner, payload={"session_id": "fresh"},
              now=T0, lock_path=lock)
    assert res["status"] == "noop" and res["lock"] == "held"
    assert runner.calls == []  # lock 保持中は C01 を呼ばない


def test_run_hook_reentrancy_lock_preserves_foreign(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=os.getpid(), host=HOST)
    before = lock.read_text()
    run(repo, dummy_c01(tmp_path), FakeRunner(), payload={"session_id": "fresh"},
        now=T0, lock_path=lock)
    assert lock.read_text() == before  # 他者 lock を消さない


def test_run_hook_steals_stale_lock(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=_dead_pid(), host=HOST)  # 孤児 lock
    runner = FakeRunner(rc=0, stdout=_report_synced())
    res = run(repo, dummy_c01(tmp_path), runner, now=T0, lock_path=lock)
    assert res["status"] == "success" and res["lock"] == "stolen"
    assert len(runner.calls) == 1


# ═══════════════════════ run_hook: lock 取得/解放 ═══════════════════════
def test_run_hook_releases_lock_on_success(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_synced()), now=T0, lock_path=lock)
    assert not lock.exists()  # 正常終了で解放


def test_run_hook_releases_lock_on_warning(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=3), now=T0, lock_path=lock)
    assert not lock.exists()  # warning でも解放


def test_run_hook_releases_lock_on_timeout(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    run(repo, dummy_c01(tmp_path), FakeRunner(timeout_exc=True), now=T0, lock_path=lock)
    assert not lock.exists()


def test_run_hook_lock_acquired_reported(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_noop()), now=T0)
    assert res["lock"] == "acquired"


def test_run_hook_skipped_does_not_hold_lock(tmp_path):
    repo = mk_repo(tmp_path)
    lock = repo / ".build" / "locks" / "l"
    run(repo, tmp_path / "nope.py", FakeRunner(), now=T0, lock_path=lock)
    assert not lock.exists()  # skipped でも lock は残さない


# ═══════════════════════ run_hook: structured log ═══════════════════════
def test_run_hook_writes_log(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_synced()), now=T0, log_path=log)
    lines = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    assert lines[-1]["status"] == "success" and lines[-1]["hook"] == "auto-sync-on-session-start"


def test_run_hook_log_has_remediation_on_warning(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=1, stdout=_report_noop()), now=T0, log_path=log)
    rec = [json.loads(x) for x in log.read_text().splitlines() if x.strip()][-1]
    assert rec["status"] == "warning_drift" and rec["remediation"] and "--apply" in rec["remediation"]


def test_run_hook_log_preserves_bounded_child_stderr(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    stderr = "diagnostic:" + ("x" * (mod.MAX_CHILD_DIAGNOSTIC_CHARS + 50))
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=2, stderr=stderr), now=T0, log_path=log)
    rec = [json.loads(x) for x in log.read_text().splitlines() if x.strip()][-1]
    assert rec["status"] == "warning_conflict"
    assert rec["c01"]["returncode"] == 2
    assert rec["c01"]["stderr"].startswith("diagnostic:")
    assert rec["c01"]["stderr"].endswith("...[truncated]")
    assert len(rec["c01"]["stderr"]) < len(stderr)


def test_run_hook_log_appends(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    c01 = dummy_c01(tmp_path)
    run(repo, c01, FakeRunner(rc=0, stdout=_report_synced()),
        payload={"session_id": "a"}, now=T0, log_path=log)
    run(repo, c01, FakeRunner(rc=1, stdout=_report_noop()),
        payload={"session_id": "b"}, now=T0 + timedelta(seconds=1), log_path=log)
    lines = [x for x in log.read_text().splitlines() if x.strip()]
    assert len(lines) == 2  # 追記される


def test_run_hook_log_timeout_record(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    run(repo, dummy_c01(tmp_path), FakeRunner(timeout_exc=True), now=T0, log_path=log)
    rec = [json.loads(x) for x in log.read_text().splitlines() if x.strip()][-1]
    assert rec["status"] == "warning_timeout" and rec["c01"]["timed_out"] is True


def test_run_hook_log_bounds_large_child_report(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    report = json.dumps({"verdict": "success", "payload": "x" * (mod.MAX_CHILD_REPORT_CHARS * 2)})
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=report), now=T0, log_path=log)
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    child = rec["c01"]["child_report"]
    assert child["truncated"] is True
    assert len(child["preview"]) <= mod.MAX_CHILD_REPORT_CHARS + len("...[truncated]")


def test_run_hook_log_redacts_session_and_secret(tmp_path):
    repo = mk_repo(tmp_path)
    log = repo / ".build" / "logs" / "l.jsonl"
    run(
        repo,
        dummy_c01(tmp_path),
        FakeRunner(
            rc=2,
            stdout=json.dumps({"token": "json-secret-value"}),
            stderr="token=super-secret-value Authorization: Bearer abc123",
        ),
        payload={"session_id": "private-session"},
        now=T0,
        log_path=log,
    )
    raw = log.read_text(encoding="utf-8")
    rec = json.loads(raw.splitlines()[-1])
    assert "private-session" not in raw
    assert "super-secret-value" not in raw
    assert "json-secret-value" not in raw and "abc123" not in raw
    assert rec["session_id"].startswith("sha256:")
    assert "token=<redacted>" in rec["c01"]["stderr"]
    assert rec["c01"]["child_report"]["token"] == "<redacted>"


def test_append_log_rotates_by_size_and_bounds_backups(tmp_path):
    log = tmp_path / "l.jsonl"
    for index in range(6):
        mod.append_log(
            log,
            {"index": index, "value": "x" * 80},
            now=T0 + timedelta(seconds=index),
            max_bytes=120,
            max_age=999999,
            max_backups=2,
        )
    assert log.is_file() and log.with_name("l.jsonl.1").is_file()
    assert log.with_name("l.jsonl.2").is_file()
    assert not log.with_name("l.jsonl.3").exists()


def test_append_log_rotates_by_age(tmp_path):
    log = tmp_path / "l.jsonl"
    mod.append_log(log, {"old": True}, now=T0, max_bytes=9999, max_age=10, max_backups=1)
    old_epoch = (T0 - timedelta(seconds=20)).timestamp()
    os.utime(log, (old_epoch, old_epoch))
    mod.append_log(log, {"new": True}, now=T0, max_bytes=9999, max_age=10, max_backups=1)
    assert json.loads(log.read_text()) == {"new": True}
    assert json.loads(log.with_name("l.jsonl.1").read_text()) == {"old": True}


# ═══════════════════════ run_hook: write 境界 ═══════════════════════
def test_run_hook_writes_only_build(tmp_path):
    repo = mk_repo(tmp_path)
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_synced()), now=T0)
    # hook が作った top-level entry は .build のみ (C01 は fake なので実書込ゼロ)。
    entries = {p.name for p in repo.iterdir()}
    assert entries == {"plugins", ".build"}


def test_run_hook_wrong_repository_is_fail_soft_and_no_write(tmp_path):
    repo = mk_wrong_repo(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    result = run(repo, dummy_c01(tmp_path), runner, now=T0)
    assert result["status"] == "skipped_wrong_repository"
    assert result["warning"] is None and result["log_path"] == ""
    assert runner.calls == []
    assert list(repo.iterdir()) == []


def test_run_hook_never_touches_forbidden(tmp_path):
    repo = mk_repo(tmp_path)
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=1, stdout=_report_noop()), now=T0)
    for forbidden in (".claude", ".agents", ".codex", ".git"):
        assert not (repo / forbidden).exists()


@pytest.mark.parametrize("option", ["lock_path", "guard_path", "log_path"])
def test_run_hook_rejects_hook_local_path_outside_build(tmp_path, option):
    repo = mk_repo(tmp_path)
    forbidden = repo / ".codex" / f"{option}.json"
    result = run(
        repo,
        dummy_c01(tmp_path),
        FakeRunner(rc=0, stdout=_report_synced()),
        now=T0,
        **{option: forbidden},
    )
    assert result["status"] == "warning_invalid"
    assert result["reason"] == "forbidden hook-local write path"
    assert not forbidden.exists()
    assert (repo / ".build" / "logs" / "auto-sync-on-session-start.jsonl").is_file()


def test_run_hook_guard_under_build_state(tmp_path):
    repo = mk_repo(tmp_path)
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_synced()),
        payload={"session_id": "s1"}, now=T0)
    assert (repo / ".build" / "state" / "auto-sync-on-session-start.json").is_file()


def test_run_hook_log_under_build_logs(tmp_path):
    repo = mk_repo(tmp_path)
    run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_noop()), now=T0)
    assert (repo / ".build" / "logs" / "auto-sync-on-session-start.jsonl").is_file()


def test_run_hook_skipped_not_recorded_in_guard(tmp_path):
    repo = mk_repo(tmp_path)
    guard = repo / ".build" / "state" / "g.json"
    run(repo, tmp_path / "nope.py", FakeRunner(), payload={"session_id": "s1"},
        now=T0, guard_path=guard)
    # 未 install は guard へ記録しない (install 後の retry を許す)。
    assert not guard.exists() or json.loads(guard.read_text()) == {}


# ═══════════════════════ run_hook: source variants ═══════════════════════
@pytest.mark.parametrize("source", ["startup", "resume", "clear"])
def test_run_hook_all_sources_run(tmp_path, source):
    repo = mk_repo(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    res = run(repo, dummy_c01(tmp_path), runner,
              payload={"session_id": f"s-{source}", "source": source}, now=T0)
    assert res["source"] == source and res["status"] == "success" and len(runner.calls) == 1


def test_run_hook_empty_payload_robust(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_noop()),
              payload={}, now=T0)
    assert res["status"] == "noop" and res["session_id"] == "" and res["source"] == "unknown"


def test_run_hook_non_dict_payload_robust(tmp_path):
    repo = mk_repo(tmp_path)
    res = run(repo, dummy_c01(tmp_path), FakeRunner(rc=0, stdout=_report_noop()),
              payload=["not", "a", "dict"], now=T0)
    assert res["status"] == "noop"  # 非 dict でも落ちない


# ═══════════════════════ build_hook_output ═══════════════════════
def _result(status, **kw):
    warning, remediation = mod.status_warning_remediation(status, Path("/repo"))
    base = {"hook": "auto-sync-on-session-start", "event": "SessionStart", "status": status,
            "warning": warning, "remediation": remediation, "source": "startup", "session_id": "s1",
            "reason": "r", "c01": {"present": True, "returncode": 0, "timed_out": False, "verdict": "success"},
            "lock": "acquired", "timestamp": mod._iso(T0), "log_path": ".build/logs/l.jsonl"}
    base.update(kw)
    return base


def test_output_success_suppressed_no_systemmessage():
    out = mod.build_hook_output(_result("success"))
    assert out["suppressOutput"] is True and "systemMessage" not in out
    assert "additionalContext" not in out["hookSpecificOutput"]


def test_output_noop_suppressed():
    out = mod.build_hook_output(_result("noop"))
    assert out["suppressOutput"] is True


def test_output_skipped_suppressed():
    out = mod.build_hook_output(_result("skipped_not_installed"))
    assert out["suppressOutput"] is True


def test_output_wrong_repository_suppressed():
    out = mod.build_hook_output(_result("skipped_wrong_repository"))
    assert out["suppressOutput"] is True


def test_output_warning_has_systemmessage():
    out = mod.build_hook_output(_result("warning_drift"))
    assert out["suppressOutput"] is False
    assert "systemMessage" in out and "warning_drift" in out["systemMessage"]


def test_output_warning_additional_context_has_remediation():
    out = mod.build_hook_output(_result("warning_conflict"))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "remediation" in ctx and "--apply" in ctx


def test_output_always_has_hook_event_name():
    for s in ("success", "warning_timeout"):
        out = mod.build_hook_output(_result(s))
        assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_output_always_continues_session():
    for s in mod.ALL_STATUSES:
        assert mod.build_hook_output(_result(s))["continue"] is True


def test_output_uses_only_documented_session_start_fields():
    out = mod.build_hook_output(_result("warning_timeout"))
    assert set(out) <= {"continue", "suppressOutput", "systemMessage", "hookSpecificOutput"}
    assert set(out["hookSpecificOutput"]) <= {"hookEventName", "additionalContext"}
    serialized = json.dumps(out)
    assert "c01" not in serialized and "session_id" not in serialized and "child_report" not in serialized


def test_output_json_serializable():
    out = mod.build_hook_output(_result("warning_drift"))
    json.dumps(out)  # 例外にならない


# ═══════════════════════ main: 常に exit 0 ═══════════════════════
def _main(monkeypatch, tmp_path, *, rc=0, stdout=None, timeout_exc=False, exc=None,
          c01_present=True, stdin=None, extra_argv=()):
    repo = mk_repo(tmp_path)
    c01 = dummy_c01(tmp_path) if c01_present else (tmp_path / "nope.py")
    runner = FakeRunner(rc=rc, stdout=stdout if stdout is not None else _report_synced(),
                        timeout_exc=timeout_exc, exc=exc)
    monkeypatch.setattr(mod, "_run_c01", runner)
    argv = ["--repo-root", str(repo), "--c01-script", str(c01), *extra_argv]
    if stdin is None:
        stdin = json.dumps({"session_id": "m1", "source": "startup"})
    code = mod.main(argv, stdin=stdin)
    return code, repo, runner


def test_main_success_exit0(monkeypatch, tmp_path, capsys):
    code, repo, runner = _main(monkeypatch, tmp_path, rc=0, stdout=_report_synced())
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["suppressOutput"] is True and "systemMessage" not in out
    assert len(runner.calls) == 1


def test_main_drift_exit0_with_systemmessage(monkeypatch, tmp_path, capsys):
    code, repo, _ = _main(monkeypatch, tmp_path, rc=1, stdout=_report_noop())
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "warning_drift" in out["systemMessage"]
    assert "--apply" in out["hookSpecificOutput"]["additionalContext"]


def test_main_conflict_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, rc=2, stdout="")
    assert code == 0
    assert "warning_conflict" in json.loads(capsys.readouterr().out)["systemMessage"]


def test_main_invalid_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, rc=3, stdout="")
    assert code == 0
    assert "warning_invalid" in json.loads(capsys.readouterr().out)["systemMessage"]


def test_main_timeout_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, timeout_exc=True)
    assert code == 0
    assert "warning_timeout" in json.loads(capsys.readouterr().out)["systemMessage"]


def test_main_c01_absent_skipped_exit0(monkeypatch, tmp_path, capsys):
    code, _, runner = _main(monkeypatch, tmp_path, c01_present=False)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["suppressOutput"] is True and "systemMessage" not in out
    assert runner.calls == []  # 実 subprocess を呼ばない


def test_main_empty_stdin_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, rc=0, stdout=_report_noop(), stdin="")
    assert code == 0
    assert json.loads(capsys.readouterr().out)["suppressOutput"] is True


def test_main_invalid_stdin_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, rc=0, stdout=_report_noop(), stdin="{ not json")
    assert code == 0
    assert json.loads(capsys.readouterr().out)["suppressOutput"] is True


def test_main_runner_exception_exit0(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, exc=RuntimeError("kaboom"))
    assert code == 0
    assert "warning_invalid" in json.loads(capsys.readouterr().out)["systemMessage"]


def test_main_writes_only_build(monkeypatch, tmp_path):
    code, repo, _ = _main(monkeypatch, tmp_path, rc=0, stdout=_report_synced())
    assert code == 0 and {p.name for p in repo.iterdir()} == {"plugins", ".build"}


def test_main_never_touches_forbidden(monkeypatch, tmp_path):
    code, repo, _ = _main(monkeypatch, tmp_path, rc=1, stdout=_report_noop())
    assert code == 0
    for forbidden in (".claude", ".agents", ".codex", ".git"):
        assert not (repo / forbidden).exists()


def test_main_resolves_repo_root_from_argv(monkeypatch, tmp_path):
    code, repo, _ = _main(monkeypatch, tmp_path, rc=0, stdout=_report_noop())
    assert code == 0
    assert (repo / ".build" / "logs" / "auto-sync-on-session-start.jsonl").is_file()


def test_main_resolves_repo_root_from_env(monkeypatch, tmp_path, capsys):
    repo = mk_repo(tmp_path)
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_noop())
    monkeypatch.setattr(mod, "_run_c01", runner)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    code = mod.main(["--c01-script", str(c01)], stdin=json.dumps({"session_id": "e1"}))
    assert code == 0
    assert (repo / ".build" / "logs" / "auto-sync-on-session-start.jsonl").is_file()


def test_main_bad_argv_does_not_break_session(monkeypatch, tmp_path, capsys):
    # 未知 flag でも argparse error を握りつぶし exit 0 (session を止めない)。
    repo = mk_repo(tmp_path)
    monkeypatch.setattr(mod, "_run_c01", FakeRunner(rc=0, stdout=_report_noop()))
    monkeypatch.chdir(repo)
    code = mod.main(["--totally-unknown-flag"], stdin=json.dumps({"session_id": "z"}))
    assert code == 0


def test_main_reentrancy_second_call_noop(monkeypatch, tmp_path, capsys):
    repo = mk_repo(tmp_path)
    c01 = dummy_c01(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    monkeypatch.setattr(mod, "_run_c01", runner)
    argv = ["--repo-root", str(repo), "--c01-script", str(c01)]
    stdin = json.dumps({"session_id": "same", "source": "startup"})
    assert mod.main(argv, stdin=stdin) == 0
    capsys.readouterr()
    assert mod.main(argv, stdin=stdin) == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["suppressOutput"] is True and "systemMessage" not in out2
    assert len(runner.calls) == 1  # 2 回目は C01 を呼ばない


def test_main_output_is_valid_json(monkeypatch, tmp_path, capsys):
    code, _, _ = _main(monkeypatch, tmp_path, rc=0, stdout=_report_synced())
    assert code == 0
    json.loads(capsys.readouterr().out)  # 例外にならない


def test_main_wrong_repository_no_write_and_documented_stdout_only(monkeypatch, tmp_path, capsys):
    repo = mk_wrong_repo(tmp_path)
    runner = FakeRunner(rc=0, stdout=_report_synced())
    monkeypatch.setattr(mod, "_run_c01", runner)
    code = mod.main(
        ["--repo-root", str(repo), "--c01-script", str(dummy_c01(tmp_path))],
        stdin=json.dumps({"session_id": "wrong-repo-session", "source": "startup"}),
    )
    assert code == 0 and list(repo.iterdir()) == [] and runner.calls == []
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"continue", "suppressOutput", "hookSpecificOutput"}
    assert out["suppressOutput"] is True
