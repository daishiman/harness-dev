# N/A判定ログテンプレート

## 用途

Phase 12（ドキュメント整備）段階で、SubAgent が担当仕様書の更新状況を記録するためのテンプレートです。各仕様書に対して以下のいずれかの判定を記録する必須フィールドです。

## 仕様書別判定ログテーブル

**指定仕様書グループ**: 推奨5点セット

| # | 仕様書名 | 判定 | 理由 | 代替証跡 | 担当SubAgent | 更新日 |
|---|----------|------|------|----------|-------------|--------|
| 1 | {{specName-1}} | 更新 / N/A | {{reason}} | {{alternativeEvidence}} | {{updatedBy}} | {{YYYY-MM-DD}} |
| 2 | {{specName-2}} | 更新 / N/A | {{reason}} | {{alternativeEvidence}} | {{updatedBy}} | {{YYYY-MM-DD}} |
| 3 | {{specName-3}} | 更新 / N/A | {{reason}} | {{alternativeEvidence}} | {{updatedBy}} | {{YYYY-MM-DD}} |
| 4 | {{specName-4}} | 更新 / N/A | {{reason}} | {{alternativeEvidence}} | {{updatedBy}} | {{YYYY-MM-DD}} |
| 5 | {{specName-5}} | 更新 / N/A | {{reason}} | {{alternativeEvidence}} | {{updatedBy}} | {{YYYY-MM-DD}} |

## 記入ガイド

### 判定フィールド

- **「更新」**: 本タスク実施中にこの仕様書に変更を加えた場合
  - 理由欄: 何を変更したのか（1文以上、中学生レベルで説明）
  - 代替証跡: diff コマンドで確認された変更行数、または「diff: +{{追加行}} / -{{削除行}}」の形式

- **「N/A」**: 本タスク実施中にこの仕様書に変更が不要であった場合
  - 理由欄: なぜ変更不要なのか（1文以上、具体的理由を記述）
  - 代替証跡: その判断の根拠（grep 検索結果、git diff の確認、参照リンク等）

### 必須・必須でないルール

| フィールド | 「更新」時 | 「N/A」時 | 備考 |
|-----------|-----------|---------|------|
| specName | 必須 | 必須 | 空文字列禁止 |
| 判定 | 必須（「更新」） | 必須（「N/A」） | これら2つのいずれか必須 |
| 理由 | 推奨1文以上 | **必須1文以上** | N/A判定は理由が必須、「更新」は推奨 |
| 代替証跡 | 推奨 | **必須** | N/A判定時は根拠が必須 |
| 担当SubAgent | **必須** | **必須** | SubAgent-A～E または leader |
| 更新日 | 必須 | 必須 | YYYY-MM-DD 形式 |

**注記**: 空文字列（""）、トリムのみで空文字列となる入力（"   "）は、バリデーターにより自動的に拒否されます。

## 記入例

### 「更新」の場合

| # | 仕様書名 | 判定 | 理由 | 代替証跡 | 担当SubAgent | 更新日 |
|---|----------|------|------|----------|-------------|--------|
| 1 | interfaces-agent.md | 更新 | AgentConfig型にtimeoutフィールドを追加 | diff: +timeout: number (L42) | SubAgent-A | 2026-03-01 |

### 「N/A」の場合

| # | 仕様書名 | 判定 | 理由 | 代替証跡 | 担当SubAgent | 更新日 |
|---|----------|------|------|----------|-------------|--------|
| 2 | api-ipc-agent.md | N/A | 本タスクはIPC変更を含まないため | grep -rn 'agent:' apps/desktop/src/main/ で変更0件を確認 | SubAgent-B | 2026-03-01 |

## バリデーションルール

以下のルールは自動バリデーターにより検証されます：

### 型チェック（第1段）

- specName: string 型、空配列不可
- status: "更新" または "N/A" のいずれか
- reason: string 型
- alternativeEvidence: string 型
- updatedBy: string 型

### 空文字列チェック（第2段）

- specName: `=== ""` で拒否
- status="N/A" の場合、reason: `=== ""` で拒否
- status="N/A" の場合、alternativeEvidence: `=== ""` で拒否

### トリム後空文字列チェック（第3段、P42準拠）

- specName: `trim() === ""` で拒否
- status="N/A" の場合、reason: `trim() === ""` で拒否
- status="N/A" の場合、alternativeEvidence: `trim() === ""` で拒否

### 値チェック

- updatedBy: 以下の値のいずれかのみ許可
  - "SubAgent-A"
  - "SubAgent-B"
  - "SubAgent-C"
  - "SubAgent-D"
  - "SubAgent-E"
  - "leader"

## バリデーション実行

記入後、以下のコマンドで自動バリデーションを実行できます：

```bash
cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts
```

成功例：

```
✓ __tests__/na-log-validator.test.ts (12)
```

失敗例（reason が空の場合）：

```
✗ validateNaLogEntry should reject N/A entry with empty reason
  AssertionError: Expected false but got true
```

## テンプレート使用フロー

1. **Phase 12 開始時**: このテンプレートを推奨5点セット仕様書でコピー
2. **SubAgent 実装中**: 各仕様書を更新し、このテーブルに判定を記録
3. **各 SubAgent 完了時**: バリデーターで確認（上記コマンドで実行）
4. **リーダー検証時**: 全 SubAgent の判定記録が完了していることを確認（チェックリスト Phase 12-完了判定-ガード参照）

## FAQ

### Q: 「更新」と判定しましたが、実際には変更しなかった場合は？

A: 再度 git diff で確認し、実際に変更があれば「更新」、なければ「N/A」に修正してください。判定が事実と乖離することは、後続の監査で検出される可能性があります。

### Q: 「N/A」の理由がどうしても1文以上にならない場合は？

A: 理由が簡潔に表現できる場合は構いませんが、後続の監査で「本当に変更不要か」が検証されます。確実な根拠（代替証跡）を提示してください。

### Q: 代替証跡に何を書けば良い？

A: 以下の形式がおすすめです：

- `grep -rn 'pattern' path/ で変更0件を確認`
- `git diff --stat -- path/ で0ファイル変更`
- `diff: +line-number / -line-number で確認`
- `参照: {{関連仕様書}}、セクション「{{セクション名}}」では変更対象外と判定`

## 関連資料

- **Phase 12 ワークフロー全体**: `.claude/skills/skill-creator/references/spec-update-workflow.md`
- **SubAgent分担表**: `phase12-subagent-assignment-template.md`
- **完了判定ガードチェックリスト**: `phase12-completion-guard-checklist.md`
- **バリデーター仕様**: `.claude/scripts/src/na-log-validator.ts`
