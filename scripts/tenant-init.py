#!/usr/bin/env python3
"""Create a tenant scaffold from tenants/_template."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from tenant_runtime import SLUG_RE

ROOT = Path(__file__).resolve().parent.parent
TENANTS = ROOT / "tenants"


def _materialize_placeholders(target: Path, slug: str, display_name: str) -> None:
    """Replace public scaffold placeholders without creating secret overlays."""
    for path in target.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        rendered = text.replace("company-slug", slug).replace("Company Name", display_name)
        if rendered != text:
            path.write_text(rendered, encoding="utf-8")


def known_prefixes() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in TENANTS.glob("*/tenant.json"):
        if path.parent.name == "_template":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prefix = str(data.get("keychain_prefix") or "")
        if prefix:
            result[prefix] = path.parent.name
    return result


def create_tenant(slug: str, display_name: str | None = None, prefix: str | None = None) -> Path:
    prefix = prefix or slug
    resolved_display_name = display_name or slug
    if not SLUG_RE.fullmatch(slug) or not SLUG_RE.fullmatch(prefix):
        raise ValueError("slug and keychain prefix must be lowercase letters, digits, and hyphens")
    duplicate = known_prefixes().get(prefix)
    if duplicate and duplicate != slug:
        raise ValueError(f"keychain_prefix {prefix!r} is already used by tenant {duplicate!r}")
    source = TENANTS / "_template"
    target = TENANTS / slug
    if target.exists():
        raise FileExistsError(f"tenant already exists: {target}")
    shutil.copytree(source, target)
    _materialize_placeholders(target, slug, resolved_display_name)
    descriptor = target / "tenant.json"
    data = json.loads(descriptor.read_text(encoding="utf-8"))
    data.update(
        slug=slug,
        display_name=resolved_display_name,
        keychain_prefix=prefix,
        core_compat=None,
        notes="Complete local overlay files before tenant-build. Never store secrets here.",
    )
    descriptor.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--display-name")
    parser.add_argument("--keychain-prefix")
    args = parser.parse_args()
    try:
        target = create_tenant(args.slug, args.display_name, args.keychain_prefix)
    except (ValueError, FileExistsError) as exc:
        print(f"[tenant-init] FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"[tenant-init] created {target.relative_to(ROOT)}")
    print("[tenant-init] next: fill notion-config.json and any enabled optional overlays, then run tenant-build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
