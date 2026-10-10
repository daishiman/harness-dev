#!/usr/bin/env python3
# /// script
# name: plugin_resources
# purpose: Harness Creator 内の sibling plugin root/resource 解決と intelligence 互換入口の転送を共有する。
# inputs: caller-owned plugin root, plugin name and resource path
# outputs: resolved Path or None; ResolverUnavailable when the bundled resolver is missing; forward_external_intelligence は転送先の実行結果 (stdout・exit・書き込み) をそのまま持つ
# contexts: [C, E]
# network: false
# write-scope: 自身は書かない。forward_external_intelligence は転送先 (skill-governance-adapters の scripts/build-external-intelligence*.py) を runpy で同じ process に実行するので、転送先の write-scope の書き込みが起きる
# dependencies: [extract-plugin-root.py]
# requires-python: ">=3.10"
# ///
"""Harness Creator's local consumers share one resolver bootstrap.

Callers supply their own plugin root; this module never infers it from cwd or
from a previously imported resolver. Missing-provider policy stays with the
caller (package failure, sentinel path, or the historical forwarder error).
"""
from __future__ import annotations

import importlib.util
import runpy
from pathlib import Path
from types import ModuleType


class ResolverUnavailable(RuntimeError):
    """The caller's bundled root resolver is missing."""


# resolver は読み込んだ file の path ごとに持つ。sys.modules の共有の名前に登録すると、
# 別の plugin root から読んだ resolver どうしが上書きし合い、呼び手の root を取り違える。
_RESOLVERS: dict[Path, ModuleType] = {}


def _load_resolver(plugin_root: Path) -> ModuleType:
    resolver = plugin_root / "scripts" / "extract-plugin-root.py"
    if not resolver.is_file():
        raise ResolverUnavailable("extract-plugin-root.py is missing from harness-creator/scripts")
    key = resolver.resolve()
    cached = _RESOLVERS.get(key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location("_harness_creator_plugin_root", key)
    if spec is None or spec.loader is None:
        raise ResolverUnavailable(f"cannot load resolver: {key}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RESOLVERS[key] = module
    return module


def resolve_root(name: str, plugin_root: Path, cwd: Path | None = None) -> Path | None:
    return _load_resolver(plugin_root).resolve(name, plugin_root, cwd or Path.cwd())


def resolve_resource(name: str, relative_path: str, plugin_root: Path) -> Path | None:
    root = resolve_root(name, plugin_root)
    return None if root is None else root / relative_path


def forward_external_intelligence(namespace: dict[str, object]) -> None:
    """Keep both historical skill script paths while forwarding their provider APIs.

    転送先は runpy で同じ process に実行する。転送先の書き込み・stdout・exit は呼び手のものになる。
    """
    caller = Path(str(namespace["__file__"])).resolve()
    provider = "skill-governance-adapters"
    relative_path = f"scripts/{caller.name}"
    try:
        canonical = resolve_resource(provider, relative_path, caller.parents[3])
    except ResolverUnavailable:
        canonical = None
    canonical = canonical if canonical is not None else Path(f"plugin:{provider}/{relative_path}")
    namespace["CANONICAL_PATH"] = canonical
    if not canonical.is_file():
        raise RuntimeError(
            "external-intelligence provider is unavailable; install "
            "skill-governance-adapters or use a standard bundle"
        )
    forwarded = runpy.run_path(
        str(canonical), run_name="__main__" if namespace["__name__"] == "__main__" else None
    )
    namespace.update({
        key: value for key, value in forwarded.items()
        if key not in {"__name__", "__file__", "__package__", "__spec__", "__loader__"}
    })
