# 外部CLIエージェント統合ガイド

> **読み込み条件**: externalCliAgents がある場合、または外部CLIエージェントとの連携設計時
> **相対パス**: `references/external-cli-agents-guide.md`

---

## 概要

Claude Code の Bash ツールを通じて外部CLIエージェント（Gemini CLI, Codex, Aider等）を
非インタラクティブに呼び出すための統合ガイド。

---

## エージェント名の正規化マッピング

interview-result.json の `agentName` とCLIコマンドの対応：

| agentName (スキーマ) | CLIコマンド | 備考                                  |
| -------------------- | ----------- | ------------------------------------- |
| `gemini`             | `gemini`    | 名前一致                              |
| `codex`              | `codex`     | 名前一致                              |
| `aider`              | `aider`     | 名前一致                              |
| `claude-code`        | `claude`    | **注意**: agentNameとCLI名が異なる    |
| `custom`             | （任意）    | ユーザー指定のカスタムコマンド        |

> スクリプト内では `claude-code` を `claude` に正規化する必要がある。

---

## 対応CLIエージェント

### Gemini CLI

| 項目           | 詳細                                            |
| -------------- | ----------------------------------------------- |
| コマンド       | `gemini`                                        |
| インストール確認 | `which gemini && gemini --version`            |
| 認証方式       | Google Cloud 認証（キャッシュ済み）             |
| 非インタラクティブ | `gemini "prompt" -o text`                   |

#### 呼び出しパターン

```bash
# 基本: プロンプト文字列で実行
gemini "このコードを分析してください: $(cat code.ts)" -o text

# JSON出力
gemini "データを構造化してください" -o json

# stdin パイプ
cat context.md | gemini -o text

# ファイル付き（-p フラグは非推奨だが動作する）
gemini -p "分析してください" -o text < input.txt

# 自動承認モード（ファイル操作含む）
gemini "リファクタリングしてください" -y -o text

# サンドボックスモード（安全な実行）
gemini "テストを実行して" --sandbox -o text
```

#### 強み
- Google AI Studio との統合
- コンテキストウィンドウが大きい
- マルチモーダル（画像入力対応）
- 無料枠あり

#### 弱み
- ファイル操作は `-y` フラグが必要
- 日本語の精度がモデルにより異なる

---

### Codex CLI

| 項目           | 詳細                                            |
| -------------- | ----------------------------------------------- |
| コマンド       | `codex`                                         |
| インストール確認 | `which codex && codex --version`              |
| 認証方式       | OpenAI API Key（OPENAI_API_KEY環境変数）        |
| 非インタラクティブ | `codex --prompt "..." --output-format text` |

#### 呼び出しパターン

```bash
# 基本: プロンプトで実行
codex --prompt "このバグを修正してください" --output-format text

# コンテキストファイル付き
codex --prompt "分析してください" --context-file context.md

# 出力先指定
codex --prompt "タスク内容" --output codex-output/

# 承認モード指定
codex --prompt "タスク内容" --approval-mode yolo
```

#### 強み
- GPT-5.2の処理能力
- コード生成に特化
- Claudeと異なる視点

#### 弱み
- OpenAI API Key 必要
- ファイル編集に制約あり
- 依存パッケージの問題（要再インストールの場合あり）

---

### Claude Code（再帰呼び出し）

| 項目           | 詳細                                            |
| -------------- | ----------------------------------------------- |
| コマンド       | `claude`                                        |
| インストール確認 | `which claude`                                |
| 認証方式       | Anthropic認証（サブスク内）                     |
| 非インタラクティブ | `claude -p "prompt" --output-format text`   |

#### 呼び出しパターン

```bash
# 非インタラクティブ実行
claude -p "このファイルを分析して: $(cat file.ts)" --output-format text

# JSON出力
claude -p "データを構造化して" --output-format json

# 特定モデル指定
claude -p "タスク" --model sonnet --output-format text
```

#### 注意事項
- 再帰呼び出しとなるため、ネストが深くならないように設計する
- 別プロセスとして実行されるため、現在のコンテキストは共有されない
- サブスク内で追加料金なし

---

### Aider

| 項目           | 詳細                                            |
| -------------- | ----------------------------------------------- |
| コマンド       | `aider`                                         |
| インストール確認 | `which aider && aider --version`              |
| 認証方式       | 各LLMのAPIキー                                  |
| 非インタラクティブ | `aider --message "..." --yes`               |

#### 呼び出しパターン

```bash
# 基本: メッセージで実行
aider --message "このバグを修正して" --yes

# ファイル指定
aider --message "リファクタリングして" --file src/main.ts --yes

# モデル指定
aider --message "タスク" --model claude-3-opus --yes
```

---

## 呼び出しパターン詳細

### 1. delegate（委譲）

特定のサブタスクを外部エージェントに完全に委譲する。

```
[Claude Code] ---(タスク委譲)---> [外部CLI]
[Claude Code] <---(結果取得)---- [外部CLI]
```

**実装例:**
```bash
# タスク準備
echo "分析対象のコード..." > .tmp/context.md

# 委譲実行
RESULT=$(gemini "$(cat .tmp/context.md)

上記のコードを分析し、改善提案をJSON形式で出力してください。" -o json)

# 結果保存
echo "$RESULT" > .tmp/external-cli-result.json
```

**適用場面:** 独立した分析、レビュー、ドキュメント生成

### 2. parallel-review（並列レビュー）

同じ入力を複数のエージェントに送信し、結果を比較する。

```
[Claude Code] ---> [Gemini]  ---> [結果A]
              \                        \
               ---> [Codex]   ---> [結果B] ---> [比較・統合]
```

**適用場面:** セカンドオピニオン、コードレビュー、設計検証

### 3. fallback（フォールバック）

