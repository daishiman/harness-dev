#!/usr/bin/env python3
# /// script
# name: sandbox-plugin-lifecycle
# purpose: Exercise plugin install, uninstall and upgrade contracts in an isolated temporary Claude home.
# inputs:
#   - --plugin: source plugin name
#   - --operation: install | uninstall | upgrade
#   - --plugins-root: source plugins directory
#   - --sandbox-root: optional persistent test sandbox
# outputs:
#   - stdout: PKG-010/011/012 JSON result
# contexts: [C, E]
# network: false
# write-scope: temporary sandbox or explicit --sandbox-root only
# dependencies: []
# ///
"""Side-effect-free plugin lifecycle smoke harness.

The real repository and user Claude home are read-only inputs. All install
surfaces are materialized below a temporary sandbox, then verified there.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
EXTERNAL_LINT = REPO_ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-external-refs.py"
PKG_BY_OPERATION = {"install": "PKG-010", "uninstall": "PKG-011", "upgrade": "PKG-012"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode())
        if path.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(b"F")
            digest.update(path.read_bytes())
        elif path.is_dir():
            digest.update(b"D")
    return digest.hexdigest()


def plugin_version(plugin_dir: Path) -> str:
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"plugin manifest version is missing: {manifest}")
    return version


def bump_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
    return version + ".sandbox-upgrade"


def _replace_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.symlink_to(target)


def install(source: Path, sandbox: Path) -> dict:
    """Install one plugin copy and derived Claude surfaces into sandbox."""
    name = source.name
    version = plugin_version(source)
    installed = sandbox / "installed-plugins" / name
    existing_version = plugin_version(installed) if installed.exists() else None
    changed = existing_version != version
    if not installed.exists():
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, installed, symlinks=True)
    elif changed:
        replacement = installed.with_name(installed.name + ".replacement")
        if replacement.exists():
            shutil.rmtree(replacement)
        shutil.copytree(source, replacement, symlinks=True)
        shutil.rmtree(installed)
        replacement.rename(installed)

    surfaces: list[str] = []
    for skill_md in sorted((installed / "skills").glob("*/SKILL.md")):
        link = sandbox / ".claude" / "skills" / skill_md.parent.name
        _replace_symlink(link, skill_md.parent)
        surfaces.append(str(link.relative_to(sandbox)))
    for agent in sorted((installed / "agents").glob("*.md")):
        link = sandbox / ".claude" / "agents" / agent.name
        _replace_symlink(link, agent)
        surfaces.append(str(link.relative_to(sandbox)))
    hooks_manifest = installed / "hooks" / "hooks.json"
    if hooks_manifest.is_file():
        link = sandbox / ".claude" / "hooks" / f"{name}.json"
        _replace_symlink(link, hooks_manifest)
        surfaces.append(str(link.relative_to(sandbox)))
    settings = installed / "settings"
    if settings.is_dir():
        for fragment in sorted(settings.glob("*.json")):
            link = sandbox / ".claude" / "settings" / name / fragment.name
            _replace_symlink(link, fragment)
            surfaces.append(str(link.relative_to(sandbox)))

    state_dir = sandbox / ".claude" / "plugin-state" / name
    state_dir.mkdir(parents=True, exist_ok=True)
    registration = {
        "plugin": name,
        "version": version,
        "installed_path": str(installed),
        "surfaces": surfaces,
    }
    (state_dir / "registration.json").write_text(
        json.dumps(registration, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"changed": changed, "version": version, "installed": installed, "surfaces": surfaces}


def uninstall(name: str, sandbox: Path) -> dict:
    state_dir = sandbox / ".claude" / "plugin-state" / name
    registration_path = state_dir / "registration.json"
    registration = json.loads(registration_path.read_text(encoding="utf-8")) if registration_path.is_file() else {}
    for relative in registration.get("surfaces", []):
        target = sandbox / relative
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
    installed = sandbox / "installed-plugins" / name
    if installed.exists():
        shutil.rmtree(installed)
    if state_dir.exists():
        shutil.rmtree(state_dir)

    residues: list[str] = []
    for path in sorted(sandbox.rglob("*"), key=lambda p: p.as_posix()):
        if path.is_symlink():
            resolved = (path.parent / os.readlink(path)).resolve(strict=False)
            if installed == resolved or installed in resolved.parents:
                residues.append(str(path.relative_to(sandbox)))
    for candidate in (
        sandbox / ".claude" / "hooks" / f"{name}.json",
        sandbox / ".claude" / "settings" / name,
        state_dir,
        installed,
    ):
        if candidate.exists() or candidate.is_symlink():
            residues.append(str(candidate.relative_to(sandbox)))
    return {"residues": sorted(set(residues)), "removed_surface_count": len(registration.get("surfaces", []))}


def external_ref_result(source: Path) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(EXTERNAL_LINT),
            "--skills-dir",
            str(source / "skills"),
            "--fail-on-external",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PKG-009 SSOT produced invalid JSON: {exc}: {proc.stderr}") from exc
    report["exit_code"] = proc.returncode
    return report


def run_install(source: Path, sandbox: Path) -> dict:
    installed = install(source, sandbox)
    external = external_ref_result(source)
    scripts_non_executable = [
        str(path.relative_to(source))
        for path in sorted((source / "scripts").glob("*"))
        if path.is_file() and path.suffix in {".py", ".sh"} and not os.access(path, os.X_OK)
    ]
    findings: list[str] = []
    if scripts_non_executable:
        findings.append(f"non-executable scripts: {scripts_non_executable}")
    if external["exit_code"] != 0:
        findings.append(
            "external reference gate failed: "
            f"refs={external.get('external_ref_count', 0)} errors={external.get('contract_errors', [])}"
        )
    return {
        "pkg_id": "PKG-010",
        "status": "fail" if findings else "pass",
        "last_run_at": now_iso(),
        "sandboxed": True,
        "installed_version": installed["version"],
        "installed_surface_count": len(installed["surfaces"]),
        "scripts_non_executable": scripts_non_executable,
        "external_reference_gate": {
            "checker": str(EXTERNAL_LINT.relative_to(REPO_ROOT)),
            "external_ref_count": external.get("external_ref_count", 0),
            "declared_dependency_ref_count": external.get("declared_dependency_ref_count", 0),
            "contract_errors": external.get("contract_errors", []),
        },
        "findings": findings,
    }


def run_uninstall(source: Path, sandbox: Path) -> dict:
    installed = install(source, sandbox)
    result = uninstall(source.name, sandbox)
    findings = [f"uninstall residue: {path}" for path in result["residues"]]
    return {
        "pkg_id": "PKG-011",
        "status": "fail" if findings else "pass",
        "last_run_at": now_iso(),
        "sandboxed": True,
        "installed_surface_count": len(installed["surfaces"]),
        "removed_surface_count": result["removed_surface_count"],
        "residues": result["residues"],
        "findings": findings,
    }


def run_upgrade(source: Path, sandbox: Path) -> dict:
    first = install(source, sandbox)
    installed_dir = first["installed"]
    before = tree_digest(installed_dir)
    state_dir = sandbox / ".claude" / "plugin-state" / source.name
    user_state = state_dir / "user-state.json"
    user_state.write_text('{"preserve":true}\n', encoding="utf-8")
    user_state_digest = tree_digest(user_state.parent)

    same = install(source, sandbox)
    after_same = tree_digest(installed_dir)

    upgrade_source = sandbox / "upgrade-source" / source.name
    upgrade_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, upgrade_source, symlinks=True)
    manifest = upgrade_source / ".claude-plugin" / "plugin.json"
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_data["version"] = bump_version(first["version"])
    manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    upgraded = install(upgrade_source, sandbox)
    after_upgrade = tree_digest(installed_dir)
    preserved = user_state.is_file() and json.loads(user_state.read_text(encoding="utf-8")) == {"preserve": True}

    findings: list[str] = []
    if same["changed"] or before != after_same:
        findings.append("same-version reinstall was not a no-op")
    if not upgraded["changed"] or after_upgrade == after_same:
        findings.append("different-version upgrade did not replace installed payload")
    if not preserved:
        findings.append("different-version upgrade destroyed plugin user state")
    if plugin_version(source) != first["version"]:
        findings.append("source plugin was modified during sandbox upgrade")
    return {
        "pkg_id": "PKG-012",
        "status": "fail" if findings else "pass",
        "last_run_at": now_iso(),
        "sandboxed": True,
        "same_version": {
            "version": first["version"],
            "changed": same["changed"],
            "digest_unchanged": before == after_same,
        },
        "different_version": {
            "from": first["version"],
            "to": upgraded["version"],
            "changed": upgraded["changed"],
            "payload_changed": after_upgrade != after_same,
            "user_state_preserved": preserved,
            "user_state_digest_before": user_state_digest,
        },
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--operation", required=True, choices=sorted(PKG_BY_OPERATION))
    parser.add_argument("--plugins-root", default=str(REPO_ROOT / "plugins"))
    parser.add_argument("--sandbox-root")
    args = parser.parse_args(argv)
    source = Path(args.plugins_root).resolve() / args.plugin
    if not source.is_dir():
        print(f"error: plugin not found: {source}", file=sys.stderr)
        return 2

    context = nullcontext(args.sandbox_root) if args.sandbox_root else tempfile.TemporaryDirectory(prefix="pkg-smoke-")
    try:
        with context as sandbox_value:
            sandbox = Path(sandbox_value).resolve()
            sandbox.mkdir(parents=True, exist_ok=True)
            if args.operation == "install":
                result = run_install(source, sandbox)
            elif args.operation == "uninstall":
                result = run_uninstall(source, sandbox)
            else:
                result = run_upgrade(source, sandbox)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        result = {
            "pkg_id": PKG_BY_OPERATION[args.operation],
            "status": "fail",
            "last_run_at": now_iso(),
            "sandboxed": True,
            "findings": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
