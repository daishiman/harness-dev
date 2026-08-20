#!/usr/bin/env python3
# /// script
# name: build-manifest-registration-plan
# purpose: Propose manifest additions for unregistered plugin files.
# inputs:
#   - argv: optional --apply after user approval
# outputs:
#   - stdout: registration plan JSON or summary
#   - file: manifest.json when legacy --apply is used
# contexts: [A, B]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Detect unregistered files in a legacy manifest.json.

This script is intentionally conservative. It proposes manifest additions, but
does not edit files unless --apply is passed after a user approval gate.
Phase 2 plugin packages use .claude-plugin/plugin.json; those manifests are
validated as the current format and require no registration plan here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


KIT_DIR = Path(__file__).resolve().parents[1]
MANIFEST = KIT_DIR / "manifest.json"
PLUGIN_MANIFEST = KIT_DIR / ".claude-plugin" / "plugin.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registered_sets(manifest: dict) -> dict[str, set[str]]:
    scripts = manifest.get("scripts", {})
    registered = {
        "skills": {s["name"] for s in manifest.get("skills", [])},
        "config": {c["source"] for c in manifest.get("config", [])},
    }
    for group, names in scripts.items():
        registered[group] = set(names)
    return registered


def infer_skill_category(name: str) -> str:
    if name == "run-skill-create":
        return "orchestrator"
    if name.startswith(("run-build", "run-skill-elicit", "run-skill-rename")):
        return "generator"
    if name.startswith(("assign-", "run-elegant-review")):
        return "evaluator"
    if name.startswith("run-skill-rubric-governance"):
        return "governance"
    if name.startswith("ref-"):
        return "reference"
    if name.startswith("run-"):
        return "workflow"
    return "reference"


def infer_skill_role(name: str) -> str:
    return f"TODO: {name} の役割を1文で記述"


def collect_proposals(manifest: dict) -> dict[str, list]:
    reg = registered_sets(manifest)
    proposals: dict[str, list] = {
        "skills": [],
        "adapters": [],
        "secrets": [],
        "cross_platform": [],
        "migrate": [],
        "lint": [],
        "hooks": [],
        "config": [],
    }

    for skill_md in sorted((KIT_DIR / "skills").glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name not in reg["skills"]:
            proposals["skills"].append({
                "name": name,
                "role": infer_skill_role(name),
                "category": infer_skill_category(name),
            })

    for path in sorted((KIT_DIR / "scripts" / "adapters").glob("*.py")):
        if path.name not in reg["adapters"]:
            proposals["adapters"].append(path.name)

    for path in sorted((KIT_DIR / "scripts" / "secrets").iterdir() if (KIT_DIR / "scripts" / "secrets").exists() else []):
        if path.is_dir() or path.name == "__pycache__":
            continue
        if path.name not in reg["secrets"]:
            proposals["secrets"].append(path.name)

    for path in sorted((KIT_DIR / "scripts" / "migrate").glob("*.py") if (KIT_DIR / "scripts" / "migrate").exists() else []):
        if path.name not in reg.get("migrate", set()):
            proposals["migrate"].append(path.name)

    for path in sorted((KIT_DIR / "scripts").glob("*.py")):
        name = path.name
        if name == "cross_platform_secret.py" and name not in reg.get("cross_platform", set()):
            proposals["cross_platform"].append(name)
        elif name.startswith(("lint-", "validate-")) and name not in (reg.get("lint", set()) | reg.get("governance", set())):
            proposals["lint"].append(name)
        elif name.startswith("hook-") and name not in (reg.get("hooks", set()) | reg.get("governance", set())):
            proposals["hooks"].append(name)

    for path in sorted((KIT_DIR / "config").iterdir() if (KIT_DIR / "config").exists() else []):
        if not path.is_file():
            continue
        source = f"config/{path.name}"
        if source not in reg["config"]:
            target = ".claude/config/" + path.name
            mode = "symlink"
            if path.name.startswith("governance-params"):
                target = "references/" + path.name
                mode = "copy"
            elif path.name.startswith("claude-settings"):
                target = ".claude/" + path.name
                mode = "copy"
            proposals["config"].append({"source": source, "target": target, "mode": mode})

    return {k: v for k, v in proposals.items() if v}


def apply_proposals(manifest: dict, proposals: dict[str, list]) -> dict:
    manifest.setdefault("skills", []).extend(proposals.get("skills", []))
    manifest.setdefault("scripts", {})
    for key in ("adapters", "secrets", "cross_platform", "migrate", "lint", "hooks"):
        manifest["scripts"].setdefault(key, [])
        manifest["scripts"][key].extend(proposals.get(key, []))
    manifest.setdefault("config", []).extend(proposals.get("config", []))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="apply proposed additions to manifest.json")
    args = ap.parse_args()

    if not MANIFEST.exists() and PLUGIN_MANIFEST.exists():
        # 本スクリプトは legacy manifest.json (harness-creator plugin 内) 専用。
        # 新形式 plugin.json plugin のルート marketplace.json / bundles.json への
        # 登録は責務外であり、`scripts/validate-plugin-completeness.py --fix`
        # (append-only・冪等・書込後自己再検証) が担う (run-skill-create workflow-manifest
        # step3.5 bundle-register に配線済)。ここでは plugin.json の必須キーのみ検査して
        # proposals 空で返す (ルート2 SSOT は触らない)。
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        required = ("name", "version", "description")
        missing = [key for key in required if not plugin.get(key)]
        if missing:
            print(json.dumps({"status": "invalid_plugin_manifest", "missing": missing}, indent=2))
            return 1
        print(json.dumps({"status": "ok", "format": "plugin", "proposals": {}}, ensure_ascii=False, indent=2))
        return 0

    manifest = load_manifest()
    proposals = collect_proposals(manifest)

    if not proposals:
        print(json.dumps({"status": "ok", "proposals": {}}, ensure_ascii=False, indent=2))
        return 0

    if args.apply:
        save_manifest(apply_proposals(manifest, proposals))
        print(json.dumps({"status": "applied", "proposals": proposals}, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({"status": "needs_confirmation", "proposals": proposals}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
