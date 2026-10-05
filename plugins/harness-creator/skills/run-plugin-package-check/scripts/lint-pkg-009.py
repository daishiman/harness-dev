#!/usr/bin/env python3
# /// script
# name: lint-pkg-009
# purpose: Resolve skill-governance-lint from the install layout and run its lint-external-refs.py for PKG-009.
# inputs:
#   - argv: lint-external-refs.py arguments, passed through unchanged
# outputs:
#   - stdout/exit: lint-external-refs.py output and exit code; when the linter is unreachable,
#     a PKG-009 fail JSON on stdout and exit 2
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [../../../scripts/extract-plugin-root.py]
# ///
"""PKG-009 の外部参照 lint を、install 配置に依存せず起動する。"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]


class LinterUnavailable(RuntimeError):
    """resolver か兄弟 plugin が無く、lint-external-refs.py に届かない。"""


def linter_path() -> Path:
    """skill-governance-lint の lint-external-refs.py を install 配置に依存せず解決する。

    install 先 (<cache>/<marketplace>/<plugin>/<version>/) では `../` で兄弟 plugin に届かないので、
    harness-creator に同梱した resolver に任せる。
    """
    resolver = PLUGIN_ROOT / "scripts" / "extract-plugin-root.py"
    # spec_from_file_location は実在しない path にも spec を返すので、先に実在を確かめる。
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", resolver) if resolver.is_file() else None
    if spec is None or spec.loader is None:
        raise LinterUnavailable("extract-plugin-root.py is missing from harness-creator/scripts")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found = module.resolve("skill-governance-lint", PLUGIN_ROOT, Path.cwd())
    if found is None:
        raise LinterUnavailable("skill-governance-lint plugin not found; install it to run PKG-009")
    return found / "scripts" / "lint-external-refs.py"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        linter = linter_path()
    except LinterUnavailable as exc:
        # 推測 path で lint は呼ばない。停止理由を PKG-009 のログ (stdout) に残し、集約で fail と数えさせる。
        print(json.dumps({"pkg_id": "PKG-009", "status": "fail", "findings": [str(exc)]}, ensure_ascii=False))
        print(exc, file=sys.stderr)
        return 2
    return subprocess.run([sys.executable, str(linter), *args], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
