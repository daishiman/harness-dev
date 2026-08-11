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


def _manifest_name(root: Path) -> str | None:
    """<root>/.claude-plugin/plugin.json の name。読めなければ None。"""
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return manifest.get("name") if isinstance(manifest, dict) else None


def _self_plugin_name() -> str | None:
    """このファイル自身が属する plugin の manifest name。

    リテラル直書きは制御リテラル散在として禁止 (tests/test_dogfooding_boundary.py)、
    SSOT 定数は「SSOT を探すのに plugin root が要る」循環のため使えない。__file__ は
    循環せず改名にも自動追従する第三の出所。plugin は入れ子にならないので、上向きに
    最初に見つかる manifest が自 plugin のもので確定する。
    """
    for parent in Path(__file__).resolve().parents:
        name = _manifest_name(parent)
        if name:
            return name
    return None


def _hc_env_root() -> Path | None:
    """env から自 plugin root を得る。他 plugin を指す値は拒否する。

    他 repo が .claude 平置き projection で本 plugin を借用している場合、
    env CLAUDE_PLUGIN_ROOT は **別 plugin** を指していることがある
    (ObsidianMemo では ubm-goal-setting)。空ではなく「存在するが別物」なので
    _existing_dir では弾けない。manifest の name で自 plugin か検証する。
    借用側は HC_ROOT を設定すれば明示指定できる。
    拒否するのは manifest が読めて **別 plugin と確認できた** 場合だけにする。
    判定材料が無い (manifest 不在) env は従来どおり採用し、既存挙動を後退
    させない。vendored コピー先 (company-master / skill-intake) でも同様。
    """
    expected = _self_plugin_name()
    if not expected:
        return None
    for _var in ("HC_ROOT", "CLAUDE_PLUGIN_ROOT"):
        root = _existing_dir(os.environ.get(_var))
        if root is None:
            continue
        _name = _manifest_name(root)
        if _name is None or _name == expected:
            return root
    return None


def _discover_plugin_root() -> Path:
    env_root = _hc_env_root()
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
