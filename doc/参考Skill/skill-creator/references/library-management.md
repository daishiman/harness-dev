# ライブラリ管理ガイド

> **読み込み条件**: 依存関係追加時、スキル初期化時
> **相対パス**: `references/library-management.md`

---

## 概要

スキルは**自己完結型**として設計されている。各スキルは独自の`package.json`と`node_modules`を持ち、プロジェクト本体の依存関係と干渉しない。

---

## 1. 設計思想

### 1.1 なぜ自己完結型か

| 理由 | 説明 |
|------|------|
| 分離 | プロジェクト本体のnode_modulesと干渉しない |
| 再現性 | スキル単位でバージョンを固定できる |
| 移植性 | スキルディレクトリごと移動・共有可能 |
| 独立性 | スキル間で異なるバージョンの同一ライブラリを使用可能 |

### 1.2 PNPMを選択する理由

| 特徴 | 利点 |
|------|------|
| ディスク効率 | 同一パッケージは1箇所に保存、ハードリンク使用 |
| 高速 | キャッシュによる高速インストール |
| 厳密な依存関係 | phantom dependencyを防止 |
| ワークスペース対応 | モノレポとの親和性 |

---

## 2. スキル構造

### 2.1 基本構造

```
.claude/skills/my-skill/
├── package.json         # 依存関係定義
├── pnpm-lock.yaml       # 依存関係ロック（自動生成）
├── node_modules/        # 依存関係（スキル内に配置）
├── SKILL.md             # スキル定義
├── LOGS.md              # 実行ログ
├── EVALS.json           # メトリクス
├── scripts/             # スクリプト
│   └── my-script.js
├── agents/              # エージェント
├── references/          # 参照資料
└── assets/              # テンプレート
```

### 2.2 package.json テンプレート

```json
{
  "name": "@skills/my-skill",
  "version": "1.0.0",
  "description": "Claude Code skill: my-skill",
  "type": "module",
  "private": true,
  "scripts": {
    "validate": "node scripts/validate_all.js",
    "log": "node scripts/log_usage.js",
    "deps:install": "pnpm install",
    "deps:add": "pnpm add"
  },
  "engines": {
    "node": ">=18.0.0"
  },
  "dependencies": {},
  "devDependencies": {},
  "keywords": ["claude-code", "skill"],
  "author": "AIWorkflowOrchestrator",
  "license": "UNLICENSED"
}
```

---

## 3. 依存関係管理コマンド

### 3.1 依存関係インストール

```bash
# 現在のスキル（skill-creator）の依存関係をインストール
node .claude/skills/skill-creator/scripts/install_deps.js

# 指定スキルの依存関係をインストール
node .claude/skills/skill-creator/scripts/install_deps.js --skill-path .claude/skills/my-skill

# 本番依存関係のみインストール
node .claude/skills/skill-creator/scripts/install_deps.js --prod

# lockfileを変更しない（CI向け）
node .claude/skills/skill-creator/scripts/install_deps.js --frozen
```

### 3.2 依存関係追加

```bash
# 本番依存関係として追加
node .claude/skills/skill-creator/scripts/add_dependency.js axios

# 開発依存関係として追加
node .claude/skills/skill-creator/scripts/add_dependency.js typescript --dev
node .claude/skills/skill-creator/scripts/add_dependency.js vitest -D

# バージョン指定で追加
node .claude/skills/skill-creator/scripts/add_dependency.js lodash@4.17.21

# 複数パッケージを追加
node .claude/skills/skill-creator/scripts/add_dependency.js zod ajv

# 他のスキルに対して実行
node .claude/skills/skill-creator/scripts/add_dependency.js axios --skill-path .claude/skills/my-skill
```

### 3.3 直接PNPMを使用

スキルディレクトリ内で直接PNPMを使用することも可能：

```bash
cd .claude/skills/my-skill

# 依存関係インストール
pnpm install

# パッケージ追加
pnpm add axios
pnpm add -D typescript

# パッケージ削除
pnpm remove axios

# パッケージ更新
pnpm update
```

---

## 4. スクリプトでの依存関係使用

### 4.1 ESM形式（推奨）

