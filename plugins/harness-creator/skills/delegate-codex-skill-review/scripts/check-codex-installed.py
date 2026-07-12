#!/usr/bin/env python3
# /// script
# name: check-codex-installed
# purpose: Check optional Codex CLI availability without shell dependencies.
# inputs:
#   - argv: none
# outputs:
#   - stdout: availability message
#   - stderr: unavailable message
#   - exit: 0=available / 2=missing
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Check optional Codex CLI availability without shell dependencies."""

from __future__ import annotations

import shutil
import sys


def main() -> int:
    codex = shutil.which("codex")
    if not codex:
        sys.stderr.write(
            "ERROR: codex CLI が見つかりません。\n"
            "       delegate-codex-skill-review は任意の外部CLI委譲Skillです。\n"
            "       標準の harness-creator フローでは必須ではありません。\n"
            "       利用する場合のみ、公式に確認済みの配布元から codex CLI を導入してください。\n"
        )
        return 2

    print(f"ok: codex command found at {codex} (optional; not executed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
