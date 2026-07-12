#!/usr/bin/env python3
# /// script
# name: render-settings-proposal
# purpose: Generate a settings.json hook merge proposal from a skill brief.
# inputs:
#   - argv: --skill-name, --brief, --out
# outputs:
#   - file: settings proposal JSON
#   - stderr: proposal path and manual merge notice
# contexts: [A, B]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""settings.json マージ案を proposal として生成 (人間承認後に手動マージ前提)."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--brief", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    brief = json.loads(Path(args.brief).read_text())
    events = brief.get("hook_events", [])
    proposal: dict = {"hooks": {}}
    for ev in events:
        proposal["hooks"][ev] = [{
            "hooks": [{
                "type": "command",
                "command": f"python3 {{{{SCRIPT_ROOT}}}}/hook-{args.skill_name}-{ev.lower()}.py"
            }]
        }]
    # permissions.deny 推奨セット (空配列で skeleton)
    proposal["permissions"] = {
        "deny": [
            f"# TODO: skill `{args.skill_name}` 固有の deny rule を追加"
        ]
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(proposal, indent=2, ensure_ascii=False))
    print(f"proposal written: {args.out}", file=sys.stderr)
    print("Review and merge manually into .claude/settings.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
