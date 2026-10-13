#!/usr/bin/env python3
# /// script
# name: hook-guard-rubric
# purpose: Block edits to canonical rubric files unless ALLOW_RUBRIC_EDIT=1
# inputs:
#   - stdin: Claude Code hook protocol JSON ({tool_name, tool_input, ...})
# outputs:
#   - stderr: deny の理由（Claude Code は exit 2 のとき、これを理由にして止める）
#   - stdout: deny のときだけ hookSpecificOutput JSON（補助。exit 2 では Claude Code は読まない）
#   - exit: 0=allow（壊れた入力・object でない入力は fail open）/ 2=deny
# requires-python: ">=3.9"
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""PreToolUse hook: deny Write/Edit on rubric.json files to prevent Goodhart loop.

Reads hook input JSON from stdin (Claude Code hook protocol):
  {"tool_name": "Edit"|"Write"|"MultiEdit", "tool_input": {"file_path": "..."}, ...}

出力プロトコル (13章: policy hook は exit 2 か structured JSON で止める):
  - deny  → stderr に理由を出して exit 2。これが主系で、Claude Code は stderr を理由にして
            tool の呼び出しを止める。exit 2 のとき Claude Code は stdout の JSON を読まない。
            stdout には {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": "..."}} も出す。
            exit 0 で JSON を読む呼び出し側と test のための補助で、判定は exit 2 だけで足りる。
  - allow → stdout 出力なし、exit 0

壊れた JSON、object でない JSON、object でない tool_input は fail open (exit 0) にする。
Claude Code は常に object を渡すので、これは手で呼んだときの入力の誤りに限られる。
NUL を含むパスも allow にする。OS はそのパスを開けないので守るファイルが無く、
Python 3.11 の normpath は NUL で文字列を切るので、先に外さないと版によって判定が変わる。

照合は、正規化したパスと resolve() 後のパスの2つを、NFC と casefold をそろえて行う。
macOS の既定のファイルシステムは大文字小文字と Unicode の正規化を区別しないので、
references/Rubric.json も正規の rubric と同じファイルを指す。大文字小文字だけが違う
別ファイルを区別するファイルシステムでは、その名前も守る側に倒す。
"""
from __future__ import annotations
import json
import os
import posixpath
import sys
import unicodedata
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
                suffixes.add(_normalized(rubric))
    return suffixes


def _normalized(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))


def _folded(path: str) -> str:
    """大文字小文字と Unicode の正規化を区別しないファイルシステムで、同じ名前を同じ鍵にする。"""
    return unicodedata.normalize("NFC", path).casefold()


def is_guarded(path: str) -> bool:
    if not isinstance(path, str) or not path or "\x00" in path:
        return False
    candidates = {_folded(_normalized(path))}
    try:
        # symlink の実体でも照合する
        candidates.add(_folded(_normalized(str(Path(path).resolve()))))
    except (OSError, RuntimeError, ValueError):
        pass
    suffixes = {_folded(suffix) for suffix in registry_guarded_suffixes()}
    for p in candidates:
        if any(p == s or p.endswith("/" + s) for s in suffixes):
            return True
        # assign-*/rubric.json or assign-*/**/rubric.json
        if p.endswith("/rubric.json") and any(part.startswith("assign-") for part in p.split("/")):
            return True
    return False


def main() -> int:
    if os.environ.get("ALLOW_RUBRIC_EDIT") == "1":
        return 0
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail open on malformed input
    if not isinstance(data, dict):
        return 0  # fail open: object でない入力は hook の入力ではない
    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    tool_input = data.get("tool_input")
    fp = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if is_guarded(fp):
        reason = (
            f"hook-guard-rubric: canonical rubric '{fp}' への直接編集を拒否。"
            " ALLOW_RUBRIC_EDIT=1 を設定するか governance フローで変更すること (Goodhart防止)。"
        )
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stderr.write(reason + "\n")
        return 2  # 主系: Claude Code は exit 2 と stderr の理由で止める
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
