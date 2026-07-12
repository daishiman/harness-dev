#!/usr/bin/env python3
# /// script
# name: resolve-skill-dirs
# purpose: Resolve harness-creator skill directories without shell-specific source files.
# inputs:
#   - argv: --skill-name, --skill-dir-name
# outputs:
#   - stdout: resolved path JSON
#   - stderr: argument errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Resolve harness-creator skill paths as JSON using only Python stdlib.

The installed plugin location and the user's project location are separate
anchors.  Marketplace installs may place this plugin anywhere, so resource
lookup is self-relative to this file / ``CLAUDE_PLUGIN_ROOT`` while generated
skills default to the current project.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _existing_dir(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_dir() else None


def _discover_plugin_root() -> Path:
    env_root = _existing_dir(os.environ.get("CLAUDE_PLUGIN_ROOT"))
    if env_root:
        return env_root

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "plugin-composition.yaml").is_file() and (parent / "skills").is_dir():
            return parent

    # Last-resort fallback for the checked-in layout:
    # <plugin>/skills/run-build-skill/scripts/resolve-skill-dirs.py
    return here.parents[3]


def _project_root() -> Path:
    env_project = _existing_dir(os.environ.get("CLAUDE_PROJECT_DIR"))
    return env_project or Path.cwd().resolve()


def _display(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-name", default="")
    parser.add_argument("--skill-dir-name", default="run-build-skill")
    args = parser.parse_args()

    root = _project_root()
    plugin_root = _discover_plugin_root()

    out_base = os.environ.get("CLAUDE_SKILL_OUT_BASE")
    if not out_base:
        if (root / "plugins" / "harness-creator" / "skills").is_dir():
            out_base = "plugins/harness-creator/skills"
        else:
            out_base = ".claude/skills"

    skill_dir = os.environ.get("CLAUDE_SKILL_DIR")
    if not skill_dir:
        plugin_skill_dir = plugin_root / "skills" / args.skill_dir_name
        candidate = (root / out_base) / args.skill_dir_name
        legacy_candidate = root / "plugins" / "harness-creator" / "skills" / args.skill_dir_name
        if candidate.exists():
            skill_dir = _display(candidate, root)
        elif plugin_skill_dir.exists():
            skill_dir = _display(plugin_skill_dir, root)
        elif legacy_candidate.exists():
            skill_dir = f"plugins/harness-creator/skills/{args.skill_dir_name}"
        else:
            skill_dir = f".claude/skills/{args.skill_dir_name}"

    result = {
        "project_root": str(root),
        "plugin_root": _display(plugin_root, root),
        "out_base": out_base,
        "skill_dir": skill_dir,
    }
    if args.skill_name:
        result["target_root"] = str(Path(out_base) / args.skill_name)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
