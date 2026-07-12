#!/usr/bin/env python3
"""Build a deterministic, distributable core archive for a tenant release."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEVER_DISTRIBUTE = {"harness-creator", "prompt-creator", "plugin-dev-planner"}


def selected_plugins(tenant: dict, bundles: dict) -> list[str]:
    by_name = {item["name"]: item for item in bundles.get("bundles", [])}
    selected: set[str] = set()
    for bundle_name in tenant.get("enabled_bundles") or []:
        if bundle_name not in by_name:
            raise ValueError(f"unknown bundle: {bundle_name}")
        selected.update(by_name[bundle_name].get("plugins") or [])
    forbidden = selected & NEVER_DISTRIBUTE
    if forbidden:
        raise ValueError(f"bundle includes NEVER_DISTRIBUTE plugin(s): {sorted(forbidden)}")
    return sorted(selected)


def git_provenance(allow_dirty: bool) -> tuple[str, bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    if dirty and not allow_dirty:
        raise ValueError("worktree is dirty; release bundles require a clean reviewed commit")
    return commit, dirty


def _tar_bytes(paths: list[Path], manifest: dict) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
        info = tarfile.TarInfo("release-manifest.json")
        info.size = len(payload)
        info.mtime = 0
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(payload))
        for path in sorted(paths, key=lambda item: item.as_posix()):
            for child in ([path] if path.is_file() else sorted(path.rglob("*"))):
                if child.is_symlink() or not child.is_file() or "__pycache__" in child.parts:
                    continue
                info = tar.gettarinfo(str(child), arcname=child.relative_to(ROOT).as_posix())
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with child.open("rb") as stream:
                    tar.addfile(info, stream)
    return buffer.getvalue()


def build(slug: str, output_dir: Path, allow_dirty: bool = False) -> tuple[Path, Path]:
    tenant_path = ROOT / "tenants" / slug / "tenant.json"
    tenant = json.loads(tenant_path.read_text(encoding="utf-8"))
    bundles = json.loads((ROOT / ".claude-plugin" / "bundles.json").read_text(encoding="utf-8"))
    plugins = selected_plugins(tenant, bundles)
    commit, dirty = git_provenance(allow_dirty)
    manifest = {
        "schema_version": 1,
        "tenant_slug": slug,
        "source_commit": commit,
        "dirty": dirty,
        "core_compat": tenant.get("core_compat"),
        "bundles": tenant.get("enabled_bundles"),
        "plugins": plugins,
    }
    paths = [ROOT / "plugins" / name for name in plugins]
    paths += [ROOT / ".claude-plugin" / "marketplace.json", ROOT / ".claude-plugin" / "bundles.json"]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
    raw_tar = _tar_bytes(paths, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"harness-core-{slug}-{commit[:12]}.tar.gz"
    with archive.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as gz:
            gz.write(raw_tar)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    archive.with_suffix(archive.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return archive, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--allow-dirty", action="store_true", help="local verification only; never publish")
    args = parser.parse_args()
    try:
        archive, checksum = build(args.slug, args.output, args.allow_dirty)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"[build-tenant-bundle] FAIL: {exc}", file=sys.stderr)
        return 2
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
