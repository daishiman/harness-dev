# SubAgent分担表テンプレート

## 用途

Phase 12（ドキュメント整備）を効率的かつ安全に実行するため、仕様書更新業務を5つの SubAgent に分担し、ワークフローを管理するためのテンプレートです。P43（rate limit 中断対策）に準拠した設計です。

## 担当割り当てテーブル

| SubAgent | 担当領域 | 対象仕様書パターン | 最大ファイル数 | 対応タスク分野 |
|----------|----------|-------------------|---------------|-------------|
| SubAgent-A | インターフェース定義 | `interfaces-*.md` | 3 | 型定義、API仕様の更新記録 |
| SubAgent-B | IPC通信仕様 | `api-ipc-*.md` | 3 | IPC ハンドラ、Preload 仕様の更新記録 |
| SubAgent-C | セキュリティ仕様 | `security-*.md` | 3 | セキュリティルール、権限管理の更新記録 |
| SubAgent-D | タスク管理・ログ | `task-workflow.md`, `aiworkflow-requirements/LOGS.md`, `task-specification-creator/LOGS.md` | 3 | 完了タスク記録、残課題テーブル更新 |
| SubAgent-E | 教訓・パターン | `lessons-learned.md`, `patterns.md` | 3 | 既知の落とし穴、実装パターンの新規記載 |

## P43対策（rate limit 中断防止）

**背景**: Phase 12 Task 2（システム仕様書更新）を1つのサブエージェントに7ファイル以上の一括更新を委譲すると、49ツール使用・402秒実行後に rate limit に到達して中断する。

**解決策**: 1 SubAgent あたり**最大3ファイル**に制限し、複数エージェントの並列実行で対応する。

**ルール**:

- [ ] 各 SubAgent の担当ファイル数が3以下であることを確認
- [ ] 超過する場合は、leader（タスクリーダー）が再分割を行う
- [ ] SubAgent は LOGS.md 更新時、「完了」を記録する前に全ファイルの変更を完了させる

## 実行順序と並列化

### 原則

- 監査 SubAgent は read-only を基本とする。
- 編集は leader / owner が直列に適用する。
- 同一ファイルを複数 SubAgent が同時に編集しない。
- skill-creator の実更新モードを開始する場合は AskUserQuestion が必須。監査のみ・編集禁止・ユーザーが更新仕様を明示済みの場合は read-only audit として扱う。

### Phase 1: 並列実行（最初の3段階）

```
─ SubAgent-A: interfaces-*.md を更新 ──┐
─ SubAgent-B: api-ipc-*.md を更新 ─────┼─→ Phase 2 へ
─ SubAgent-C: security-*.md を更新 ────┘
```

**実行時間**: 約1時間（合計3エージェント並列実行）

**完了条件**:
- [ ] SubAgent-A: 担当ファイル全てに「更新」or「N/A」判定を記録
- [ ] SubAgent-B: 担当ファイル全てに「更新」or「N/A」判定を記録
- [ ] SubAgent-C: 担当ファイル全てに「更新」or「N/A」判定を記録

### Phase 2: 並列実行（後半2段階）

```
─ SubAgent-D: task-workflow.md + LOGS.md x2 を更新 ──┐
─ SubAgent-E: lessons-learned.md + patterns.md を更新 ─┼─→ Phase 3 へ
```

**実行時間**: 約1時間（合計2エージェント並列実行）

**完了条件**:
- [ ] SubAgent-D: LOGS.md （2箇所）の「完了」記録、task-workflow.md の残課題テーブル更新
- [ ] SubAgent-E: lessons-learned.md への新規教訓の記載、patterns.md への新規パターンの記載

### Phase 3: リーダー検証（最終段階）

```
leader が Phase 1 + Phase 2 の全成果物を検証
  ├─ N/Aログ検証: validateNaLogEntries() で全エントリを確認
  ├─ 三点突合: validateTripleCheck() で artifacts/changelog/audit を確認
  └─ 監査実行: audit-unassigned-tasks --diff-from HEAD を基本に、completed direct path は audit-unassigned-tasks --target-file で current=0 を確認
```

**実行時間**: 約30分

**完了条件**:
- [ ] 全SubAgent の判定記録が完了
- [ ] N/Aログバリデーターで全エントリが PASS
- [ ] 三点突合で artifacts=completed, changelog=synced, audit current=0 を確認
- [ ] Phase 12 ガードチェックリストの全項目が ✓

## SubAgent別完了条件チェックリスト

### SubAgent-A: インターフェース定義

- [ ] `interfaces-agent.md` に完了タスクを記録（該当する場合）
- [ ] `interfaces-agent-sdk.md` に完了タスクを記録（該当する場合）
- [ ] `interfaces-{{category}}.md` その他の変更ファイルに記録
- [ ] 全ファイル分の N/A判定ログ記入（3ファイル以下）
- [ ] バリデーション実行: `cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts` で PASS

### SubAgent-B: IPC通信仕様

- [ ] `api-ipc-agent.md` に完了タスクセクションを追加
- [ ] `api-ipc-skill.md` に完了タスクセクションを追加（該当する場合）
- [ ] `api-ipc-{{category}}.md` その他の変更ファイルに記録
- [ ] 全ファイル分の N/A判定ログ記入（3ファイル以下）
- [ ] バリデーション実行: `cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts` で PASS

### SubAgent-C: セキュリティ仕様

- [ ] `security-api-electron.md` に完了タスクテーブルを追加
- [ ] `security-{{category}}.md` その他の変更ファイルに記録
- [ ] 全ファイル分の N/A判定ログ記入（3ファイル以下）
- [ ] バリデーション実行: `cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts` で PASS

