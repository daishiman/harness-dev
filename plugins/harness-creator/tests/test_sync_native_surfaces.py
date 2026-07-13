"""sync-native-surfaces.py (C01) の機能テスト — build/update 単一 orchestrator。

conftest 非依存で module-level に importlib ロードする (自己完結)。
**すべての --apply は合成 tempdir に対してのみ実行し、実 `.claude/` や実 repo 状態を
一切書き換えない** (repo-root / lock-path / generator script path を tempdir へ向ける)。

網羅: write-scope 境界 (allow/forbid)・fingerprint/atomic replace・lock 取得/steal/timeout/
解放・activation scope filter (enabled のみ対象・非 enabled skipped)・adapter 委譲 (subprocess を
fake で stub)・各 exit code (0 noop/skipped, 1 drift, 2 lock-timeout/conflict, 3 invalid)・
exit 優先順位 (3>2>1>0)・--check/--dry-run が無書込・実 generator 委譲の isolation。
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load("sync-native-surfaces")

# 実 generator (integration 用・すべて tempdir を対象に isolation 実行する)。
PLUGIN_ROOT = SCRIPTS.parent
REPO_ROOT = PLUGIN_ROOT.parent.parent
REAL_SYMLINKS = REPO_ROOT / "scripts" / "build-claude-symlinks.py"
REAL_SETTINGS = REPO_ROOT / "scripts" / "build-claude-settings.py"
REAL_CODEX = SCRIPTS / "check-native-surface-parity.py"
REAL_CODEX_SETTINGS = SCRIPTS / "sync-codex-project-settings.py"
REAL_CONTRACT = PLUGIN_ROOT / "references" / "native-surface-contract.md"
REAL_PLAN_DIR = REPO_ROOT / "plugin-plans" / "harness-creator-hook-agents-sync"

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


def make_sym(check_ret, apply_ret=(0, "{}"), calls=None):
    def _f(script, plugins_dir, target_dir, *, check, excludes, prune=True):
        if calls is not None:
            calls.append(("symlinks", "check" if check else "apply", list(excludes), prune))
        return check_ret if check else apply_ret
    return _f


def make_set(check_ret, apply_ret=(0, ""), calls=None):
    def _f(script, plugins_dir, target, *, check, excludes=()):
        if calls is not None:
            calls.append(("settings", "check" if check else "apply", list(excludes)))
        return check_ret if check else apply_ret
    return _f


def make_codex(ret, calls=None):
    def _f(script, repo_root, slug, contract, plan_dir):
        if calls is not None:
            calls.append(("codex",))
        return ret
    return _f


def _sym_summary(created=0, updated=0):
    return json.dumps({"summary": {"created": created, "updated": updated, "noop": 0, "conflict": 0}})


@pytest.fixture
def dummy_scripts(tmp_path):
    d = tmp_path / "gen"
    d.mkdir()
    sym, st, cx = d / "sym.py", d / "set.py", d / "cx.py"
    for p in (sym, st, cx):
        p.write_text("x", encoding="utf-8")
    return sym, st, cx


def mk_repo(tmp_path, enabled=None, plugins=("harness-creator",), settings=True, bad_settings=False):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "skills", "plugins": []}), encoding="utf-8"
    )
    if settings:
        if bad_settings:
            (repo / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
        else:
            ep = {f"{p}@skills": True for p in (enabled or [])}
            (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": ep}), encoding="utf-8")
    for p in plugins:
        (repo / "plugins" / p).mkdir(parents=True)
    return repo


def _orch(repo, mode, dummy, *, lock_timeout=5.0, lock_path=None, slug="harness-creator"):
    sym, st, cx = dummy
    return mod.orchestrate(
        repo_root=repo, mode=mode, lock_timeout=lock_timeout,
        symlinks_script=sym, settings_script=st, codex_script=cx,
        slug=slug, contract=repo / "contract.md", plan_dir=repo / "plan",
        lock_path=lock_path or (repo / ".build" / "locks" / "lock"),
    )


# ═══════════════════════ is_write_allowed: allowed ═══════════════════════
def test_write_allowed_claude_skills(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".claude" / "skills" / "s")


def test_write_allowed_claude_agents(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".claude" / "agents" / "a.md")


def test_write_allowed_claude_commands(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".claude" / "commands" / "c.md")


def test_write_allowed_settings_json(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".claude" / "settings.json")


def test_write_allowed_marketplace(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "plugins" / "marketplace.json")


def test_write_allowed_codex_manifest(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / "plugins" / "harness-creator" / ".codex-plugin" / "plugin.json")


def test_write_allowed_build_lock(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".build" / "locks" / "x.lock")


# ═══════════════════════ is_write_allowed: forbidden ═══════════════════════
def test_write_forbidden_home_codex(tmp_path):
    assert not mod.is_write_allowed(tmp_path, Path.home() / ".codex" / "config.toml")


def test_write_forbidden_home_claude(tmp_path):
    assert not mod.is_write_allowed(tmp_path, Path.home() / ".claude" / "settings.json")


def test_write_forbidden_agents_skills_beads(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "skills" / "beads" / "x")


def test_write_forbidden_agents_skills(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "skills" / "s")


def test_write_forbidden_agents_agents(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "agents" / "a")


def test_write_forbidden_agents_commands(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "commands" / "c")


def test_write_forbidden_agents_hooks(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "hooks" / "h.json")


def test_write_allows_only_managed_project_codex_files(tmp_path):
    assert mod.is_write_allowed(tmp_path, tmp_path / ".codex" / "hooks.json")
    assert mod.is_write_allowed(tmp_path, tmp_path / ".codex" / "config.toml")
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".codex" / "other.toml")


def test_write_forbidden_git(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".git" / "config")


def test_write_forbidden_plugin_source_skills(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / "plugins" / "p" / "skills" / "s")


def test_write_forbidden_plugin_source_hooks(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / "plugins" / "p" / "hooks" / "hooks.json")


def test_write_forbidden_outside_repo_abs(tmp_path):
    assert not mod.is_write_allowed(tmp_path, Path("/etc/passwd"))


def test_write_forbidden_repo_root_itself(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path)


def test_write_forbidden_claude_other_file(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".claude" / "unmanaged.json")


def test_write_forbidden_agents_plugins_other(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / ".agents" / "plugins" / "other.json")


def test_write_forbidden_codex_manifest_wrong_depth(tmp_path):
    assert not mod.is_write_allowed(tmp_path, tmp_path / "plugins" / ".codex-plugin" / "plugin.json")


# ═══════════════════════ fingerprint ═══════════════════════
def test_fingerprint_bytes_deterministic():
    assert mod.fingerprint_bytes(b"abc") == mod.fingerprint_bytes(b"abc")
    assert mod.fingerprint_bytes(b"abc") != mod.fingerprint_bytes(b"abd")


def test_fingerprint_path_none_when_absent(tmp_path):
    assert mod.fingerprint_path(tmp_path / "nope") is None


def test_fingerprint_path_matches_bytes(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"hello")
    assert mod.fingerprint_path(p) == mod.fingerprint_bytes(b"hello")


# ═══════════════════════ atomic write ═══════════════════════
def test_atomic_write_bytes_creates_and_content(tmp_path):
    p = tmp_path / "d" / "f"
    mod.atomic_write_bytes(p, b"data")
    assert p.read_bytes() == b"data"


def test_atomic_write_no_temp_residue(tmp_path):
    p = tmp_path / "f"
    mod.atomic_write_text(p, "x")
    assert [q.name for q in tmp_path.iterdir()] == ["f"]


def test_atomic_write_creates_parent(tmp_path):
    p = tmp_path / "a" / "b" / "c" / "f"
    mod.atomic_write_text(p, "y")
    assert p.is_file()


def test_atomic_write_overwrites(tmp_path):
    p = tmp_path / "f"
    p.write_text("old")
    mod.atomic_write_text(p, "new")
    assert p.read_text() == "new"


# ═══════════════════════ sync_repo_owned_file ═══════════════════════
def test_sync_repo_owned_noop_when_identical(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"same")
    assert mod.sync_repo_owned_file(tmp_path, target, b"same") == "noop"


def test_sync_repo_owned_written_when_diff(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    assert mod.sync_repo_owned_file(tmp_path, target, b"new") == "written"
    assert target.read_bytes() == b"new"


def test_sync_repo_owned_would_write_dry_run_no_change(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    assert mod.sync_repo_owned_file(tmp_path, target, b"new", dry_run=True) == "would-write"
    assert target.read_bytes() == b"old"  # 無書込


def test_sync_repo_owned_refuses_forbidden_home(tmp_path):
    with pytest.raises(mod.WriteScopeError):
        mod.sync_repo_owned_file(tmp_path, Path.home() / ".codex" / "config.toml", b"x")


def test_sync_repo_owned_refuses_agents_skills(tmp_path):
    with pytest.raises(mod.WriteScopeError):
        mod.sync_repo_owned_file(tmp_path, tmp_path / ".agents" / "skills" / "beads" / "x", b"x")


def test_sync_repo_owned_atomic_no_residue(tmp_path):
    target = tmp_path / ".build" / "f"
    mod.sync_repo_owned_file(tmp_path, target, b"data")
    assert [q.name for q in (tmp_path / ".build").iterdir()] == ["f"]


def test_sync_repo_owned_writes_codex_manifest(tmp_path):
    target = tmp_path / "plugins" / "harness-creator" / ".codex-plugin" / "plugin.json"
    assert mod.sync_repo_owned_file(tmp_path, target, b'{"name":"x"}') == "written"
    assert target.is_file()


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
    assert mod.lock_is_stale(None, T0, 3600) is True


def test_lock_stale_non_dict():
    assert mod.lock_is_stale("garbage", T0, 3600) is True


def test_lock_stale_bad_started_at():
    assert mod.lock_is_stale({"started_at": "nope", "pid": 1, "host": HOST}, T0, 3600) is True


def test_lock_stale_age_exceeds_ttl():
    old = mod._iso(T0 - timedelta(seconds=7200))
    assert mod.lock_is_stale({"started_at": old, "pid": os.getpid(), "host": HOST}, T0, 3600) is True


def test_lock_stale_dead_pid_same_host():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": _dead_pid(), "host": HOST}, T0, 3600) is True


def test_lock_not_stale_live_same_host():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": os.getpid(), "host": HOST}, T0, 3600) is False


def test_lock_not_stale_other_host_within_ttl():
    fresh = mod._iso(T0)
    assert mod.lock_is_stale({"started_at": fresh, "pid": _dead_pid(), "host": "__other__"}, T0, 3600) is False


# ═══════════════════════ acquire / release lock ═══════════════════════
def test_acquire_lock_when_free(tmp_path):
    lock = tmp_path / "l"
    assert mod.acquire_lock(lock, 0, clock=lambda: T0) == "acquired"
    content = json.loads(lock.read_text())
    assert content["pid"] == os.getpid() and content["host"] == HOST


def test_acquire_lock_creates_parent_dir(tmp_path):
    lock = tmp_path / ".build" / "locks" / "l"
    assert mod.acquire_lock(lock, 0) == "acquired"
    assert lock.exists()


def test_acquire_lock_steal_dead_pid(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=_dead_pid(), host=HOST)
    assert mod.acquire_lock(lock, 0, clock=lambda: T0) == "stolen"
    assert json.loads(lock.read_text())["pid"] == os.getpid()


def test_acquire_lock_steal_old_ttl(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0 - timedelta(seconds=7200)), pid=os.getpid(), host=HOST)
    assert mod.acquire_lock(lock, 0, lock_ttl=3600, clock=lambda: T0) == "stolen"


def test_acquire_lock_steal_corrupt(tmp_path):
    lock = tmp_path / "l"
    lock.write_text("{ not json")
    assert mod.acquire_lock(lock, 0, clock=lambda: T0) == "stolen"
    assert json.loads(lock.read_text())["pid"] == os.getpid()


def test_acquire_lock_timeout_returns_none_live(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=os.getpid(), host=HOST)
    assert mod.acquire_lock(lock, 0, clock=lambda: T0) is None  # 生存 lock → timeout
    assert json.loads(lock.read_text())["pid"] == os.getpid()  # 不変


def test_acquire_lock_no_steal_other_host_timeout(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=_dead_pid(), host="__other__")
    assert mod.acquire_lock(lock, 0, clock=lambda: T0) is None


def test_acquire_lock_timeout_polls_then_gives_up(tmp_path):
    lock = tmp_path / "l"
    _write_lock(lock, started_at=mod._iso(T0), pid=os.getpid(), host=HOST)
    sleeps = {"n": 0}

    def fake_sleep(_):
        sleeps["n"] += 1

    it = iter([0.0, 0.4, 0.8, 1.2])
    result = mod.acquire_lock(lock, 1.0, monotonic=lambda: next(it), sleep=fake_sleep, clock=lambda: T0)
    assert result is None
    assert sleeps["n"] == 2  # deadline 1.0 未満で 2 回 poll してから諦める


def test_acquire_lock_atomic_no_residue_on_steal(tmp_path):
    d = tmp_path / "locks"
    d.mkdir()
    lock = d / "l"
    lock.write_text("{ corrupt")
    mod.acquire_lock(lock, 0, clock=lambda: T0)
    assert [q.name for q in d.iterdir()] == ["l"]


def test_release_lock_unlinks(tmp_path):
    lock = tmp_path / "l"
    lease = mod.acquire_lock(lock, 0, clock=lambda: T0)
    assert lease is not None
    assert mod.release_lock(lock, lease) is True
    assert not lock.exists()


def test_release_lock_missing_ok(tmp_path):
    assert mod.release_lock(tmp_path / "nope", "missing-owner") is False


def test_release_lock_refuses_foreign_owner(tmp_path):
    lock = tmp_path / "l"
    lease = mod.acquire_lock(lock, 0, clock=lambda: T0)
    assert lease is not None
    assert mod.release_lock(lock, "foreign-owner") is False
    assert lock.exists()
    assert mod.release_lock(lock, lease) is True


def test_lock_payload_shape():
    p = mod._lock_payload(T0)
    assert p["started_at"] == "2026-07-06T12:00:00Z"
    assert p["pid"] == os.getpid() and p["host"] == HOST
    assert isinstance(p["owner_token"], str) and p["owner_token"]


def test_two_processes_racing_stale_lock_have_one_owner(tmp_path):
    """Real OS processes race one stale inode; only one may acquire the lease."""
    lock = tmp_path / "race.lock"
    lock.write_text("{ corrupt", encoding="utf-8")
    gate = tmp_path / "go"
    worker = r'''
import importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
spec = importlib.util.spec_from_file_location("sync_native_worker", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
lock, gate, ready, attempt = map(Path, sys.argv[2:6])
ready.touch()
while not gate.exists(): time.sleep(0.002)
lease = mod.acquire_lock(lock, 0, lock_ttl=300,
                         clock=lambda: datetime(2026, 7, 6, 12, tzinfo=timezone.utc))
attempt.touch()
if lease is None:
    print(json.dumps({"acquired": False}))
else:
    print(json.dumps({"acquired": True, "token": lease.owner_token}), flush=True)
    deadline = time.monotonic() + 5
    while len(list(attempt.parent.glob("attempt-*"))) < 2:
        if time.monotonic() >= deadline: raise RuntimeError("peer did not attempt")
        time.sleep(0.002)
    mod.release_lock(lock, lease)
'''
    processes = []
    ready_paths = []
    for index in range(2):
        ready = tmp_path / f"ready-{index}"
        ready_paths.append(ready)
        argv = [
            sys.executable, "-c", worker, str(SCRIPTS / "sync-native-surfaces.py"),
            str(lock), str(gate), str(ready), str(tmp_path / f"attempt-{index}"),
        ]
        processes.append(subprocess.Popen(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    deadline = time.monotonic() + 5
    while not all(path.exists() for path in ready_paths):
        assert time.monotonic() < deadline
        time.sleep(0.005)
    gate.touch()
    results = []
    for proc in processes:
        stdout, stderr = proc.communicate(timeout=5)
        assert proc.returncode == 0, stderr
        results.append(json.loads(stdout))
    assert sum(1 for result in results if result["acquired"]) == 1, results


# ═══════════════════════ read_activation_scope ═══════════════════════
def test_scope_enabled_filtered(tmp_path):
    repo = mk_repo(tmp_path, enabled=["a"], plugins=("a", "b", "c"))
    scope = mod.read_activation_scope(repo)
    assert scope["enabled"] == ["a"]


def test_scope_skipped_listed(tmp_path):
    repo = mk_repo(tmp_path, enabled=["a"], plugins=("a", "b", "c"))
    scope = mod.read_activation_scope(repo)
    assert sorted(s["plugin"] for s in scope["skipped"]) == ["b", "c"]
    assert all("not enabled" in s["reason"] for s in scope["skipped"])


def test_scope_missing_settings_error(tmp_path):
    repo = mk_repo(tmp_path, plugins=("a",), settings=False)
    scope = mod.read_activation_scope(repo)
    assert scope["scope_error"] is not None
    assert scope["skipped"] == [] and scope["enabled"] == []  # fail-safe: filter しない


def test_scope_invalid_settings_error(tmp_path):
    repo = mk_repo(tmp_path, plugins=("a",), bad_settings=True)
    scope = mod.read_activation_scope(repo)
    assert scope["scope_error"] is not None
    assert scope["enabled"] == []


def test_scope_no_plugins_dir(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {}}))
    scope = mod.read_activation_scope(repo)
    assert scope["present"] == []


def test_scope_enabledplugins_non_dict(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"name": "skills"}))
    (repo / "plugins" / "a").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": ["a"]}))
    scope = mod.read_activation_scope(repo)
    assert scope["enabled"] == [] and scope["skipped"] == []
    assert scope["scope_error"] == "settings.json enabledPlugins missing or not an object"


def test_scope_missing_enabledplugins_is_invalid_not_empty_selection(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / "plugins" / "a").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    scope = mod.read_activation_scope(repo)
    assert scope["scope_error"] is not None
    assert scope["skipped"] == []  # no destructive-prune selection is derived


def test_scope_suffix_stripped(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"name": "skills"}))
    (repo / "plugins" / "harness-creator").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"harness-creator@skills": True}}))
    scope = mod.read_activation_scope(repo)
    assert scope["enabled"] == ["harness-creator"]


def test_scope_false_value_excluded(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"name": "s"}))
    (repo / "plugins" / "a").mkdir(parents=True)
    (repo / "plugins" / "b").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"a@s": True, "b@s": False}}))
    scope = mod.read_activation_scope(repo)
    assert scope["enabled"] == ["a"] and [s["plugin"] for s in scope["skipped"]] == ["b"]


def test_scope_foreign_marketplace_same_slug_is_not_enabled(tmp_path):
    repo = mk_repo(tmp_path, enabled=[], plugins=("harness-creator",))
    settings = repo / ".claude" / "settings.json"
    settings.write_text(
        json.dumps({"enabledPlugins": {"harness-creator@foreign": True}}),
        encoding="utf-8",
    )

    scope = mod.read_activation_scope(repo)

    assert scope["enabled"] == []
    assert scope["skipped"] == [{
        "plugin": "harness-creator",
        "identity": "harness-creator@skills",
        "reason": "exact plugin@marketplace identity not enabled in .claude/settings.json enabledPlugins",
    }]


def test_scope_missing_marketplace_identity_fails_closed(tmp_path):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    (repo / ".claude-plugin" / "marketplace.json").unlink()

    scope = mod.read_activation_scope(repo)

    assert scope["scope_error"] is not None
    assert scope["enabled"] == [] and scope["skipped"] == []


def test_scope_present_sorted(tmp_path):
    repo = mk_repo(tmp_path, enabled=[], plugins=("z", "a", "m"))
    scope = mod.read_activation_scope(repo)
    assert scope["present"] == ["a", "m", "z"]


# ═══════════════════════ _map_exit / _symlinks_changed ═══════════════════════
def test_map_exit_all():
    assert mod._map_exit(0) == 0
    assert mod._map_exit(1) == 1
    assert mod._map_exit(2) == 2
    assert mod._map_exit(3) == 3
    assert mod._map_exit(4) == 3  # generator の OSError=4 も invalid へ写す


def test_symlinks_changed_parses_summary():
    assert mod._symlinks_changed(_sym_summary(created=2, updated=3)) == 5


def test_symlinks_changed_bad_json_zero():
    assert mod._symlinks_changed("not json") == 0


def test_symlinks_changed_no_summary_zero():
    assert mod._symlinks_changed(json.dumps({"x": 1})) == 0


# ═══════════════════════ adapter_symlinks ═══════════════════════
def _sym_args(dummy, repo, mode, excludes=()):
    sym, _, _ = dummy
    return dict(script=sym, plugins_dir=repo / "plugins", target_dir=repo / ".claude",
                excludes=list(excludes), repo_root=repo)


def test_adapter_symlinks_skipped_when_absent(tmp_path):
    r = mod.adapter_symlinks("check", script=tmp_path / "nope.py", plugins_dir=tmp_path,
                             target_dir=tmp_path, excludes=[], repo_root=tmp_path)
    assert r["status"] == "skipped_not_installed" and r["exit"] == 0


def test_adapter_symlinks_check_clean_noop(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    r = mod.adapter_symlinks("check", **_sym_args(dummy_scripts, tmp_path, "check"))
    assert r["status"] == "noop" and r["exit"] == 0 and r["changed"] == 0


def test_adapter_symlinks_check_drift(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=2))))
    r = mod.adapter_symlinks("check", **_sym_args(dummy_scripts, tmp_path, "check"))
    assert r["status"] == "drift" and r["exit"] == 1 and r["changed"] == 2
    assert r["remediation"] and "--apply" in r["remediation"]


def test_adapter_symlinks_check_conflict(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((2, "{}")))
    r = mod.adapter_symlinks("check", **_sym_args(dummy_scripts, tmp_path, "check"))
    assert r["status"] == "conflict" and r["exit"] == 2


def test_adapter_preserves_bounded_child_diagnostics(monkeypatch, tmp_path, dummy_scripts):
    child = {
        "verdict": "FAIL",
        "violations": [{"code": "x", "detail": "bad"}],
        "remediation": "repair child",
    }
    monkeypatch.setattr(
        mod,
        "_run_codex",
        make_codex((1, json.dumps(child), "E" * (mod.MAX_CHILD_DIAGNOSTIC_CHARS + 20))),
    )
    r = mod.adapter_codex(
        "check", script=dummy_scripts[2], repo_root=tmp_path, slug="x",
        contract=tmp_path / "c", plan_dir=tmp_path,
    )
    assert r["child_report"]["verdict"] == "FAIL"
    assert r["violations"] == child["violations"]
    assert r["stdout"].startswith("{")
    assert r["stderr"].endswith("...[truncated]")
    assert r["remediation"]  # normalized adapter remediation is never lost


def test_adapter_symlinks_check_invalid(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((3, "")))
    r = mod.adapter_symlinks("check", **_sym_args(dummy_scripts, tmp_path, "check"))
    assert r["status"] == "invalid" and r["exit"] == 3


def test_adapter_symlinks_apply_noop_when_clean(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary()), calls=calls))
    r = mod.adapter_symlinks("apply", **_sym_args(dummy_scripts, tmp_path, "apply"))
    assert r["status"] == "noop" and r["changed"] == 0
    assert [c[1] for c in calls] == ["check"]  # fingerprint no-op: apply へ進まない


def test_adapter_symlinks_apply_synced_when_drift(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks",
                        make_sym((1, _sym_summary(created=2)), apply_ret=(0, _sym_summary(created=2)), calls=calls))
    r = mod.adapter_symlinks("apply", **_sym_args(dummy_scripts, tmp_path, "apply"))
    assert r["status"] == "synced" and r["changed"] == 2 and r["exit"] == 0
    assert [c[1] for c in calls] == ["check", "apply"]


def test_adapter_symlinks_apply_conflict_no_write(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((2, "{}"), calls=calls))
    r = mod.adapter_symlinks("apply", **_sym_args(dummy_scripts, tmp_path, "apply"))
    assert r["status"] == "conflict" and r["exit"] == 2
    assert [c[1] for c in calls] == ["check"]  # conflict は書かない (fail-closed)


def test_adapter_symlinks_dry_run_no_apply(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=2)), calls=calls))
    r = mod.adapter_symlinks("dry-run", **_sym_args(dummy_scripts, tmp_path, "dry-run"))
    assert r["status"] == "drift"
    assert [c[1] for c in calls] == ["check"]  # dry-run は無書込


def test_adapter_symlinks_excludes_forwarded(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary()), calls=calls))
    mod.adapter_symlinks("check", **_sym_args(dummy_scripts, tmp_path, "check", excludes=["x", "y"]))
    assert calls[0][2] == ["x", "y"]
    assert calls[0][3] is False


def test_adapter_symlinks_apply_prunes_only_on_write(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(
        mod,
        "_run_symlinks",
        make_sym((1, _sym_summary()), apply_ret=(0, _sym_summary(updated=1)), calls=calls),
    )
    result = mod.adapter_symlinks(
        "apply", **_sym_args(dummy_scripts, tmp_path, "apply", excludes=["disabled"])
    )
    assert result["status"] == "synced"
    assert [(call[1], call[3]) for call in calls] == [("check", False), ("apply", True)]


# ═══════════════════════ adapter_settings ═══════════════════════
def _set_args(dummy, repo):
    _, st, _ = dummy
    return dict(script=st, plugins_dir=repo / "plugins", target=repo / ".claude" / "settings.json", repo_root=repo)


def test_adapter_settings_skipped_when_absent(tmp_path):
    r = mod.adapter_settings("check", script=tmp_path / "nope.py", plugins_dir=tmp_path,
                             target=tmp_path / "s.json", repo_root=tmp_path)
    assert r["status"] == "skipped_not_installed" and r["exit"] == 0


def test_adapter_settings_check_clean_noop(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    r = mod.adapter_settings("check", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "noop" and r["exit"] == 0


def test_adapter_settings_check_drift(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_settings", make_set((1, "")))
    r = mod.adapter_settings("check", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "drift" and r["exit"] == 1 and r["changed"] == 1


def test_adapter_settings_check_conflict(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_settings", make_set((2, "")))
    r = mod.adapter_settings("check", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "conflict" and r["exit"] == 2


def test_adapter_settings_check_invalid(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_settings", make_set((3, "")))
    r = mod.adapter_settings("check", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "invalid" and r["exit"] == 3


def test_adapter_settings_apply_noop_when_clean(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_settings", make_set((0, ""), calls=calls))
    r = mod.adapter_settings("apply", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "noop" and [c[1] for c in calls] == ["check"]


def test_adapter_settings_apply_synced_when_drift(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_settings", make_set((1, ""), apply_ret=(0, ""), calls=calls))
    r = mod.adapter_settings("apply", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "synced" and r["changed"] == 1 and [c[1] for c in calls] == ["check", "apply"]


def test_adapter_settings_apply_conflict_no_write(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_settings", make_set((2, ""), calls=calls))
    r = mod.adapter_settings("apply", **_set_args(dummy_scripts, tmp_path))
    assert r["status"] == "conflict" and [c[1] for c in calls] == ["check"]


def test_adapter_settings_excludes_forwarded(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_settings", make_set((0, ""), calls=calls))
    mod.adapter_settings(
        "check", **_set_args(dummy_scripts, tmp_path), excludes=["disabled", "untrusted"]
    )
    assert calls[0][2] == ["disabled", "untrusted"]


# ═══════════════════════ adapter_codex ═══════════════════════
def _cx_args(dummy, repo):
    _, _, cx = dummy
    return dict(script=cx, repo_root=repo, slug="harness-creator", contract=repo / "c.md", plan_dir=repo / "plan")


def test_adapter_codex_skipped_when_absent(tmp_path):
    r = mod.adapter_codex("check", script=tmp_path / "nope.py", repo_root=tmp_path,
                          slug="s", contract=tmp_path / "c", plan_dir=tmp_path)
    assert r["status"] == "skipped_not_installed" and r["exit"] == 0


def test_adapter_codex_checked_ok(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    r = mod.adapter_codex("check", **_cx_args(dummy_scripts, tmp_path))
    assert r["status"] == "checked" and r["exit"] == 0 and r["changed"] == 0


def test_adapter_codex_drift(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_codex", make_codex((1, "")))
    r = mod.adapter_codex("check", **_cx_args(dummy_scripts, tmp_path))
    assert r["status"] == "drift" and r["exit"] == 1 and "marketplace" in r["remediation"]


def test_adapter_codex_conflict(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_codex", make_codex((2, "")))
    r = mod.adapter_codex("check", **_cx_args(dummy_scripts, tmp_path))
    assert r["status"] == "conflict" and r["exit"] == 2


def test_adapter_codex_invalid(monkeypatch, tmp_path, dummy_scripts):
    monkeypatch.setattr(mod, "_run_codex", make_codex((3, "")))
    r = mod.adapter_codex("check", **_cx_args(dummy_scripts, tmp_path))
    assert r["status"] == "invalid" and r["exit"] == 3


def test_adapter_codex_readonly_in_apply_mode(monkeypatch, tmp_path, dummy_scripts):
    calls = []
    monkeypatch.setattr(mod, "_run_codex", make_codex((1, ""), calls=calls))
    r = mod.adapter_codex("apply", **_cx_args(dummy_scripts, tmp_path))
    # apply mode でも read-only: 1 回の parity check のみ、changed=0。
    assert r["exit"] == 1 and r["changed"] == 0 and len(calls) == 1


# ═══════════════════════ orchestrate ═══════════════════════
def test_orchestrate_check_clean_exit0(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, code = _orch(repo, "check", dummy_scripts)
    assert code == 0 and report["verdict"] == "success"
    statuses = {a["name"]: a["status"] for a in report["adapters"]}
    assert statuses == {"claude_symlinks": "noop", "claude_settings": "noop", "codex_parity": "checked"}


def test_orchestrate_check_drift_exit1(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=1))))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, code = _orch(repo, "check", dummy_scripts)
    assert code == 1 and report["verdict"] == "drift"


def test_orchestrate_check_conflict_exit2(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((2, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, code = _orch(repo, "check", dummy_scripts)
    assert code == 2 and report["verdict"] == "conflict"


def test_orchestrate_check_invalid_exit3(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((3, "")))
    report, code = _orch(repo, "check", dummy_scripts)
    assert code == 3 and report["verdict"] == "invalid"


def test_orchestrate_exit_priority_max(monkeypatch, tmp_path, dummy_scripts):
    # drift(1) + conflict(2) + invalid(3) が混在 → 最重 3 を返す。
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=1))))
    monkeypatch.setattr(mod, "_run_settings", make_set((2, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((3, "")))
    report, code = _orch(repo, "check", dummy_scripts)
    assert code == 3


def test_orchestrate_apply_acquires_and_releases_lock(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    lock = repo / ".build" / "locks" / "lock"
    report, code = _orch(repo, "apply", dummy_scripts, lock_path=lock)
    assert code == 0 and report["lock"] == "acquired"
    assert not lock.exists()  # finally で解放


def test_orchestrate_apply_lock_timeout_exit2(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    lock = repo / ".build" / "locks" / "lock"
    _write_lock(lock, started_at=mod._iso(mod._now_utc()), pid=os.getpid(), host=HOST)  # 生存 lock
    report, code = _orch(repo, "apply", dummy_scripts, lock_timeout=0, lock_path=lock)
    assert code == 2 and report["verdict"] == "lock_timeout" and report["lock"] == "timeout"
    assert report["adapters"] == []  # lock 取れず adapter を走らせない


def test_orchestrate_apply_lock_timeout_preserves_foreign_lock(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    lock = repo / ".build" / "locks" / "lock"
    _write_lock(lock, started_at=mod._iso(mod._now_utc()), pid=os.getpid(), host=HOST)
    before = lock.read_text()
    _orch(repo, "apply", dummy_scripts, lock_timeout=0, lock_path=lock)
    assert lock.read_text() == before  # 他者 lock を消さない


def test_orchestrate_apply_releases_lock_on_exception(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "_run_symlinks", boom)
    lock = repo / ".build" / "locks" / "lock"
    with pytest.raises(RuntimeError):
        _orch(repo, "apply", dummy_scripts, lock_path=lock)
    assert not lock.exists()  # 例外時も finally で解放


def test_orchestrate_dry_run_no_apply_calls(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=1)), calls=calls))
    monkeypatch.setattr(mod, "_run_settings", make_set((1, ""), calls=calls))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, ""), calls=calls))
    _orch(repo, "dry-run", dummy_scripts)
    assert all(c[1] == "check" for c in calls if c[0] in ("symlinks", "settings"))  # apply 呼び出し 0


def test_orchestrate_check_no_lock(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    lock = repo / ".build" / "locks" / "lock"
    report, _ = _orch(repo, "check", dummy_scripts, lock_path=lock)
    assert report["lock"] is None and not lock.exists()  # check は lock を握らない


def test_orchestrate_report_shape(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, _ = _orch(repo, "check", dummy_scripts)
    assert set(report) == {"mode", "adapters", "scope", "lock", "verdict", "exit_code"}
    for a in report["adapters"]:
        assert set(a) == {
            "name", "status", "changed", "exit", "skipped_reason", "warning", "remediation",
            "child_report", "violations", "stdout", "stderr",
        }
    assert set(report["scope"]) == {"enabled", "skipped", "scope_error", "activation_evidence"}
    evidence = report["scope"]["activation_evidence"]
    assert evidence["claude"]["enabled_state"] == "verified"
    assert evidence["codex"]["trust_state"] == "not_verified"


def test_orchestrate_scope_in_report(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"], plugins=("harness-creator", "other"))
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, _ = _orch(repo, "check", dummy_scripts)
    assert report["scope"]["enabled"] == ["harness-creator"]
    assert [s["plugin"] for s in report["scope"]["skipped"]] == ["other"]


def test_orchestrate_scope_excludes_forwarded_to_symlinks(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"], plugins=("harness-creator", "other"))
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary()), calls=calls))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    _orch(repo, "check", dummy_scripts)
    assert calls[0][2] == ["other"]  # 非 enabled plugin を symlink surface から除外


@pytest.mark.parametrize("mode", ["check", "apply"])
def test_orchestrate_scope_error_fails_closed_without_running_adapters(
    monkeypatch, tmp_path, dummy_scripts, mode,
):
    repo = mk_repo(tmp_path, plugins=("a", "b"), bad_settings=True)
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary()), calls=calls))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    report, code = _orch(repo, mode, dummy_scripts)
    assert code == 3
    assert report["verdict"] == "invalid_activation_scope"
    assert report["adapters"] == []
    assert calls == []


def test_orchestrate_scope_excludes_forwarded_to_settings(monkeypatch, tmp_path, dummy_scripts):
    repo = mk_repo(tmp_path, enabled=["harness-creator"], plugins=("harness-creator", "other"))
    calls = []
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, ""), calls=calls))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    _orch(repo, "check", dummy_scripts)
    assert calls[0][2] == ["other"]


def test_orchestrate_skipped_when_all_generators_absent(tmp_path):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    report, code = mod.orchestrate(
        repo_root=repo, mode="check", lock_timeout=1.0,
        symlinks_script=tmp_path / "no1.py", settings_script=tmp_path / "no2.py",
        codex_script=tmp_path / "no3.py", slug="harness-creator",
        contract=tmp_path / "c", plan_dir=tmp_path, lock_path=repo / "lock",
    )
    assert code == 0  # 全 generator 未 install → skipped_not_installed (exit 0)
    assert all(a["status"] == "skipped_not_installed" for a in report["adapters"])


# ═══════════════════════ main / CLI ═══════════════════════
def _main_args(repo, dummy, *extra):
    sym, st, cx = dummy
    return ["--repo-root", str(repo), "--symlinks-script", str(sym),
            "--settings-script", str(st), "--codex-parity-script", str(cx),
            "--codex-settings-script", str(repo / "absent-codex-settings.py"), *extra]


def test_main_check_json_output(monkeypatch, tmp_path, dummy_scripts, capsys):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    code = mod.main(_main_args(repo, dummy_scripts, "--check", "--json"))
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "check" and out["exit_code"] == 0


def test_main_default_mode_is_check(monkeypatch, tmp_path, dummy_scripts, capsys):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    code = mod.main(_main_args(repo, dummy_scripts, "--json"))
    assert json.loads(capsys.readouterr().out)["mode"] == "check" and code == 0


def test_main_exit_code_propagated(monkeypatch, tmp_path, dummy_scripts, capsys):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((3, "")))
    code = mod.main(_main_args(repo, dummy_scripts, "--check", "--json"))
    assert code == 3


def test_main_human_output(monkeypatch, tmp_path, dummy_scripts, capsys):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((1, _sym_summary(created=1))))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    code = mod.main(_main_args(repo, dummy_scripts, "--check"))
    out = capsys.readouterr().out
    assert "verdict: drift" in out and "adapter claude_symlinks" in out
    assert code == 1


def test_main_apply_uses_tempdir_lock(monkeypatch, tmp_path, dummy_scripts, capsys):
    repo = mk_repo(tmp_path, enabled=["harness-creator"])
    monkeypatch.setattr(mod, "_run_symlinks", make_sym((0, _sym_summary())))
    monkeypatch.setattr(mod, "_run_settings", make_set((0, "")))
    monkeypatch.setattr(mod, "_run_codex", make_codex((0, "")))
    code = mod.main(_main_args(repo, dummy_scripts, "--apply", "--json",
                               "--lock-path", str(repo / ".build" / "locks" / "l")))
    assert code == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "apply"


def test_main_missing_repo_root_errors(capsys):
    code = mod.main(["--check"])
    assert code == 2  # argparse usage error


# ═══════════════════════ integration: 実 generator を tempdir へ isolation 実行 ═══════════════════════
def _synth_repo(tmp_path, enabled=("p1",)):
    """実 generator を安全に走らせる合成 repo (実 .claude を一切触らない)。"""
    repo = tmp_path / "synthrepo"
    skill = repo / "plugins" / "p1" / "skills" / "s1"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: s1\n---\nbody\n", encoding="utf-8")
    manifest = repo / "plugins" / "p1" / ".claude-plugin"
    manifest.mkdir(parents=True)
    (manifest / "plugin.json").write_text(json.dumps({"name": "p1"}), encoding="utf-8")
    codex_manifest = repo / "plugins" / "p1" / ".codex-plugin"
    codex_manifest.mkdir(parents=True)
    (codex_manifest / "plugin.json").write_text(json.dumps({"name": "p1"}), encoding="utf-8")
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "skills", "plugins": []}), encoding="utf-8"
    )
    (repo / ".codex").mkdir(parents=True)
    (repo / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (repo / ".codex" / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    (repo / ".agents" / "plugins").mkdir(parents=True)
    (repo / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps({"name": "fixture", "plugins": []}) + "\n", encoding="utf-8"
    )
    (repo / "plugins" / "p1" / "native-surfaces.toml").write_text(
        '''schema_version = 1
[activation]
claude_marketplace = "skills"
codex_discovery = ".agents/plugins/marketplace.json"
[codex]
hooks_file = ".codex/hooks.json"
config_file = ".codex/config.toml"
features_hooks = true
[discovery]
marketplace_name = "fixture"
plugin_name = "p1"
source_path = "./plugins/p1"
installation = "AVAILABLE"
authentication = "ON_INSTALL"
category = "Internal-Tooling"
distributable = false
scope = "repo-internal"
activation_requires = ["user-install", "user-enable", "user-hook-trust"]
hooks = []
''', encoding="utf-8"
    )
    ep = {f"{p}@skills": True for p in enabled}
    (repo / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": ep}), encoding="utf-8")
    return repo


def _real_orch(repo, mode, slug="p1"):
    return mod.orchestrate(
        repo_root=repo, mode=mode, lock_timeout=5.0,
        symlinks_script=REAL_SYMLINKS, settings_script=REAL_SETTINGS, codex_script=REAL_CODEX,
        slug=slug, contract=REAL_CONTRACT, plan_dir=REAL_PLAN_DIR,
        lock_path=repo / ".build" / "locks" / "lock",
        codex_settings_script=REAL_CODEX_SETTINGS,
        native_surfaces_contract=repo / "plugins" / "p1" / "native-surfaces.toml",
    )


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_check_drift_real_generators(tmp_path):
    repo = _synth_repo(tmp_path)
    report, code = _real_orch(repo, "check")
    # symlink/settings drift に加え、合成 manifest は完全な配布 metadata を持たないため invalid。
    assert code == 3 and report["verdict"] == "invalid"


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_apply_writes_only_allowed_paths(tmp_path):
    repo = _synth_repo(tmp_path)
    report, code = _real_orch(repo, "apply")
    # Claude surface は同期される。
    assert (repo / ".claude" / "skills" / "s1").is_symlink()
    assert (repo / ".claude" / "settings.json").is_file()
    # read-only 境界: discovery source は参照するが、非公式 .agents 投影面や
    # .git へは一切書かない。
    assert (repo / ".agents" / "plugins" / "marketplace.json").is_file()
    for forbidden in (".agents/agents", ".agents/commands", ".agents/hooks", ".git"):
        assert not (repo / forbidden).exists()
    codex = {a["name"]: a for a in report["adapters"]}["codex_parity"]
    assert codex["status"] == "invalid" and codex["changed"] == 0  # parity adapter は read-only


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_apply_fingerprint_noop_second_run(tmp_path):
    repo = _synth_repo(tmp_path)
    _real_orch(repo, "apply")  # 1 回目: 同期。
    report, _ = _real_orch(repo, "apply")  # 2 回目: fingerprint 一致 → no-op。
    statuses = {a["name"]: a["status"] for a in report["adapters"]}
    assert statuses["claude_symlinks"] == "noop"
    assert statuses["claude_settings"] == "noop"


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_scope_excludes_disabled_from_symlinks(tmp_path):
    # p1 は present だが未 enabled → symlink/settings 両 surface から除外。
    repo = _synth_repo(tmp_path, enabled=())
    report, _ = _real_orch(repo, "apply")
    statuses = {a["name"]: a["status"] for a in report["adapters"]}
    assert statuses["claude_symlinks"] == "noop"  # scope 外 → 生成しない
    assert not (repo / ".claude" / "skills" / "s1").exists()
    # First apply may normalize the managed marker even with zero active sources,
    # but no disabled plugin values may enter that marker.
    assert statuses["claude_settings"] in ("synced", "noop")
    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    managed = settings["_build_claude_settings"]
    assert managed["managed_hooks"] == []
    assert managed["managed_permissions"] == []


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_enabled_then_disabled_is_pruned_and_immediate_check_is_clean(tmp_path):
    repo = _synth_repo(tmp_path, enabled=("p1",))
    _real_orch(repo, "apply")
    projected = repo / ".claude" / "skills" / "s1"
    assert projected.is_symlink()

    settings_path = repo / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["enabledPlugins"] = {}
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    apply_report, _ = _real_orch(repo, "apply")
    assert not projected.exists()
    assert {a["name"]: a["status"] for a in apply_report["adapters"]}["claude_symlinks"] == "synced"

    check_report, check_code = _real_orch(repo, "check")
    assert check_code == 3  # synthetic repo intentionally lacks complete Codex plugin metadata
    adapters = {a["name"]: a for a in check_report["adapters"]}
    assert adapters["claude_symlinks"]["status"] == "noop"
    assert adapters["claude_symlinks"]["exit"] == 0


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_check_does_not_write(tmp_path):
    repo = _synth_repo(tmp_path)
    _real_orch(repo, "check")
    # check は read-only: symlink も lock も生成されない。
    assert not (repo / ".claude" / "skills" / "s1").exists()
    assert not (repo / ".build" / "locks" / "lock").exists()


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_dry_run_does_not_write(tmp_path):
    repo = _synth_repo(tmp_path)
    _real_orch(repo, "dry-run")
    assert not (repo / ".claude" / "skills" / "s1").exists()


@pytest.mark.skipif(not (REAL_SYMLINKS.is_file() and REAL_SETTINGS.is_file() and REAL_CODEX.is_file()),
                    reason="real generators absent")
def test_integration_managed_projection_rollback_and_reapply_are_reproducible(tmp_path):
    """P05/P11: prove managed-only rollback in an isolated fixture repository."""
    repo = _synth_repo(tmp_path)
    settings_path = repo / ".claude" / "settings.json"
    codex_hooks_path = repo / ".codex" / "hooks.json"
    codex_config_path = repo / ".codex" / "config.toml"
    codex_discovery_path = repo / ".agents" / "plugins" / "marketplace.json"
    codex_config_path.write_text("[features]\nhooks = false\n", encoding="utf-8")
    source_paths = (
        repo / ".claude-plugin" / "marketplace.json",
        repo / "plugins" / "p1" / ".claude-plugin" / "plugin.json",
        repo / "plugins" / "p1" / ".codex-plugin" / "plugin.json",
        repo / "plugins" / "p1" / "native-surfaces.toml",
    )

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def projection_snapshot():
        skill = repo / ".claude" / "skills" / "s1"
        return {
            "settings": settings_path.read_bytes(),
            "skill_exists": skill.is_symlink(),
            "skill_target": os.readlink(skill) if skill.is_symlink() else None,
            "codex_hooks": codex_hooks_path.read_bytes(),
            "codex_config": codex_config_path.read_bytes(),
            "codex_discovery": codex_discovery_path.read_bytes(),
        }

    source_before = {path.relative_to(repo).as_posix(): sha(path) for path in source_paths}
    pre_file_bytes = {
        settings_path: settings_path.read_bytes(),
        codex_hooks_path: codex_hooks_path.read_bytes(),
        codex_config_path: codex_config_path.read_bytes(),
        codex_discovery_path: codex_discovery_path.read_bytes(),
    }
    pre_projection = projection_snapshot()
    pre_existing = {
        path.relative_to(repo).as_posix()
        for path in (
            settings_path,
            repo / ".claude" / "skills" / "s1",
            codex_hooks_path,
            codex_config_path,
            codex_discovery_path,
        )
        if path.exists() or path.is_symlink()
    }

    _real_orch(repo, "apply")
    post_projection = projection_snapshot()
    candidates = (
        settings_path,
        repo / ".claude" / "skills" / "s1",
        codex_hooks_path,
        codex_config_path,
        codex_discovery_path,
    )
    created_paths = sorted(
        path.relative_to(repo).as_posix()
        for path in candidates
        if (path.exists() or path.is_symlink()) and path.relative_to(repo).as_posix() not in pre_existing
    )
    assert created_paths == [".claude/skills/s1"]
    assert source_before == {path.relative_to(repo).as_posix(): sha(path) for path in source_paths}

    # managed-only rollback: restore pre-existing file bytes and remove only
    # paths proven absent in the pre snapshot. Source manifests are untouched.
    for path, content in pre_file_bytes.items():
        path.write_bytes(content)
    for rel in created_paths:
        path = repo / rel
        if path.is_symlink() or path.is_file():
            path.unlink()
    assert projection_snapshot() == pre_projection
    assert source_before == {path.relative_to(repo).as_posix(): sha(path) for path in source_paths}

    _real_orch(repo, "apply")
    assert projection_snapshot() == post_projection
    assert source_before == {path.relative_to(repo).as_posix(): sha(path) for path in source_paths}
