"""manage-build-lease.py (TG-C07) の機能テスト — build 開始前安全性ゲート。

conftest 非依存で module-level に importlib ロードする (自己完結)。
lock 取得/二重起動 already-held/孤児 steal (ttl 超過・pid 非生存)/破損 lock/別ホスト非 steal/
force-release/release/renew (renewed・lost・foreign)/lock-ttl 既定=2×lease/producer scripts
preflight/find_expired_leases 純関数/graph_hash pin 一致・不一致 (subprocess 委譲は
monkeypatch)/repin 時 task-graph 転送/reap 委譲 を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mbl = _load("manage-build-lease")


T0 = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
HOST = socket.gethostname()


# ─────────────────────────── helpers ───────────────────────────
def _dead_pid() -> int:
    """生存していない pid を探索して返す (steal 判定テスト用)。"""
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


def _write_lock(path: Path, *, started_at: str, pid: int, host: str,
                owner_token: str = "owner-a") -> None:
    path.write_text(json.dumps({"started_at": started_at, "pid": pid, "host": host,
                                "owner_token": owner_token}) + "\n",
                    encoding="utf-8")


def _write_legacy_lock(path: Path, *, started_at: str, pid: int, host: str) -> None:
    path.write_text(json.dumps({"started_at": started_at, "pid": pid, "host": host}) + "\n",
                    encoding="utf-8")


def _state(*nodes) -> dict:
    return {"schema_version": "1.0", "graph_hash": None, "nodes": [dict(n) for n in nodes]}


def _node(nid, state="pending", **extra) -> dict:
    base = {"id": nid, "state": state, "started_at": None, "lease_expires_at": None}
    base.update(extra)
    return base


# ─────────────────────────── pid_alive ───────────────────────────
def test_pid_alive_true_for_self():
    assert mbl.pid_alive(os.getpid()) is True


def test_pid_alive_false_for_dead():
    assert mbl.pid_alive(_dead_pid()) is False


def test_pid_alive_false_for_invalid():
    assert mbl.pid_alive(0) is False
    assert mbl.pid_alive(-1) is False


# ─────────────────────────── acquire_lock ───────────────────────────
def test_acquire_lock_creates_when_absent(tmp_path):
    lock = tmp_path / ".build.lock"
    assert mbl.acquire_lock(lock, T0, 900) == "acquired"
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert content["started_at"] == "2026-07-06T12:00:00Z"
    assert content["pid"] == os.getpid()
    assert content["host"] == HOST
    assert isinstance(content["owner_token"], str) and len(content["owner_token"]) >= 16


def test_acquire_lock_already_held_when_live(tmp_path):
    lock = tmp_path / ".build.lock"
    # 現プロセス pid + 直近 started_at の生存 lock。
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    assert mbl.acquire_lock(lock, T0, 900) == "already-held"
    # 中身は上書きされていない。
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_acquire_lock_steals_when_ttl_exceeded(tmp_path):
    lock = tmp_path / ".build.lock"
    old = mbl._iso(T0 - timedelta(seconds=1800))  # ttl=900 を大きく超過
    _write_lock(lock, started_at=old, pid=os.getpid(), host=HOST)
    assert mbl.acquire_lock(lock, T0, 900) == "stolen"
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert content["started_at"] == "2026-07-06T12:00:00Z"  # 自分の中身で上書き


def test_acquire_lock_steals_when_pid_dead(tmp_path):
    lock = tmp_path / ".build.lock"
    # ttl 内だが同一ホストで pid 非生存 → 孤児 steal。
    _write_lock(lock, started_at=mbl._iso(T0), pid=_dead_pid(), host=HOST)
    assert mbl.acquire_lock(lock, T0, 900) == "stolen"
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_acquire_stale_legacy_lock_migrates_to_owner_token(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_legacy_lock(lock, started_at=mbl._iso(T0), pid=_dead_pid(), host=HOST)
    lease = mbl.acquire_lock(lock, T0, 900)
    assert lease == "stolen"
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert mbl._lock_format(content) == "owner-token"
    assert isinstance(content["owner_token"], str) and content["owner_token"]


def test_acquire_lock_no_steal_when_different_host(tmp_path):
    lock = tmp_path / ".build.lock"
    # 別ホストは pid 生存判定できないため ttl 内なら steal しない。
    _write_lock(lock, started_at=mbl._iso(T0), pid=_dead_pid(), host="__other_host__")
    assert mbl.acquire_lock(lock, T0, 900) == "already-held"


def test_acquire_lock_steals_when_corrupt(tmp_path):
    lock = tmp_path / ".build.lock"
    lock.write_text("{ not json", encoding="utf-8")
    # 破損 lock は恒久 lockout 回避のため stale とみなし steal。
    assert mbl.acquire_lock(lock, T0, 900) == "stolen"
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_acquire_stale_compare_delete_race_preserves_new_owner(tmp_path, monkeypatch):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0 - timedelta(seconds=1800)), pid=_dead_pid(), host=HOST)
    real_compare_delete = mbl._compare_delete
    raced = False

    def _race(path, expected):
        nonlocal raced
        if not raced:
            raced = True
            _write_lock(path, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST,
                        owner_token="new-owner")
        return real_compare_delete(path, expected)

    monkeypatch.setattr(mbl, "_compare_delete", _race)
    assert mbl.acquire_lock(lock, T0, 900) == "already-held"
    assert json.loads(lock.read_text(encoding="utf-8"))["owner_token"] == "new-owner"


# ─────────────────────────── renew_lock / release_lock ───────────────────────────
def test_renew_lock_updates_started_at_when_held(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0 - timedelta(seconds=300)), pid=os.getpid(), host=HOST)
    assert mbl.renew_lock(lock, T0, "owner-a") == "renewed"
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert content["started_at"] == "2026-07-06T12:00:00Z"
    assert content["pid"] == os.getpid() and content["host"] == HOST


def test_renew_lock_lost_when_absent(tmp_path):
    lock = tmp_path / ".build.lock"
    assert mbl.renew_lock(lock, T0, "owner-a") == "lost"
    assert not lock.exists()  # 再作成しない (lock 喪失を隠蔽しない)


def test_renew_lock_foreign_when_other_host(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0 - timedelta(seconds=300)), pid=os.getpid(), host="__other_host__")
    assert mbl.renew_lock(lock, T0, "wrong-owner") == "foreign"
    # 他者の lock を書き換えない。
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert content["started_at"] == mbl._iso(T0 - timedelta(seconds=300))


def test_renew_lock_foreign_when_live_other_pid_same_host(tmp_path):
    lock = tmp_path / ".build.lock"
    live_other = os.getppid()  # 実際に生存している自プロセス以外の pid
    _write_lock(lock, started_at=mbl._iso(T0), pid=live_other, host=HOST)
    assert mbl.renew_lock(lock, T0, "wrong-owner") == "foreign"
    # 生きた他 dispatcher の lock は不変。
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == live_other


def test_renew_lock_renewed_with_owner_token_even_when_pid_is_dead(tmp_path):
    # CLI 都度呼出し運用で pid は変わるため owner token で継続を認証する。
    lock = tmp_path / ".build.lock"
    dead = _dead_pid()
    _write_lock(lock, started_at=mbl._iso(T0 - timedelta(seconds=300)), pid=dead, host=HOST)
    assert mbl.renew_lock(lock, T0, "owner-a") == "renewed"
    content = json.loads(lock.read_text(encoding="utf-8"))
    assert content["started_at"] == "2026-07-06T12:00:00Z"
    assert content["pid"] == dead and content["host"] == HOST  # 識別情報は保持


def test_release_lock_unlinks(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    assert mbl.release_lock(lock, "owner-a") == "released"
    assert not lock.exists()


def test_release_lock_missing_ok(tmp_path):
    assert mbl.release_lock(tmp_path / ".build.lock", "owner-a") == "lost"


def test_release_lock_refuses_foreign_owner(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    assert mbl.release_lock(lock, "owner-b") == "foreign"
    assert lock.exists()


def test_legacy_lock_cannot_be_renewed_or_released_without_admin(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_legacy_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    assert mbl.renew_lock(lock, T0, "guessed") == "foreign"
    assert mbl.release_lock(lock, "guessed") == "foreign"
    assert lock.exists()


def test_write_lock_atomic_no_temp_residue(tmp_path):
    lock = tmp_path / ".build.lock"
    mbl._write_lock(lock, {"pid": 1})
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == 1
    assert [p.name for p in tmp_path.iterdir()] == [".build.lock"]  # tempfile 残骸なし


# ─────────────────────────── find_expired_leases (純関数) ───────────────────────────
def test_find_expired_leases_returns_running_past_expiry():
    st = _state(
        _node("T1", "running", lease_expires_at=mbl._iso(T0 - timedelta(seconds=60))),
        _node("T2", "running", lease_expires_at=mbl._iso(T0 + timedelta(seconds=60))),
        _node("T3", "pending", lease_expires_at=mbl._iso(T0 - timedelta(seconds=60))),
        _node("T4", "done"),
    )
    assert mbl.find_expired_leases(st, T0) == ["T1"]


def test_find_expired_leases_skips_missing_lease():
    st = _state(_node("T1", "running", lease_expires_at=None))
    assert mbl.find_expired_leases(st, T0) == []


def test_find_expired_leases_empty_state():
    assert mbl.find_expired_leases({}, T0) == []


def test_find_expired_leases_is_pure(tmp_path):
    st = _state(_node("T1", "running", lease_expires_at=mbl._iso(T0 - timedelta(seconds=60))))
    snapshot = json.dumps(st, sort_keys=True)
    mbl.find_expired_leases(st, T0)
    assert json.dumps(st, sort_keys=True) == snapshot  # 入力不変


def test_repin_graph_hash_forwards_task_graph_to_single_writer(tmp_path, monkeypatch):
    """accepted repin は TG-C02 がdone dirty-closure を導出できるよう graph を渡す。"""
    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0

    def _fake_run(cmd, *, capture_output, text):
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["text"] = text
        return _Proc()

    monkeypatch.setattr(mbl.subprocess, "run", _fake_run)
    graph = tmp_path / "task-graph.json"
    new_hash = "sha256:" + "f" * 64
    rc = mbl._repin_graph_hash(
        tmp_path / "sync-task-state.py",
        tmp_path / "task-state.json",
        tmp_path / "task-events.jsonl",
        graph,
        new_hash,
        {"sha256:" + "b" * 64, new_hash},
    )

    assert rc == 0
    cmd = captured["cmd"]
    assert cmd[cmd.index("--task-graph") + 1] == str(graph)
    assert cmd[cmd.index("--repin-graph-hash") + 1] == new_hash
    assert [cmd[i + 1] for i, value in enumerate(cmd) if value == "--authorized-hash"] == sorted({
        "sha256:" + "b" * 64, new_hash,
    })


# ─────────────────────────── main: release / force-release / renew ───────────────────────────
def test_main_release_exit0(tmp_path):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    rc = mbl.main(["--lock-action", "release", "--lock-path", str(lock),
                   "--owner-token", "owner-a"])
    assert rc == 0 and not lock.exists()


def test_main_force_release_exit0(tmp_path, capsys):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)  # 生存 lock でも無条件解放
    rc = mbl.main(["--lock-action", "force-release", "--lock-path", str(lock), "--admin"])
    assert rc == 0 and not lock.exists()
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "released"


def test_main_force_release_requires_admin(tmp_path, capsys):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST)
    rc = mbl.main(["--lock-action", "force-release", "--lock-path", str(lock)])
    assert rc == 2 and lock.exists()
    assert "--admin" in capsys.readouterr().err


def test_force_release_compare_delete_race_preserves_new_owner(tmp_path, monkeypatch):
    lock = tmp_path / ".build.lock"
    _write_legacy_lock(lock, started_at=mbl._iso(T0), pid=_dead_pid(), host=HOST)
    real_compare_delete = mbl._compare_delete

    def _race(path, expected):
        _write_lock(path, started_at=mbl._iso(T0), pid=os.getpid(), host=HOST,
                    owner_token="new-owner")
        return real_compare_delete(path, expected)

    monkeypatch.setattr(mbl, "_compare_delete", _race)
    assert mbl.force_release_lock(lock) == "lost"
    assert json.loads(lock.read_text(encoding="utf-8"))["owner_token"] == "new-owner"


def test_main_renew_exit0(tmp_path, capsys):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0 - timedelta(seconds=300)), pid=os.getpid(), host=HOST)
    rc = mbl.main(["--lock-action", "renew", "--lock-path", str(lock),
                   "--owner-token", "owner-a"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "renewed"
    # started_at が現在時刻へ更新されている (300 秒前ではない)。
    assert json.loads(lock.read_text(encoding="utf-8"))["started_at"] != mbl._iso(T0 - timedelta(seconds=300))


def test_main_renew_lost_exit1(tmp_path, capsys):
    lock = tmp_path / ".build.lock"
    rc = mbl.main(["--lock-action", "renew", "--lock-path", str(lock),
                   "--owner-token", "owner-a"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "lost"
    assert not lock.exists()  # 再作成しない


def test_main_renew_foreign_exit1(tmp_path, capsys):
    lock = tmp_path / ".build.lock"
    _write_lock(lock, started_at=mbl._iso(T0), pid=4242, host="__other_host__")
    rc = mbl.main(["--lock-action", "renew", "--lock-path", str(lock),
                   "--owner-token", "owner-b"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "foreign"
    # 他者の lock は不変。
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == 4242


# ─────────────────────────── main: acquire ───────────────────────────
def _stub_ok(monkeypatch, *, derive_hash="sha256:" + "a" * 64, verify=True):
    """subprocess 委譲ヘルパを monkeypatch し決定論化する。"""
    monkeypatch.setattr(mbl, "_initialize_state", lambda *a, **k: 0)
    monkeypatch.setattr(mbl, "_reap_lease", lambda *a, **k: 0)
    monkeypatch.setattr(mbl, "_derive_graph_hash", lambda *a, **k: derive_hash)
    monkeypatch.setattr(mbl, "_pin_graph_hash", lambda *a, **k: 0)
    monkeypatch.setattr(mbl, "_verify_graph_hash_pin", lambda *a, **k: verify)


def test_main_acquire_already_held_exit1(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    _write_lock(build / ".build.lock", started_at=mbl._iso(mbl._utc_now()), pid=os.getpid(), host=HOST)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "already-held"


def test_main_acquire_live_legacy_lock_reports_admin_migration_path(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    _write_legacy_lock(build / ".build.lock", started_at=mbl._iso(mbl._utc_now()),
                       pid=os.getpid(), host=HOST)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1 and out["lock_format"] == "legacy"
    assert "force-release --admin" in out["remediation"]
    assert mbl._lock_format(json.loads((build / ".build.lock").read_text())) == "legacy"


def test_main_acquire_pins_when_unset(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    # task-state 不在 (graph_hash 未設定) → 初回 pin 経路。
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["lock"] == "acquired" and out["graph_hash_pin"] == "pinned"
    assert out["owner_token"] == json.loads((build / ".build.lock").read_text())["owner_token"]
    assert out["reaped_task_ids"] == []
    assert (build / ".build.lock").exists()  # lock は保持したまま


def test_main_acquire_verified_when_set(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    state = _state(_node("T1", "done"))
    state["graph_hash"] = "sha256:" + "b" * 64
    (build / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    _stub_ok(monkeypatch, verify=True)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["graph_hash_pin"] == "verified"


def test_main_acquire_mismatch_releases_and_exit1(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    state = _state(_node("T1", "pending"))
    state["graph_hash"] = "sha256:" + "c" * 64
    (build / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    _stub_ok(monkeypatch, verify=False)  # pin 不一致
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["graph_hash_pin"] == "mismatch"
    # fail-closed: lock を解放してから exit1。
    assert not (build / ".build.lock").exists()


def test_main_acquire_repins_when_drained(tmp_path, monkeypatch, capsys):
    """外ループ再入: pin 不一致でも現 graph hash が accepted form の resulting_graph_hash と
    一致すれば provenance-gated 再 pin して repinned exit0 (crux)。"""
    build = tmp_path / "build"
    build.mkdir()
    new_hash = "sha256:" + "f" * 64
    state = _state(_node("T1", "done"))
    state["graph_hash"] = "sha256:" + "0" * 64  # 旧 pin (drain 前)
    (build / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    # inbox に accepted form (resulting_graph_hash == 現 graph の新 hash)
    inbox = build / "discovered-tasks"
    inbox.mkdir()
    (inbox / "d1.json").write_text(json.dumps({"status": "accepted", "resulting_graph_hash": new_hash}), encoding="utf-8")
    _stub_ok(monkeypatch, derive_hash=new_hash, verify=False)  # pin 不一致 → 再入判定へ
    monkeypatch.setattr(mbl, "_repin_graph_hash", lambda *a, **k: 0)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["graph_hash_pin"] == "repinned"
    assert (build / ".build.lock").exists()  # lock 保持 (再入して build 継続)


def test_main_acquire_mismatch_when_hash_unauthorized(tmp_path, monkeypatch, capsys):
    """pin 不一致かつ現 graph hash が accepted form のどれとも不一致 → 不正混入として mismatch abort。"""
    build = tmp_path / "build"
    build.mkdir()
    state = _state(_node("T1", "pending"))
    state["graph_hash"] = "sha256:" + "0" * 64
    (build / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    inbox = build / "discovered-tasks"
    inbox.mkdir()
    # accepted form はあるが resulting_graph_hash が現 graph hash と別物 (認可されない)
    (inbox / "d1.json").write_text(json.dumps({"status": "accepted", "resulting_graph_hash": "sha256:" + "9" * 64}), encoding="utf-8")
    _stub_ok(monkeypatch, derive_hash="sha256:" + "f" * 64, verify=False)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["graph_hash_pin"] == "mismatch"
    assert not (build / ".build.lock").exists()  # fail-closed: lock 解放


def test_main_acquire_reaps_expired_leases(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    state = _state(
        _node("T1", "running", lease_expires_at=mbl._iso(mbl._utc_now() - timedelta(seconds=120))),
        _node("T2", "running", lease_expires_at=mbl._iso(mbl._utc_now() + timedelta(seconds=600))),
    )
    (build / "task-state.json").write_text(json.dumps(state), encoding="utf-8")
    reaped_calls: list[str] = []

    def _fake_reap(sync_script, state_path, events_path, task_id):
        reaped_calls.append(task_id)
        return 0

    monkeypatch.setattr(mbl, "_initialize_state", lambda *a, **k: 0)
    monkeypatch.setattr(mbl, "_reap_lease", _fake_reap)
    monkeypatch.setattr(mbl, "_derive_graph_hash", lambda *a, **k: "sha256:" + "a" * 64)
    monkeypatch.setattr(mbl, "_pin_graph_hash", lambda *a, **k: 0)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["reaped_task_ids"] == ["T1"]  # 期限切れの running のみ
    assert reaped_calls == ["T1"]


def test_main_acquire_requires_task_graph(tmp_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
    ])
    assert rc == 2
    # graph_hash 検証に到達できないため lock は解放される。
    assert not (build / ".build.lock").exists()


def test_main_acquire_initialize_failure_releases_lock(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    _stub_ok(monkeypatch)
    monkeypatch.setattr(mbl, "_initialize_state", lambda *a, **k: 1)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 1
    assert "--initialize-from-graph" in capsys.readouterr().err
    assert not (build / ".build.lock").exists()


def test_initialize_state_delegates_to_c02_and_materializes_sparse_state(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    state_path = build / "task-state.json"
    events_path = build / "task-events.jsonl"
    state_path.write_text(json.dumps(_state(*[_node(f"T{i}", "done") for i in range(110)])),
                          encoding="utf-8")
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps({
        "nodes": [{"id": f"T{i}"} for i in range(135)], "edges": [],
    }), encoding="utf-8")
    sync_script = SCRIPTS / "sync-task-state.py"
    assert mbl._initialize_state(sync_script, state_path, events_path, str(graph_path)) == 0
    nodes = json.loads(state_path.read_text(encoding="utf-8"))["nodes"]
    assert len(nodes) == 135
    assert sum(node["state"] == "done" for node in nodes) == 110
    assert sum(node["state"] == "pending" for node in nodes) == 25


def test_main_acquire_default_path_from_resolve_build_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--target-plugin-slug", "acme", "--cycle-id", "20260706-x",
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 0
    lock = tmp_path / "eval-log/acme/build/20260706-x/.build.lock"
    assert lock.exists()


def test_main_missing_slug_and_state_exit2(tmp_path):
    rc = mbl.main(["--lock-action", "release"])
    assert rc == 2


# ─────────────────────────── lock-ttl 既定 = 2×lease ───────────────────────────
def _write_aged_own_lock(build: Path, age_seconds: int) -> None:
    _write_lock(build / ".build.lock",
                started_at=mbl._iso(mbl._utc_now() - timedelta(seconds=age_seconds)),
                pid=os.getpid(), host=HOST)


def test_main_acquire_ttl_defaults_to_twice_lease(tmp_path, monkeypatch, capsys):
    """--lock-ttl-seconds 省略時は 2×lease-seconds。aged 700s は ttl=600 で孤児 steal。"""
    build = tmp_path / "build"
    build.mkdir()
    _write_aged_own_lock(build, 700)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"), "--lease-seconds", "300",
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "stolen"


def test_main_acquire_default_lease_ttl_keeps_live_lock(tmp_path, monkeypatch, capsys):
    """既定 lease (C02 DEFAULT_LEASE_SECONDS=3600) 由来 ttl=7200 では aged 700s は生存扱い。"""
    build = tmp_path / "build"
    build.mkdir()
    _write_aged_own_lock(build, 700)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "already-held"


def test_main_acquire_explicit_ttl_overrides_lease_derivation(tmp_path, monkeypatch, capsys):
    """明示 --lock-ttl-seconds は 2×lease 導出より優先 (aged 700s < ttl=3600 → already-held)。"""
    build = tmp_path / "build"
    build.mkdir()
    _write_aged_own_lock(build, 700)
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
        "--lease-seconds", "300", "--lock-ttl-seconds", "3600",
    ])
    assert rc == 1
    assert json.loads(capsys.readouterr().out.strip())["lock"] == "already-held"


# ─────────────────────────── producer scripts preflight ───────────────────────────
def test_main_acquire_preflight_missing_producer_scripts_exit2(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build"
    build.mkdir()
    empty_dir = tmp_path / "no-planner-scripts"
    empty_dir.mkdir()
    _stub_ok(monkeypatch)
    rc = mbl.main([
        "--lock-action", "acquire", "--task-state", str(build / "task-state.json"),
        "--task-graph", str(tmp_path / "task-graph.json"),
        "--planner-scripts-dir", str(empty_dir),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "derive-task-graph.py" in err and "check-task-state-schema.py" in err
    assert not (build / ".build.lock").exists()  # preflight は lock 取得前


def test_default_planner_scripts_dir_from_resolve_planner_root():
    expected = mbl.resolve_planner_root() / "skills" / "run-plugin-dev-plan" / "scripts"
    assert mbl._default_planner_scripts_dir() == expected
    assert (expected / "derive-task-graph.py").is_file()
    assert (expected / "check-task-state-schema.py").is_file()


# ─────────────────────────── C02 SSOT import 再利用 ───────────────────────────
def test_resolve_build_dir_imported_from_c02():
    assert mbl.resolve_build_dir("acme", None) == "eval-log/acme/build"
    assert mbl.resolve_build_dir("acme", "20260706-x") == "eval-log/acme/build/20260706-x"


def test_lease_default_and_time_utils_shared_with_c02():
    sts = _load("sync-task-state")
    assert mbl.DEFAULT_LEASE_SECONDS == sts.DEFAULT_LEASE_SECONDS
    # 時刻ユーティリティは複製ではなく C02 定義の関数 (定義元ファイルで判定)。
    for fn in (mbl._iso, mbl._parse_iso, mbl._utc_now):
        assert fn.__code__.co_filename.endswith("sync-task-state.py")
