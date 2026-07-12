#!/usr/bin/env python3
"""Generate plugin rollback script from rollback.template.sh (phase2-04 contract)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "eval-log/task/phase2-04/rollback.template.sh"
DEFAULT_PARTITION = REPO_ROOT / "eval-log/task/phase2-02/partition-plan.json"
DEFAULT_MIGRATION_ORDER = REPO_ROOT / "eval-log/task/phase2-03/migration-order.json"
# snapshot 一次保存先は phase2-04 配下に統一 (phase2-06 との循環依存を解消)。
DEFAULT_SNAPSHOT_BASE = REPO_ROOT / "eval-log/task/phase2-04/snapshots"

REQUIRED_SNAPSHOT_FILES = (
    "settings.before.json",
    "settings.before.sha256",
    "git-status.before.txt",
    "claude-symlinks.before.txt",
)


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate rollback-<plugin>.sh from template")
    p.add_argument("--plugin", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--snapshot-dir", default=None)
    p.add_argument("--partition", default=str(DEFAULT_PARTITION))
    p.add_argument("--migration-order", default=str(DEFAULT_MIGRATION_ORDER))
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def load_partition(path: Path, plugin: str) -> dict:
    if not path.is_file():
        log(f"[gen-rollback][ERROR] partition not found: {path}")
        sys.exit(3)
    data = json.loads(path.read_text())
    for part in data.get("partitions", []):
        if part.get("name") == plugin:
            return part
    log(f"[gen-rollback][ERROR] plugin '{plugin}' not in {path}")
    sys.exit(3)


def resolve_snapshot_id(snapshot_dir: Path) -> str:
    sid = snapshot_dir / "snapshot-id.txt"
    if sid.is_file():
        return sid.read_text().strip() or "unknown"
    name = snapshot_dir.name
    return name if name else "unknown"


def check_snapshot(snapshot_dir: Path) -> None:
    missing = [snapshot_dir / name for name in REQUIRED_SNAPSHOT_FILES if not (snapshot_dir / name).is_file()]
    if missing:
        for path in missing:
            log(f"[gen-rollback][ERROR] missing required snapshot: {path}")
        sys.exit(1)
    # sha256 改竄/破損検査: settings.before.sha256 の先頭フィールドが
    # settings.before.json の sha256 と一致することを必須化。
    settings_json = snapshot_dir / "settings.before.json"
    sha_file = snapshot_dir / "settings.before.sha256"
    try:
        expected = sha_file.read_text().strip().split()[0]
    except (OSError, IndexError):
        log(f"[gen-rollback][ERROR] cannot read sha256 record: {sha_file}")
        sys.exit(1)
    actual = hashlib.sha256(settings_json.read_bytes()).hexdigest()
    if expected.lower() != actual.lower():
        log(
            f"[gen-rollback][ERROR] snapshot sha256 mismatch: "
            f"expected={expected} actual={actual} file={settings_json}"
        )
        sys.exit(1)


def build_moved_paths_literal(part: dict) -> str:
    # Sort lexicographically for byte-stable reproducible output across runs.
    rels = sorted({f["rel"] for f in part.get("files", []) if "rel" in f})
    if not rels:
        return "MOVED_PATHS=()"
    quoted = " ".join(shlex.quote(r) for r in rels)
    return f"MOVED_PATHS=({quoted})"


def render(template: str, plugin: str, snapshot_id: str, moved_line: str) -> str:
    out = template.replace(
        'PLUGIN="${PLUGIN:-PLACEHOLDER_PLUGIN}"',
        f'PLUGIN="${{PLUGIN:-{plugin}}}"',
    )
    out = out.replace(
        'SNAPSHOT_ID="${SNAPSHOT_ID:-PLACEHOLDER_SNAPSHOT}"',
        f'SNAPSHOT_ID="${{SNAPSHOT_ID:-{snapshot_id}}}"',
    )
    out = out.replace(
        'MOVED_PATHS=("${MOVED_PATHS_PLACEHOLDER:-}")',
        moved_line,
    )
    return out


def validate_out_path(out: Path) -> None:
    parent = out.parent
    if not parent.is_dir():
        log(f"[gen-rollback][ERROR] out parent dir does not exist: {parent}")
        sys.exit(3)
    if not os.access(parent, os.W_OK):
        log(f"[gen-rollback][ERROR] out parent dir not writable: {parent}")
        sys.exit(3)


def bash_syntax_check(path: Path) -> bool:
    res = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    if res.returncode != 0:
        log(f"[gen-rollback][ERROR] bash -n failed: {res.stderr.strip()}")
        return False
    return True


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not TEMPLATE_PATH.is_file():
        log(f"[gen-rollback][ERROR] template missing: {TEMPLATE_PATH}")
        return 3

    partition_path = Path(args.partition)
    part = load_partition(partition_path, args.plugin)

    snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else DEFAULT_SNAPSHOT_BASE / args.plugin
    out_path = Path(args.out).resolve()
    if not args.dry_run:
        check_snapshot(snapshot_dir)
        validate_out_path(out_path)

    template = TEMPLATE_PATH.read_text()
    snapshot_id = resolve_snapshot_id(snapshot_dir)
    moved_line = build_moved_paths_literal(part)
    content = render(template, args.plugin, snapshot_id, moved_line)

    if args.dry_run:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    out_path.write_text(content)
    if not bash_syntax_check(out_path):
        try:
            out_path.unlink()
        except OSError:
            pass
        return 2
    out_path.chmod(0o755)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
