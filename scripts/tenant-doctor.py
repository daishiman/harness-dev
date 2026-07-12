#!/usr/bin/env python3
"""Fail-closed structural and credential readiness checks for a tenant."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from tenant_runtime import TenantConfigError, credential_ref, load_tenant

ROOT = Path(__file__).resolve().parent.parent
TENANTS = ROOT / "tenants"

PLUGIN_DOCTORS = {
    "company-master": ["plugins/company-master/scripts/company_master.py", "doctor"],
    "mf-kessai-invoice-check": ["plugins/mf-kessai-invoice-check/lib/mfk_doctor.py", "--json"],
    "notion-gmail-send": ["plugins/notion-gmail-send/lib/setup_doctor.py"],
    "contract-generator": ["plugins/contract-generator/lib/setup_doctor.py"],
}


def _compare_contract(example: Any, actual: Any, path: str = "$") -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    if type(example) is not type(actual):
        return [f"{path}: expected {type(example).__name__}, got {type(actual).__name__}"], warnings
    if isinstance(example, dict):
        for key, value in example.items():
            if key not in actual:
                failures.append(f"{path}.{key}: missing")
            else:
                child_failures, child_warnings = _compare_contract(value, actual[key], f"{path}.{key}")
                failures.extend(child_failures)
                warnings.extend(child_warnings)
        for key in actual.keys() - example.keys():
            warnings.append(f"{path}.{key}: unknown key")
    return failures, warnings


def _all_prefixes() -> tuple[dict[str, str], list[str]]:
    owners: dict[str, str] = {}
    failures: list[str] = []
    for path in TENANTS.glob("*/tenant.json"):
        if path.parent.name == "_template":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: invalid JSON: {exc}")
            continue
        prefix = str(data.get("keychain_prefix") or "")
        if prefix in owners:
            failures.append(f"duplicate keychain_prefix {prefix!r}: {owners[prefix]}, {path.parent.name}")
        owners[prefix] = path.parent.name
    return owners, failures


def _enabled_plugins(tenant: dict[str, Any]) -> set[str]:
    bundles_path = ROOT / ".claude-plugin" / "bundles.json"
    bundles = json.loads(bundles_path.read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in bundles.get("bundles", [])}
    enabled: set[str] = set()
    for name in tenant.get("enabled_bundles") or []:
        if name not in by_name:
            raise TenantConfigError(f"unknown enabled bundle: {name}")
        enabled.update(by_name[name].get("plugins") or [])
    return enabled


def _plugin_doctor_env(slug: str, tenant: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HARNESS_ROOT=str(ROOT),
        HARNESS_TENANT=slug,
        HARNESS_KEYCHAIN_PREFIX=str(tenant["keychain_prefix"]),
        CLAUDE_PROJECT_DIR=str(ROOT),
    )
    base = TENANTS / slug
    overlays = tenant.get("overlays") or {}
    for field, names in {
        "notion_config": ("NOTION_CONFIG_PATH", "NOTION_GMAIL_CONFIG"),
        "party_a": ("PARTY_A_JSON_PATH",),
        "google_config": ("GOOGLE_CONFIG_PATH",),
    }.items():
        relative = overlays.get(field)
        if not relative:
            continue
        path = base / str(relative)
        if path.is_file():
            for name in names:
                env[name] = str(path)
    return env


def _run_plugin_doctors(
    slug: str, tenant: dict[str, Any]
) -> tuple[list[str], list[str], dict[str, Any]]:
    failures: list[str] = []
    warnings: list[str] = []
    statuses: dict[str, Any] = {}
    enabled = _enabled_plugins(tenant)
    env = _plugin_doctor_env(slug, tenant)
    for plugin, argv in PLUGIN_DOCTORS.items():
        if plugin not in enabled:
            continue
        result = subprocess.run(
            [sys.executable, *argv],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        status: dict[str, Any] = {"exit_code": result.returncode}
        if plugin == "mf-kessai-invoice-check" and result.returncode == 0:
            try:
                items = json.loads(result.stdout).get("items") or []
            except json.JSONDecodeError:
                failures.append(f"plugin doctor returned invalid JSON: {plugin}")
            else:
                warn_labels = [item.get("label") for item in items if item.get("status") == "WARN"]
                status["warnings"] = warn_labels
                warnings.extend(f"plugin doctor {plugin}: {label}" for label in warn_labels)
        if result.returncode != 0:
            tail = next((line.strip() for line in reversed(result.stdout.splitlines()) if line.strip()), "")
            failures.append(
                f"plugin doctor failed: {plugin} (exit {result.returncode})"
                + (f": {tail}" if tail else "")
            )
        statuses[plugin] = status
    return failures, warnings, statuses


def diagnose(
    slug: str,
    dump_resolved: bool = False,
    mode: str = "standard",
    include_plugin_doctors: bool = True,
) -> tuple[list[str], list[str], dict[str, Any]]:
    tenant = load_tenant(slug)
    failures: list[str] = []
    warnings: list[str] = []
    _, prefix_failures = _all_prefixes()
    failures.extend(prefix_failures)
    base = TENANTS / slug
    resolved: dict[str, Any] = {"tenant": slug, "overlays": {}, "credentials": {}}
    for field, relative in (tenant.get("overlays") or {}).items():
        if field == "ref_company_rules":
            continue
        actual = base / str(relative)
        example = base / str(relative).replace(".json", ".example.json")
        resolved["overlays"][field] = str(actual)
        if not actual.is_file():
            failures.append(f"{field}: overlay missing: {actual}")
            continue
        if example.is_file():
            try:
                expected_data = json.loads(example.read_text(encoding="utf-8"))
                actual_data = json.loads(actual.read_text(encoding="utf-8"))
                contract_failures, contract_warnings = _compare_contract(expected_data, actual_data)
                failures.extend(f"{field} {message}" for message in contract_failures)
                warnings.extend(f"{field} {message}" for message in contract_warnings)
                if field == "notion_config":
                    resolved["databases"] = {
                        key: value.get("db_id")
                        for key, value in (actual_data.get("databases") or {}).items()
                    }
            except (OSError, json.JSONDecodeError) as exc:
                failures.append(f"{field}: invalid JSON: {exc}")
    system = platform.system().lower()
    for purpose, item in (tenant.get("credentials") or {}).items():
        service, account = credential_ref(purpose, tenant)
        resolved["credentials"][purpose] = {"service": service, "account": account}
        if not item.get("required"):
            continue
        env_name = item.get("env_fallback")
        available = bool(env_name and os.environ.get(str(env_name)))
        if system == "darwin" and not available:
            probe = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", account],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            available = probe.returncode == 0
        if not available:
            failures.append(f"required credential unavailable: {purpose} ({service}, {account})")
    if system == "windows":
        failures.append("Windows encrypted credential backend is not implemented")
    elif system == "linux":
        warnings.append("Linux plaintext XDG backend requires explicit company security approval")
    if mode == "maintainer_symlink":
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip()
        allowed_ref = os.environ.get("HARNESS_ALLOWED_REF", "main")
        if status:
            failures.append("harness canonical worktree is dirty")
        if branch != allowed_ref:
            failures.append(f"harness canonical ref is {branch!r}; expected {allowed_ref!r}")
    elif mode == "customer_bundle":
        receipt_path = ROOT / ".harness-install-receipt.json"
        if not receipt_path.is_file():
            failures.append(f"install receipt missing: {receipt_path}")
        else:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            resolved["install_receipt"] = receipt
            expected = tenant.get("core_compat")
            if expected and receipt.get("core_compat") != expected:
                failures.append(
                    f"core_compat mismatch: tenant={expected!r}, receipt={receipt.get('core_compat')!r}"
                )
    if include_plugin_doctors:
        doctor_failures, doctor_warnings, doctor_statuses = _run_plugin_doctors(slug, tenant)
        failures.extend(doctor_failures)
        warnings.extend(doctor_warnings)
        resolved["plugin_doctors"] = doctor_statuses
    if dump_resolved:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    return failures, warnings, resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--dump-resolved", action="store_true")
    parser.add_argument("--mode", choices=("standard", "maintainer_symlink", "customer_bundle"), default="standard")
    parser.add_argument("--skip-plugin-doctors", action="store_true")
    args = parser.parse_args()
    try:
        failures, warnings, _ = diagnose(
            args.slug,
            args.dump_resolved,
            args.mode,
            include_plugin_doctors=not args.skip_plugin_doctors,
        )
    except (TenantConfigError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"[tenant-doctor] FAIL: {exc}", file=sys.stderr)
        return 2
    for message in warnings:
        print(f"[tenant-doctor] WARN: {message}")
    for message in failures:
        print(f"[tenant-doctor] FAIL: {message}", file=sys.stderr)
    if failures:
        return 1
    print(f"[tenant-doctor] OK: {args.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
