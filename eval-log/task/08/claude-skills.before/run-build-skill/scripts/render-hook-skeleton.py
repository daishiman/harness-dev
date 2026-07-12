#!/usr/bin/env python3
# /// script
# name: render-hook-skeleton
# purpose: Generate a hook script skeleton for a selected hook event.
# inputs:
#   - argv: --skill-name, --event, --out
# outputs:
#   - file: generated hook script
#   - stdout: generated path
# contexts: [A, B]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Hook event 別の hook script skeleton を生成 (stdlib only, 設計書10章§設計判断5)."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


TEMPLATE = '''#!/usr/bin/env python3
# /// script
# name: hook-{name}-{event_lc}
# purpose: {event} hook for skill `{name}`.
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""{event} hook (TODO: 実装する).

設計書10章§設計判断5 に従い、stdin から JSON を受け取り、
contract 違反は exit 2 で block、許可は exit 0、警告は stderr 出力 + exit 0。
"""
from __future__ import annotations
import json
import sys


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {{}}
    except Exception:
        return 0
    # TODO(human): {event} 固有の判定ロジックを実装する。
    # 例: tool_input の path が deny pattern に match するなら return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        print(f"already exists, skip: {out}", file=sys.stderr)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(
        name=args.skill_name, event=args.event, event_lc=args.event.lower()
    ))
    out.chmod(0o755)
    print(f"generated: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
