#!/usr/bin/env python3
"""Verify and install a tenant core archive, then write an install receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def verify_checksum(archive: Path, checksum_file: Path) -> str:
    expected = checksum_file.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"checksum mismatch: expected {expected}, got {actual}")
    return actual


def safe_extract(archive: Path, target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            destination = (target / member.name).resolve()
            try:
                destination.relative_to(target.resolve())
            except ValueError as exc:
                raise ValueError(f"archive path escapes target: {member.name}") from exc
            if member.issym() or member.islnk():
                raise ValueError(f"links are not allowed in release archive: {member.name}")
        manifest_member = tar.getmember("release-manifest.json")
        manifest = json.load(tar.extractfile(manifest_member))
        tar.extractall(target, filter="data")
    return manifest


def install(archive: Path, checksum_file: Path, target: Path) -> Path:
    checksum = verify_checksum(archive, checksum_file)
    manifest = safe_extract(archive, target)
    receipt = {
        "schema_version": 1,
        "archive": archive.name,
        "sha256": checksum,
        "source_commit": manifest.get("source_commit"),
        "core_compat": manifest.get("core_compat"),
        "plugins": manifest.get("plugins"),
    }
    path = target / ".harness-install-receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("checksum", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    try:
        receipt = install(args.archive, args.checksum, args.target)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"[install-tenant-bundle] FAIL: {exc}")
        return 2
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