主エージェントが失敗した場合に代替エージェントで再試行する。

```
[Claude Code] ---> [Codex] ---(失敗)---> [Gemini] ---(成功)---> [結果]
```

**適用場面:** 可用性重視のタスク、API制限対策

### 4. pipeline（パイプライン）

複数のエージェントを順次連携させる。

```
[Gemini: 分析] → [Claude Code: 設計] → [Codex: 実装]
```

**適用場面:** 複合タスク、段階的な処理

---

## CLIバージョン管理

外部CLIツールの互換性を確保するため、バージョン情報を記録する。

### バージョン取得方法

| エージェント | バージョン確認コマンド | 備考 |
| --- | --- | --- |
| gemini | `gemini --version` | |
| codex | `codex --version` | |
| claude | `claude --version` | |
| aider | `aider --version` | |

### バージョン記録

実行結果は `external-cli-result.json` の `cliVersion` フィールドに記録する。
厳密なバージョンピニングは現時点では行わないが、
デバッグ・トラブルシューティング時の参照情報として保存する。

---

## コンテキスト準備ガイドライン

### 含めるべき情報

```markdown
# コンテキスト

## タスク概要
- 目的: [何を達成するか]
- 制約: [守るべきルール]

## 入力データ
- [関連するコード、データ、ドキュメント]

## 期待する出力
- フォーマット: [text/json/markdown]
- 構造: [期待する出力の構造]
```

### 含めるべきでない情報

- 機密情報（APIキー、パスワード、認証トークン）
- 無関係なファイル内容
- 過度に大きなコードベース（2,000文字以下が推奨）

---

## スキル生成時の組み込み

skill-creator で新規スキルを生成する際に、外部CLIエージェント連携を組み込む方法:

### SKILL.md への記述テンプレート

```markdown
## 外部CLIエージェント連携

| エージェント | 用途         | 呼び出しパターン | 入力形式      |
| ------------ | ------------ | ---------------- | ------------- |
| gemini       | コード分析   | delegate         | context-file  |
| codex        | レビュー     | parallel-review  | prompt-string |

### 実行方法

\`\`\`bash
# Gemini による分析
gemini "$(cat .tmp/context.md)" -o json > .tmp/analysis.json

# Codex によるレビュー（利用可能な場合）
codex --prompt "レビューしてください" --context-file .tmp/context.md || echo "Codex unavailable"
\`\`\`
```

### スクリプトへの組み込み

```javascript
// scripts/analyze_with_external.js
import { execFileSync } from 'child_process';
import { writeFileSync, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { getArg, EXIT_CODES } from './utils.js';

const agent = getArg('--agent', 'gemini');
const input = getArg('--input');
const timeout = parseInt(getArg('--timeout', '1200')) * 1000;

// エージェント名をホワイトリストで検証（インジェクション防止）
const ALLOWED_AGENTS = ['gemini', 'codex', 'claude', 'aider'];
if (!ALLOWED_AGENTS.includes(agent)) {
  console.error(`Unknown agent: ${agent}. Allowed: ${ALLOWED_AGENTS.join(', ')}`);
  process.exit(EXIT_CODES.INVALID_INPUT);
}

// 可用性チェック（execFileSync でシェル解釈を回避）
try {
  execFileSync('which', [agent], { stdio: 'ignore' });
} catch {
  console.error(`${agent} is not installed`);
  process.exit(EXIT_CODES.PREREQUISITE_NOT_MET);
}

// プロンプトをファイル経由で渡す（シェルインジェクション防止）
const tmpFile = join('.tmp', `prompt-${Date.now()}.txt`);
writeFileSync(tmpFile, input, 'utf-8');

// エージェント別の引数配列（シェル解釈なし）
const agentConfigs = {
  gemini:  { bin: 'gemini', args: ['-o', 'text'],                         stdin: true },
  codex:   { bin: 'codex',  args: ['--prompt', input, '--output-format', 'text'], stdin: false },
  claude:  { bin: 'claude', args: ['-p', input, '--output-format', 'text'],       stdin: false },
  aider:   { bin: 'aider',  args: ['--message', input, '--yes'],                  stdin: false },
};

const config = agentConfigs[agent];

try {
  let result;
  if (config.stdin) {
    // stdin パイプでプロンプトを渡す
    const promptData = readFileSync(tmpFile);
    result = execFileSync(config.bin, config.args, {
      input: promptData, timeout, encoding: 'utf-8'
    });
  } else {
    result = execFileSync(config.bin, config.args, { timeout, encoding: 'utf-8' });
  }
  console.log(result);
} finally {
  try { unlinkSync(tmpFile); } catch { /* cleanup best-effort */ }
}
```

> **セキュリティ注意**: `execSync` + テンプレート文字列は**シェルインジェクション脆弱性**の原因になります。
> 必ず `execFileSync` + 引数配列を使用し、ユーザー入力をシェル解釈させないでください。

---

## 将来の拡張: MCP統合

> **検討事項**: 外部CLIエージェントとの通信手段として、将来的に
> [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) を活用する選択肢がある。
> MCPサーバーを介したツール呼び出しにより、CLI直接実行よりも型安全で
> 構造化された通信が可能になる。現時点ではCLI直接実行で十分だが、
> エージェント間の複雑な協調が必要になった場合はMCPベースの統合を検討すること。

---

## 変更履歴

| Version | Date       | Changes                                      |
| ------- | ---------- | -------------------------------------------- |
| 1.2.0   | 2026-02-13 | CLIバージョン管理セクション追加（バージョン取得方法・記録方法） |
| 1.1.0   | 2026-02-13 | セキュリティ修正、正規化マッピング、MCP検討追加 |
| 1.0.0   | 2026-02-13 | 初版作成                                     |
