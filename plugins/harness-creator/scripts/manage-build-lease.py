#!/usr/bin/env python3
# /// script
# name: manage-build-lease
# purpose: task-graph 駆動 build の開始前安全性ゲート (TG-C07)。build lock 排他 (.build.lock の O_EXCL 生成/孤児 steal)・孤児 lease 回収 (実書込は TG-C02 sync-task-state.py へ subprocess 委譲)・graph_hash pin 検証/初回 pin (producer derive/check への read-only subprocess) を build 開始時に一度だけ実行する。TG-C07 自身は task-state.json を直接書かない (単一 writer=TG-C02 を維持)。
# inputs:
#   - argv: --lock-action acquire|release|force-release|renew
#           --target-plugin-slug S [--cycle-id C] [--task-state P] [--task-graph G]
#           [--lock-path L] [--lease-seconds N] [--lock-ttl-seconds N (省略時 2×lease)] [--planner-scripts-dir D]
# outputs:
#   - stdout: 結果 JSON ({"lock":...}/{"graph_hash_pin":...}/{"lock":..,"reaped_task_ids":[..],"graph_hash_pin":..})
#   - stderr: エラーメッセージ
#   - exit: 0=OK / 1=already-held or graph_hash mismatch or renew lost/foreign (fail-closed) / 2=usage/IO error・producer scripts 欠落
#   - write-scope: <build-dir>/.build.lock のみ (task-state.json/task-events.jsonl は TG-C02 へ委譲)
# contexts: [C, E]
# network: false
# write-scope: <build-dir>/.build.lock (co-located build dir・lock ファイルのみ)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""build 開始前安全性ゲート (TG-C07)。

lease 回収・build lock 排他・graph_hash pin 検証の 3 検査を
「build 開始時に一度だけ実行される安全性検査」という共通タイミングで単一 script へ統合し、
dispatcher 側の呼び出し漏れ (lock だけ取得し pin 検証を呼び忘れる等) を防ぐ。

lock 中身は `{started_at, pid, host, owner_token}` JSON で、os.O_CREAT|os.O_EXCL の排他生成で取得する。
既存 lock が heartbeat 途絶 (ttl 超過) または同一ホストで pid 非生存の場合のみ孤児と判定して
steal し、dispatcher クラッシュ後の残留 lock による恒久 lockout (resume 時の自己締め出し) を防ぐ。
owner_token 導入前の legacy lock は、生存中なら自動移行せず already-held を返す。TTL 超過/死 pid
なら通常の stale steal で owner-token 形式へ移行し、緊急時だけ人間が `force-release --admin` を使う。

実書込 (task-state.json への lease 回収 / graph_hash pin) は TG-C02 sync-task-state.py へ subprocess
委譲し、TG-C07 自身は task-state を直接書かない (単一 writer 規約の維持)。resolve_build_dir は
TG-C02 を SSOT として import 再利用する (周回衝突排除ロジックを再実装しない)。
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

LOCK_FILENAME = ".build.lock"


