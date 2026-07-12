#!/usr/bin/env python3
# /// script
# name: tenant_runtime
# version: 0.1.0
# purpose: active tenant の同定と credential 参照名 (service/account/scoped env) の解決を行う
#          vendored 共有 library。secret 値そのものは読まない・保存しない。
# inputs:
#   - env: HARNESS_TENANT / HARNESS_ROOT / HARNESS_TENANT_CONFIG
#   - files: .notion-config.json (tenant symlink) / tenants/<slug>/tenant.json
# outputs:
#   - return: tenant slug / tenant config dict / credential 参照名を呼び出し側 module へ返す (stdout 出力なし)
#   - exit: なし (import して関数利用する library)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Tenant identity and credential-reference resolution shared by plugins.

This module never reads or stores secret values. It resolves only the active
tenant, credential service/account names, and tenant-scoped environment names.
Plugins vendor this file so standalone installs do not import across plugin
boundaries. ``scripts/lint-vendored-ssot.py`` enforces byte parity.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class TenantConfigError(RuntimeError):
    """Tenant selection or public contract is invalid."""


def _candidate_roots(start: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("HARNESS_ROOT", "").strip()
    if explicit:
        roots.append(Path(explicit).expanduser())
    for anchor in (start or Path.cwd(), Path(__file__).resolve()):
        resolved = anchor.resolve()
        roots.extend([resolved, *resolved.parents])
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root not in seen:
            unique.append(root)
            seen.add(root)
    return unique


def find_harness_root(start: Path | None = None) -> Path | None:
    for root in _candidate_roots(start):
        if (root / "tenants").is_dir():
            return root
    return None


def _slug_from_notion_symlink(root: Path) -> str | None:
    selector = root / ".notion-config.json"
    if not selector.is_symlink():
        return None
    try:
        target = selector.resolve(strict=False)
        relative = target.relative_to((root / "tenants").resolve())
    except (OSError, ValueError):
        return None
    return relative.parts[0] if len(relative.parts) >= 2 else None


def active_tenant_slug(start: Path | None = None) -> str:
    slug = os.environ.get("HARNESS_TENANT", "").strip()
    root = find_harness_root(start)
    linked = _slug_from_notion_symlink(root) if root else None
    if slug and linked and slug != linked:
        raise TenantConfigError(
            f"HARNESS_TENANT={slug!r} conflicts with .notion-config.json tenant {linked!r}"
        )
    slug = slug or linked or ""
    if not slug:
        raise TenantConfigError(
            "active tenant is not selected; set HARNESS_TENANT or activate a tenant symlink"
        )
    if not SLUG_RE.fullmatch(slug):
        raise TenantConfigError(f"invalid tenant slug: {slug!r}")
    return slug


def tenant_config_path(slug: str | None = None, start: Path | None = None) -> Path:
    explicit = os.environ.get("HARNESS_TENANT_CONFIG", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
    else:
        root = find_harness_root(start)
        if root is None:
            raise TenantConfigError(
                "tenant root not found; set HARNESS_ROOT or HARNESS_TENANT_CONFIG"
            )
        path = root / "tenants" / (slug or active_tenant_slug(start)) / "tenant.json"
    if not path.is_file():
        raise TenantConfigError(f"tenant config not found: {path}")
    return path


def load_tenant(slug: str | None = None, start: Path | None = None) -> dict[str, Any]:
    path = tenant_config_path(slug, start)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TenantConfigError(f"invalid tenant config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TenantConfigError(f"tenant config must be an object: {path}")
    expected_slug = slug or active_tenant_slug(start)
    if data.get("slug") != expected_slug or path.parent.name != expected_slug:
        raise TenantConfigError(
            f"tenant slug mismatch: selected={expected_slug!r}, file={data.get('slug')!r}, dir={path.parent.name!r}"
        )
    return data


def keychain_prefix(tenant: Mapping[str, Any] | None = None) -> str:
    prefix = os.environ.get("HARNESS_KEYCHAIN_PREFIX", "").strip()
    if not prefix:
        prefix = str((tenant or load_tenant()).get("keychain_prefix") or "").strip()
    if not prefix:
        raise TenantConfigError("keychain_prefix is required; refusing tenant-independent fallback")
    if not SLUG_RE.fullmatch(prefix):
        raise TenantConfigError(f"invalid keychain_prefix: {prefix!r}")
    return prefix


def credential_ref(
    purpose: str, tenant: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    tenant_data = dict(tenant or load_tenant())
    prefix = keychain_prefix(tenant_data)
    credential = (tenant_data.get("credentials") or {}).get(purpose) or {}
    service = str(credential.get("service") or f"{purpose}.{prefix}").strip()
    account = str(credential.get("account") or prefix).strip()
    if not service or not account:
        raise TenantConfigError(f"credential reference is incomplete: {purpose}")
    return service, account


def scoped_secret_env(purpose: str, tenant: Mapping[str, Any] | None = None) -> str:
    tenant_data = dict(tenant or load_tenant())
    slug = str(tenant_data.get("slug") or "").upper().replace("-", "_")
    key = purpose.upper().replace("-", "_")
    return f"HARNESS_SECRET_{slug}_{key}"
