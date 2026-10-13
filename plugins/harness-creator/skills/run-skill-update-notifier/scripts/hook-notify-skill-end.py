#!/usr/bin/env python3
"""PostToolUse hook (matcher=Skill): Skill の実行後に版の食い違いを利用者に表示する。常に exit 0。

stdin の payload から plugin 名を推定し、notifier-check.py の notify subcommand を呼ぶ。
通知があれば `{"systemMessage": "<plugin>: <通知>"}` の JSON 1 個を stdout に出す。
Claude Code は PostToolUse の素の stdout を debug log に送るだけで利用者に見せないが、
stdout 全体が JSON 1 個なら JSON として読み、systemMessage を利用者に表示する。
通知が無いときは何も出さない。plugin 名が特定できない場合も no-op (graceful degradation)。
payload の session_id を --session-id で渡し、同じ session で同じ plugin の通知を
2 度出さない (記録は notifier-check.py が cache の notified.<plugin> に残す)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTIFIER = HERE / "notifier-check.py"


def _extract_plugin_name(payload: dict) -> str | None:
    # Skill tool の payload には skill 名 (e.g., "harness-creator:run-skill-create") が入る想定。
    # plugin prefix が無い場合 (built-in skill 等) は None を返す。
    skill_name = (
        payload.get("tool_input", {}).get("skill")
        or payload.get("tool_input", {}).get("skill_name")
        or ""
    )
    if ":" in skill_name:
        return skill_name.split(":", 1)[0]
    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if payload.get("tool_name") != "Skill":
            return 0
        plugin = _extract_plugin_name(payload)
        if not plugin:
            return 0
        args = ["notify", "--plugin", plugin]
        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id:
            # `=` で繋ぐ。値が `-` で始まっても option と取り違えない
            args.append(f"--session-id={session_id}")
        # 起動するのは notifier-check.py だけ。argv の先頭 2 要素は呼び出しの場で固定する
        result = subprocess.run(["python3", str(NOTIFIER), *args],
                                capture_output=True, text=True, timeout=5)
        line = result.stdout.strip()
        if line:
            # 通知は作者に向けた版の食い違いで Claude の作業には関係しないので、
            # additionalContext (Claude への文脈) は付けず、利用者への表示だけにする
            print(json.dumps({"systemMessage": f"{plugin}: {line}"}, ensure_ascii=False))
    except Exception as exc:
        print(f"[notifier-hook] skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
