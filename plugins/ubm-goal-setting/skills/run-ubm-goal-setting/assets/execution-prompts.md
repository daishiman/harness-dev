# UBM目標設定 実行ガイド

**各Phase の実行プロンプトはエージェントファイルに統合済み。**
このファイルはフロー全体の参照ガイドとして使用する。

---

## 並列実行の原則（全Phase共通）

**依存関係のないタスクは常に並列実行する。** 具体的には:

| Phase | 並列実行可能な処理 | 順次実行が必要な処理 |
|-------|-------------------|---------------------|
| Phase 0 | — | ユーザーへの質問（1ターン） |
| Phase 1-2 | Step 1〜3.7 の5ステップを全て並列（Step 3.7はweeklyのみ）。各Step内の複数ファイルReadも並列 | Step 4（サマリー生成）は全Step完了後 |
| Phase 3 開始時 | 参照ファイル4本を並列Read（thinking-guide/principles/templates/best-practices） | Step 1→2→3→4→5 は対話のため順次 |
| Phase 4 | テンプレート＋既存ファイルの並列Read（期報時） | データ整形→バリデーション→保存は順次 |

**Phase横断の並列化**:
- Phase 1-2 SubAgent をバックグラウンド起動し、待機中に Phase 3 の参照ファイルを事前読み込み

---

## 実行フロー全体像

```
Phase 0: 目標種別の確認（AskUserQuestion: 1ターン）
    ↓
Phase 1-2: 情報収集 → agents/info-collector.md
    ├── Step 1: 過去目標収集 ──────┐
    ├── Step 2: 合宿情報収集 ──────┤
    ├── Step 3: ナレッジ参照 ──────┤ ← 5つを並列実行（Step 3.7はweeklyのみ）
    ├── Step 3.5: UBMルート確認 ──┤
    ├── Step 3.7: ジャーナル収集 ──┘
    └── Step 4: サマリー生成（↑全完了後）
    ↓  ※ 待機中に Phase 3 参照ファイルを並列事前読み込み可
Phase 3: 高速対話ヒアリング → agents/phase3-coordinator.md + skills/run-ubm-goal-setting/prompts/R1-R5
    ├── [並列Read] thinking-guide + principles + templates + best-practices
    ├── Step 1: 現状確認+前回振り返り（要素分解×MECE×経験学習×改善思考）
    ├── Step 2: 差分分析+原因深掘り（Why思考×ボトルネック×仮説×論点）
    ├── Step 3: 前提検証+目標設定（ダブルループ×批判×逆算×戦略×確率）
    ├── Step 4: 行動計画（GTD×プロセス×2軸）
    └── Step 5: 最終確認+合宿整合性（メタ思考×システム思考）
    ↓
Phase 4: 出力・保存 → agents/output-formatter.md
    ├── [並列Read] テンプレート + 既存期報（bimonthly時）
    ├── データ整形 → バリデーション → 保存（順次）
    └── ファイル保存
```

---

## Phase 0: 目標種別の確認

AskUserQuestion で以下を確認:

```
UBMの目標設定を始めます。どの種類の目標を作成・確認しますか？

1. 1週間目標（週報）
2. 1ヶ月目標（月報）
3. 2ヶ月目標（期報）
4. 既存目標の見直し・改善（北原視点レビュー）

あわせて、目標期間（開始日〜終了日）を教えてください（1〜3の場合）。
```

- オプション1〜3 → Phase 1-2 → Phase 3 → Phase 4 の通常フロー
- オプション4 → 「目標レビューフロー」（下記参照）
- 引数で指定されている場合はスキップ。

---

## Phase 1-2: 情報収集

**実行プロンプト**: `agents/info-collector.md` の「実行プロンプト」セクションをそのまま使用。

Agent ツールで SubAgent を起動する際の設定:
- `subagent_type`: general-purpose
- `prompt`: info-collector.md 内の実行プロンプトを `{{goal_type}}` 等の変数を埋めて渡す
- `run_in_background`: false（結果を待つ）

**並列実行**: SubAgent 内部で Step 1〜3.5 を並列実行する（詳細は info-collector.md の並列実行ポリシー参照）。SubAgent 完了待ちの間に Phase 3 の参照ファイルを事前読み込みすることも可能。

---

## Phase 3: 高速対話ヒアリング

**エージェント**: `agents/phase3-coordinator.md` を Task（isolation:fork）で起動し、その中で各 `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/prompts/R{1..5}-*.md`（責務単位 7 層プロンプト正本）を Read して順次実行する（step は独立 SubAgent 化しない）。

**開始時の並列Read（4本）**:
- `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/references/thinking-guide.md`
- `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-knowledge-sync/assets/kitahara-principles-db.md`
- `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/assets/interview-quick-templates.md`
- `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-goal-setting/assets/action-goals-best-practices.md`

**所要時間目安**: 週報 5-8ターン / 月報 8-12ターン / 期報 12-15ターン

---

## Phase 4: 出力・保存

**実行プロンプト**: `agents/output-formatter.md` の「実行プロンプト」セクションをそのまま使用。

Agent ツールで SubAgent を起動する際の設定:
- `subagent_type`: general-purpose
- `prompt`: output-formatter.md 内の実行プロンプトを変数を埋めて渡す
- `run_in_background`: false（結果を待つ）

**並列実行**: テンプレート読み込み時、output-formats.md と既存ファイル（期報時）を並列Readする（詳細は output-formatter.md の並列実行ポリシー参照）。

---

## 目標レビューフロー（Phase 0 オプション4）

**エージェント**: `agents/goal-reviewer.md` に従い SubAgent を起動する。

Agent ツールで SubAgent を起動する際の設定:
- `subagent_type`: general-purpose
- `prompt`: goal-reviewer.md 内の「実行プロンプト」を変数を埋めて渡す
- `run_in_background`: false（結果を待つ）

**対象ファイルの特定**（引数未指定の場合）:
```bash
# 最新の目標設定ファイルを自動検出
ls -t $UBM_VAULT_ROOT/05_Project/UBM/目標設定/UBM\ -\ *.md | head -1
```

**出力内容**: 8項目チェック + Top 3 優先改善事項（NG→OK書き直し案付き）+ 北原さんならこう言う + プロジェクト/習慣の運用チェック

**起動タイミング**（複数あり）:
- Phase 0 でオプション4を選択した場合（スタンドアロン実行）
- Phase 4（目標ファイル保存後）にユーザーが追加レビューを希望した場合

---

## 回答パターン別の対応（全Phase共通）

詳細は `agents/phase3-coordinator.md` の「回答パターン対応」セクションを参照。

---

## ナレッジ同期（スキルの成長）

```bash
# 更新検知（差分確認）
! python3 $CLAUDE_PLUGIN_ROOT/skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py --registry $CLAUDE_PLUGIN_ROOT/knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM

# 全件再構築
! python3 $CLAUDE_PLUGIN_ROOT/skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py --registry $CLAUDE_PLUGIN_ROOT/knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM --all

# ナレッジ同期（検知→抽出→JSON格納を一括実行）
/ubm-knowledge-sync
```

詳細は `agents/knowledge-extractor.md` および `$CLAUDE_PLUGIN_ROOT/commands/ubm-knowledge-sync.md` を参照。
