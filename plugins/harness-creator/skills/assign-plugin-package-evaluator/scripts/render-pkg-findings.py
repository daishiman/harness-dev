#!/usr/bin/env python3
"""findings JSON → 人間可読 markdown レポート変換。"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def render(data: dict) -> str:
    lines = [
        f"# PKG Validator Report: {data['target_plugin']}",
        "",
        f"- run_id: `{data['run_id']}`",
        f"- package_mode: `{data['package_mode']}`",
        f"- verdict: pass={data['verdict']['pass']} fail={data['verdict']['fail']} "
        f"skip={data['verdict']['skip']} not_applicable={data['verdict']['not_applicable']}",
        "",
    ]
    for pkg_id, result in sorted(data["pkg_checks"].items()):
        status_emoji = {"pass": "OK", "fail": "FAIL", "skip": "SKIP", "not_applicable": "N/A"}[result["status"]]
        lines.append(f"## [{status_emoji}] {pkg_id}")
        if result.get("skip_reason"):
            lines.append(f"- skip_reason: {result['skip_reason']}")
        for f in result.get("findings", []):
            lines.append(f"- **{f['id']}** ({f['severity']}) `{f['location']}`")
            lines.append(f"    - evidence: {f['evidence']}")
            if f.get("suggested_fix"):
                lines.append(f"    - fix: {f['suggested_fix']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="findings JSON path or - for stdin")
    args = ap.parse_args()
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(args.input).read_text())
    print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
