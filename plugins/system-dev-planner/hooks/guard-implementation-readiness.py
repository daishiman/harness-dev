#!/usr/bin/env python3
# /// script
# name: guard-implementation-readiness
# purpose: active staging run の Bash/Task 実装呼出しを readiness/TTL/repo boundary で fail-closed 制御する。
# inputs: stdin Claude PreToolUse JSON; env CLAUDE_PROJECT_DIR (repo root 宣言のみ・run 識別 env には非依存)
# outputs: exit 0 pass-through, exit 2 blocked
# contexts: [E]
# network: false
# write-scope: expired lock cleanup and audit only
# dependencies: [scripts/resolve-project-context.py, scripts/check-implementation-readiness.py, scripts/manage-system-plan-lock.py]
# requires-python: ">=3.10"
# ///
"""C07 lifecycle guard. It self-discovers active run locks for the resolved
repository (no run-id env needed) and is inactive unless such a lock exists."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent


def _load_context():
    path = PLUGIN / "scripts" / "resolve-project-context.py"
    spec = importlib.util.spec_from_file_location("sdp_context", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _load_lock_manager():
    path = PLUGIN / "scripts" / "manage-system-plan-lock.py"
    spec = importlib.util.spec_from_file_location("sdp_lock_manager", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _parse_time(value: object):
    if not isinstance(value, str): return None
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return None


def _classify_lock(state: dict, repository_id: str, now: datetime) -> str:
    """Classify one loaded staging lock for the resolved repository. Return exactly
    one of the three string verdicts below (main acts on each):
      "enforce" -> an active run of THIS repository -> guard must run readiness,
      "expired" -> belongs to THIS repository but past expires_at -> cleanup+skip,
      "ignore"  -> unrelated (other repository) or otherwise not gating -> skip.

    Now that no env identifies the run, this predicate is the SOLE authority that
    decides which staging lock activates the guard, so the security posture lives here.

    Inputs:
      state         = dict parsed from the lock JSON. Bound fields (SKILL.md `plan`):
                      repository_id / run_id / session_owner / expires_at (+ feature id/digest).
      repository_id = the resolved caller repository id to match against.
      now           = timezone-aware datetime (UTC) captured once by main.
    Helper: `_parse_time(state.get("expires_at"))` -> aware datetime or None.

    Design decisions to encode:
      - repository boundary: only THIS repository's locks may gate (others -> "ignore").
      - freshness: past expires_at -> "expired"; still valid -> "enforce".
      - fail-open vs fail-closed when expires_at is missing/malformed (None): a lock
        for this repo with an unreadable expiry — treat it as an active run and
        "enforce" to stay safe, or "ignore" to avoid false blocks? Choose deliberately.
    """
    if state.get("repository_id") != repository_id:
        return "ignore"
    expires = _parse_time(state.get("expires_at"))
    if expires is None:
        # Fail closed: a lock owned by this repository whose expiry is missing or
        # unreadable must not become a silent escape hatch. "enforce" only runs the
        # readiness check, which passes through when the project is genuinely ready.
        return "enforce"
    if expires <= now:
        return "expired"
    return "enforce"


def main() -> int:
    try: payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError: return 0
    if payload.get("tool_name") not in {"Bash", "Task"}: return 0
    c09 = _load_context()
    lock_manager = _load_lock_manager()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return 0
    declared_root = Path(project_dir)
    declared_config = declared_root / ".dev-graph" / "config.json"
    if not declared_config.exists() and not declared_config.is_symlink():
        return 0  # genuinely unmanaged repository: no system-dev-planner state
    try:
        context = c09.build_context([], dict(os.environ))
    except Exception as exc:
        # Once the managed-repo marker exists, malformed identity/containment
        # is a policy failure, not an excuse to disable the hook.
        print(f"[readiness-guard] BLOCKED: managed repository context is invalid: {exc}", file=sys.stderr)
        return 2
    repository_id = context["repository_id"]
    locks = Path(context["local_state"]["locks"]["absolute"])
    if not locks.is_dir(): return 0
    now = datetime.now(timezone.utc)
    enforce = False
    for lock in sorted(locks.glob("system-dev-plan-*.json")):
        try:
            state, _raw = lock_manager._read_lock(lock)
        except (lock_manager.DomainBlock, OSError) as exc:
            # The lock directory is repository-local authority.  A malformed
            # candidate must never disable the guard by becoming unparseable.
            print(f"[readiness-guard] BLOCKED: malformed system plan lock {lock.name}: {exc}", file=sys.stderr)
            return 2
        if lock.name == lock_manager.LOCK_NAME and state.get("repository_id") != repository_id:
            print("[readiness-guard] BLOCKED: canonical lock repository identity mismatch", file=sys.stderr)
            return 2
        verdict = _classify_lock(state, repository_id, now)
        if verdict == "expired":
            try:
                lock_manager.cleanup_expired_lock(
                    repo_root=Path(context["repo_root"]),
                    locks=locks,
                    lock_path=lock,
                    repository_id=repository_id,
                    now=now,
                )
            except (lock_manager.DomainBlock, lock_manager.ContractError, OSError) as exc:
                print(f"[readiness-guard] BLOCKED: expired lock cleanup failed: {exc}", file=sys.stderr)
                return 2
        elif verdict == "enforce": enforce = True; break
    if not enforce: return 0
    cmd = [sys.executable, str(PLUGIN / "scripts" / "check-implementation-readiness.py"),
           "--repo-root", context["repo_root"], "--config", context["config_path"]]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write("[readiness-guard] BLOCKED: implementation_readiness incomplete\n" + result.stdout + result.stderr)
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
