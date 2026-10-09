#!/usr/bin/env python3
# /// script
# name: publish-staged-files
# purpose: 承認済みmanifestと下書きのハッシュを照合して正式保存する（中央guard execute専用）。
# inputs: ["--manifest absolute-json", "--manifest-sha256 SHA256"]
# outputs: ["stdout JSON receipt", "exit 0=saved / 2=contract or IO error"]
# contexts: [E]
# network: false
# write-scope: manifest.roots配下の明示されたファイルのみ
# dependencies: []
# ///
"""Publish exact staged bytes; callers run this argv only through guard execute.

All entries are checked before the first mutation. Each replacement is atomic,
but the batch is not transactional; a mid-write IO error must be reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

SHA = re.compile(r"^[0-9a-f]{64}$")


class PublicationError(ValueError):
    def __init__(self, error: str, saved: list[dict], failed_target: Path):
        super().__init__(error)
        self.saved = saved.copy()
        self.failed_target = str(failed_target)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def absolute(raw: object) -> Path:
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise ValueError("absolute path required")
    path = Path(raw)
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("parent traversal or symlink is forbidden")
    return path.resolve()


def current_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"target is not a regular file: {path}")
    return digest(path.read_bytes())


def publish(manifest_path: Path, expected_hash: str) -> dict:
    if not SHA.fullmatch(expected_hash):
        raise ValueError("manifest SHA256 is invalid")
    raw = absolute(str(manifest_path)).read_bytes()
    if digest(raw) != expected_hash:
        raise ValueError("manifest changed after preview")
    plan = json.loads(raw)
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    stage = absolute(plan.get("stage_root"))
    roots = plan.get("roots")
    entries = plan.get("entries")
    if not stage.is_dir() or not isinstance(roots, dict) or not roots or not isinstance(entries, list) or not entries:
        raise ValueError("stage_root, roots and nonempty entries required")
    resolved = {key: absolute(value) for key, value in roots.items()}
    for root in resolved.values():
        if stage == root or stage.is_relative_to(root) or root.is_relative_to(stage):
            raise ValueError("staging and official roots must be disjoint")
    prepared = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("root") not in resolved:
            raise ValueError("entry root is not declared")
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("entry path must be a relative POSIX path")
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts or str(rel) == ".":
            raise ValueError("entry escapes declared root")
        target = absolute(str(resolved[entry["root"]] / relative))
        if not target.is_relative_to(resolved[entry["root"]]) or target in seen:
            raise ValueError("duplicate target or root escape")
        seen.add(target)
        old = entry.get("old_sha256")
        if "old_sha256" not in entry or (old is not None and (not isinstance(old, str) or not SHA.fullmatch(old))):
            raise ValueError("old_sha256 must explicitly be SHA256 or null")
        if current_hash(target) != old:
            raise ValueError(f"official file changed after staging: {target}")
        operation = entry.get("operation")
        payload = None
        if operation == "write":
            source = absolute(entry.get("source"))
            if not source.is_relative_to(stage) or not source.is_file():
                raise ValueError("source must be a regular file inside stage_root")
            payload = source.read_bytes()
            if digest(payload) != entry.get("new_sha256"):
                raise ValueError("draft changed after validation/preview")
        elif operation != "delete" or old is None:
            raise ValueError("operation must be write or delete of an existing file")
        prepared.append((target, old, payload))
    # Writes precede deletes, so an archive copy is saved before the original is removed.
    prepared.sort(key=lambda item: item[2] is None)
    saved = []
    for target, old, payload in prepared:
        try:
            absolute(str(target))  # recheck path components before use
            if current_hash(target) != old:
                raise ValueError(f"official file changed during publication: {target}")
            if payload is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(prefix=".ubm-publish-", dir=target.parent)
                try:
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, target)
                finally:
                    Path(temporary).unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            raise PublicationError(str(exc), saved, target) from exc
        saved.append({"path": str(target), "operation": "delete" if payload is None else "write", "sha256": None if payload is None else digest(payload)})
    return {"manifest_sha256": expected_hash, "saved": saved, "batch_atomic": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        receipt = publish(Path(args.manifest), args.manifest_sha256)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"saved": getattr(exc, "saved", []),
                          "failed_target": getattr(exc, "failed_target", None),
                          "error": str(exc), "batch_atomic": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
