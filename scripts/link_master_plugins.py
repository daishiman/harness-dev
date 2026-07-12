#!/usr/bin/env python3
"""Check or create one-way plugin symlinks from a reference repo to harness."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def profile_names(profile: str) -> list[str]:
    data = json.loads((ROOT / ".claude-plugin" / "link-profiles.json").read_text(encoding="utf-8"))
    try:
        names = data["profiles"][profile]
    except KeyError as exc:
        raise ValueError(f"unknown link profile: {profile}") from exc
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate plugin in profile: {profile}")
    return names


def check(reference_root: Path, profile: str) -> list[str]:
    failures: list[str] = []
    for name in profile_names(profile):
        canonical = (ROOT / "plugins" / name).resolve()
        link = reference_root / "plugins" / name
        if not canonical.is_dir():
            failures.append(f"canonical plugin missing: {canonical}")
        elif not link.is_symlink():
            failures.append(f"not a symlink: {link}")
        elif link.resolve() != canonical:
            failures.append(f"wrong target: {link} -> {link.resolve()} (expected {canonical})")
    return failures


def apply(reference_root: Path, profile: str, backup_root: Path | None = None) -> Path:
    if reference_root.resolve() == ROOT.resolve():
        raise ValueError("reference root must differ from harness root")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root or reference_root / ".harness-link-backup" / stamp
    for name in profile_names(profile):
        canonical = (ROOT / "plugins" / name).resolve()
        if not canonical.is_dir():
            raise FileNotFoundError(canonical)
        link = reference_root / "plugins" / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() and link.resolve() == canonical:
            continue
        if os.path.lexists(link):
            backup.mkdir(parents=True, exist_ok=True)
            shutil.move(str(link), str(backup / name))
        link.symlink_to(canonical, target_is_directory=True)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_root", type=Path)
    parser.add_argument("--profile", default="master-link-set")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-root", type=Path)
    args = parser.parse_args()
    try:
        if args.check:
            failures = check(args.reference_root, args.profile)
            if failures:
                for failure in failures:
                    print(f"[link-master-plugins] FAIL: {failure}", file=sys.stderr)
                return 1
            print(f"[link-master-plugins] OK: {args.profile}")
        else:
            backup = apply(args.reference_root, args.profile, args.backup_root)
            print(f"[link-master-plugins] linked {args.profile}; backup={backup}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[link-master-plugins] FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
