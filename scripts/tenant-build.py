#!/usr/bin/env python3
"""Validate and activate a tenant without reading secret values."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from tenant_runtime import TenantConfigError, credential_ref, load_tenant

ROOT = Path(__file__).resolve().parent.parent


def _safe_overlay(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise TenantConfigError(f"overlay escapes tenant directory: {relative}") from exc
    return path


def validate_bundles(tenant: dict) -> None:
    data = json.loads((ROOT / ".claude-plugin" / "bundles.json").read_text(encoding="utf-8"))
    known = {item["name"] for item in data.get("bundles", [])}
    requested = tenant.get("enabled_bundles")
    if not isinstance(requested, list) or not requested:
        raise TenantConfigError("enabled_bundles must be a non-empty list")
    unknown = sorted(set(requested) - known)
    if unknown:
        raise TenantConfigError(f"unknown enabled bundle(s): {', '.join(unknown)}")


def build(slug: str, *, activate: bool = True) -> list[str]:
    tenant = load_tenant(slug)
    validate_bundles(tenant)
    base = ROOT / "tenants" / slug
    overlays = tenant.get("overlays") or {}
    notion = _safe_overlay(base, str(overlays.get("notion_config") or ""))
    if not notion.is_file():
        raise TenantConfigError(f"required Notion overlay not found: {notion}")
    exports = {
        "HARNESS_ROOT": str(ROOT),
        "HARNESS_TENANT": slug,
        "HARNESS_KEYCHAIN_PREFIX": str(tenant["keychain_prefix"]),
        "NOTION_CONFIG_PATH": str(notion),
    }
    for field, env_name in (("party_a", "PARTY_A_JSON_PATH"), ("google_config", "GOOGLE_CONFIG_PATH")):
        relative = overlays.get(field)
        if relative:
            path = _safe_overlay(base, str(relative))
            if path.is_file():
                exports[env_name] = str(path)
    if activate:
        selector = ROOT / ".notion-config.json"
        if selector.exists() and not selector.is_symlink():
            raise TenantConfigError(f"refusing to replace non-symlink selector: {selector}")
        if selector.is_symlink() or os.path.lexists(selector):
            selector.unlink()
        selector.symlink_to(notion.relative_to(ROOT))
    commands: list[str] = []
    for key, value in exports.items():
        commands.append(f"export {key}={shlex.quote(value)}")
    for purpose, item in (tenant.get("credentials") or {}).items():
        if not item.get("required"):
            continue
        service, account = credential_ref(purpose, tenant)
        commands.append(
            "security add-generic-password -U "
            f"-s {shlex.quote(service)} -a {shlex.quote(account)} -w"
        )
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--check", action="store_true", help="validate without changing the active symlink")
    args = parser.parse_args()
    try:
        commands = build(args.slug, activate=not args.check)
    except (TenantConfigError, KeyError, json.JSONDecodeError) as exc:
        print(f"[tenant-build] FAIL: {exc}", file=sys.stderr)
        return 2
    print("# Evaluate these exports in the shell that will run tenant-aware plugins:")
    print("\n".join(commands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
