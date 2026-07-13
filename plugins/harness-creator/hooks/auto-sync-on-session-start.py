#!/usr/bin/env python3
# /// script
# name: auto-sync-on-session-start
# purpose: C05 SessionStart lifecycle hook。install/enable/trust 済み後の新セッション開始時に、C01 sync-native-surfaces.py --apply --json を一度だけ呼び、repo-owned projection の drift だけを安全に修復する薄い hook。毎回の全量書込みや user global config mutation は行わない。reentrancy guard・process lock・content-hash no-op (C01 委譲)・timeout を必須とし、child failure を成功へ畳まず structured warning + 永続ログに remediation 付きで残す。session continuation を絶対に壊さないため常に exit 0。
# inputs:
#   - stdin: Claude/Codex SessionStart payload JSON (session_id/source/cwd 等・空/不正でも堅牢に既定へ)
#   - env: CLAUDE_PROJECT_DIR (repo root 解決)
#   - argv: [--repo-root PATH] [--c01-script PATH] [--timeout SEC] [--debounce SEC] [--lock-path PATH] [--guard-path PATH] [--log-path PATH]
# outputs:
#   - stdout: 公式 SessionStart hook JSON fields のみ (continue/suppressOutput/systemMessage/hookSpecificOutput)。warning 時のみ要約と remediation を出し、child report は出さない。
#   - write: harness repo identity 確認後の hook local のみ (.build/locks/auto-sync-on-session-start.lock / .build/state/auto-sync-on-session-start.json / .build/logs/auto-sync-on-session-start.jsonl)。managed native surface の実書込は C01 --apply へ委譲する。
#   - exit: 常に 0。内部 status = success|noop|skipped_not_installed|skipped_wrong_repository|warning_drift|warning_conflict|warning_invalid|warning_timeout。
# contexts: [C, E]
# network: false
# write-scope: .build/locks/auto-sync-on-session-start.lock / .build/state/auto-sync-on-session-start.json / .build/logs/auto-sync-on-session-start.jsonl (hook local log/lock/state)。managed projection は C01 sync-native-surfaces.py --apply へ委譲。user global config (~/.claude ~/.codex)・plugin trust store・.agents/skills(/beads)・.agents/{agents,commands,hooks}・.claude・.codex・.git へは hook 自身は一切書かない。
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C05 auto-sync-on-session-start — 薄い SessionStart lifecycle hook。

役割 (component-inventory C05 / P02 契約):

- ユーザーが install/enable/trust を完了した後の新セッション開始時に、
  ``sync-native-surfaces.py`` (C01) を ``--apply --json`` で **一度だけ** 呼び、
  repo-owned projection の drift だけを安全に修復する。C01 は fingerprint 差分時のみ
  atomic replace で書くため、hook 側は「content hash no-op」を C01 に委譲する。
- **session continuation を絶対に壊さない**: プロセスは常に exit 0。内部 status を
  ``success|noop|skipped_not_installed|skipped_wrong_repository|warning_drift|
  warning_conflict|warning_invalid|warning_timeout`` として保持し、C01 の
  exit 0/1/2/3 と timeout をこの status へ写像する。
- **failure を session へ伝播しない**: どの警告状態でも stdout の statusMessage
  (systemMessage) と structured local log に remediation 付きで残し、success へ畳まない。
- **reentrancy / lock**: 同一セッションの二重発火 (startup→resume→clear) を debounce guard で、
  並行 SessionStart を hook-local process lock で抑止する。いずれも noop で早期 return (exit 0)。
- **write 境界**: harness repo identity を確認するまで書込 0。確認後も hook 自身は
  ``.build`` 配下の log/lock/state のみ。managed native surface の実書込は C01 に
  委譲し、global config・trust store・.agents/skills/beads は触らない。

plugin-root script のため cross-plugin import は行わず Python 標準ライブラリのみで自己完結する。
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 定数 ───────────────────────────────────────────────────────────
HOOK_NAME = "auto-sync-on-session-start"
HOOK_EVENT = "SessionStart"

