#!/usr/bin/env python3
# /// script
# name: build-flyer
# purpose: 同じフォルダのNode CLIへ引数と終了コードを渡す
# inputs: argv: CLI command and project arguments
# outputs: stdout/stderr and backend exit code
# contexts: [C, E]
# network: false
# write-scope: 案件コマンドが明示するproject/ledger出力。doctor/validate系は読取
# dependencies: []
# ///
"""自己相対でNode描画バックエンドへ接続する、Python標準ライブラリの入口。"""
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    node = shutil.which('node')
    if node is None:
        print('Node.js 22以降を導入してください。READMEのセットアップを参照。', file=sys.stderr)
        return 2
    backend = Path(__file__).resolve().with_name('cli.cjs')
    return subprocess.run([node, str(backend), *sys.argv[1:]], check=False).returncode

if __name__ == '__main__':
    sys.exit(main())
