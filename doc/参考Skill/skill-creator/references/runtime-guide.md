# ランタイムガイド

> **読み込み条件**: スクリプト実装時、ランタイム選定時
> **相対パス**: `references/runtime-guide.md`

---

## 概要

4つのランタイム（Node.js, Python, Bash, Deno）の特性と使い分けガイド。

---

## ランタイム比較

| 項目 | Node.js | Python | Bash | Deno |
|------|---------|--------|------|------|
| 得意分野 | 非同期I/O, Web | データ処理, AI | システム操作 | セキュア実行 |
| パッケージ管理 | npm/pnpm | pip/poetry | system | deno.land |
| 型サポート | TypeScript | 型ヒント | なし | TypeScript |
| 起動速度 | 中 | 遅 | 速 | 中 |
| エコシステム | 豊富 | 豊富 | OS依存 | 成長中 |

---

## 1. Node.js (ESM)

### 基本構造

```javascript
#!/usr/bin/env node

import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// 終了コード
const EXIT_SUCCESS = 0;
const EXIT_ERROR = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_NOT_FOUND = 3;
const EXIT_VALIDATION_FAILED = 4;

// 引数パース
function getArg(args, name) {
  const index = args.indexOf(name);
  return index !== -1 && args[index + 1] ? args[index + 1] : null;
}

async function main() {
  const args = process.argv.slice(2);
  // 実装
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_ERROR);
});
```

### 推奨パッケージ

| カテゴリ | パッケージ | 用途 |
|----------|-----------|------|
| HTTP | axios, node-fetch | API呼び出し |
| ファイル | fs-extra, glob | ファイル操作 |
| CLI | commander, yargs | 引数パース |
| 検証 | ajv, zod | スキーマ検証 |
| テスト | vitest, jest | テスト実行 |
| Git | simple-git | Git操作 |

### ベストプラクティス

| DO | DON'T |
|----|-------|
| ESMモジュール使用 | CommonJS混在 |
| async/await使用 | コールバック地獄 |
| 絶対パス使用 | 相対パス依存 |
| 終了コード明示 | process.exit()省略 |

---

## 2. Python

### 基本構造

```python
#!/usr/bin/env python3
"""
スクリプトの説明
"""

import sys
import os
import json
import argparse
from pathlib import Path

# 終了コード
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ARGS_ERROR = 2
EXIT_FILE_NOT_FOUND = 3
EXIT_VALIDATION_FAILED = 4

def parse_args():
    parser = argparse.ArgumentParser(description="スクリプトの説明")
    parser.add_argument("--input", required=True, help="入力ファイル")
    parser.add_argument("--output", help="出力ファイル")
    parser.add_argument("--verbose", action="store_true", help="詳細出力")
    return parser.parse_args()

def main():
    args = parse_args()
    # 実装

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
```

### 推奨パッケージ

| カテゴリ | パッケージ | 用途 |
|----------|-----------|------|
| HTTP | requests, httpx | API呼び出し |
| データ | pandas, numpy | データ処理 |
| CLI | argparse, click | 引数パース |
| 検証 | jsonschema, pydantic | スキーマ検証 |
| AI | openai, anthropic | AI API |
| Web | beautifulsoup4, selenium | スクレイピング |

### ベストプラクティス

| DO | DON'T |
|----|-------|
| Python 3.10+ 使用 | Python 2互換 |
| pathlib使用 | os.path混在 |
| 型ヒント使用 | 動的型のみ |
| argparse使用 | sys.argv直接 |

---

## 3. Bash

### 基本構造

```bash
#!/usr/bin/env bash
set -euo pipefail

# 終了コード
readonly EXIT_SUCCESS=0
readonly EXIT_ERROR=1
readonly EXIT_ARGS_ERROR=2
readonly EXIT_FILE_NOT_FOUND=3

# カラー出力
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly NC='\033[0m'

# ログ関数
log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ヘルプ表示
show_help() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --input <path>   入力ファイル（必須）
  --output <path>  出力ファイル
  -h, --help       ヘルプ表示
EOF
}

# 引数パース
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --input) INPUT="$2"; shift 2 ;;
      --output) OUTPUT="$2"; shift 2 ;;
      -h|--help) show_help; exit $EXIT_SUCCESS ;;
      *) log_error "不明なオプション: $1"; exit $EXIT_ARGS_ERROR ;;
    esac
  done
}

# メイン処理
main() {
  parse_args "$@"

  if [[ -z "${INPUT:-}" ]]; then
    log_error "--input は必須です"
    exit $EXIT_ARGS_ERROR
  fi

  # 実装

  log_info "完了"
  exit $EXIT_SUCCESS
}

main "$@"
```

