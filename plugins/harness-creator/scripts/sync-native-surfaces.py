#!/usr/bin/env python3
# /// script
# name: sync-native-surfaces
# purpose: C01 build/update 時の単一 orchestrator。Claude symlink/settings、Codex project settings、Codex parity の4 adaptersを common native-surfaces.toml と activation scope から apply/check する。
# inputs:
#   - argv: --repo-root PATH [--apply|--check|--dry-run] [--json] [--lock-timeout SEC]
#           [--plugin-slug SLUG] [--surface-contract PATH] [--plan-dir PATH]
#           [--symlinks-script PATH] [--settings-script PATH] [--codex-parity-script PATH]
#           [--lock-path PATH] [--lock-ttl SEC]
# outputs:
#   - stdout: 人間可読サマリ (既定) / JSON (--json)。各 adapter の status/changed/skipped_reason/warning/remediation、activation scope、verdict、exit_code。
#   - write: repo-owned managed projection のみ (.claude/{skills,agents,commands} symlink・.claude/settings.json managed 領域を委譲 generator 経由、owner=repo と宣言された Codex manifest/marketplace file)。--check/--dry-run は無書込。
#   - exit: 0=success/noop/skipped_not_installed / 1=drift / 2=conflict・lock timeout / 3=parse・invalid layout (重い順に評価: 3>2>1>0)。
# contexts: [C, E]
# network: false
# write-scope: .claude managed projection / .codex/hooks.json / .codex/config.toml / .build lock。Codex project filesは native-surfaces.toml の固定 exact pathsだけを child adapterが非破壊反映する。user global config・.agents tool-owned namespaces・その他 .codex は read-only。
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C01 native surface 同期 orchestrator。

build/update の単一エントリとして 4 adapter を合成する:

- ``claude_symlinks`` : ``scripts/build-claude-symlinks.py`` へ ``--check``/apply を委譲し
  ``.claude/{skills,agents,commands}`` の symlink projection を同期する。
- ``claude_settings`` : ``scripts/build-claude-settings.py`` へ委譲し ``.claude/settings.json``
  の managed 領域 (hooks/permissions) を反映する。
- ``codex_project_settings`` : common ``native-surfaces.toml`` から ``.codex/hooks.json``
  と ``.codex/config.toml`` の repo-owned managed 部分を非破壊 apply/check する。
- ``codex_parity``    : C02 ``check-native-surface-parity.py`` を read-only 呼び出しし、
  dual manifest・repo marketplace・plugin hook trust 前提の parity を検査する。

契約 (native-surface-contract.md / P02 / P05):

