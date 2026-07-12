#!/usr/bin/env python3
# /// script
# name: test-self-regenerate
# version: 0.1.0
# purpose: creator-kit の対象 Skill を再生成して差分が閾値内かを検証（self-hosting drift 検知）
# inputs:
#   - --target: 検証対象 Skill ディレクトリ（必須）
#   - --max-diff-lines: 許容する差分行数（既定 50）
#   - --regenerate-cmd: 再生成コマンド（既定 echo のみで dry-run）
# outputs:
#   - stdout: 差分件数とサンプル
#   - exit: 0=OK / 1=drift 検知 / 2=usage
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, B]
# network: false
# write-scope: output-dir
# ///
"""creator-kit 自身を再生成して差分行数で drift を検知する。"""
from __future__ import annotations
import argparse
import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--max-diff-lines", type=int, default=50)
    ap.add_argument("--regenerate-cmd", default="")
    args = ap.parse_args()

    target = Path(args.target)
    if not target.is_dir():
        print(f"error: target not a directory: {target}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmpdir:
        regen = Path(tmpdir) / target.name
        if args.regenerate_cmd:
            shutil.copytree(target, regen)
            subprocess.run(
                args.regenerate_cmd.split(),
                cwd=regen,
                check=False,
            )
        else:
            shutil.copytree(target, regen)
            print(f"warning: --regenerate-cmd not provided, comparing to identical copy", file=sys.stderr)

        diff_total = 0
        samples: list[str] = []
        for orig in sorted(target.rglob("*")):
            if not orig.is_file():
                continue
            rel = orig.relative_to(target)
            new = regen / rel
            if not new.is_file():
                diff_total += 1
                samples.append(f"missing: {rel}")
                continue
            a = orig.read_text(encoding="utf-8", errors="replace").splitlines()
            b = new.read_text(encoding="utf-8", errors="replace").splitlines()
            d = list(difflib.unified_diff(a, b, n=0))
            diff_lines = sum(1 for ln in d if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))
            if diff_lines:
                diff_total += diff_lines
                if len(samples) < 5:
                    samples.append(f"{rel}: {diff_lines} lines")

        print(f"diff_total={diff_total} max={args.max_diff_lines}")
        for s in samples:
            print(f"  {s}")
        return 0 if diff_total <= args.max_diff_lines else 1


if __name__ == "__main__":
    sys.exit(main())
