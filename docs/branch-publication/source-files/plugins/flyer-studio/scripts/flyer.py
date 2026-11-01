#!/usr/bin/env python3
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