- **activation evidence**: Claude は repo 正本 ``.claude-plugin/marketplace.json`` の name と
  ``.claude/settings.json`` の ``enabledPlugins`` を突合し、``plugin@marketplace`` 完全 identity が
  true の installed plugin のみ managed source とし、それ以外は skipped と明示する。Codex の
  enabled/trust は repo-owned file からは検証できないため ``not_verified`` と明示する
  (全 ``plugins/*`` の無条件 apply は禁止)。symlink surface は ``--exclude-plugin`` で scope 外
  plugin を除外し、settings reflector にも同じ repeatable ``--exclude-plugin`` を渡す。
  activation state を parse できない場合は全 plugin 投影に fallback せず invalid で fail-closed する。
- **write policy**: ``--apply`` は fingerprint 差分がある surface のみ書く (check→drift 時のみ
  apply へ進む no-op ゲート)。書込は atomic replace。書込先は write-scope の allowlist 内に限定し、
  それ以外 (user global config・tool-owned namespace・unsupported kind) へは絶対に書かない。
- **failure taxonomy**: generator 不在のみ ``skipped_not_installed`` (exit 0 側)。
  drift=1 / conflict・lock timeout=2 / parse・invalid layout=3。drift/conflict/parse/race/timeout を
  success へ畳まない。exit code は最も重い severity を返す (3>2>1>0)。

plugin-root script のため cross-plugin import は行わず Python 標準ライブラリのみで自己完結する。
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── severity 定数 (= exit code の重み) ─────────────────────────────
SEV_OK = 0
SEV_DRIFT = 1
SEV_CONFLICT = 2
SEV_INVALID = 3

# ── 既定値 ─────────────────────────────────────────────────────────
DEFAULT_PLUGIN_SLUG = "harness-creator"
DEFAULT_PLAN_SUBDIR = ("plugin-plans", "harness-creator-hook-agents-sync")
DEFAULT_LOCK_TIMEOUT = 30.0
DEFAULT_LOCK_TTL = 3600.0
MAX_CHILD_DIAGNOSTIC_CHARS = 4096
MAX_CHILD_REPORT_CHARS = 16384
MAX_CHILD_VIOLATIONS = 100
LOCK_REL = (".build", "locks", "sync-native-surfaces.lock")

# ── write-scope allowlist / denylist (repo-root 相対 posix) ───────────
# 明示 allow に一致しない書込は既定拒否 (default-deny)。forbidden は allow へ将来展開しても
# 破れないよう先に評価する多層防御 (~/.codex ~/.claude・.agents/skills(/beads)・.agents/{agents,
# commands,hooks}・project .codex hook owner・.git 等は read-only)。
FORBIDDEN_PREFIXES = (
    ".agents/skills",
    ".agents/agents",
    ".agents/commands",
    ".agents/hooks",
    ".git",
)
ALLOWED_DIR_PREFIXES = (
    ".claude/skills",
    ".claude/agents",
    ".claude/commands",
    ".build",
)
ALLOWED_EXACT = (
    ".claude/settings.json",
    ".codex/hooks.json",
    ".codex/config.toml",
    ".agents/plugins/marketplace.json",
)

# ── remediation 文言 ───────────────────────────────────────────────
REMEDIATION_INVALID = "invalid layout/contract/parse を stderr の指示で修正し再実行する"
REMEDIATION_CONFLICT = "report の name/hook/permission conflict を解消してから --apply を再実行する"
REMEDIATION_CODEX = (
    "repo-owned Codex surface を配線する: plugins/<slug>/.codex-plugin/plugin.json と "
    ".agents/plugins/marketplace.json を作成する (repo integration owner)"
)


def _apply_cmd(repo_root: Path) -> str:
    return (
        f"python3 plugins/harness-creator/scripts/sync-native-surfaces.py "
        f"--repo-root {repo_root} --apply"
    )


# ─────────────────── 時刻ユーティリティ ───────────────────
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("started_at is not a string")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ─────────────────── fingerprint / atomic replace ───────────────────
def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_path(path: Path) -> str | None:
    """既存 file の sha256 を返す。file が無ければ None (=未生成 fingerprint)。"""
    p = Path(path)
    if not p.is_file():
        return None
    return fingerprint_bytes(p.read_bytes())


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """同 dir の tempfile へ書いてから os.replace する原子的上書き (途中書込を残さない)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


# ─────────────────── write-scope 境界判定 ───────────────────
def is_write_allowed(repo_root: Path, target: Path) -> bool:
    """target が C01 の managed write-scope 内かを判定する (read-only 境界の唯一の門番)。

    repo 外 (user global config ~/.codex ~/.claude 等・絶対 path) は常に拒否。repo 内でも
    forbidden prefix (tool-owned namespace・.git) は拒否。allow は
    ``.claude/{skills,agents,commands}``・``.claude/settings.json``・``.build``・
    ``.codex/{hooks.json,config.toml}`` の exact paths・``.agents/plugins/marketplace.json``・
    ``plugins/<slug>/.codex-plugin/plugin.json`` に限定する。
    """
    repo_root = Path(repo_root).resolve()
    try:
        rel = Path(target).resolve().relative_to(repo_root)
    except ValueError:
        return False  # repo 外 (home 配下・絶対 path 含む)
    rel_str = rel.as_posix()
    if rel_str in (".", ""):
        return False

    def _under(prefix: str) -> bool:
        return rel_str == prefix or rel_str.startswith(prefix + "/")

    # (1) forbidden を最優先で拒否 (多層防御)。
    if any(_under(fp) for fp in FORBIDDEN_PREFIXES):
        return False
    # (2) 明示 exact allow。
    if rel_str in ALLOWED_EXACT:
        return True
    # (3) repo-owned Codex manifest: plugins/<slug>/.codex-plugin/plugin.json。
    parts = rel.parts
    if (
        len(parts) == 4
        and parts[0] == "plugins"
        and parts[2] == ".codex-plugin"
        and parts[3] == "plugin.json"
    ):
        return True
    # (4) allow dir prefix。
    if any(_under(prefix) for prefix in ALLOWED_DIR_PREFIXES):
        return True
    return False


class WriteScopeError(Exception):
    """write-scope 外への書込企図 (fail-closed で拒否)。"""


def sync_repo_owned_file(repo_root: Path, target: Path, desired: bytes, *, dry_run: bool = False) -> str:
    """owner=repo と宣言された managed file を fingerprint 差分時のみ atomic replace する。

    戻り値: ``noop`` (fingerprint 一致・無書込) / ``would-write`` (dry-run・差分あり) /
    ``written`` (差分ありで atomic 書込)。write-scope 外は ``WriteScopeError`` で fail-closed。
    """
    target = Path(target)
    if not is_write_allowed(Path(repo_root), target):
        raise WriteScopeError(f"write outside managed scope refused: {target}")
    if fingerprint_path(target) == fingerprint_bytes(desired):
        return "noop"
    if dry_run:
        return "would-write"
    atomic_write_bytes(target, desired)
    return "written"


# ─────────────────── pid 生存 / lock stale 判定 ───────────────────
def pid_alive(pid: object) -> bool:
    """os.kill(pid, 0) の成否で pid 生存を判定する (別ユーザ所有 PermissionError は生存扱い)。"""
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
    """既存 lock が孤児 (回収可) かを判定する。

    stale = parse 不能 (破損) / age>ttl (heartbeat 途絶) / 同一ホストで pid 非生存 (死んだ orchestrator)。
    恒久 lockout 回避のため破損 lock は stale とみなす。
    """
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


def _lock_payload(now: datetime, owner_token: str | None = None) -> dict:
    return {
        "started_at": _iso(now),
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "owner_token": owner_token or secrets.token_hex(16),
    }


class LockLease:
    """A lock acquisition plus the unguessable token required to release it."""

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
    """Delete only the exact locked inode/bytes inspected by the decision."""
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


def acquire_lock(
    lock_path: Path,
    timeout: float,
    *,
    lock_ttl: float = DEFAULT_LOCK_TTL,
    poll: float = 0.05,
    monotonic=time.monotonic,
    sleep=time.sleep,
    clock=_now_utc,
) -> LockLease | None:
    """repo-local file lock を O_CREAT|O_EXCL で原子的に取得する。

    戻り値: ``acquired`` (新規取得) / ``stolen`` (孤児 lock を回収して取得) / ``None`` (timeout)。
    生存 lock が居る場合は ``timeout`` 秒まで poll し、取得できなければ ``None`` を返す
    (呼び出し側で exit 2)。
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    owner_token = secrets.token_hex(16)
    acquired_state = "acquired"
    deadline = monotonic() + max(0.0, timeout)
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            snapshot = _read_lock_bytes(lock_path)
            existing = _decode_lock(snapshot)
            if lock_is_stale(existing, clock(), lock_ttl):
                # Never replace a stale path in place: two contenders could both
                # believe they own it. Compare/delete the inspected instance, then
                # return to O_EXCL so exactly one contender can create the lease.
                if snapshot is not None and _compare_delete(lock_path, snapshot):
                    acquired_state = "stolen"
                continue
            if monotonic() >= deadline:
                return None
            sleep(poll)
            continue
        payload = _lock_payload(clock(), owner_token)
        try:
            # Serialize publication against a contender inspecting the newly
            # created (initially empty) inode as a corrupt stale lock.
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
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            fh.flush()
        return LockLease(acquired_state, owner_token)


def release_lock(lock_path: Path, lease: LockLease | str | None) -> bool:
    """Release only when the on-disk owner token still matches this lease."""
    token = lease.owner_token if isinstance(lease, LockLease) else lease
    if not isinstance(token, str) or not token:
        return False
    snapshot = _read_lock_bytes(lock_path)
    existing = _decode_lock(snapshot)
    if snapshot is None or not isinstance(existing, dict) or existing.get("owner_token") != token:
        return False
    return _compare_delete(lock_path, snapshot)


# ─────────────────── activation scope ───────────────────
def read_activation_scope(repo_root: Path) -> dict:
    """``enabledPlugins`` の plugin@marketplace 完全 identity から scope を導出する。

    戻り値 keys: ``enabled`` (installed かつ enabled)・``skipped`` ([{plugin,reason}])・
    ``present`` (plugins/ 実在 dir)・``scope_error`` (settings.json 読取不能時の説明・else None)。
    """
    repo_root = Path(repo_root)
    plugins_dir = repo_root / "plugins"
    present = (
        sorted(p.name for p in plugins_dir.iterdir() if p.is_dir())
        if plugins_dir.is_dir()
        else []
    )
    enabled_identities: set[str] = set()
    scope_error: str | None = None
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace_name: str | None = None
    if marketplace_path.is_file():
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            scope_error = f"marketplace.json 読取不能: {exc}"
            marketplace = None
        if not isinstance(marketplace, dict):
            scope_error = "marketplace.json root must be an object"
        elif not isinstance(marketplace.get("name"), str) or not marketplace["name"]:
            scope_error = "marketplace.json name must be a non-empty string"
        else:
            marketplace_name = marketplace["name"]
    else:
        scope_error = f"marketplace.json 不在: {marketplace_path}"

    settings_path = repo_root / ".claude" / "settings.json"
    if scope_error is None and settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            scope_error = f"settings.json 読取不能: {exc}"
            data = None
        if not isinstance(data, dict):
            scope_error = "settings.json root must be an object"
        else:
            enabled_plugins = data.get("enabledPlugins")
            if not isinstance(enabled_plugins, dict):
                scope_error = "settings.json enabledPlugins missing or not an object"
            else:
                for key, value in enabled_plugins.items():
                    if not isinstance(key, str) or not isinstance(value, bool):
                        scope_error = "settings.json enabledPlugins entries must be string:boolean"
                        enabled_identities.clear()
                        break
                    if value is True:
                        enabled_identities.add(key)
    elif scope_error is None:
        scope_error = f"settings.json 不在: {settings_path}"

    if scope_error is not None:
        # scope 不明時は fail-safe に filter を掛けない (全除外の暴発を避ける)。
        return {"enabled": [], "skipped": [], "present": present, "scope_error": scope_error}

    expected_identities = {p: f"{p}@{marketplace_name}" for p in present}
    enabled = [p for p in present if expected_identities[p] in enabled_identities]
    skipped = [
        {
            "plugin": p,
            "identity": expected_identities[p],
            "reason": "exact plugin@marketplace identity not enabled in .claude/settings.json enabledPlugins",
        }
        for p in present
        if expected_identities[p] not in enabled_identities
    ]
    return {"enabled": enabled, "skipped": skipped, "present": present, "scope_error": None}


# ─────────────────── subprocess 委譲 (monkeypatch 点) ───────────────────
def _run_process(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _run_symlinks(
    script: Path,
    plugins_dir: Path,
    target_dir: Path,
    *,
    check: bool,
    excludes,
    prune: bool = True,
) -> tuple[int, str]:
    argv = [
        sys.executable, str(script),
        "--plugins-dir", str(plugins_dir),
        "--target-dir", str(target_dir),
        "--json",
    ]
    for name in excludes:
        argv += ["--exclude-plugin", name]
    # Activation scope 外へ移った managed symlink は orphan になる。
    # apply 時だけ --prune で除去する。check は prune なしでも orphan を
    # drift と判定するため、read-only のまま同じ収束条件を検査できる。
    if prune:
        argv.append("--prune")
    if check:
        argv.append("--check")
    return _run_process(argv)


def _run_settings(script: Path, plugins_dir: Path, target: Path, *, check: bool, excludes=()) -> tuple[int, str]:
    argv = [
        sys.executable, str(script),
        "--plugins-dir", str(plugins_dir),
        "--target", str(target),
        "--json",
    ]
    for name in excludes:
        argv += ["--exclude-plugin", name]
    if check:
        argv.append("--check")
    return _run_process(argv)


def _run_codex(script: Path, repo_root: Path, slug: str, contract: Path, plan_dir: Path) -> tuple[int, str]:
    argv = [
        sys.executable, str(script),
        "--repo-root", str(repo_root),
        "--plugin-slug", str(slug),
        "--surface-contract", str(contract),
        "--plan-dir", str(plan_dir),
        "--json",
    ]
    return _run_process(argv)


def _run_codex_project(script: Path, repo_root: Path, contract: Path, *, apply: bool) -> tuple[int, str, str]:
    argv = [
        sys.executable, str(script), "--repo-root", str(repo_root),
        "--contract", str(contract), "--json", "--apply" if apply else "--check",
    ]
    return _run_process(argv)


# ─────────────────── adapter result 正規化 ───────────────────
def _bounded_text(value: object, limit: int = MAX_CHILD_DIAGNOSTIC_CHARS) -> str:
    text = value if isinstance(value, str) else ""
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _bounded_json(value: object) -> object:
    """Keep parsed child JSON useful while enforcing a finite report envelope."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    if len(encoded) <= MAX_CHILD_REPORT_CHARS:
        return value
    if isinstance(value, dict):
        compact = {
            key: value[key]
            for key in ("verdict", "exit_code", "summary", "remediation")
            if key in value
        }
        compact["_truncated"] = True
        compact["_original_chars"] = len(encoded)
        return compact
    return {"_truncated": True, "_original_chars": len(encoded)}


def _normalize_child_result(result) -> tuple[int, str, str]:
    if isinstance(result, tuple) and len(result) == 3:
        return result[0], result[1], result[2]
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1], ""
    raise TypeError("child runner must return (exit, stdout[, stderr])")


def _child_evidence(result) -> dict:
    code, stdout, stderr = _normalize_child_result(result)
    try:
        parsed = json.loads(stdout) if isinstance(stdout, str) and stdout.strip() else None
    except (json.JSONDecodeError, TypeError):
        parsed = None
    violations = parsed.get("violations", []) if isinstance(parsed, dict) else []
    if not isinstance(violations, list):
        violations = []
    violations = [_bounded_json(v) for v in violations[:MAX_CHILD_VIOLATIONS]]
    remediation = parsed.get("remediation") if isinstance(parsed, dict) else None
    return {
        "code": code,
        "child_report": _bounded_json(parsed),
        "violations": violations,
        "child_remediation": _bounded_json(remediation),
        "stdout": _bounded_text(stdout),
        "stderr": _bounded_text(stderr),
    }


def _adapter_result(
    name, *, status, changed=0, exit=0, skipped_reason=None, warning=None,
    remediation=None, child=None,
) -> dict:
    child = child or {}
    return {
        "name": name,
        "status": status,
        "changed": changed,
        "exit": exit,
        "skipped_reason": skipped_reason,
        "warning": warning,
        "remediation": (
            child.get("child_remediation")
            if child.get("child_remediation") is not None
            else remediation
        ),
        "child_report": child.get("child_report"),
        "violations": child.get("violations", []),
        "stdout": child.get("stdout", ""),
        "stderr": child.get("stderr", ""),
    }


def _skipped(name: str, reason: str) -> dict:
    return _adapter_result(name, status="skipped_not_installed", exit=SEV_OK, skipped_reason=reason)


def _map_exit(code: int) -> int:
    """generator の生 exit code を C01 taxonomy へ写す (0/1/2 は同値、それ以外は invalid=3)。"""
    if code == 0:
        return SEV_OK
    if code == 1:
        return SEV_DRIFT
    if code == 2:
        return SEV_CONFLICT
    return SEV_INVALID


def _symlinks_changed(out: str) -> int:
    """build-claude-symlinks --json の summary から created+updated 件数を数える。"""
    try:
        report = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return 0
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict):
        return 0
    try:
        return int(summary.get("created", 0)) + int(summary.get("updated", 0))
    except (TypeError, ValueError):
        return 0


def _classify_claude(name: str, code: int, *, changed: int, applied: bool, repo_root: Path, child=None) -> dict:
    """Claude generator の (exit, changed) を adapter result へ分類する。"""
    sev = _map_exit(code)
    if sev == SEV_INVALID:
        return _adapter_result(name, status="invalid", exit=SEV_INVALID,
                               warning="invalid layout or parse error", remediation=REMEDIATION_INVALID, child=child)
    if sev == SEV_CONFLICT:
        return _adapter_result(name, status="conflict", exit=SEV_CONFLICT,
                               warning="managed projection has conflicts", remediation=REMEDIATION_CONFLICT, child=child)
    if sev == SEV_DRIFT:
        return _adapter_result(name, status="drift", changed=changed, exit=SEV_DRIFT,
                               warning="managed projection drifts from plugin sources",
                               remediation=_apply_cmd(repo_root), child=child)
    if applied and changed > 0:
        return _adapter_result(name, status="synced", changed=changed, exit=SEV_OK, child=child)
    return _adapter_result(name, status="noop", changed=0, exit=SEV_OK, child=child)


def _classify_codex(code: int, *, child=None) -> dict:
    """C02 parity validator の exit を adapter result へ分類する (read-only なので changed=0)。"""
    sev = _map_exit(code)
    if sev == SEV_INVALID:
        return _adapter_result("codex_parity", status="invalid", exit=SEV_INVALID,
                               warning="invalid native-surface contract or layout", remediation=REMEDIATION_INVALID, child=child)
    if sev == SEV_CONFLICT:
        return _adapter_result("codex_parity", status="conflict", exit=SEV_CONFLICT,
                               warning="codex native surface conflict", remediation=REMEDIATION_CONFLICT, child=child)
    if sev == SEV_DRIFT:
        return _adapter_result("codex_parity", status="drift", exit=SEV_DRIFT,
                               warning="codex native surface parity drift", remediation=REMEDIATION_CODEX, child=child)
    return _adapter_result("codex_parity", status="checked", exit=SEV_OK, child=child)


# ─────────────────── adapters ───────────────────
def adapter_symlinks(mode, *, script, plugins_dir, target_dir, excludes, repo_root) -> dict:
    if not Path(script).is_file():
        return _skipped("claude_symlinks", f"generator absent: {script}")
    if mode == "apply":
        # fingerprint ゲート: まず check し drift 時のみ apply へ進む。
        check_child = _child_evidence(_run_symlinks(
            script, plugins_dir, target_dir, check=True, excludes=excludes, prune=False
        ))
        code_c, out_c = check_child["code"], check_child["stdout"]
        sev = _map_exit(code_c)
        if sev >= SEV_CONFLICT:  # conflict/invalid は書かず fail-closed。
            return _classify_claude("claude_symlinks", code_c, changed=0, applied=False,
                                    repo_root=repo_root, child=check_child)
        if sev == SEV_OK and _symlinks_changed(out_c) == 0:
            return _classify_claude("claude_symlinks", 0, changed=0, applied=False,
                                    repo_root=repo_root, child=check_child)
        apply_child = _child_evidence(_run_symlinks(
            script, plugins_dir, target_dir, check=False, excludes=excludes, prune=True
        ))
        return _classify_claude("claude_symlinks", apply_child["code"],
                                changed=_symlinks_changed(apply_child["stdout"]),
                                applied=True, repo_root=repo_root, child=apply_child)
    # check / dry-run: read-only。
    child = _child_evidence(_run_symlinks(
        script, plugins_dir, target_dir, check=True, excludes=excludes, prune=False
    ))
    return _classify_claude("claude_symlinks", child["code"],
                            changed=_symlinks_changed(child["stdout"]), applied=False,
                            repo_root=repo_root, child=child)


def adapter_settings(mode, *, script, plugins_dir, target, repo_root, excludes=()) -> dict:
    if not Path(script).is_file():
        return _skipped("claude_settings", f"generator absent: {script}")
    if mode == "apply":
        check_child = _child_evidence(_run_settings(script, plugins_dir, target, check=True, excludes=excludes))
        code_c = check_child["code"]
        sev = _map_exit(code_c)
        if sev >= SEV_CONFLICT:
            return _classify_claude("claude_settings", code_c, changed=0, applied=False,
                                    repo_root=repo_root, child=check_child)
        if sev == SEV_OK:
            return _classify_claude("claude_settings", 0, changed=0, applied=False,
                                    repo_root=repo_root, child=check_child)
        apply_child = _child_evidence(_run_settings(script, plugins_dir, target, check=False, excludes=excludes))
        # settings は単一 managed file → 反映すれば changed=1。
        return _classify_claude("claude_settings", apply_child["code"], changed=1,
                                applied=True, repo_root=repo_root, child=apply_child)
    child = _child_evidence(_run_settings(script, plugins_dir, target, check=True, excludes=excludes))
    changed = 1 if _map_exit(child["code"]) == SEV_DRIFT else 0
    return _classify_claude("claude_settings", child["code"], changed=changed,
                            applied=False, repo_root=repo_root, child=child)


def adapter_codex(mode, *, script, repo_root, slug, contract, plan_dir) -> dict:
    # mode に依らず read-only (C02 は write-scope: none)。generator 不在のみ skipped。
    if not Path(script).is_file():
        return _skipped("codex_parity", f"validator absent: {script}")
    child = _child_evidence(_run_codex(script, repo_root, slug, contract, plan_dir))
    return _classify_codex(child["code"], child=child)


def adapter_codex_project_settings(mode, *, script, repo_root, contract) -> dict:
    if not Path(script).is_file():
        return _skipped("codex_project_settings", f"generator absent: {script}")
    check_child = _child_evidence(_run_codex_project(script, repo_root, contract, apply=False))
    severity = _map_exit(check_child["code"])
    if mode == "apply" and severity == SEV_DRIFT:
        applied = _child_evidence(_run_codex_project(script, repo_root, contract, apply=True))
        child_changed = applied.get("child_report", {}).get("changed")
        changed = child_changed if isinstance(child_changed, int) and not isinstance(child_changed, bool) and child_changed >= 0 else 1
        return _classify_claude(
            "codex_project_settings", applied["code"], changed=changed, applied=True,
            repo_root=repo_root, child=applied,
        )
    child_changed = check_child.get("child_report", {}).get("changed")
    changed = child_changed if isinstance(child_changed, int) and not isinstance(child_changed, bool) and child_changed >= 0 else (1 if severity == SEV_DRIFT else 0)
    return _classify_claude(
        "codex_project_settings", check_child["code"], changed=changed,
        applied=False, repo_root=repo_root, child=check_child,
    )


# ─────────────────── orchestration ───────────────────
_VERDICT = {SEV_OK: "success", SEV_DRIFT: "drift", SEV_CONFLICT: "conflict", SEV_INVALID: "invalid"}


def _build_report(mode, adapters, scope, *, lock, exit_code, verdict) -> dict:
    return {
        "mode": mode,
        "adapters": adapters,
        "scope": {
            "enabled": scope["enabled"],
            "skipped": scope["skipped"],
            "scope_error": scope.get("scope_error"),
            "activation_evidence": {
                "claude": {
        "source": ".claude-plugin/marketplace.json name + .claude/settings.json enabledPlugins exact identity",
                    "enabled_state": "verified" if not scope.get("scope_error") else "unavailable",
                    "trust_state": "not_exposed_by_repo_settings",
                },
                "codex": {
                    "source": "repo-owned manifest/marketplace parity only",
                    "enabled_state": "not_verified",
                    "trust_state": "not_verified",
                },
            },
        },
        "lock": lock,
        "verdict": verdict,
        "exit_code": exit_code,
    }


def orchestrate(
    *,
    repo_root,
    mode,
    lock_timeout=DEFAULT_LOCK_TIMEOUT,
    symlinks_script,
    settings_script,
    codex_script,
    slug,
    contract,
    plan_dir,
    lock_path,
    lock_ttl=DEFAULT_LOCK_TTL,
    codex_settings_script=None,
    native_surfaces_contract=None,
) -> tuple[dict, int]:
    """4 adapters を mode に応じ合成し (report, exit_code) を返す。--apply のみ lock を握る。"""
    repo_root = Path(repo_root)
    scope = read_activation_scope(repo_root)
    # Repo-present + project-enabled is the observable local projection boundary.
    # Product install/trust is a separate user gate; if project scope cannot be read,
    # applying every plugin would bypass the boundary, so fail closed.
    if scope["scope_error"]:
        report = _build_report(
            mode,
            [],
            scope,
            lock=None,
            exit_code=SEV_INVALID,
            verdict="invalid_activation_scope",
        )
        return report, SEV_INVALID
    excludes = [s["plugin"] for s in scope["skipped"]]

    lock_lease: LockLease | None = None
    if mode == "apply":
        lock_lease = acquire_lock(lock_path, lock_timeout, lock_ttl=lock_ttl)
        if lock_lease is None:
            report = _build_report(mode, [], scope, lock="timeout", exit_code=SEV_CONFLICT, verdict="lock_timeout")
            return report, SEV_CONFLICT

    try:
        adapters = [
            adapter_symlinks(mode, script=symlinks_script, plugins_dir=repo_root / "plugins",
                             target_dir=repo_root / ".claude", excludes=excludes, repo_root=repo_root),
            adapter_settings(mode, script=settings_script, plugins_dir=repo_root / "plugins",
                             target=repo_root / ".claude" / "settings.json", repo_root=repo_root,
                             excludes=excludes),
        ]
        if codex_settings_script is not None:
            adapters.append(
                adapter_codex_project_settings(
                    mode, script=codex_settings_script, repo_root=repo_root,
                    contract=native_surfaces_contract,
                )
            )
        adapters.append(
            adapter_codex(mode, script=codex_script, repo_root=repo_root, slug=slug,
                          contract=contract, plan_dir=plan_dir)
        )
    finally:
        if lock_lease is not None:
            release_lock(lock_path, lock_lease)

    exit_code = max((a["exit"] for a in adapters), default=SEV_OK)
    verdict = _VERDICT[exit_code]
    report = _build_report(mode, adapters, scope,
                           lock=(lock_lease.state if lock_lease is not None else None),
                           exit_code=exit_code, verdict=verdict)
    return report, exit_code


# ─────────────────── rendering / CLI ───────────────────
def render_human(report: dict, out) -> None:
    out.write(f"mode: {report['mode']}  verdict: {report['verdict']} (exit {report['exit_code']})\n")
    lock = report.get("lock")
    if lock is not None:
        out.write(f"lock: {lock}\n")
    for a in report.get("adapters", []):
        line = f"  adapter {a['name']}: {a['status']} changed={a['changed']} exit={a['exit']}"
        out.write(line + "\n")
        if a.get("skipped_reason"):
            out.write(f"    skipped: {a['skipped_reason']}\n")
        if a.get("warning"):
            out.write(f"    warning: {a['warning']}\n")
        if a.get("remediation"):
            out.write(f"    remediation: {a['remediation']}\n")
    scope = report.get("scope", {})
    out.write(f"  scope enabled: {', '.join(scope.get('enabled', [])) or '(none)'}\n")
    for s in scope.get("skipped", []):
        out.write(f"  scope skipped: {s['plugin']} ({s['reason']})\n")
    if scope.get("scope_error"):
        out.write(f"  scope error: {scope['scope_error']}\n")


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="sync-native-surfaces.py",
        description="C01 native surface 同期 orchestrator (Claude symlink/settings apply/check + Codex parity check)。",
    )
    ap.add_argument("--repo-root", required=True, help="repo ルート")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--apply", action="store_const", const="apply", dest="mode", help="fingerprint 差分時に実書込")
    grp.add_argument("--check", action="store_const", const="check", dest="mode", help="read-only 検査 (既定)")
    grp.add_argument("--dry-run", action="store_const", const="dry-run", dest="mode", help="変更計画のみ・無書込")
    ap.set_defaults(mode="check")
    ap.add_argument("--json", dest="as_json", action="store_true", help="機械可読 JSON 出力")
    ap.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT, help="lock 取得の最大待機秒 (既定 30)")
    ap.add_argument("--lock-ttl", type=float, default=DEFAULT_LOCK_TTL, help="lock heartbeat 途絶判定 ttl 秒 (既定 3600)")
    ap.add_argument("--plugin-slug", default=DEFAULT_PLUGIN_SLUG, help="対象 plugin slug (既定 harness-creator)")
    ap.add_argument("--surface-contract", default=None, help="native-surface-contract.md (既定はプラグイン references 配下)")
    ap.add_argument("--plan-dir", default=None, help="C02 digest input を含む plan dir")
    ap.add_argument("--symlinks-script", default=None, help="build-claude-symlinks.py path (既定 <repo>/scripts/)")
    ap.add_argument("--settings-script", default=None, help="build-claude-settings.py path (既定 <repo>/scripts/)")
    ap.add_argument("--codex-parity-script", default=None, help="check-native-surface-parity.py path (既定は同 dir sibling)")
    ap.add_argument("--codex-settings-script", default=None, help="sync-codex-project-settings.py path")
    ap.add_argument("--native-surfaces-contract", default=None, help="native-surfaces.toml path")
    ap.add_argument("--lock-path", default=None, help="lock file path (既定 <repo>/.build/locks/sync-native-surfaces.lock)")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    repo_root = Path(args.repo_root).resolve()
    c01_dir = Path(__file__).resolve().parent

    symlinks_script = Path(args.symlinks_script) if args.symlinks_script else repo_root / "scripts" / "build-claude-symlinks.py"
    settings_script = Path(args.settings_script) if args.settings_script else repo_root / "scripts" / "build-claude-settings.py"
    codex_script = Path(args.codex_parity_script) if args.codex_parity_script else c01_dir / "check-native-surface-parity.py"
    codex_settings_script = Path(args.codex_settings_script) if args.codex_settings_script else c01_dir / "sync-codex-project-settings.py"
    native_surfaces_contract = Path(args.native_surfaces_contract) if args.native_surfaces_contract else c01_dir.parent / "native-surfaces.toml"
    contract = Path(args.surface_contract) if args.surface_contract else c01_dir.parent / "references" / "native-surface-contract.md"
    plan_dir = Path(args.plan_dir) if args.plan_dir else repo_root.joinpath(*DEFAULT_PLAN_SUBDIR)
    lock_path = Path(args.lock_path) if args.lock_path else repo_root.joinpath(*LOCK_REL)

    report, code = orchestrate(
        repo_root=repo_root,
        mode=args.mode,
        lock_timeout=args.lock_timeout,
        symlinks_script=symlinks_script,
        settings_script=settings_script,
        codex_script=codex_script,
        slug=args.plugin_slug,
        contract=contract,
        plan_dir=plan_dir,
        lock_path=lock_path,
        lock_ttl=args.lock_ttl,
        codex_settings_script=codex_settings_script,
        native_surfaces_contract=native_surfaces_contract,
    )
    if args.as_json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        render_human(report, sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