LOCK_REL = (".build", "locks", "auto-sync-on-session-start.lock")
GUARD_REL = (".build", "state", "auto-sync-on-session-start.json")
LOG_REL = (".build", "logs", "auto-sync-on-session-start.jsonl")

DEFAULT_TIMEOUT = 45.0      # C01 subprocess の最大待機秒 (hook budget 内)
DEFAULT_DEBOUNCE = 900.0    # 同一 session の再発火を無視する窓 (秒)
DEFAULT_LOCK_TTL = 300.0    # 孤児 lock を stale とみなす経過秒
DEFAULT_RETENTION = 86400.0 # guard に残す session id の保持秒
MAX_CHILD_DIAGNOSTIC_CHARS = 4096  # log/stdout へ載せる child diagnostic の上限
MAX_CHILD_REPORT_CHARS = 8192      # parsed child report の JSON 表現上限
MAX_LOG_BYTES = 1024 * 1024        # active JSONL の最大 size (1 MiB)
MAX_LOG_AGE_SECONDS = 7 * 86400.0  # active JSONL の最大 age (7 days)
MAX_LOG_BACKUPS = 3                # .1 .. .3 の bounded rotation

# 内部 status 集合 (SSOT)。
STATUS_SUCCESS = "success"
STATUS_NOOP = "noop"
STATUS_SKIPPED = "skipped_not_installed"
STATUS_WRONG_REPO = "skipped_wrong_repository"
STATUS_DRIFT = "warning_drift"
STATUS_CONFLICT = "warning_conflict"
STATUS_INVALID = "warning_invalid"
STATUS_TIMEOUT = "warning_timeout"

ALL_STATUSES = frozenset(
    {STATUS_SUCCESS, STATUS_NOOP, STATUS_SKIPPED, STATUS_WRONG_REPO, STATUS_DRIFT,
     STATUS_CONFLICT, STATUS_INVALID, STATUS_TIMEOUT}
)
WARNING_STATUSES = frozenset({STATUS_DRIFT, STATUS_CONFLICT, STATUS_INVALID, STATUS_TIMEOUT})

STATUS_REASON = {
    STATUS_SUCCESS: "C01 applied repo-owned projection updates",
    STATUS_NOOP: "no drift; repo-owned projection already current",
    STATUS_SKIPPED: "C01 orchestrator not installed; nothing to sync",
    STATUS_WRONG_REPO: "resolved cwd is not the harness repository; nothing to sync",
    STATUS_DRIFT: "C01 reported drift (exit 1)",
    STATUS_CONFLICT: "C01 reported conflict (exit 2)",
    STATUS_INVALID: "C01 reported invalid layout/contract/parse (exit 3)",
    STATUS_TIMEOUT: "C01 sync timed out",
}

# write 境界: hook 自身が書いてよいのは .build 配下のみ (それ以外は default-deny)。
HOOK_ALLOWED_PREFIX = ".build"
HARNESS_MANIFEST_REL = ("plugins", "harness-creator", ".claude-plugin", "plugin.json")
HARNESS_C01_REL = ("plugins", "harness-creator", "scripts", "sync-native-surfaces.py")

_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"']?\b(?:token|secret|password|passwd|api[_-]?key)\b[\"']?\s*[:=]\s*)"
    r"([\"']?)([^\"'\s,;]+)\2"
)
_AUTHORIZATION_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)[^\r\n,;]+")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SENSITIVE_KEYS = frozenset({"token", "secret", "password", "passwd", "apikey", "authorization"})


