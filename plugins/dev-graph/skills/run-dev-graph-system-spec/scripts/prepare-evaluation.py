#!/usr/bin/env python3
# /// script
# name: prepare-evaluation
# purpose: 開始時の C24 receipt を検証し、cwd に依存しない evaluator args を出力する。
# inputs: ["argv: --context-receipt PATH --output eval-log/REPORT.json"]
# outputs: ["stdout: JSON {skill_args, spec_dir, output, evidence_ref, context_sha256}"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def absolute(value: object) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ValueError("receipt paths must be absolute")
    return Path(value).resolve(strict=True)


def prepare(receipt_path: Path, report_ref: str) -> dict:
    original = receipt_path.read_bytes()
    pinned = json.loads(original)
    if not isinstance(pinned, dict) or pinned.get("mode") != "write":
        raise ValueError("a write-mode C24 receipt is required")
    root = absolute(pinned.get("repo_root"))
    roots = pinned.get("content_roots")
    if not isinstance(roots, dict) or absolute(roots.get("repository")) != root:
        raise ValueError("repo_root and content_roots.repository disagree")
    config = Path(pinned["local_state_paths"]["config"])
    if not config.is_absolute():
        raise ValueError("receipt config must be absolute")
    config.resolve().relative_to(root)
    # C24 を固定済み root に対して再検証する。cwd を新しい authority として探索しない。
    resolver = Path(__file__).resolve().parents[3] / "scripts/resolve-repo-context.py"
    proc = subprocess.run([sys.executable, "-B", str(resolver), "--repo-root", str(root),
                           "--config", str(config), "--mode", "write"],
                          capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ValueError(f"C24 verification failed: {proc.stderr.strip()}")
    current = json.loads(proc.stdout)
    for key in ("repo_root", "repository_id", "worktree_id", "git_common_dir", "git_dir"):
        if not pinned.get(key) or pinned[key] != current.get(key):
            raise ValueError(f"C24 identity changed: {key}")
    for key in ("repository", "system_spec"):
        if roots.get(key) != current["content_roots"].get(key):
            raise ValueError(f"C24 content root changed: {key}")
    spec = absolute(roots.get("system_spec"))
    spec.relative_to(root)
    if not spec.is_dir() or spec == root:
        raise ValueError("system_spec must be a directory below the repository")
    relative = Path(report_ref)
    if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2
            or relative.parts[0] != "eval-log" or relative.suffix != ".json"):
        raise ValueError("report must be a repository-relative eval-log/*.json path")
    output = root / relative
    for candidate in (output, *output.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError("report path must not traverse symlinks")
    output = output.resolve()
    output.relative_to(root / "eval-log")
    if output.exists() and not output.is_file():
        raise ValueError("report path is not a regular file")
    return {"skill_args": shlex.join(["--spec-dir", str(spec), "--output", str(output)]),
            "spec_dir": str(spec), "output": str(output),
            "evidence_ref": relative.as_posix(),
            "context_sha256": hashlib.sha256(original).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-receipt", type=Path, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.context_receipt, args.output)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"evaluation_context_invalid: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
