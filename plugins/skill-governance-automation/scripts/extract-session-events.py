#!/usr/bin/env python3
# /// script
# name: extract-session-events
# purpose: Collect Claude Code hook events for the Meta-Harness feedback loop.
# inputs:
#   - argv[1]: user_prompt | tool_use | stop
#   - stdin: Claude Code hook JSON payload
# outputs:
#   - file: .claude/logs/<YYYY-MM-DD>.jsonl
# contexts: [D, E]
# network: false
# write-scope: workspace
# dependencies: []
# ///
"""extract-session-events.py

35章 Meta-Harness Feedback Loop の Phase 1 ログ収集機構。
Claude Code の hook (UserPromptSubmit / PostToolUse / Stop) から呼ばれ、
session event を `.claude/logs/<YYYY-MM-DD>.jsonl` に追記する。

opt-in 方式: `.claude/settings.json` の hooks 配列に登録された場合のみ動作する。

usage (hook configuration):
  {
    "hooks": {
      "UserPromptSubmit": [{"hooks":[{"type":"command","command":"python3 scripts/extract-session-events.py user_prompt"}]}],
      "PostToolUse":      [{"hooks":[{"type":"command","command":"python3 scripts/extract-session-events.py tool_use"}]}],
      "Stop":             [{"hooks":[{"type":"command","command":"python3 scripts/extract-session-events.py stop"}]}]
    }
  }

スキーマ v1.0 (確定): .claude/logs/schema-v1.0.json と本ファイル先頭定数を正本とする。
スキーマ変更は P0_breaking (33章 § log-driven ref-* 改善)。

exit code:
  0 always (hook が session を blocking しないため)
  stderr に warning 出力のみ

CONVENTIONS: stdlib only.
"""
import datetime as dt
import json
import os
import pathlib
import sys

SCHEMA_VERSION = "1.0"
# LOG_ROOT: install 後は scripts/ 配下から PROJECT_ROOT/.claude/logs を解決する。
# CLAUDE_LOG_ROOT があれば優先し、creator-kit 内での検証時は PROJECT_ROOT で上書きできる。
LOG_ROOT = (
    pathlib.Path(os.environ["CLAUDE_LOG_ROOT"])
    if os.environ.get("CLAUDE_LOG_ROOT")
    else pathlib.Path(os.environ.get("PROJECT_ROOT", pathlib.Path(__file__).resolve().parent.parent))
    / ".claude"
    / "logs"
)

EVENT_KINDS = {"user_prompt", "tool_use", "stop"}


def read_hook_payload():
    """hook は stdin で JSON を渡す (Claude Code 仕様)。空なら {} を返す。"""
    if sys.stdin.isatty():
        return {}
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except json.JSONDecodeError:
        return {}


def build_event(kind: str, payload: dict) -> dict:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    session_id = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")
    base = {
        "schema_version": SCHEMA_VERSION,
        "ts": now,
        "session_id": session_id,
        "event": kind,
    }
    if kind == "user_prompt":
        base["text"] = payload.get("prompt", "")[:2000]
    elif kind == "tool_use":
        base["tool_name"] = payload.get("tool_name", "")
        base["skill_invoked"] = payload.get("tool_name", "").startswith("Skill")
        tin = payload.get("tool_input") or {}
        if isinstance(tin, dict):
            base["skill"] = tin.get("skill") or tin.get("subagent_type") or ""
        base["success"] = bool(payload.get("tool_response", {}).get("success", True)) if isinstance(payload.get("tool_response"), dict) else True
    elif kind == "stop":
        base["reason"] = payload.get("reason", "")
    return base


def append_log(event: dict) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    day = event["ts"][:10]
    path = LOG_ROOT / f"{day}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main(argv):
    if len(argv) < 2 or argv[1] not in EVENT_KINDS:
        print(f"WARN extract-session-events: unknown event kind {argv[1:]!r}", file=sys.stderr)
        return 0
    kind = argv[1]
    payload = read_hook_payload()
    try:
        event = build_event(kind, payload)
        append_log(event)
    except Exception as e:
        print(f"WARN extract-session-events: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