# ── TG-C02 (sync-task-state.py) を SSOT として import 再利用 ────────────────────
# resolve_build_dir/resolve_planner_root/lease 既定/時刻ユーティリティは C02 が正本。
# 複製を持たず module 属性の再 export に留める (drift 封鎖)。
def _load_sync_task_state():
    path = Path(__file__).resolve().parent / "sync-task-state.py"
    spec = importlib.util.spec_from_file_location("sync_task_state", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sts = _load_sync_task_state()
resolve_build_dir = _sts.resolve_build_dir
resolve_planner_root = _sts.resolve_planner_root
DEFAULT_LEASE_SECONDS = _sts.DEFAULT_LEASE_SECONDS
_utc_now = _sts._utc_now
_iso = _sts._iso
_parse_iso = _sts._parse_iso


# ── pid 生存判定 (os.kill(pid, 0)) ────────────────────────────────────────────
def pid_alive(pid: int) -> bool:
    """os.kill(pid, 0) の成否で pid 生存を判定する。

    - 成功 (シグナル 0 送出可) → True。
    - ProcessLookupError (該当 pid 無し) → False。
    - PermissionError (プロセスは存在するが別ユーザ所有) → True (生存とみなす)。
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ── lock 中身の直列化 ─────────────────────────────────────────────────────────
def _lock_content(now: datetime) -> dict:
    return _lock_content_for_owner(now, secrets.token_hex(16))


def _lock_content_for_owner(now: datetime, owner_token: str) -> dict:
    return {
        "started_at": _iso(now), "pid": os.getpid(), "host": socket.gethostname(),
        "owner_token": owner_token,
    }


def _write_lock(lock_path: Path, content: dict) -> None:
    """同 dir の tempfile へ書いてから os.replace する原子的上書き (steal の途中書込 lock を防ぐ)。"""
    fd, tmp = tempfile.mkstemp(dir=str(lock_path.parent), prefix=LOCK_FILENAME + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(content, ensure_ascii=False) + "\n")
        os.replace(tmp, str(lock_path))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_lock(lock_path: Path) -> dict | None:
    return _decode_lock(_read_lock_bytes(lock_path))


def _read_lock_bytes(lock_path: Path) -> bytes | None:
    try:
        return Path(lock_path).read_bytes()
    except OSError:
        return None


def _decode_lock(raw: bytes | None) -> dict | None:
    try:
        data = json.loads(raw.decode("utf-8")) if raw is not None else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _lock_format(existing: object) -> str:
    """診断用 lock format。legacy 生存 lock の安全な移行導線を CLI へ出す。"""
    if not isinstance(existing, dict):
        return "invalid"
    token = existing.get("owner_token")
    return "owner-token" if isinstance(token, str) and token else "legacy"


class LockLease:
    """取得結果と renew/release に必須の推測不能 owner token。"""

    def __init__(self, state: str, owner_token: str):
        self.state = state
        self.owner_token = owner_token

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.state == other
        if isinstance(other, LockLease):
            return (self.state, self.owner_token) == (other.state, other.owner_token)
        return False


def _compare_delete(lock_path: Path, expected: bytes) -> bool:
    """判定時に読んだ inode と内容が同一の場合だけ unlink する。"""
    fd: int | None = None
    try:
        fd = os.open(str(lock_path), os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        opened = os.fstat(fd)
        current = os.stat(lock_path)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            return False
        os.lseek(fd, 0, os.SEEK_SET)
        if os.read(fd, max(len(expected) + 1, 1)) != expected:
            return False
        Path(lock_path).unlink()
        return True
    except (FileNotFoundError, OSError):
        return False
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def _compare_replace(lock_path: Path, expected: bytes, content: dict) -> bool:
    """判定時の inode/content が変わっていない場合だけ heartbeat を原子的更新する。"""
    fd: int | None = None
    try:
        fd = os.open(str(lock_path), os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        opened = os.fstat(fd)
        current = os.stat(lock_path)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            return False
        os.lseek(fd, 0, os.SEEK_SET)
        if os.read(fd, max(len(expected) + 1, 1)) != expected:
            return False
        _write_lock(lock_path, content)
        return True
    except (FileNotFoundError, OSError):
        return False
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def _is_stale(existing: dict | None, now: datetime, lock_ttl_seconds: int) -> bool:
    """既存 lock が孤児 (回収可) か判定する。

    is_stale = (now - started_at) > ttl  (heartbeat 途絶)
               or (host == 現ホスト and not pid_alive(pid))  (同一ホストの死んだ dispatcher)
    parse 不能な破損 lock は恒久 lockout 回避のため stale とみなす。
    """
    if not isinstance(existing, dict):
        return True
    started = existing.get("started_at")
    try:
        age = (now - _parse_iso(started)).total_seconds()
    except (TypeError, ValueError):
        return True
    if age > lock_ttl_seconds:
        return True
    if existing.get("host") == socket.gethostname() and not pid_alive(existing.get("pid")):
        return True
    return False


# ── 公開 API: lock 取得/更新/解放 ─────────────────────────────────────────────
def acquire_lock(lock_path: Path, now: datetime, lock_ttl_seconds: int) -> LockLease | str:
    """.build.lock を O_CREAT|O_EXCL で排他生成する。

    - 新規生成成功 → 中身 {started_at,pid,host,owner_token} を書いて "acquired"。
    - FileExistsError → 既存 lock を読み is_stale を評価。
        stale → 自分の中身で上書き再取得して "stolen"。
        生存 → "already-held" (取得失敗)。
    """
    lock_path = Path(lock_path)
    owner_token = secrets.token_hex(16)
    acquired_state = "acquired"
    # stale compare-delete 後は必ず O_EXCL に戻る。複数 contender が stale と判定しても
    # 最終的に 1 者だけが新 inode を発行する。race が続く場合は fail-closed。
    for _attempt in range(16):
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            snapshot = _read_lock_bytes(lock_path)
            existing = _decode_lock(snapshot)
            if _is_stale(existing, now, lock_ttl_seconds):
                if snapshot is not None and _compare_delete(lock_path, snapshot):
                    acquired_state = "stolen"
                continue
            return "already-held"
        try:
            # 新規 inode の空内容を他 contender が破損 stale と誤判定しないよう、
            # 公開まで inode lock を保持する。
            fcntl.flock(fd, fcntl.LOCK_EX)
            opened = os.fstat(fd)
            current = os.stat(lock_path)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                os.close(fd)
                continue
            content = _lock_content_for_owner(now, owner_token)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(content, ensure_ascii=False) + "\n")
                fh.flush()
            return LockLease(acquired_state, owner_token)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
    return "already-held"


def renew_lock(lock_path: Path, now: datetime, owner_token: str | None) -> str:
    """保持中 lock の started_at のみ now へ更新する (heartbeat・pid/host は保持)。

    lock 不在 (parse 不能含む) は "lost"、別ホストまたは同一ホストで生存中の他プロセスが
    保持する lock は "foreign" を返し再作成しない (lock 喪失/横取りを隠蔽せず dispatcher へ
    通知し二重 build を防ぐ)。CLI 都度呼出し運用では lock 所有者 pid は過去の自 subprocess
    (非生存) が正常のため、同一ホストの死 pid は自己継続とみなし更新して "renewed"。
    """
    lock_path = Path(lock_path)
    snapshot = _read_lock_bytes(lock_path)
    existing = _decode_lock(snapshot)
    if existing is None or snapshot is None:
        return "lost"
    if not owner_token or existing.get("owner_token") != owner_token:
        return "foreign"
    content = dict(existing)
    content["started_at"] = _iso(now)
    return "renewed" if _compare_replace(lock_path, snapshot, content) else "lost"


def release_lock(lock_path: Path, owner_token: str | LockLease | None) -> str:
    """owner token が一致する、読取後未変更の lock だけを解放する。"""
    token = owner_token.owner_token if isinstance(owner_token, LockLease) else owner_token
    snapshot = _read_lock_bytes(lock_path)
    existing = _decode_lock(snapshot)
    if snapshot is None:
        return "lost"
    if not isinstance(existing, dict) or not token or existing.get("owner_token") != token:
        return "foreign"
    return "released" if _compare_delete(lock_path, snapshot) else "lost"


def force_release_lock(lock_path: Path) -> str:
    """admin 導線専用。読み取った inode/content だけを強制解放する。"""
    snapshot = _read_lock_bytes(lock_path)
    if snapshot is None:
        return "lost"
    return "released" if _compare_delete(lock_path, snapshot) else "lost"


# ── 孤児 lease 検出 (純関数・実書込みを持たない) ──────────────────────────────
def find_expired_leases(task_state: dict, now: datetime) -> list[str]:
    """state==running かつ lease_expires_at<now の node id 一覧を返す (純関数)。

    dispatcher の --renew-lease heartbeat で延長された lease は将来時刻となり対象外
    (正当な長時間 running は回収されない=F1)。lease_expires_at 不在/parse 不能はスキップ。
    """
    out: list[str] = []
    for node in task_state.get("nodes", []):
        if node.get("state") != "running":
            continue
        lease = node.get("lease_expires_at")
        if lease is None:
            continue
        try:
            expired = _parse_iso(lease) < now
        except (TypeError, ValueError):
            continue
        if expired:
            out.append(node.get("id"))
    return out


# ── 実書込 / hash 算出の subprocess 委譲 (monkeypatch 点) ──────────────────────
def _reap_lease(sync_script: Path, state_path: Path, events_path: Path, task_id: str) -> int:
    """TG-C02 へ lease 回収 (running→pending) を委譲する。TG-C07 は task-state を直接書かない。"""
    proc = subprocess.run(
        [sys.executable, str(sync_script), "--task-state", str(state_path),
         "--events", str(events_path), "--task-id", task_id,
         "--to-state", "pending", "--reap-lease"],
        capture_output=True, text=True,
    )
    return proc.returncode


def _initialize_state(sync_script: Path, state_path: Path, events_path: Path,
                      task_graph_path: str) -> int:
    """TG-C02 単一 writer へ graph node set の pending materialize を委譲する。"""
    proc = subprocess.run(
        [sys.executable, str(sync_script), "--task-state", str(state_path),
         "--events", str(events_path), "--task-graph", str(task_graph_path),
         "--initialize-from-graph"],
        capture_output=True, text=True,
    )
    return proc.returncode


def _derive_graph_hash(derive_script: Path, task_graph_path: str) -> str | None:
    """producer derive-task-graph.py --print-graph-hash (read-only・FC-4) で hash を算出する。"""
    proc = subprocess.run(
        [sys.executable, str(derive_script), "--print-graph-hash", str(task_graph_path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _pin_graph_hash(sync_script: Path, state_path: Path, events_path: Path, graph_hash: str) -> int:
    """TG-C02 --pin-graph-hash で初回 pin を委譲する。"""
    proc = subprocess.run(
        [sys.executable, str(sync_script), "--task-state", str(state_path),
         "--events", str(events_path), "--pin-graph-hash", graph_hash],
        capture_output=True, text=True,
    )
    return proc.returncode


def _verify_graph_hash_pin(check_script: Path, state_path: Path, task_graph_path: str) -> bool:
    """producer check-task-state-schema.py の graph_hash pin 再照合 (exit0=一致) を委譲する。"""
    proc = subprocess.run(
        [sys.executable, str(check_script), "--task-state", str(state_path),
         "--task-graph", str(task_graph_path)],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def _scan_authorized_hashes(inbox_dir: Path) -> set[str]:
    """外ループ再入認可: accepted discovered-task form の resulting_graph_hash 集合を返す (SS-4)。

    planner drain が accepted form へ焼いた最終 graph_hash のみが正当な再入先。これに一致
    しない graph 差替えは TG-C07 が fail-closed 拒否する (実行中の不正混入=F10 を維持)。
    """
    out: set[str] = set()
    if not inbox_dir.is_dir():
        return out
    for form_path in inbox_dir.glob("*.json"):
        try:
            form = json.loads(form_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if form.get("status") == "accepted" and isinstance(form.get("resulting_graph_hash"), str):
            out.add(form["resulting_graph_hash"])
    return out


def _repin_graph_hash(sync_script: Path, state_path: Path, events_path: Path,
                      new_hash: str, authorized: set[str]) -> int:
    """TG-C02 --repin-graph-hash で provenance-gated 再 pin を委譲する (外ループ再入)。"""
    cmd = [sys.executable, str(sync_script), "--task-state", str(state_path),
           "--events", str(events_path), "--repin-graph-hash", new_hash]
    for h in sorted(authorized):
        cmd += ["--authorized-hash", h]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode


def _default_planner_scripts_dir() -> Path:
    """producer scripts の既定所在。planner root は C02 resolve_planner_root() を SSOT として再利用。"""
    return resolve_planner_root() / "skills" / "run-plugin-dev-plan" / "scripts"


def _read_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"schema_version": "1.0", "graph_hash": None, "nodes": []}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "1.0", "graph_hash": None, "nodes": []}
    return data if isinstance(data, dict) else {"schema_version": "1.0", "graph_hash": None, "nodes": []}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manage-build-lease.py",
        description="build 開始前安全性ゲート (lock 排他 + 孤児 lease 回収委譲 + graph_hash pin 検証)。",
    )
    p.add_argument("--lock-action", required=True,
                   choices=["acquire", "release", "force-release", "renew"])
    p.add_argument("--target-plugin-slug", default=None)
    p.add_argument("--cycle-id", default=None)
    p.add_argument("--task-state", default=None, help="省略時 resolve_build_dir(...)/task-state.json")
    p.add_argument("--task-graph", default=None, help="acquire 時の graph_hash pin/検証用")
    p.add_argument("--lock-path", default=None, help="省略時 resolve_build_dir(...)/.build.lock")
    p.add_argument("--owner-token", default=None,
                   help="acquire 出力の owner_token (renew/release で必須)")
    p.add_argument("--admin", action="store_true",
                   help="force-release を許可する明示 admin gate")
    p.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS,
                   help="task lease 秒数 (既定は C02 DEFAULT_LEASE_SECONDS を共有)")
    p.add_argument("--lock-ttl-seconds", type=int, default=None,
                   help="lock heartbeat 途絶判定 ttl (省略時 2×lease-seconds)")
    p.add_argument("--planner-scripts-dir", default=None,
                   help="producer derive/check スクリプトの所在 (省略時は既定 planner scripts dir)")
    return p


def _resolve_paths(args) -> tuple[Path, Path, Path, Path]:
    """(build_dir, state_path, events_path, lock_path) を導出する。

    build_dir 導出の優先順位: --task-state > --target-plugin-slug (resolve_build_dir) >
    --lock-path の親 (lock 単独操作 release/renew/force-release 用)。いずれも無ければ ValueError。
    """
    if args.task_state:
        state_path = Path(args.task_state)
        build_dir = state_path.parent
    elif args.target_plugin_slug:
        build_dir = Path(resolve_build_dir(args.target_plugin_slug, args.cycle_id))
        state_path = build_dir / "task-state.json"
    elif args.lock_path:
        build_dir = Path(args.lock_path).parent
        state_path = build_dir / "task-state.json"
    else:
        raise ValueError("--task-state / --target-plugin-slug / --lock-path のいずれかが必須")
    events_path = build_dir / "task-events.jsonl"
    lock_path = Path(args.lock_path) if args.lock_path else build_dir / LOCK_FILENAME
    return build_dir, state_path, events_path, lock_path


def _do_acquire(args, build_dir: Path, state_path: Path, events_path: Path, lock_path: Path) -> int:
    now = _utc_now()
    sync_script = Path(__file__).resolve().parent / "sync-task-state.py"
    planner_dir = Path(args.planner_scripts_dir) if args.planner_scripts_dir else _default_planner_scripts_dir()
    derive_script = planner_dir / "derive-task-graph.py"
    check_script = planner_dir / "check-task-state-schema.py"

    # (0) producer scripts preflight。欠落したまま lock を取ると pin 算出/検証が不能なまま
    # abort するため、lock 取得前に原因を明示して exit2 する。
    missing = [str(p) for p in (derive_script, check_script) if not p.is_file()]
    if missing:
        print(
            f"producer scripts 欠落 (planner-scripts-dir={planner_dir}): {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    # (1) build lock を排他取得。already-held なら fail-closed (exit1)。
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lease = acquire_lock(lock_path, now, args.lock_ttl_seconds)
    result = lease.state if isinstance(lease, LockLease) else lease
    if result == "already-held":
        existing = _read_lock(lock_path)
        lock_format = _lock_format(existing)
        payload = {"lock": "already-held", "lock_format": lock_format}
        if lock_format == "legacy":
            payload["remediation"] = (
                "legacy lock は生存中のため自動移行しない。owner の終了または TTL 失効を待つ。"
                "緊急時のみ人間が --lock-action force-release --admin を実行する"
            )
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    if not args.task_graph:
        release_lock(lock_path, lease)
        print("acquire には --task-graph が必須 (state 初期化 + graph_hash pin/検証)", file=sys.stderr)
        return 2

    # (2) graph の全 node を TG-C02 単一 writer で materialize。既存状態は保持し、
    # 不足 node だけ pending で追加してから lease 回収/pin parity へ進む。
    if _initialize_state(sync_script, state_path, events_path, args.task_graph) != 0:
        release_lock(lock_path, lease)
        print("task-state graph 初期化委譲失敗 (sync-task-state.py --initialize-from-graph)",
              file=sys.stderr)
        return 1

    # (3) 孤児 lease を検出し TG-C02 へ回収委譲 (TG-C07 自身は task-state を書かない)。
    state = _read_state(state_path)
    reaped: list[str] = []
    for tid in find_expired_leases(state, now):
        if _reap_lease(sync_script, state_path, events_path, tid) == 0:
            reaped.append(tid)
        else:
            print(f"warning: lease 回収委譲失敗 (task_id={tid})", file=sys.stderr)

    # (4) graph_hash pin: 未設定なら初回 pin・設定済みなら node-set 含め再照合。
    pinned = state.get("graph_hash")
    if pinned in (None, ""):
        graph_hash = _derive_graph_hash(derive_script, args.task_graph)
        if graph_hash is None:
            release_lock(lock_path, lease)
            print("graph_hash 算出失敗 (derive-task-graph.py)", file=sys.stderr)
            return 1
        if _pin_graph_hash(sync_script, state_path, events_path, graph_hash) != 0:
            release_lock(lock_path, lease)
            print("graph_hash 初回 pin 委譲失敗 (sync-task-state.py --pin-graph-hash)", file=sys.stderr)
            return 1
        graph_hash_pin = "pinned"
    else:
        if _verify_graph_hash_pin(check_script, state_path, args.task_graph):
            graph_hash_pin = "verified"
        else:
            # mismatch: 外ループ再入 (planner drain で graph 改善済み) か不正混入かを判別する。
            # 現 task-graph の hash が accepted discovered-task の resulting_graph_hash と一致すれば
            # 正当な再入として provenance-gated 再 pin する。一致しなければ fail-closed 拒否 (F10)。
            new_hash = _derive_graph_hash(derive_script, args.task_graph)
            authorized = _scan_authorized_hashes(build_dir / "discovered-tasks")
            if new_hash is not None and new_hash in authorized:
                if _repin_graph_hash(sync_script, state_path, events_path, new_hash, authorized) != 0:
                    release_lock(lock_path, lease)
                    print("graph_hash 再 pin 委譲失敗 (sync-task-state.py --repin-graph-hash)", file=sys.stderr)
                    return 1
                graph_hash_pin = "repinned"  # 外ループ再入: 改善済み graph を新 pin で再消費
            else:
                release_lock(lock_path, lease)
                print(json.dumps({"graph_hash_pin": "mismatch"}, ensure_ascii=False))
                return 1

    # (5) 全成功。lock は build 完了まで維持し dispatcher の明示 release まで解放しない。
    print(json.dumps(
        {"lock": result, "owner_token": lease.owner_token,
         "reaped_task_ids": reaped, "graph_hash_pin": graph_hash_pin},
        ensure_ascii=False,
    ))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    # lock-ttl 既定 = 2×lease (heartbeat 2 周期の途絶で孤児判定)。明示指定はそのまま優先。
    if args.lock_ttl_seconds is None:
        args.lock_ttl_seconds = 2 * args.lease_seconds

    try:
        build_dir, state_path, events_path, lock_path = _resolve_paths(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    action = args.lock_action
    if action == "release":
        status = release_lock(lock_path, args.owner_token)
        print(json.dumps({"lock": status}, ensure_ascii=False))
        return 0 if status in ("released", "lost") else 1
    if action == "force-release":
        if not args.admin:
            print("force-release は --admin 明示時のみ許可", file=sys.stderr)
            return 2
        status = force_release_lock(lock_path)
        print(json.dumps({"lock": status}, ensure_ascii=False))
        return 0 if status in ("released", "lost") else 1
    if action == "renew":
        status = renew_lock(lock_path, _utc_now(), args.owner_token)
        print(json.dumps({"lock": status}, ensure_ascii=False))
        return 0 if status == "renewed" else 1
    # action == "acquire"
    return _do_acquire(args, build_dir, state_path, events_path, lock_path)


if __name__ == "__main__":
    sys.exit(main())
