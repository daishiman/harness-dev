#!/usr/bin/env python3
# /// script
# name: sink-local
# purpose: Write payloads to local files under Sink Contract v1.0.
# inputs:
#   - argv: --payload, --params, optional --dry-run
# outputs:
#   - stdout: Sink Contract JSON result
#   - stderr: sanitized adapter errors
# contexts: [E]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Local filesystem sink adapter. Sink Contract v1.0準拠。"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path


def slugify(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        payload = json.loads(Path(args.payload).read_text())
        params = json.loads(Path(args.params).read_text())
    except Exception as e:
        print(json.dumps({"status": "failure", "adapter": "local", "errors": [f"invalid input: {e}"]}))
        sys.exit(1)

    base = Path(params.get("path", "out/"))
    fmt = params.get("format", "markdown")
    conflict = params.get("on_conflict", "append")

    if not args.dry_run:
        base.mkdir(parents=True, exist_ok=True)
    name = slugify(payload.get("title") or payload.get("kind", "untitled"))
    ext = {"markdown": "md", "json": "json", "jsonl": "jsonl"}.get(fmt, "txt")
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    out_path = base / f"{digest}-{name}.{ext}"

    if args.dry_run:
        print(json.dumps({"status": "success", "adapter": "local", "location": str(out_path), "external_id": digest, "dry_run": True, "errors": []}))
        return

    try:
        if out_path.exists() and conflict == "error":
            print(json.dumps({"status": "failure", "adapter": "local", "errors": [f"file exists: {out_path}"]}))
            sys.exit(1)
        if out_path.exists() and conflict == "skip":
            print(json.dumps({"status": "success", "adapter": "local", "location": str(out_path), "external_id": digest, "errors": []}))
            return
        if fmt == "markdown":
            content = f"# {payload.get('title','')}\n\n{payload.get('body','')}\n"
            if conflict == "append" and out_path.exists():
                out_path.write_text(out_path.read_text() + "\n---\n" + content)
            else:
                out_path.write_text(content)
        elif fmt in ("json",):
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        elif fmt == "jsonl":
            line = json.dumps(payload, ensure_ascii=False) + "\n"
            with out_path.open("a") as f:
                f.write(line)
        else:
            out_path.write_text(payload.get("body", ""))
    except Exception as e:
        print(json.dumps({"status": "failure", "adapter": "local", "errors": [str(e)]}))
        sys.exit(1)

    print(json.dumps({"status": "success", "adapter": "local", "location": str(out_path), "external_id": digest, "errors": []}))


if __name__ == "__main__":
    main()
