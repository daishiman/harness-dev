# /// script
# name: plugin_resources
# purpose: Harness Creator 内の sibling plugin root/resource 解決と intelligence 互換入口の転送を共有する。
# inputs: caller-owned plugin root, plugin name and resource path
# outputs: resolved Path or None; ResolverUnavailable when the bundled resolver is missing
# contexts: [C, E]
# network: false
# write-scope: none
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
import sys
from pathlib import Path


class ResolverUnavailable(RuntimeError):
    """The caller's bundled root resolver is missing."""


def resolve_root(name: str, plugin_root: Path, cwd: Path | None = None) -> Path | None:
    resolver = plugin_root / "scripts" / "extract-plugin-root.py"
    spec = (
        importlib.util.spec_from_file_location("_harness_creator_plugin_root", resolver)
        if resolver.is_file() else None
    )
    if spec is None or spec.loader is None:
        raise ResolverUnavailable("extract-plugin-root.py is missing from harness-creator/scripts")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.resolve(name, plugin_root, cwd or Path.cwd())


def resolve_resource(name: str, relative_path: str, plugin_root: Path) -> Path | None:
    root = resolve_root(name, plugin_root)
    return None if root is None else root / relative_path


def forward_external_intelligence(namespace: dict[str, object]) -> None:
    """Keep both historical skill script paths while forwarding their provider APIs."""
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
