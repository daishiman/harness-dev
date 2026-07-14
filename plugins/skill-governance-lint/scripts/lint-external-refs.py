#!/usr/bin/env python3
# /// script
# name: lint-external-refs
# purpose: Reject undeclared cross-plugin SKILL.md references while allowing package-contract dependencies.
# inputs:
#   - --skills-dir: directory containing skill subdirectories
#   - --json: emit machine-readable JSON
#   - --fail-on-external: exit 1 when external references are found
# outputs:
#   - stdout: inventory report
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""SKILL.md の外部参照を棚卸しする。

34章 Phase 0 の「全 SKILL.md 外部参照棚卸し」を機械化するための最小 lint。
plugin 間参照は `references/package-contract.json.depends_on` を唯一の
allowlist とし、未宣言依存は fail-closed にする。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


DEFAULT_ALLOWED_PREFIXES = (
    ".claude/",
    "eval-log/",
    "references/",
    "scripts/",
)

PATH_RE = re.compile(
    r"(?P<path>(?:(?:\.\./)+|(?:\.claude|scripts|doc|references|eval-log|plugins)/)"
    r"[A-Za-z0-9_\-./一-龠ぁ-んァ-ンー]+)"
)
PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


def load_declared_dependencies(contract_path: pathlib.Path) -> tuple[set[str], list[str]]:
    """Load the explicit dependency allowlist; malformed input is an error."""
    if not contract_path.is_file():
        return set(), [f"package contract not found: {contract_path}"]
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), [f"package contract parse error: {contract_path}: {exc}"]
    raw = data.get("depends_on", [])
    if not isinstance(raw, list):
        return set(), ["package contract depends_on must be an array"]
    errors: list[str] = []
    dependencies: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or not PLUGIN_NAME_RE.fullmatch(value):
            errors.append(f"invalid depends_on plugin name: {value!r}")
        else:
            dependencies.add(value)
    return dependencies, errors


def _plugin_slug_for_ref(
    ref: str,
    skill_path: pathlib.Path,
    plugin_dir: pathlib.Path | None,
) -> str | None:
    if ref.startswith("plugins/"):
        parts = pathlib.PurePosixPath(ref).parts
        return parts[1] if len(parts) >= 3 else None
    if not ref.startswith("../") or plugin_dir is None:
        return None
    plugins_root = plugin_dir.resolve().parent
    resolved = (skill_path.parent / ref).resolve(strict=False)
    try:
        relative = resolved.relative_to(plugins_root)
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 2 else None


def scan_skill(
    path: pathlib.Path,
    allowed_prefixes: tuple[str, ...],
    *,
    plugin_dir: pathlib.Path | None = None,
    declared_dependencies: set[str] | frozenset[str] = frozenset(),
) -> dict:
    text = path.read_text(encoding="utf-8")
    refs = []
    for match in PATH_RE.finditer(text):
        ref = match.group("path").rstrip(").,`\"'")
        dependency = _plugin_slug_for_ref(ref, path, plugin_dir)
        if dependency is not None:
            if plugin_dir is not None and dependency == plugin_dir.name:
                external = False
                classification = "same_plugin"
            elif dependency in declared_dependencies:
                external = False
                classification = "declared_plugin_dependency"
            else:
                external = True
                classification = "undeclared_plugin_dependency"
        elif ref.startswith("../") and plugin_dir is not None:
            resolved = (path.parent / ref).resolve(strict=False)
            try:
                resolved.relative_to(plugin_dir.resolve())
                external = False
                classification = "same_plugin"
            except ValueError:
                external = True
                classification = "outside_plugin"
        else:
            external = not ref.startswith(allowed_prefixes)
            classification = "allowed_prefix" if not external else "outside_plugin"
        refs.append(
            {
                "ref": ref,
                "line": text.count("\n", 0, match.start()) + 1,
                "external": external,
                "classification": classification,
                **({"dependency": dependency} if dependency is not None else {}),
            }
        )
    return {
        "skill": path.parent.name,
        "path": str(path),
        "refs": refs,
        "external_refs": [r for r in refs if r["external"]],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", default="plugins/harness-creator/skills")
    parser.add_argument("--allowed-prefix", action="append", default=[])
    parser.add_argument(
        "--package-contract",
        help="dependency allowlist JSON; default: <skills-dir>/../references/package-contract.json",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-external", action="store_true")
    args = parser.parse_args(argv[1:])

    skills_dir = pathlib.Path(args.skills_dir)
    plugin_dir = skills_dir.parent.resolve()
    allowed = tuple(args.allowed_prefix or DEFAULT_ALLOWED_PREFIXES)
    contract_path = (
        pathlib.Path(args.package_contract)
        if args.package_contract
        else plugin_dir / "references" / "package-contract.json"
    )
    dependencies, contract_errors = load_declared_dependencies(contract_path)
    reports = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        reports.append(scan_skill(
            skill_md,
            allowed,
            plugin_dir=plugin_dir,
            declared_dependencies=dependencies,
        ))

    external_total = sum(len(r["external_refs"]) for r in reports)
    declared_total = sum(
        1
        for report in reports
        for ref in report["refs"]
        if ref["classification"] == "declared_plugin_dependency"
    )
    payload = {
        "skills_dir": str(skills_dir),
        "allowed_prefixes": list(allowed),
        "package_contract": str(contract_path),
        "declared_dependencies": sorted(dependencies),
        "contract_errors": contract_errors,
        "skills_scanned": len(reports),
        "external_ref_count": external_total,
        "declared_dependency_ref_count": declared_total,
        "reports": reports,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"skills_scanned={payload['skills_scanned']} "
            f"external_ref_count={external_total} "
            f"declared_dependency_ref_count={declared_total}"
        )
        for error in contract_errors:
            print(f"CONTRACT_ERROR {error}")
        for report in reports:
            for ref in report["external_refs"]:
                print(
                    f"EXTERNAL {report['skill']}:{ref['line']} {ref['ref']} "
                    f"({ref['classification']})"
                )

    return 1 if args.fail_on_external and (external_total or contract_errors) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