### SubAgent-D: タスク管理・ログ

- [ ] `task-workflow.md` の完了タスクテーブルにタスクID を追加
- [ ] `aiworkflow-requirements/LOGS.md` に完了記録を追加
- [ ] `task-specification-creator/LOGS.md` に完了記録を追加（**2ファイル両方必須**、P25対策）
- [ ] N/A判定ログ記入（3ファイル以下）
- [ ] バリデーション実行: `cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts` で PASS

### SubAgent-E: 教訓・パターン

- [ ] `lessons-learned.md` に新規教訓を記載（検出されない場合は「新規教訓: 0件」と記載）
- [ ] `patterns.md` に新規パターンを記載（検出されない場合は「新規パターン: 0件」と記載）
- [ ] N/A判定ログ記入（3ファイル以下）
- [ ] バリデーション実行: `cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts` で PASS

## リーダー（タスク統括者）の責務

### Phase 1-2 開始前の準備

- [ ] 各 SubAgent に担当ファイルリストを配布
- [ ] `phase12-na-judgment-log-template.md` を全 SubAgent に共有
- [ ] 想定完了時間（Phase 1: 1時間、Phase 2: 1時間）を周知

### Phase 1-2 中の進捗管理

- [ ] SubAgent の進捗状況を定期確認（30分ごと）
- [ ] ファイル数超過時は即座に再分割を実施
- [ ] LOGS.md への「完了」記録は全ファイル更新後に行うよう指示

### Phase 3: 最終検証

- [ ] N/Aログバリデーター実行: `pnpm vitest run __tests__/na-log-validator.test.ts`
- [ ] 三点突合バリデーター実行: `pnpm vitest run __tests__/triple-check-validator.test.ts`
- [ ] 監査実行: `audit-unassigned-tasks --diff-from HEAD`（必要時は `audit-unassigned-tasks --target-file <path>` を併記）
- [ ] `phase12-completion-guard-checklist.md` の全項目をチェック
- [ ] Phase 12 完了を宣言（全項目 ✓ の場合のみ）

## 監査・検証コマンド一覧

```bash
# N/Aログ検証（全SubAgent の判定記録確認）
cd .claude/scripts && pnpm vitest run __tests__/na-log-validator.test.ts

# 三点突合検証（artifacts/changelog/audit の確認）
cd .claude/scripts && pnpm vitest run __tests__/triple-check-validator.test.ts

# 監査実行（current/baseline 違反検出）
cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator && \
  pnpm audit-unassigned-tasks --diff-from HEAD
  pnpm audit-unassigned-tasks --target-file docs/30-workflows/completed-tasks/<task>.md

# 全検証をまとめて実行
cd .claude/scripts && pnpm vitest run && cd /Users/dm/dev/dev/個人開発/AIWorkflowOrchestrator && pnpm audit-unassigned-tasks --diff-from HEAD
```

## トラブルシューティング

### Q: SubAgent の完了時間がフェーズ想定時間を大幅に超過した

A: 以下を確認してください：

1. 担当ファイル数が3を超えていないか（P43対策）
2. N/A判定ログの記入に時間がかかっていないか（テンプレート再確認）
3. バリデーターで FAIL が出ていないか（エラー内容を確認）

### Q: バリデーターで FAIL が出た場合は？

A: エラーメッセージ内容に従い、以下のように修正してください：

- 「specName must be a non-empty string」→ specName を記入
- 「reason must be a non-empty string」→ N/A判定時の理由を記入
- 「updatedBy must be one of」→ updatedBy を許可値から選択

### Q: 監査で current > 0 が出た場合は？

A: 以下のいずれかが原因です：

1. 仕様書の更新が不完全（再度 git diff で確認）
2. N/A判定の根拠が不十分（代替証跡を追加）
3. 未タスク検出（Phase 12 Task 4 で対応）

## 関連資料

- **N/A判定ログテンプレート**: `phase12-na-judgment-log-template.md`
- **完了判定ガードチェックリスト**: `phase12-completion-guard-checklist.md`
- **監査結果記録テンプレート**: `phase12-audit-record-template.md`
- **バリデーター**: `.claude/scripts/src/na-log-validator.ts`
- **P43対策詳細**: `.claude/rules/06-known-pitfalls.md` セクション P43

## テンプレート使用例

### 実例1: 正常系（全PASS）

**Phase 1 完了状況**:

- SubAgent-A: interfaces-agent.md, interfaces-agent-sdk.md, interfaces-skill.md （3ファイル） ✓
- SubAgent-B: api-ipc-agent.md, api-ipc-skill.md （2ファイル） ✓
- SubAgent-C: security-api-electron.md, security-ipc.md, security-permissions.md （3ファイル） ✓

**Phase 2 完了状況**:

- SubAgent-D: task-workflow.md, LOGS.md x2 （3ファイル） ✓
- SubAgent-E: lessons-learned.md, patterns.md （2ファイル） ✓

**Phase 3 検証結果**:

```
N/Aログ検証: ✓ PASS
三点突合検証: ✓ PASS (artifacts=completed, changelog=synced, audit current=0)
監査実行: ✓ PASS (currentViolations.total === 0)
最終判定: ✓ PASS → Phase 12 完了を宣言
```

### 実例2: P43対策が必要なケース

**初期割り当て**:

- SubAgent-A: 5ファイル → **4ファイル超過**

**リーダーの判断**: 再分割が必要

**修正後**:

- SubAgent-A: interfaces-agent.md, interfaces-agent-sdk.md, interfaces-skill.md （3ファイル）
- 追加 SubAgent-F: interfaces-ipc.md, interfaces-workflow.md （2ファイル）

この対応により、rate limit 中断を予防します。