# ─────────────────── 時刻ユーティリティ ───────────────────
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("not a string timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _safe_json(text: object):
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


# ─────────────────── write 境界判定 (hook local) ───────────────────
def is_hook_write_allowed(repo_root: Path, target: Path) -> bool:
    """target が hook-local write-scope (``.build`` 配下) かを判定する。

    managed native surface (.claude 等) の書込は C01 へ委譲するため、hook 自身は
    ``.build`` 配下の log/lock/state 以外へは絶対に書かない (default-deny)。repo 外・
    絶対 path (home 配下の global config 含む) は常に拒否。
    """
    repo_root = Path(repo_root).resolve()
    try:
        rel = Path(target).resolve().relative_to(repo_root)
    except ValueError:
        return False  # repo 外 (~/.claude ~/.codex・絶対 path 含む)
    rel_str = rel.as_posix()
    if rel_str in (".", ""):
        return False
    return rel_str == HOOK_ALLOWED_PREFIX or rel_str.startswith(HOOK_ALLOWED_PREFIX + "/")


def _bounded_diagnostic(value: object) -> str:
    """Child diagnostic を構造化証跡へ載せる前に有限長へ制限する。"""
    text = value if isinstance(value, str) else ""
    if len(text) <= MAX_CHILD_DIAGNOSTIC_CHARS:
        return text
    return text[:MAX_CHILD_DIAGNOSTIC_CHARS] + "...[truncated]"


def _bounded_child_report(value: object) -> object:
    """Parsed child JSON を上限内に保つ。大きい report は bounded preview へ縮退する。"""
    report = _safe_json(value)
    if report is None:
        return None
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if len(serialized) <= MAX_CHILD_REPORT_CHARS:
        return report
    return {
        "truncated": True,
        "original_chars": len(serialized),
        "preview": serialized[:MAX_CHILD_REPORT_CHARS] + "...[truncated]",
    }


def _redact_text(value: str) -> str:
    text = _SENSITIVE_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}<redacted>", value)
    text = _AUTHORIZATION_RE.sub(lambda m: f"{m.group(1)}<redacted>", text)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    return text


def _sanitize_log_value(value: object, *, key: str = "") -> object:
    """Local log のみに適用する redaction/bounding。stdout には詳細を出さない。"""
    if key in {"session_id", "sessionId"} and isinstance(value, str) and value:
        digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]
        return f"sha256:{digest}"
    normalized_key = re.sub(r"[^a-z]", "", key.lower())
    if normalized_key in _SENSITIVE_KEYS and value not in (None, ""):
        return "<redacted>"
    if isinstance(value, str):
        return _bounded_diagnostic(_redact_text(value))
    if isinstance(value, dict):
        return {
            str(k): _sanitize_log_value(v, key=str(k))
            for k, v in list(value.items())[:64]
        }
    if isinstance(value, list):
        return [_sanitize_log_value(v) for v in value[:64]]
    return value


def is_harness_repository(repo_root: Path) -> bool:
    """Target root が harness source checkout であることを 2 markers で fail-closed 確認する。"""
    root = Path(repo_root).resolve()
    manifest = root.joinpath(*HARNESS_MANIFEST_REL)
    c01 = root.joinpath(*HARNESS_C01_REL)
    if not manifest.is_file() or not c01.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("name") == "harness-creator"


# ─────────────────── atomic write / append ───────────────────
def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _rotate_log(log_path: Path, incoming_bytes: int, *, now: datetime,
                max_bytes: int, max_age: float, max_backups: int) -> None:
    if not log_path.exists():
        return
    stat = log_path.stat()
    too_large = stat.st_size + incoming_bytes > max_bytes
    too_old = now.timestamp() - stat.st_mtime > max_age
    if not (too_large or too_old):
        return
    for index in range(max_backups, 0, -1):
        current = log_path.with_name(log_path.name + f".{index}")
        if index == max_backups:
            try:
                current.unlink()
            except FileNotFoundError:
                pass
        else:
            older = log_path.with_name(log_path.name + f".{index + 1}")
            if current.exists():
                os.replace(current, older)
    os.replace(log_path, log_path.with_name(log_path.name + ".1"))


