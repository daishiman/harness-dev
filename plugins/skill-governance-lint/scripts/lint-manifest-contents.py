#!/usr/bin/env python3
# /// script
# name: lint-manifest-contents
# purpose: Verify plugin or legacy manifest entries point to existing files.
# inputs:
#   - argv: optional manifest path
# outputs:
#   - stdout: OK status
#   - stderr: missing or invalid manifest entries
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""Verify plugin.json or legacy manifest.json matches files present in the package."""
from __future__ import annotations

import json
import sys
import pathlib
from pathlib import Path


KIT_DIR = Path(__file__).resolve().parents[1]
MANIFEST = KIT_DIR / "manifest.json"
PLUGIN_MANIFEST = KIT_DIR / ".claude-plugin" / "plugin.json"
SETTINGS_EXAMPLE = KIT_DIR / "config" / "claude-settings-hooks.json.example"


def expect(path: Path, findings: list[str]) -> None:
    if not path.exists() and not path.is_symlink():
        findings.append(f"missing: {path.relative_to(KIT_DIR)}")


def main() -> int:
    bidirectional = "--bidirectional" in sys.argv
    if not MANIFEST.exists() and PLUGIN_MANIFEST.exists():
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        findings: list[str] = []
        for key in ("name", "version", "description"):
            if not plugin.get(key):
                findings.append(f"plugin.json missing required key: {key}")
        if findings:
            for finding in findings:
                print(finding)
            return 1
        print("OK: plugin manifest contents valid")
        return 0

    manifest = json.loads(MANIFEST.read_text())
    findings: list[str] = []

    for skill in manifest.get("skills", []):
        expect(KIT_DIR / "skills" / skill["name"] / "SKILL.md", findings)

    for agent in manifest.get("agents", []):
        source = agent.get("source") or f"agents/{agent['name']}.md"
        expect(KIT_DIR / source, findings)
        target = agent.get("path", "")
        if target and not target.startswith(".claude/agents/"):
            findings.append(f"agent target must be under .claude/agents/: {target}")

    scripts = manifest.get("scripts", {})
    script_group_dirs = {
        "adapters": KIT_DIR / "scripts" / "adapters",
        "secrets": KIT_DIR / "scripts" / "secrets",
        "migrate": KIT_DIR / "scripts" / "migrate",
    }
    for group, names in scripts.items():
        base_dir = script_group_dirs.get(group, KIT_DIR / "scripts")
        for name in names:
            expect(base_dir / name, findings)

    for config in manifest.get("config", []):
        expect(KIT_DIR / config["source"], findings)

    if bidirectional:
        check_bidirectional(manifest, findings)

    if SETTINGS_EXAMPLE.exists():
        settings = json.loads(SETTINGS_EXAMPLE.read_text(encoding="utf-8"))
        deny = settings.get("permissions", {}).get("deny", [])
        if not deny:
            findings.append("config/claude-settings-hooks.json.example missing permissions.deny")
        hooks = settings.get("hooks", {})
        if "FileChanged" not in hooks:
            findings.append("config/claude-settings-hooks.json.example missing FileChanged hook")
        if "TaskCreated" not in hooks:
            findings.append("config/claude-settings-hooks.json.example missing TaskCreated hook")

    if findings:
        for finding in findings:
            print(finding)
        return 1

    # C-5 freshness check
    warnings: list[str] = []
    check_yaml_spec_freshness(warnings)
    for w in warnings:
        print(w)
    print("OK: manifest contents match package files")
    return 0




def load_excluded_paths(manifest: dict) -> list[str]:
    """manifest の excluded_paths を返す（未設定時は空リスト）。"""
    return manifest.get("excluded_paths", [])


def is_excluded(rel_path: str, excluded: list[str]) -> bool:
    """rel_path が excluded_paths のいずれかの接頭辞に一致すれば True。"""
    for ex in excluded:
        if rel_path.startswith(ex.rstrip("/")):
            return True
    return False


def check_bidirectional(manifest: dict, findings: list[str]) -> None:
    """scripts/ と skills/ を走査し、manifest 未登録を検出する。"""
    excluded = load_excluded_paths(manifest)

    # -- scripts --
    registered_scripts: set[str] = set()
    for names in manifest.get("scripts", {}).values():
        for name in names:
            registered_scripts.add(name)
    # lifecycle (sh/ps1 含む)
    for entry in manifest.get("lifecycle", []):
        if isinstance(entry, str):
            registered_scripts.add(entry)
    # bootstrap
    for entry in manifest.get("bootstrap", []):
        if isinstance(entry, dict):
            src = entry.get("source", "")
            if src:
                registered_scripts.add(pathlib.Path(src).name)

    scripts_dir = KIT_DIR / "scripts"
    for p in scripts_dir.iterdir():
        if p.is_dir():
            continue  # サブディレクトリは個別走査しない（adapters/secrets/migrate は別グループ）
        rel = str(p.relative_to(KIT_DIR))
        if is_excluded(rel, excluded):
            continue
        if p.name not in registered_scripts:
            findings.append(f"bidirectional: scripts/{p.name} は manifest 未登録")

    # -- skills --
    registered_skills = {s["name"] for s in manifest.get("skills", [])}
    skills_dir = KIT_DIR / "skills"
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            rel = str(skill_dir.relative_to(KIT_DIR)) + "/"
            if is_excluded(rel, excluded):
                continue
            if skill_dir.name not in registered_skills:
                findings.append(f"bidirectional: skills/{skill_dir.name} は manifest 未登録")


# ---- C-5: yaml-spec-cache.md last_fetched 30日超過警告 ----
def check_yaml_spec_freshness(findings_warn: list[str]) -> None:
    """yaml-spec-cache.md の last_fetched が 30 日超過なら WARNING を stdout に出力."""
    import datetime
    cache_paths = [
        Path(__file__).resolve().parents[1]
        / ".claude" / "skills" / "ref-yaml-spec-fetcher" / "references" / "yaml-spec-cache.md",
    ]
    for cache_path in cache_paths:
        if not cache_path.exists():
            continue
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("last_fetched:"):
                ts_str = line.split(":", 1)[1].strip()
                try:
                    fetched_at = datetime.datetime.fromisoformat(
                        ts_str.replace("Z", "+00:00")
                    )
                    age_days = (
                        datetime.datetime.now(datetime.timezone.utc) - fetched_at
                    ).days
                    if age_days > 30:
                        findings_warn.append(
                            f"WARNING: yaml-spec-cache.md last_fetched={ts_str} "
                            f"is {age_days} days old (> 30 days). "
                            f"Run scripts/build-yaml-spec-cache.py to refresh."
                        )
                except (ValueError, TypeError):
                    pass
                break

if __name__ == "__main__":
    sys.exit(main())
