#!/usr/bin/env python3
# /// script
# name: extract-plugin-root
# version: 0.1.0
# purpose: 兄弟 plugin の root を、install 先の配置に依存せず絶対パスで返す vendored 共有 CLI。
#          `${PLUGIN_ROOT}/../<plugin>` は repo の plugins/ でしか兄弟に届かないため、その代わりに使う。
# inputs:
#   - argv: <plugin-name> [--from <plugin-root>]
#   - env: CLAUDE_CONFIG_DIR / CODEX_HOME / HOME
#   - files: <claude-config>/plugins/installed_plugins.json, <root>/.claude-plugin/plugin.json,
#            <root>/.codex-plugin/plugin.json
# outputs:
#   - stdout: 解決した plugin root の絶対パス 1 行
#   - exit: 0=解決 / 1=見つからない / 2=usage
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Resolve a sibling plugin root regardless of where the host installed it.

repo では plugins/<name>/ が兄弟として並ぶが、install 先は
``<cache>/<marketplace>/<plugin>/<version>/`` なので ``<root>/..`` の先は
同じ plugin の別 version 群になり兄弟へ届かない。本 CLI は候補を

1. 自分自身 (依頼された名前が自 plugin)
2. ``<root>/../<name>`` (repo / marketplace の兄弟配置)
3. Claude の installed_plugins.json のうち自分と同じ marketplace の現行 install
4. 自分と同じ marketplace の cache の最新 version
5. 他の marketplace の installed_plugins.json
6. Claude / Codex の cache 全体の最新 version

の順に挙げ、manifest の ``name`` が一致した最初の候補だけを返す。
見つからなければ exit 1 で止め、呼び出し側に外部変更へ進ませない (fail-closed)。

repo-root の scripts/extract-plugin-root.py が正本。各 plugin の scripts/ へ
byte 一致で vendor し、``scripts/lint-vendored-ssot.py`` が一致を強制する。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator, Optional

MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def manifest_name(root: Path) -> Optional[str]:
    """root が plugin なら manifest の name を返す (どちらの host の manifest でもよい)。"""
    for rel in MANIFESTS:
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name:
            return name
    return None


def _version_key(path: Path) -> tuple:
    """semver の version dir を新しい順に並べる。git sha などの dir は semver より後ろ。"""
    match = SEMVER_RE.fullmatch(path.name)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    if match:
        return (1, tuple(int(part) for part in match.groups()), mtime)
    return (0, (), mtime)


def _versions(plugin_dir: Path) -> list:
    try:
        children = [child for child in plugin_dir.iterdir() if child.is_dir()]
    except OSError:
        return []
    return sorted(children, key=_version_key, reverse=True)


def _is_within(path: Path, ancestor: Path) -> bool:
    try:
        path.resolve().relative_to(ancestor.resolve())
    except (OSError, ValueError):
        return False
    return True


def _claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def _installed(name: str, cwd: Path) -> tuple:
    """有効な (marketplace, project 一致, installPath) と scope 外専用 path を返す。

    他プロジェクト専用 (scope=project/local) の install は、そのプロジェクトの外では
    有効でないので cache fallback でも候補にしない。同じ path に有効な登録もある
    場合は共有 install として許可する。
    """
    path = _claude_home() / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], set()
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return [], set()
    rows = []
    blocked = set()
    for key, entries in plugins.items():
        plugin, _, marketplace = str(key).partition("@")
        if plugin != name or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("installPath"), str):
                continue
            project = entry.get("projectPath")
            in_project = isinstance(project, str) and _is_within(cwd, Path(project))
            install_path = Path(entry["installPath"])
            if entry.get("scope") in ("project", "local") and not in_project:
                blocked.add(install_path.resolve())
                continue
            rows.append((marketplace, in_project, install_path))
    # project 単位の install は user 単位より優先される (host の解決順と同じ)。
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows, blocked - {path.resolve() for _, _, path in rows}


def candidates(name: str, self_root: Path, cwd: Path) -> Iterator[Path]:
    """name の plugin root になりうる場所を、確からしい順に返す (検証は呼び出し側)。"""
    own_name = manifest_name(self_root)
    installed, blocked = _installed(name, cwd)
    if own_name == name:
        yield self_root
    sibling = self_root.parent / name
    if sibling.resolve() not in blocked:
        yield sibling
    # cache 配置 (<cache>/<marketplace>/<plugin>/<version>/) なら自分の marketplace が分かる。
    marketplace = self_root.parent.parent.name if self_root.parent.name == own_name else None
    if marketplace is not None:
        for market, _, path in installed:
            if market == marketplace:
                yield path
        yield from (
            path for path in _versions(self_root.parent.parent / name)
            if path.resolve() not in blocked
        )
    for market, _, path in installed:
        if market != marketplace:
            yield path
    cached = []
    for home in (_claude_home(), _codex_home()):
        cache = home / "plugins" / "cache"
        try:
            markets = sorted(child for child in cache.iterdir() if child.is_dir())
        except OSError:
            continue
        for market_dir in markets:
            cached.extend(_versions(market_dir / name))
    yield from (
        path for path in sorted(cached, key=_version_key, reverse=True)
        if path.resolve() not in blocked
    )


def resolve(name: str, self_root: Path, cwd: Optional[Path] = None) -> Optional[Path]:
    seen = set()
    for candidate in candidates(name, self_root, cwd or Path.cwd()):
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_dir() and manifest_name(candidate) == name:
            return candidate.resolve()
    return None


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plugin", help="解決したい plugin の name (manifest の name)")
    parser.add_argument(
        "--from",
        dest="self_root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="探索の起点にする plugin root (既定: この script を持つ plugin)",
    )
    args = parser.parse_args(argv)
    if not NAME_RE.fullmatch(args.plugin):
        print(f"invalid plugin name: {args.plugin!r}", file=sys.stderr)
        return 2
    found = resolve(args.plugin, args.self_root.resolve())
    if found is None:
        print(
            f"plugin not found: {args.plugin} (searched sibling dir, installed_plugins.json, "
            f"{_claude_home() / 'plugins' / 'cache'}, {_codex_home() / 'plugins' / 'cache'})",
            file=sys.stderr,
        )
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
