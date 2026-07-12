#!/usr/bin/env python3
"""Prepare or execute a guarded real Notion publish smoke test.

Default mode is non-mutating: it validates arguments and prints the exact
pipeline command. Add --execute to run the command and mutate the target page.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE = SCRIPT_DIR / "intake_publish_pipeline.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", dest="out_dir", help="output/<hint> directory")
    parser.add_argument("--hint", help="output/<hint> shorthand")
    parser.add_argument("--intake", help="explicit intake.json path")
    parser.add_argument("--manifest", help="explicit notion-manifest.json path")
    parser.add_argument("--page-url", dest="page_url", help="test Notion page URL")
    parser.add_argument("--page-id", dest="page_id", help="test Notion page ID")
    parser.add_argument("--database-id", dest="database_id")
    parser.add_argument("--execute", action="store_true", help="actually run Notion API update")
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif args.hint:
        out_dir = Path("output") / args.hint
    elif args.intake:
        out_dir = Path(args.intake).parent
    else:
        raise ValueError("--dir, --hint, or --intake is required")

    intake = Path(args.intake) if args.intake else out_dir / "intake.json"
    manifest = Path(args.manifest) if args.manifest else out_dir / "notion-manifest.json"
    return out_dir, intake, manifest


def main() -> int:
    args = parse_args()
    if not (args.page_url or args.page_id):
        print(
            "[smoke_notion_publish] target page is required: pass --page-url or --page-id. "
            "This smoke never creates a new page.",
            file=sys.stderr,
        )
        return 2

    try:
        out_dir, intake, manifest = resolve_paths(args)
    except ValueError as exc:
        print(f"[smoke_notion_publish] {exc}", file=sys.stderr)
        return 2

    missing = [str(p) for p in (intake, manifest) if not p.exists()]
    if missing:
        print(f"[smoke_notion_publish] missing required files: {missing}", file=sys.stderr)
        return 2

    cmd = [
        sys.executable,
        str(PIPELINE),
        "--intake",
        str(intake),
        "--manifest",
        str(manifest),
        "--revise",
    ]
    if args.page_id:
        cmd += ["--page-id", args.page_id]
    if args.page_url:
        cmd += ["--page-url", args.page_url]
    if args.database_id:
        cmd += ["--database-id", args.database_id]

    payload = {
        "status": "ready" if not args.execute else "executing",
        "execute": bool(args.execute),
        "out_dir": str(out_dir),
        "intake": str(intake),
        "manifest": str(manifest),
        "target": {"page_id": args.page_id or "", "page_url": args.page_url or ""},
        "command": cmd,
        "note": "No Notion mutation was performed. Re-run with --execute to update the target page."
        if not args.execute
        else "Executing guarded update against the specified Notion page.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.execute:
        return 0
    result = subprocess.run(cmd)
    return result.returncode if result.returncode is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