### 推奨コマンド

| カテゴリ | コマンド | 用途 |
|----------|---------|------|
| テキスト | grep, sed, awk | テキスト処理 |
| ファイル | find, tar, zip | ファイル操作 |
| ネットワーク | curl, wget | HTTP通信 |
| JSON | jq | JSON処理 |
| Git | git | バージョン管理 |
| Docker | docker, docker-compose | コンテナ |

### ベストプラクティス

| DO | DON'T |
|----|-------|
| set -euo pipefail | エラー無視 |
| "${VAR}" 形式 | $VAR 形式 |
| [[ ]] 使用 | [ ] 使用 |
| readonly 定数 | 定数なし |
| 関数分離 | 巨大スクリプト |

---

## 4. Deno

### 基本構造

```typescript
#!/usr/bin/env -S deno run --allow-read --allow-write

import { parse } from "https://deno.land/std/flags/mod.ts";
import { exists } from "https://deno.land/std/fs/mod.ts";

const EXIT_SUCCESS = 0;
const EXIT_ERROR = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_NOT_FOUND = 3;

interface Args {
  input: string;
  output?: string;
  help?: boolean;
}

function showHelp(): void {
  console.log(`
Usage: deno run script.ts --input <path> [options]

Options:
  --input <path>   入力ファイル（必須）
  --output <path>  出力ファイル
  --help           ヘルプ表示
`);
}

async function main(): Promise<void> {
  const args = parse(Deno.args) as Args;

  if (args.help) {
    showHelp();
    Deno.exit(EXIT_SUCCESS);
  }

  if (!args.input) {
    console.error("Error: --input は必須です");
    Deno.exit(EXIT_ARGS_ERROR);
  }

  if (!(await exists(args.input))) {
    console.error(`Error: ファイルが存在しません: ${args.input}`);
    Deno.exit(EXIT_FILE_NOT_FOUND);
  }

  // 実装

  console.log("✓ 完了");
  Deno.exit(EXIT_SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  Deno.exit(EXIT_ERROR);
});
```

### パーミッション

| フラグ | 用途 |
|--------|------|
| `--allow-read` | ファイル読み取り |
| `--allow-write` | ファイル書き込み |
| `--allow-net` | ネットワークアクセス |
| `--allow-env` | 環境変数アクセス |
| `--allow-run` | サブプロセス実行 |
| `--allow-all` | 全権限（開発用） |

### ベストプラクティス

| DO | DON'T |
|----|-------|
| 最小権限指定 | --allow-all |
| URL import | node_modules |
| TypeScript使用 | JavaScript |
| std ライブラリ | npm互換モジュール |

---

## ランタイム選定ガイド

### 判断フローチャート

```
要件分析
    │
    ├─ システム操作が主体? → Bash
    │
    ├─ データ処理/AI? → Python
    │
    ├─ 非同期I/O/Web? → Node.js
    │
    ├─ セキュリティ重視? → Deno
    │
    └─ 複合要件?
        ├─ 既存エコシステム優先 → Node.js or Python
        └─ シンプルさ優先 → Bash
```

### タイプ別推奨ランタイム

| タイプ | 第1推奨 | 第2推奨 | 理由 |
|--------|---------|---------|------|
| api-client | Node.js | Python | async/await、axios |
| scraper | Python | Node.js | beautifulsoup、selenium |
| database | Node.js | Python | ORM、接続プール |
| git-ops | Bash | Node.js | CLIネイティブ |
| test-runner | Node.js | Python | vitest、pytest |
| docker | Bash | - | CLIネイティブ |
| ai-tool | Bash | Node.js | Claude CLI |
| mcp-bridge | Node.js | - | SDK |
| universal | Node.js | Python | 汎用性 |

---

## 関連リソース

- **タイプカタログ**: See [script-types-catalog.md](script-types-catalog.md)
- **変数ガイド**: See [variable-template-guide.md](variable-template-guide.md)
