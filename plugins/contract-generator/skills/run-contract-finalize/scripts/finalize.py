#!/usr/bin/env python3
# /// script
# name: finalize
# purpose: run-contract-finalize のエントリ。共有lib(engine)を --phase poll→finalize で呼び、承認検知→PDF生成+Slack共有する。
# inputs:
#   - argv: --type --row --config --dry-run (engineへ委譲)
# outputs:
#   - 承認検知(approved化) + PDF生成 + Slack再共有 + 台帳completed化
# contexts: [C, E]
# network: true
# write-scope: google-drive,google-sheets,slack
# dependencies: []
# requires-python: ">=3.11"
# ///
"""run-contract-finalize(承認+確定責務)のエントリ。

poll(承認検知)→finalize(PDF生成・共有)を順に実行。共有ライブラリ lib を呼ぶ。
既定はユーザーが Claude Code で確定を明示指示したときに 1 回実行する(pull型)。
任意で cron 定期起動も可(純Pythonのため LLM トークン費用ゼロ。常駐デプロイの代替)。
"""

import os
import sys

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib")
sys.path.insert(0, os.path.abspath(LIB))

import engine  # noqa: E402


def _strip_phase(argv):
    out, skip = [], False
    for x in argv:
        if skip:
            skip = False
            continue
        if x == "--phase":
            skip = True
            continue
        out.append(x)
    return out


def main():
    # 既定(pull型): Claude Code 実行が発火条件。finalize で draft 行を直接 PDF 化→completed。
    # Slack承認は必須ゲートではないため poll は回さない。
    # 任意で二者承認したい場合のみ `python3 lib/engine.py --phase poll` を別途実行する。
    base_argv = _strip_phase(sys.argv[1:])
    sys.argv = ["finalize", "--phase", "finalize"] + base_argv
    return engine.main()


if __name__ == "__main__":
    sys.exit(main())