def append_log(log_path: Path, record: dict, *, now: datetime | None = None,
               max_bytes: int = MAX_LOG_BYTES, max_age: float = MAX_LOG_AGE_SECONDS,
               max_backups: int = MAX_LOG_BACKUPS) -> None:
    """Redacted/bounded JSONL を追記し size/age で bounded rotation する (fail-soft)。"""
    try:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        safe_record = _sanitize_log_value(record)
        line = json.dumps(safe_record, ensure_ascii=False) + "\n"
        _rotate_log(
            log_path,
            len(line.encode("utf-8")),
            now=now or _now_utc(),
            max_bytes=max_bytes,
            max_age=max_age,
            max_backups=max_backups,
        )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


# ─────────────────── pid 生存 / lock stale ───────────────────
def pid_alive(pid: object) -> bool:
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


def _read_lock(lock_path: Path) -> dict | None:
    return _decode_lock(_read_lock_bytes(lock_path))


def lock_is_stale(existing: dict | None, now: datetime, ttl: float) -> bool:
    """既存 lock が孤児 (回収可) かを判定する。破損/期限切れ/死んだ pid を stale とみなす。"""
    if not isinstance(existing, dict):
        return True
    try:
        age = (now - _parse_iso(existing.get("started_at"))).total_seconds()
    except (TypeError, ValueError):
        return True
    if age > ttl:
        return True
    if existing.get("host") == socket.gethostname() and not pid_alive(existing.get("pid")):
        return True
    return False


def _lock_payload(now: datetime, getpid, owner_token: str | None = None, host=None) -> dict:
    return {
        "started_at": _iso(now),
        "pid": getpid(),
        "host": host or socket.gethostname(),
        "owner_token": owner_token or secrets.token_hex(16),
    }


class LockLease:
    def __init__(self, state: str, owner_token: str):
        self.state = state
        self.owner_token = owner_token

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.state == other
        if isinstance(other, LockLease):
            return (self.state, self.owner_token) == (other.state, other.owner_token)
        return False

    def __repr__(self) -> str:
        return f"LockLease(state={self.state!r}, owner_token=<redacted>)"


def _compare_delete(lock_path: Path, expected: bytes) -> bool:
    fd = None
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


