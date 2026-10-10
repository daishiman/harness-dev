#!/usr/bin/env python3
# /// script
# name: render-pkg-findings
# version: 0.2.0
# purpose: validate-plugin-package.py の findings JSON を人が読む markdown レポートへ変換する
# inputs:
#   - argv: findings JSON のパス、または - で stdin
# outputs:
#   - stdout: markdown レポート
#   - stderr: 入力エラーの診断 (error: ...)
#   - exit: 0=変換した / 2=読めない・JSON でない・findings JSON の形でない
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: none
# ///
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
    try:
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # ValueError は JSONDecodeError と UnicodeDecodeError の両方を含む
        print(f"error: cannot read findings JSON: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    try:
        report = render(data)
    except (KeyError, TypeError, AttributeError) as e:
        print(f"error: not a findings JSON of validate-plugin-package: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
