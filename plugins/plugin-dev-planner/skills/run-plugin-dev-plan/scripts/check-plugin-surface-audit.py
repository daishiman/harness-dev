#!/usr/bin/env python3
# /// script
# name: check-plugin-surface-audit
# purpose: plugins/ 配下の現物プラグインが持つ skill/agent/command/hook/script/test 等の surface を横断棚卸しする。
# inputs:
#   - argv: [--plugins-dir plugins] [--strict-manifest] [--expect-plan-ready <plugin-name>] [--json]
# outputs:
#   - stdout: audit summary or JSON report
#   - stderr: audit violations
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Live plugin surface auditor.

This checks the real ``plugins/<name>/`` directories, not a generated plan.
It complements check-surface-inventory.py:

* check-surface-inventory.py validates an L3 plan's component-inventory.json.
* this script audits existing L4 plugin directories so planner coverage can be
  compared with actual plugin shapes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SURFACE_KEYS = (
    "skills",
    "agents",
    "commands",
    "hooks",
    "scripts",
    "tests",
    "references",
    "config",
    "assets",
    "schemas",
    "vendor",
    "mcp_app_connector",
    "harness_eval",
    "plugin_composition",
    "plugin_manifest",
)

PLAN_READY_REQUIRED = frozenset({
    "skills",
    "agents",
    "commands",
    "hooks",
    "scripts",
    "tests",
    "references",
    "harness_eval",
    "plugin_composition",
    "plugin_manifest",
})


def _files(root: Path, pattern: str) -> list[str]:
    out: list[str] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        out.append(path.relative_to(root).as_posix())
    return sorted(out)


def _top_level_files(root: Path, names: tuple[str, ...]) -> list[str]:
    return sorted(name for name in names if (root / name).is_file())


def _owned_symlink_counts(root: Path, rel_paths: list[str]) -> dict:
    owned = 0
    symlink = 0
    for rel in rel_paths:
        path = root / rel
        if path.is_symlink():
            symlink += 1
        else:
            owned += 1
    return {"owned": owned, "symlink": symlink}


def collect_plugin(plugin_dir: Path) -> dict:
    """Return a deterministic surface inventory for one plugin directory."""
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = None
    manifest_error = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            manifest_error = f"JSON parse error: {exc}"

    surfaces = {
        "skills": _files(plugin_dir, "skills/*/SKILL.md"),
        "agents": _files(plugin_dir, "agents/*.md"),
        "commands": _files(plugin_dir, "commands/*.md"),
        "hooks": sorted(
            p.relative_to(plugin_dir).as_posix()
            for p in plugin_dir.rglob("hooks/*")
            if p.is_file() and p.suffix in {".py", ".sh"} and "__pycache__" not in p.parts
        ),
        "scripts": _files(plugin_dir, "scripts/*.py"),
        "tests": _files(plugin_dir, "tests/test_*.py"),
        "references": _files(plugin_dir, "references/*"),
        "config": _files(plugin_dir, "config/*"),
        "assets": _files(plugin_dir, "assets/*"),
        "schemas": _files(plugin_dir, "schemas/*.json") + _files(plugin_dir, "skills/*/schemas/*.json"),
        "vendor": _files(plugin_dir, "vendor/*"),
        "mcp_app_connector": _top_level_files(plugin_dir, (".mcp.json", ".app.json")),
        "harness_eval": ["EVALS.json"] if (plugin_dir / "EVALS.json").is_file() else [],
        "plugin_composition": ["plugin-composition.yaml"] if (plugin_dir / "plugin-composition.yaml").is_file() else [],
        "plugin_manifest": [".claude-plugin/plugin.json"] if manifest_path.is_file() else [],
    }
    return {
        "name": plugin_dir.name,
        "path": plugin_dir.as_posix(),
        "manifest": manifest,
        "manifest_error": manifest_error,
        "surfaces": surfaces,
        "counts": {key: len(value) for key, value in surfaces.items()},
        "ownership": {key: _owned_symlink_counts(plugin_dir, value) for key, value in surfaces.items()},
    }


def audit(plugins_dir: Path, *, strict_manifest: bool, expect_plan_ready: set[str]) -> tuple[dict, list[str]]:
    errors: list[str] = []
    if not plugins_dir.is_dir():
        # 早期 return も正常パス (171-) と同形に保つ。_print_summary が無条件に
        # plugin_count / surface_keys を読むため、非対称だと本来の "not found"
        # エラー報告前に KeyError でクラッシュしていた (CI cwd で顕在化)。
        return {
            "plugins_dir": plugins_dir.as_posix(),
            "plugin_count": 0,
            "surface_keys": list(SURFACE_KEYS),
            "plugins": [],
        }, [f"plugins dir not found: {plugins_dir}"]

    plugins = [
        collect_plugin(path)
        for path in sorted(plugins_dir.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]

    for item in plugins:
        name = item["name"]
        counts = item["counts"]
        manifest = item["manifest"]
        if item["manifest_error"]:
            errors.append(f"{name}: manifest parse failed: {item['manifest_error']}")
        if strict_manifest:
            if not counts["plugin_manifest"]:
                errors.append(f"{name}: .claude-plugin/plugin.json missing")
            elif isinstance(manifest, dict) and manifest.get("name") != name:
                errors.append(f"{name}: manifest.name {manifest.get('name')!r} != directory name")
            asset_total = sum(counts[key] for key in SURFACE_KEYS if key != "plugin_manifest")
            if asset_total == 0:
                errors.append(f"{name}: no plugin assets found")
        if name in expect_plan_ready:
            missing = [key for key in sorted(PLAN_READY_REQUIRED) if counts.get(key, 0) == 0]
            if missing:
                errors.append(f"{name}: plan-ready surface missing: {', '.join(missing)}")

    known = {item["name"] for item in plugins}
    for name in sorted(expect_plan_ready - known):
        errors.append(f"{name}: expected plugin not found under {plugins_dir}")

    report = {
        "plugins_dir": plugins_dir.as_posix(),
        "plugin_count": len(plugins),
        "surface_keys": list(SURFACE_KEYS),
        "plugins": plugins,
    }
    return report, errors


def _print_summary(report: dict) -> None:
    sys.stdout.write(f"Audited {report['plugin_count']} plugins under {report['plugins_dir']}\n")
    header = "plugin " + " ".join(SURFACE_KEYS)
    sys.stdout.write(header + "\n")
    for item in report["plugins"]:
        counts = item["counts"]
        values = " ".join(str(counts[key]) for key in SURFACE_KEYS)
        sys.stdout.write(f"{item['name']} {values}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="plugins/ 配下の live plugin surface を棚卸しする")
    ap.add_argument("--plugins-dir", default="plugins", help="plugin root directory")
    ap.add_argument("--strict-manifest", action="store_true", help="manifest/name/assets の最低条件を検査する")
    ap.add_argument(
        "--expect-plan-ready",
        action="append",
        default=[],
        metavar="PLUGIN",
        help="指定 plugin が全 surface を dogfood していることを要求する",
    )
    ap.add_argument("--json", action="store_true", help="JSON report を stdout へ出力する")
    args = ap.parse_args(argv)

    report, errors = audit(
        Path(args.plugins_dir),
        strict_manifest=args.strict_manifest,
        expect_plan_ready=set(args.expect_plan_ready),
    )
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        _print_summary(report)
    if errors:
        for err in errors:
            sys.stderr.write(err + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