def acquire_lock(lock_path: Path, *, lock_ttl: float, now: datetime, getpid, host=None) -> LockLease | None:
    """hook-local process lock を O_CREAT|O_EXCL で 1 度だけ取得する (SessionStart は待たない)。

    戻り値: ``acquired`` (新規) / ``stolen`` (孤児回収) / ``None`` (生存 lock 保持中→noop)。
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    owner_token = secrets.token_hex(16)
    state = "acquired"
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            snapshot = _read_lock_bytes(lock_path)
            existing = _decode_lock(snapshot)
            if not lock_is_stale(existing, now, lock_ttl):
                return None
            if snapshot is not None and _compare_delete(lock_path, snapshot):
                state = "stolen"
            # Whether we deleted or lost the race, retry via O_EXCL. Never
            # overwrite a path another contender may have just acquired.
            continue
        payload = json.dumps(
            _lock_payload(now, getpid, owner_token, host=host), ensure_ascii=False
        ) + "\n"
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            continue
        try:
            opened = os.fstat(fd)
            current = os.stat(lock_path)
        except FileNotFoundError:
            os.close(fd)
            continue
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            os.close(fd)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
        return LockLease(state, owner_token)


def release_lock(lock_path: Path, lease: LockLease | str | None) -> bool:
    token = lease.owner_token if isinstance(lease, LockLease) else lease
    if not isinstance(token, str) or not token:
        return False
    snapshot = _read_lock_bytes(lock_path)
    existing = _decode_lock(snapshot)
    if snapshot is None or not isinstance(existing, dict) or existing.get("owner_token") != token:
        return False
    return _compare_delete(lock_path, snapshot)


# ─────────────────── reentrancy guard (session debounce) ───────────────────
def read_guard(guard_path: Path) -> dict:
    try:
        data = json.loads(Path(guard_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def guard_recently_ran(guard: dict, session_id: str, now: datetime, window: float) -> bool:
    """session_id が debounce 窓内に既に sync 済みかを判定する (二重発火の抑止)。"""
    if not session_id or not isinstance(guard, dict):
        return False
    ts = guard.get(session_id)
    try:
        prev = _parse_iso(ts)
    except (TypeError, ValueError):
        return False
    return (now - prev).total_seconds() < window


def write_guard(guard_path: Path, guard: dict, session_id: str, now: datetime, *, retention: float) -> None:
    """guard に session_id=now を記録し、retention 超過の古い entry を prune する (fail-soft)。"""
    if not session_id:
        return
    try:
        merged = dict(guard) if isinstance(guard, dict) else {}
        merged[session_id] = _iso(now)
        pruned = {}
        for sid, ts in merged.items():
            try:
                if (now - _parse_iso(ts)).total_seconds() <= retention:
                    pruned[sid] = ts
            except (TypeError, ValueError):
                continue
        _atomic_write_text(guard_path, json.dumps(pruned, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


# ─────────────────── payload 解釈 ───────────────────
def parse_payload(raw: object) -> dict:
    """stdin raw を SessionStart payload dict へ (空/不正/非 dict は {} へ堅牢に既定)。"""
    data = _safe_json(raw if isinstance(raw, str) else "")
    return data if isinstance(data, dict) else {}


def session_id(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("session_id", "sessionId"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def session_source(payload: dict) -> str:
    if isinstance(payload, dict):
        v = payload.get("source")
        if isinstance(v, str) and v:
            return v
    return "unknown"


def resolve_repo_root(payload: dict, argv_root: str | None = None, env: dict | None = None) -> Path:
    """repo root を argv > env CLAUDE_PROJECT_DIR > payload cwd > 現在 cwd の順で解決する。"""
    env = env if env is not None else os.environ
    if argv_root:
        return Path(argv_root).resolve()
    cpd = env.get("CLAUDE_PROJECT_DIR")
    if cpd:
        return Path(cpd).resolve()
    if isinstance(payload, dict):
        for key in ("cwd", "project_dir", "projectDir", "workspace_root", "workspaceRoot"):
            v = payload.get(key)
            if isinstance(v, str) and v:
                return Path(v).resolve()
    return Path.cwd()


# ─────────────────── C01 subprocess 委譲 (monkeypatch 点) ───────────────────
def _run_c01(argv: list[str], timeout: float) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _default_c01_script() -> Path:
    """hook の兄弟 scripts/ 配下の C01 orchestrator を既定 path とする (repo_root 非依存)。"""
    return Path(__file__).resolve().parent.parent / "scripts" / "sync-native-surfaces.py"


def _c01_verdict(stdout: str) -> str | None:
    report = _safe_json(stdout)
    if isinstance(report, dict):
        v = report.get("verdict")
        if isinstance(v, str):
            return v
    return None


def invoke_c01(repo_root: Path, c01_script: Path, *, timeout: float, runner=None) -> dict:
    """C01 を ``--apply --json`` で 1 回だけ呼ぶ。不在は present=False、timeout は timed_out。"""
    c01_script = Path(c01_script)
    if not c01_script.is_file():
        return {"present": False, "returncode": None, "stdout": "", "stderr": "",
                "timed_out": False, "verdict": None}
    runner = runner if runner is not None else _run_c01
    argv = [sys.executable, str(c01_script), "--repo-root", str(repo_root), "--apply", "--json"]
    try:
        rc, out, err = runner(argv, timeout)
    except subprocess.TimeoutExpired:
        return {"present": True, "returncode": None, "stdout": "", "stderr": "",
                "timed_out": True, "verdict": None}
    return {"present": True, "returncode": rc, "stdout": out, "stderr": err,
            "timed_out": False, "verdict": _c01_verdict(out)}


# ─────────────────── C01 exit → 内部 status 写像 ───────────────────
def _classify_exit0(stdout: str) -> str:
    """C01 exit 0 を verdict/adapters に応じ success/noop/skipped_not_installed へ分ける。"""
    report = _safe_json(stdout)
    adapters = report.get("adapters") if isinstance(report, dict) else None
    if not isinstance(adapters, list) or not adapters:
        return STATUS_NOOP  # 判別材料なし → 無害な noop へ倒す
    dicts = [a for a in adapters if isinstance(a, dict)]
    statuses = [a.get("status") for a in dicts]
    if statuses and all(s == "skipped_not_installed" for s in statuses):
        return STATUS_SKIPPED
    changed = 0
    for a in dicts:
        try:
            changed += int(a.get("changed", 0) or 0)
        except (TypeError, ValueError):
            pass
    if changed > 0 or any(a.get("status") == "synced" for a in dicts):
        return STATUS_SUCCESS
    return STATUS_NOOP


def classify_c01(result: dict) -> str:
    """invoke_c01 の結果を内部 status へ写す (絶対に exit 0 側を壊さない)。"""
    if not result.get("present"):
        return STATUS_SKIPPED
    if result.get("timed_out"):
        return STATUS_TIMEOUT
    rc = result.get("returncode")
    if rc == 0:
        return _classify_exit0(result.get("stdout", ""))
    if rc == 1:
        return STATUS_DRIFT
    if rc == 2:
        return STATUS_CONFLICT
    if rc == 3:
        return STATUS_INVALID
    return STATUS_INVALID  # 未知 exit (負/>3/None) も invalid へ写す


def _apply_cmd(repo_root: Path) -> str:
    return (
        f"python3 plugins/harness-creator/scripts/sync-native-surfaces.py "
        f"--repo-root {repo_root} --apply"
    )


def status_warning_remediation(status: str, repo_root: Path) -> tuple[str | None, str | None]:
    """status に応じた warning 文言と remediation コマンドを返す (非 warning は (None, None))。"""
    if status == STATUS_DRIFT:
        return ("C01 が repo-owned projection の drift を報告した (未修復の可能性)",
                _apply_cmd(repo_root))
    if status == STATUS_CONFLICT:
        return ("C01 が name/hook/permission conflict を報告した (書込は fail-closed)",
                "report の conflict を解消してから C01 --apply を再実行する: " + _apply_cmd(repo_root))
    if status == STATUS_INVALID:
        return ("C01 が invalid layout/contract/parse を報告した",
                "invalid layout/contract を C01 stderr の指示で修正し再実行する: " + _apply_cmd(repo_root))
    if status == STATUS_TIMEOUT:
        return ("C01 sync が timeout した (未完了)",
                "lock 競合や重い I/O を確認し手動再実行する: " + _apply_cmd(repo_root))
    return (None, None)


# ─────────────────── run_hook (core・全 injectable) ───────────────────
def run_hook(
    payload: dict,
    *,
    repo_root: Path,
    c01_script: Path,
    lock_path: Path | None = None,
    guard_path: Path | None = None,
    log_path: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    debounce: float = DEFAULT_DEBOUNCE,
    lock_ttl: float = DEFAULT_LOCK_TTL,
    retention: float = DEFAULT_RETENTION,
    runner=None,
    now: datetime | None = None,
    getpid=None,
    host=None,
) -> dict:
    """SessionStart の 1 実行を成す。戻り値は structured result (main が stdout へ写す)。

    プロセスを絶対に壊さないため、内部で例外が起きても warning_invalid の result を返す。
    """
    repo_root = Path(repo_root)
    now = now if now is not None else _now_utc()
    getpid = getpid if getpid is not None else os.getpid
    lock_path = Path(lock_path) if lock_path else repo_root.joinpath(*LOCK_REL)
    guard_path = Path(guard_path) if guard_path else repo_root.joinpath(*GUARD_REL)
    log_path = Path(log_path) if log_path else repo_root.joinpath(*LOG_REL)

    payload = payload if isinstance(payload, dict) else {}
    sid = session_id(payload)
    source = session_source(payload)

    # Target repository identity は .build の parent mkdir/lock/log より前に検査する。
    # Plugin hook は他 repo でも発火し得るため、wrong repo は完全 no-write で終了する。
    if not is_harness_repository(repo_root):
        return {
            "hook": HOOK_NAME,
            "event": HOOK_EVENT,
            "status": STATUS_WRONG_REPO,
            "warning": None,
            "remediation": None,
            "source": source,
            "session_id": sid,
            "reason": STATUS_REASON[STATUS_WRONG_REPO],
            "c01": {"present": None, "returncode": None, "timed_out": False,
                    "verdict": None, "child_report": None, "stdout": "", "stderr": ""},
            "lock": None,
            "timestamp": _iso(now),
            "log_path": "",
        }

    # CLI で path を上書きされても hook 自身の write scope は repo/.build から広げない。
    # invalid path の警告ログは既定の安全な .build/logs path にのみ残す。
    invalid_write_paths = [
        p for p in (lock_path, guard_path, log_path)
        if not is_hook_write_allowed(repo_root, p)
    ]
    if invalid_write_paths:
        safe_log_path = repo_root.joinpath(*LOG_REL)
        result = {
            "hook": HOOK_NAME,
            "event": HOOK_EVENT,
            "status": STATUS_INVALID,
            "warning": "hook local path が許可済み repo/.build scope 外を指している",
            "remediation": "--lock-path/--guard-path/--log-path を repo/.build 配下へ戻す",
            "source": source,
            "session_id": sid,
            "reason": "forbidden hook-local write path",
            "c01": {"present": None, "returncode": None, "timed_out": False,
                    "verdict": None, "stderr": ""},
            "lock": None,
            "timestamp": _iso(now),
            "log_path": safe_log_path.as_posix(),
        }
        append_log(safe_log_path, result, now=now)
        return result

    def _finish(status: str, *, reason: str, lock=None, c01=None) -> dict:
        warning, remediation = status_warning_remediation(status, repo_root)
        result = {
            "hook": HOOK_NAME,
            "event": HOOK_EVENT,
            "status": status,
            "warning": warning,
            "remediation": remediation,
            "source": source,
            "session_id": sid,
            "reason": reason,
            "c01": c01 or {"present": None, "returncode": None, "timed_out": False,
                            "verdict": None, "stderr": ""},
            "lock": lock,
            "timestamp": _iso(now),
            "log_path": log_path.as_posix(),
        }
        append_log(log_path, result, now=now)
        return result

    # 1) reentrancy: 同一 session の debounce 窓内なら noop で早期 return。
    guard = read_guard(guard_path)
    if guard_recently_ran(guard, sid, now, debounce):
        return _finish(STATUS_NOOP, reason="reentrancy: session already synced within debounce window")

    # 2) concurrency lock: 生存 lock 保持中なら noop (待たない)。
    try:
        lock_lease = acquire_lock(lock_path, lock_ttl=lock_ttl, now=now, getpid=getpid, host=host)
    except OSError as exc:
        return _finish(
            STATUS_INVALID,
            reason=f"lock filesystem error: {exc}",
            lock="filesystem_error",
        )
    if lock_lease is None:
        return _finish(STATUS_NOOP, reason="reentrancy: another sync holds the lock", lock="held")

    try:
        c01_result = invoke_c01(repo_root, c01_script, timeout=timeout, runner=runner)
        status = classify_c01(c01_result)
        c01_meta = {
            "present": c01_result.get("present"),
            "returncode": c01_result.get("returncode"),
            "timed_out": c01_result.get("timed_out"),
            "verdict": c01_result.get("verdict"),
            "child_report": _bounded_child_report(c01_result.get("stdout", "")),
            "stdout": _bounded_diagnostic(c01_result.get("stdout", "")),
            "stderr": _bounded_diagnostic(c01_result.get("stderr", "")),
        }
        # C01 が実際に呼べた場合のみ debounce guard を記録 (未 install は次回 retry を許す)。
        if status != STATUS_SKIPPED:
            write_guard(guard_path, guard, sid, now, retention=retention)
        return _finish(status, reason=STATUS_REASON.get(status, status), lock=lock_lease.state, c01=c01_meta)
    except Exception as exc:  # noqa: BLE001 — fail-soft: 例外を session へ伝播しない
        return _finish(
            STATUS_INVALID,
            reason=f"hook internal error during C01 invocation: {exc}",
            lock=lock_lease.state,
            c01={"present": None, "returncode": None, "timed_out": False,
                 "verdict": None, "stderr": ""},
        )
    finally:
        release_lock(lock_path, lock_lease)


# ─────────────────── stdout hook output ───────────────────
def build_hook_output(result: dict) -> dict:
    """result を Claude/Codex SessionStart hook JSON へ整形する。

    - warning 状態のみ ``systemMessage`` と ``hookSpecificOutput.additionalContext``
      (remediation 付き) を出す。success/noop/skipped は ``suppressOutput`` で無音。
    - structured child detail は bounded/redacted local JSONL にのみ残し、stdout は
      公式 SessionStart fields のみとする。
    """
    status = result.get("status", STATUS_NOOP)
    warning = result.get("warning")
    has_warning = warning is not None
    out: dict = {
        "continue": True,
        "suppressOutput": not has_warning,
        "hookSpecificOutput": {"hookEventName": HOOK_EVENT},
    }
    if has_warning:
        remediation = result.get("remediation")
        out["systemMessage"] = f"harness-creator auto-sync: {status}: {warning}"
        ctx = (
            f"harness-creator auto-sync 警告 ({status}): {warning}\n"
            f"remediation: {remediation}\n"
            f"log: {result.get('log_path')}"
        )
        out["hookSpecificOutput"]["additionalContext"] = ctx
    return out


# ─────────────────── stdin / CLI ───────────────────
def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:  # noqa: BLE001
        return ""


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=f"{HOOK_NAME}.py", description="C05 SessionStart auto-sync hook。")
    ap.add_argument("--repo-root", default=None, help="repo ルート (既定は env/payload/cwd から解決)")
    ap.add_argument("--c01-script", default=None, help="sync-native-surfaces.py path (既定は兄弟 scripts/)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="C01 subprocess timeout 秒")
    ap.add_argument("--debounce", type=float, default=DEFAULT_DEBOUNCE, help="同一 session 再発火 debounce 秒")
    ap.add_argument("--lock-path", default=None, help="hook lock file path")
    ap.add_argument("--guard-path", default=None, help="reentrancy guard state file path")
    ap.add_argument("--log-path", default=None, help="structured local log (JSONL) path")
    return ap


def main(argv: list[str] | None = None, stdin: str | None = None) -> int:
    """SessionStart hook entrypoint。session continuation を壊さないため常に 0 を返す。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit:
        # argparse の usage error でも session を止めない。
        args = _build_parser().parse_args([])

    raw = stdin if stdin is not None else _read_stdin()
    payload = parse_payload(raw)
    repo_root = resolve_repo_root(payload, args.repo_root)
    c01_script = Path(args.c01_script) if args.c01_script else _default_c01_script()

    try:
        result = run_hook(
            payload,
            repo_root=repo_root,
            c01_script=c01_script,
            lock_path=args.lock_path,
            guard_path=args.guard_path,
            log_path=args.log_path,
            timeout=args.timeout,
            debounce=args.debounce,
        )
    except Exception as exc:  # noqa: BLE001 — 最終防波堤: 何があっても exit 0。
        result = {
            "hook": HOOK_NAME, "event": HOOK_EVENT, "status": STATUS_INVALID,
            "warning": "hook fatal error", "remediation": None,
            "source": session_source(payload), "session_id": session_id(payload),
            "reason": f"fatal: {exc}", "c01": {"present": None, "returncode": None,
            "timed_out": False, "verdict": None, "stderr": ""}, "lock": None,
            "timestamp": _iso(_now_utc()), "log_path": "",
        }

    try:
        sys.stdout.write(json.dumps(build_hook_output(result), ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
