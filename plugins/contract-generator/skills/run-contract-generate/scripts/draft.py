#!/usr/bin/env python3
# /// script
# name: draft
# purpose: run-contract-generate のエントリ。共有lib(engine)を --phase draft で呼び、下書きDocs生成+Slack通知する。
# inputs:
#   - argv: --type --row --config --dry-run (engineへ委譲)
# outputs:
#   - Docs黄色版生成 + Slack通知 + 台帳draft化
# contexts: [C, E]
# network: true
# write-scope: google-drive,google-sheets,slack
# dependencies: []
# requires-python: ">=3.11"
# ///
"""run-contract-generate(draft責務)のエントリ。共有ライブラリ plugins/contract-generator/lib を呼ぶ。"""

import os
import sys

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib")
sys.path.insert(0, os.path.abspath(LIB))

import engine  # noqa: E402

if __name__ == "__main__":
    if "--phase" not in sys.argv:
        sys.argv += ["--phase", "draft"]
    sys.exit(engine.main())