```javascript
#!/usr/bin/env node

// 外部パッケージをインポート
import axios from "axios";
import { z } from "zod";

// Node.js組み込みモジュール
import { readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  // axiosを使用
  const response = await axios.get("https://api.example.com/data");

  // zodでバリデーション
  const schema = z.object({
    id: z.number(),
    name: z.string(),
  });

  const validated = schema.parse(response.data);
  console.log(validated);
}

main().catch(console.error);
```

### 4.2 package.json の type 設定

ESMを使用するには、package.jsonに`"type": "module"`が必要：

```json
{
  "type": "module"
}
```

---

## 5. よくある依存関係パターン

### 5.1 API連携

```bash
node .claude/skills/skill-creator/scripts/add_dependency.js axios   # HTTPクライアント
node .claude/skills/skill-creator/scripts/add_dependency.js got     # 軽量HTTPクライアント
```

### 5.2 データ処理

```bash
node .claude/skills/skill-creator/scripts/add_dependency.js lodash        # ユーティリティ
node .claude/skills/skill-creator/scripts/add_dependency.js date-fns      # 日付処理
node .claude/skills/skill-creator/scripts/add_dependency.js csv-parse     # CSV解析
node .claude/skills/skill-creator/scripts/add_dependency.js yaml          # YAML処理
```

### 5.3 バリデーション

```bash
node .claude/skills/skill-creator/scripts/add_dependency.js zod           # スキーマバリデーション
node .claude/skills/skill-creator/scripts/add_dependency.js ajv           # JSONスキーマ
```

### 5.4 開発ツール

```bash
node .claude/skills/skill-creator/scripts/add_dependency.js typescript --dev   # TypeScript
node .claude/skills/skill-creator/scripts/add_dependency.js vitest --dev       # テスト
node .claude/skills/skill-creator/scripts/add_dependency.js prettier --dev     # フォーマッター
```

---

## 6. トラブルシューティング

### 6.1 PNPMがインストールされていない

```bash
# エラー
Error: pnpm がインストールされていません

# 解決策
npm install -g pnpm
```

### 6.2 package.jsonが存在しない

```bash
# エラー
Error: package.json が存在しません

# 解決策1: init_skill.js を使用
node .claude/skills/skill-creator/scripts/init_skill.js my-skill

# 解決策2: 手動作成
echo '{"name":"@skills/my-skill","type":"module","dependencies":{}}' > package.json
```

### 6.3 依存関係の競合

```bash
# pnpm-lock.yamlを削除して再インストール
rm pnpm-lock.yaml
pnpm install
```

### 6.4 phantom dependency エラー

```
Error: Cannot find module 'some-package'
```

PNPMは厳密な依存関係を強制するため、package.jsonに明示的に追加されていないパッケージは使用できない。

```bash
# 解決策: 必要なパッケージを明示的に追加
node .claude/skills/skill-creator/scripts/add_dependency.js some-package
```

---

## 7. ベストプラクティス

### すべきこと

| 推奨事項 | 理由 |
|----------|------|
| pnpm-lock.yaml をコミット | 再現性確保 |
| node_modules を .gitignore | ストレージ節約 |
| 最小限の依存関係 | シンプルさ維持 |
| バージョン固定 | 安定性確保 |

### 避けるべきこと

| アンチパターン | 問題 |
|----------------|------|
| グローバルインストール | 移植性低下 |
| node_modules をコミット | リポジトリ肥大化 |
| `*` バージョン指定 | 不安定性 |
| 不要な依存関係 | 複雑さ増大 |

---

## 8. .gitignore 設定

スキルディレクトリ用の推奨設定：

```gitignore
# スキル内のnode_modules
.claude/skills/*/node_modules/

# 一時ファイル
.claude/skills/*/.tmp/
```

---

## 関連リソース

- **スクリプト**: See [scripts/install_deps.js](.claude/skills/skill-creator/scripts/install_deps.js)
- **スクリプト**: See [scripts/add_dependency.js](.claude/skills/skill-creator/scripts/add_dependency.js)
- **初期化**: See [scripts/init_skill.js](.claude/skills/skill-creator/scripts/init_skill.js)
- **スキル構造**: See [references/skill-structure.md](.claude/skills/skill-creator/references/skill-structure.md)
