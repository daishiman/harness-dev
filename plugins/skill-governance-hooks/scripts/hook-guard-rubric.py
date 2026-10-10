#!/usr/bin/env python3
# /// script
# name: hook-guard-rubric
# purpose: Block edits to canonical rubric files unless ALLOW_RUBRIC_EDIT=1
# inputs:
#   - stdin: Claude Code hook protocol JSON ({tool_name, tool_input, ...})
# outputs:
#   - stdout: hookSpecificOutput.permissionDecision JSON
#   - exit: 0=allow / 2=deny
# contexts: [C]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""PreToolUse hook: deny Write/Edit on rubric.json files to prevent Goodhart loop.

Reads hook input JSON from stdin (Claude Code hook protocol):
  {"tool_name": "Edit"|"Write", "tool_input": {"file_path": "..."}, ...}

出力プロトコル (13章 P1: PreToolUse は hookSpecificOutput.permissionDecision を使う):
  - deny  → stdout に JSON {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "..."}}
            かつ exit 0 (exit code ではなく JSON で制御する)
  - allow → stdout 出力なし、exit 0

後方互換のため exit 2 は維持するが、主系は JSON 出力とする。
"""
from __future__ import annotations
import json
import os
import posixpath
import sys
from pathlib import Path


GUARDED_SUFFIXES = (
    "ref-skill-design-rubric/rubric.json",
    "ref-skill-design-rubric/references/rubric.json",
)
REPO_ROOT = Path(__file__).resolve().parents[3]


def registry_guarded_suffixes() -> set[str]:
    suffixes = set(GUARDED_SUFFIXES)
    bases = (Path.cwd(), Path(os.environ.get("PROJECT_ROOT", Path.cwd())),
             REPO_ROOT)
    registries = dict.fromkeys(
        base / relative for base in bases for relative in (
            "plugins/skill-governance-config/config/rubric-registry.json",
            "creator-kit/config/rubric-registry.json",  # older consumer installs
        )
    )
    for registry in registries:
        if not registry.exists():
            continue
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("rubrics"), list):
            continue
        for item in data["rubrics"]:
            if not isinstance(item, dict):
                continue
            rubric = item.get("rubric")
            if isinstance(rubric, str) and rubric:
                suffixes.add(posixpath.normpath(rubric.replace("\\", "/")))
    return suffixes


def is_guarded(path: str) -> bool:
    if not path:
        return False
    if not isinstance(path, str):
        return False
    p = posixpath.normpath(path.replace("\\", "/"))
    if any(p == s or p.endswith("/" + s) for s in registry_guarded_suffixes()):
        return True
    # assign-*/rubric.json or assign-*/**/rubric.json
    if any(part.startswith("assign-") for part in p.split("/")) and p.endswith("/rubric.json"):
        return True
    try:
        resolved = str(Path(path).resolve())
        if resolved != p:
            return is_guarded(resolved)
    except (OSError, RuntimeError):
        return False
    return False


def main() -> int:
    if os.environ.get("ALLOW_RUBRIC_EDIT") == "1":
        return 0
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail open on malformed input
    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    fp = (data.get("tool_input") or {}).get("file_path", "")
    if is_guarded(fp):
        reason = (
            f"hook-guard-rubric: canonical rubric '{fp}' への直接編集を拒否。"
            " ALLOW_RUBRIC_EDIT=1 を設定するか governance フローで変更すること (Goodhart防止)。"
        )
        # 13章 P1: PreToolUse は hookSpecificOutput.permissionDecision JSON で制御する
        import json as _json
        sys.stdout.write(_json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stderr.write(reason + "\n")
        return 2  # 後方互換
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
