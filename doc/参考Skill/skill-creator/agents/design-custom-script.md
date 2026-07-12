# Task仕様書：カスタムスクリプト設計

> **読み込み条件**: 定義済みタイプに収まらない独自スクリプトが必要な時
> **相対パス**: `agents/design-custom-script.md`
> **Phase**: 2（設計サブタスク）

## 1. メタ情報

| 項目     | 内容                       |
| -------- | -------------------------- |
| 名前     | Kent Beck                  |
| 専門領域 | ソフトウェア設計・テスト駆動開発 |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

定義済みタイプに収まらない独自スクリプトを設計する。
ユーザーの要件をヒアリングし、ゼロから柔軟にスクリプトを設計する。

### 2.2 目的

ユーザー要件から、custom-script-design.jsonを生成し、コード生成の基盤を提供する。

### 2.3 責務

| 責務                   | 成果物                 |
| ---------------------- | ---------------------- |
| スクリプト設計         | custom-script-design.json |
| 変数定義               | variables部分          |

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント               | 適用方法                           |
| ------------------------------- | ---------------------------------- |
| Clean Code (Robert C. Martin)   | 単一責任の原則、明示的な入出力     |
| Test Driven Development (Beck)  | テスト可能な設計                   |
| references/runtime-guide.md     | ランタイム別ベストプラクティス     |
| schemas/custom-script-design.json | 出力スキーマ                     |

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション                                     | 担当 |
| -------- | ---------------------------------------------- | ---- |
| 1        | ユーザー要件を受け取る                         | LLM  |
| 2        | 目的（purpose）を明確化                        | LLM  |
| 3        | 入力（inputs）を特定                           | LLM  |
| 4        | 出力（outputs）を特定                          | LLM  |
| 5        | ランタイム（runtime）を決定                    | LLM  |
| 6        | 依存関係（dependencies）を特定                 | LLM  |
| 7        | 構造（structure）を設計                        | LLM  |
| 8        | エラーハンドリング戦略を決定                   | LLM  |
| 9        | テンプレート変数（variables）を設計            | LLM  |
| 10       | custom-script-design.jsonを出力                | LLM  |

### 4.2 設計パターン

| パターン         | 用途                       | 例                   |
| ---------------- | -------------------------- | -------------------- |
| データパイプライン | 入力→変換→出力の流れ      | ログ解析、CSVからJSON |
| オーケストレーション | 複数ステップの制御        | CI/CD、バッチ処理     |
| イベント駆動     | 待機→検知→処理のループ    | ファイル監視、Webhook |
| ラッパー/ブリッジ | 既存コマンドの拡張        | CLIラッパー、API連携  |

### 4.3 チェックリスト

| 項目                     | 基準                         |
| ------------------------ | ---------------------------- |
| 目的が明確か             | 1つの明確な責務              |
| 入出力が定義されているか | 型、説明、必須/任意が明確    |
| ランタイムが決定しているか | node/python/bash/bun/deno  |
| 依存関係が特定されているか | 必要なパッケージがリスト化  |
| 関数構造が設計されているか | メイン関数、コア処理が明確  |
| 変数がプレースホルダー化されているか | {{変数名}}形式       |

### 4.4 ビジネスルール（制約）

| 制約             | 説明                               |
| ---------------- | ---------------------------------- |
| 単一責任の原則   | 1つのスクリプトは1つの責務         |
| 明示的な入出力   | 暗黙の依存を避ける                 |
| 設定の外部化     | ハードコードを避ける               |
| エラーの明示     | 失敗を隠さない                     |
| テスト可能な設計 | 関数を純粋に保つ                   |

---

## 5. インターフェース

### 5.1 入力

| データ名         | 提供元          | 検証ルール           | 欠損時処理       |
| ---------------- | --------------- | -------------------- | ---------------- |
| ユーザー要件     | interview-result.jsonまたは直接入力 | scriptsセクションが存在 | ヒアリング実施  |
| ランタイム       | detect_runtime.js | 有効なランタイム     | デフォルトnode   |

### 5.2 出力

| 成果物名                 | 受領先          | 内容                           |
| ------------------------ | --------------- | ------------------------------ |
| custom-script-design.json | generate-code   | スクリプト設計の構造化データ   |

#### 出力スキーマ

```json
{
  "$schema": ".claude/skills/skill-creator/schemas/custom-script-design.json",
  "name": "{{string: スクリプト名}}",
  "purpose": "{{string: スクリプトの目的}}",
  "runtime": "{{enum: node|python|bash|bun|deno}}",
  "inputs": [
    {
      "name": "{{string: 入力名}}",
      "type": "{{enum: string|number|boolean|array|object|file}}",
      "description": "{{string: 入力の説明}}",
      "required": "{{boolean}}",
      "default": "{{any: デフォルト値}}"
    }
  ],
  "outputs": [
    {
      "name": "{{string: 出力名}}",
      "type": "{{enum: string|number|boolean|array|object|file}}",
      "description": "{{string: 出力の説明}}"
    }
  ],
  "dependencies": [
    {
      "name": "{{string: パッケージ名}}",
      "version": "{{string: バージョン}}",
      "purpose": "{{string: 使用目的}}"
    }
  ],
  "structure": {
    "functions": [
      {
        "name": "{{string: 関数名}}",
        "purpose": "{{string: 関数の目的}}",
        "params": ["{{string: パラメータ}}"],
        "returns": "{{string: 戻り値の型}}"
      }
    ],
    "mainFlow": ["{{string: 処理フローのステップ}}"]
  },
  "errorHandling": {
    "strategy": "{{enum: throw|return|log|retry}}",
    "retryCount": "{{number: リトライ回数}}",
    "fallback": "{{string: フォールバック処理}}"
  },
  "variables": [
    {
      "name": "{{string: 変数名}}",
      "placeholder": "{{string: {{変数名}}}}",
      "type": "{{enum: string|number|boolean}}",
      "description": "{{string: 変数の説明}}",
      "default": "{{any: デフォルト値}}"
    }
  ]
}
```

### 5.3 後続処理

```bash
# スキーマ検証（Script Task）
node scripts/validate_schema.js \
  --input .tmp/custom-script-design.json \
  --schema schemas/custom-script-design.json

# コード生成へ（次のLLM Task）
# → generate-code.md を読み込み
```

---

## 6. 補足：ランタイム別構造

### Node.js (ESM)

```javascript
import { parseArgs } from 'node:util';
import { readFile, writeFile } from 'node:fs/promises';

async function main() {
  const { values } = parseArgs({ options: { /* ... */ } });
  // 処理
}

main().catch(console.error);
```

### Python

```python
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    # 引数定義
    args = parser.parse_args()
    # 処理

if __name__ == "__main__":
    main()
```

### Bash

```bash
#!/usr/bin/env bash
set -euo pipefail

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

main() {
  # 処理
}

main "$@"
```

---

## 7. 補足：ヒアリング質問

```
AskUserQuestion:
  questions:
    - question: "どのような処理を行いますか？"
      header: "処理内容"
      options:
        - label: "データ変換"
        - label: "外部連携"
        - label: "ファイル操作"
        - label: "その他"

    - question: "入力はどこから取得しますか？"
      header: "入力"
      options:
        - label: "コマンドライン引数"
        - label: "ファイル"
        - label: "標準入力"
        - label: "環境変数"

    - question: "エラー時の動作は？"
      header: "エラー処理"
      options:
        - label: "即座に終了"
        - label: "リトライ"
        - label: "スキップ"
        - label: "フォールバック"
```
