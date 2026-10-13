正式保存の実行境界は `../../references/guarded-publication-contract.md` が正本。output-formatterは一時下書きのみ返し、正式目標・archive・Daily.mdは親が承認済みargvの中央executeで反映する。

# UBM目標設定 実行ガイド

**各Phase の実行プロンプトはエージェントファイルに統合済み。**
このファイルはフロー全体の参照ガイドとして使用する。

---

## 並列実行の原則（全Phase共通）

**依存関係のないタスクは常に並列実行する。** 具体的には:

| Phase | 並列実行可能な処理 | 順次実行が必要な処理 |
|-------|-------------------|---------------------|
| Phase 0 | — | ユーザーへの質問（1ターン） |
| Phase 1-2 | Step 1〜3.9 を全て並列（対象と条件は info-collector.md の Layer 6「実行原則」）。各Step内の複数ファイルReadも並列 | Step 4（サマリー生成）は全Step完了後 |
| Phase 3 開始時 | 参照ファイル4本を並列Read（thinking-guide/principles/templates/best-practices） | Step 1→2→3→4→5 は対話のため順次 |
| Phase 4 | テンプレート＋既存ファイルの並列Read（期報時・1年時） | データ整形→バリデーション→保存は順次 |

**Phase横断の並列化**:
- Phase 1-2 のサブエージェントをバックグラウンド起動し、待機中に Phase 3 の参照ファイルを事前読み込み

---

## 実行フロー全体像

> **Step 番号の読み方**: Phase 1-2 の「Step 1〜4」は**情報収集の並列タスク番号**、Phase 3 の「Step 1〜5」は**対話の進行段階**であり、番号が同じでも別物である（例: Phase 1-2 の Step 3＝ナレッジ参照／Phase 3 の Step 3＝目標設定）。Phase を伴わない「Step 3」という言及は Phase 3 の対話段階を指す（責務プロンプト R1〜R5 の番号と 1:1 対応する）。

```
Phase 0: 目標種別の確認（AskUserQuestion: 1ターン）
    ↓
Phase 1-2: 情報収集 → agents/info-collector.md
    ├── Step 1: 過去目標収集 ──────┐
    ├── Step 2: 合宿情報収集 ──────┤
    ├── Step 3: ナレッジ参照 ──────┤ ← 並列実行（対象と条件は info-collector.md の Layer 6「実行原則」）
    ├── Step 3.5: UBMルート確認 ──┤
    ├── Step 3.7: ジャーナル収集 ──┤
    ├── Step 3.8: 相談の引き継ぎ ──┤
    ├── Step 3.9: 挑戦宣言の文脈 ──┘
    └── Step 4: サマリー生成（↑全完了後）
    ↓  ※ 待機中に Phase 3 参照ファイルを並列事前読み込み可
Phase 3: 親コンテキストの高速対話ヒアリング → skills/run-ubm-goal-setting/prompts/R1-R5（必要時のみ agents/phase3-coordinator.md の読み取り専用助言）
    ├── [並列Read] thinking-guide + principles + templates + best-practices
    ├── Step 1: 現状確認+前回振り返り（要素分解×MECE×経験学習×改善思考）
    ├── Step 2: 差分分析+原因深掘り（なぜ思考×ボトルネック×仮説×論点）
    ├── Step 3: 前提検証+目標設定（ダブルループ×批判×逆算×戦略×確率）
    ├── Step 4: 行動計画（GTD×プロセス×2軸）
    └── Step 5: 最終確認+合宿整合性（メタ思考×システム思考）
    ↓
Phase 4: 下書き・検証 → agents/output-formatter.md、正式保存 → 親の中央guard execute
    ├── [並列Read] テンプレート + 既存期報（quarterly時・旧名ファイルも対象）+ 既存1年目標（yearly時）
    ├── データ整形 → バリデーション → 保存（順次）
    └── 検証済み下書きを親へ返し、親が中央guard executeで保存
```

---

## Phase 0: 目標種別の確認

AskUserQuestion で以下を確認:

```
UBMの目標設定を始めます。どの種類の目標を作成・確認しますか？

1. 1週間目標（週報）
2. 1ヶ月目標（月報）
3. 3ヶ月目標（期報）
4. 1年目標（4層の最上位・正本は挑戦宣言）
5. 既存目標の見直し・改善（北原視点レビュー）

あわせて、目標期間（開始日〜終了日）を教えてください（1〜4の場合）。
```

- オプション1〜4 → Phase 1-2 → Phase 3 → Phase 4 の通常フロー
- オプション5 → 「目標レビューフロー」（下記参照）
- 引数で指定されている場合はスキップ。
- 引数の値は `weekly` / `monthly` / `quarterly` / `yearly` の4層（`bimonthly` は `quarterly` の後方互換の別名）。
- オプション4（`yearly`）は暦の1年で期間を切る（下位3層の最終月曜起点とは別）。期間の例は `2026-10-01〜2027-09-30`。

---

## Phase 1-2: 情報収集

**実行プロンプト**: `agents/info-collector.md` の「実行プロンプト」セクションをそのまま使用。

Agent ツールでサブエージェントを起動する際の設定:
- `subagent_type`: `general-purpose`
- `prompt`: info-collector.md 内の実行プロンプトを `{{goal_type}}` 等の変数を埋めて渡す
- `run_in_background`: `false`（結果を待つ）

**並列実行**: サブエージェント内部で収集の Step を並列実行する（どの Step を並べるかは、info-collector.md の Layer 6「実行原則」を参照）。サブエージェント完了待ちの間に Phase 3 の参照ファイルを事前読み込みすることも可能。

---

## Phase 3: 高速対話ヒアリング

**実行主体**: 呼び出し元のスキルの親コンテキストが各 `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-goal-setting/prompts/R{1..5}-*.md`（責務単位 7 層プロンプト正本）を Read して順次対話する。次問の判断が難しい場合だけ `agents/phase3-coordinator.md` を読み取り専用の助言役の Task として起動し、親が回答の受領と状態更新を続ける（Step は独立したサブエージェントにしない）。

**開始時の並列Read（4本）**:
- `$PLUGIN_ROOT/skills/run-ubm-goal-setting/references/thinking-guide.md`
- `$PLUGIN_ROOT/skills/run-ubm-knowledge-sync/assets/kitahara-principles-db.md`
- `$PLUGIN_ROOT/skills/run-ubm-goal-setting/assets/interview-quick-templates.md`
- `$PLUGIN_ROOT/skills/run-ubm-goal-setting/assets/action-goals-best-practices.md`

**所要時間目安**: 週報 5-8ターン / 月報 8-12ターン / 期報 12-15ターン（1年は期報と同じ骨格で、到達点を挑戦宣言から持ち込むため、挑戦宣言が確定していることを前提とする）

**1年層の対話での扱い**: 種別が `yearly` のときは【今年の最重要数字】に到達点（月間売上到達点・継続コンサル人数）を置き、そこから 3ヶ月 → 1ヶ月 → 1週間 へ割る前提で聞く。種別が `quarterly` / `monthly` / `weekly` のときも、Phase 1-2 が持ち上げた1年層の到達点を対話の起点に置き、下位層の数字がそこから割られているかを確認する（直す向きは上から下）。

---

## Phase 4: 出力・保存

**実行プロンプト**: `agents/output-formatter.md` の「実行プロンプト」セクションをそのまま使用。

Agent ツールでサブエージェントを起動する際の設定:
- `subagent_type`: `general-purpose`
- `prompt`: output-formatter.md 内の実行プロンプトを変数を埋めて渡す
- `run_in_background`: `false`（結果を待つ）

**並列実行**: テンプレートの読み込みでは、読むファイルを並列 Read する（対象は output-formatter.md の Layer 6「実行原則」を参照）。

---

## 目標レビューフロー（Phase 0 オプション5。オプション4は1年目標（`yearly`））

**エージェント**: `agents/goal-reviewer.md` に従いサブエージェントを起動する。

Agent ツールでサブエージェントを起動する際の設定:
- `subagent_type`: `general-purpose`
- `prompt`: goal-reviewer.md 内の「実行プロンプト」を変数を埋めて渡す
- `run_in_background`: `false`（結果を待つ）

**対象ファイルの特定**（引数未指定の場合）: 解決済みの `vault_root` 配下 `05_Project/UBM/目標設定/` 直下を `UBM - *.md` で `Glob` し、更新日時が最新の1件を選ぶ（`archive/` は候補にしない）。Bash は `python3` の実行だけに許可されているので、`ls` で探さない。

**出力内容**: 13項目チェック（基本2＋合宿整合性3＋関係構築3＋三層分離5）+ 上位3つの優先改善事項（NG→OK書き直し案付き）+ 北原さんならこう言う + プロジェクト/習慣の運用チェック

**起動タイミング**（複数あり）:
- Phase 0 でオプション5を選択した場合（スタンドアロン実行）
- Phase 4（目標ファイル保存後）にユーザーが追加レビューを希望した場合

---

## 回答パターン別の対応（全Phase共通）

詳細は `agents/phase3-coordinator.md` の「品質基準（回答パターン別対応ルール）」節を参照。

---

## ナレッジ同期（スキルの成長）

```bash
# 更新検知（差分確認）
! python3 $PLUGIN_ROOT/skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py --registry $PLUGIN_ROOT/knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM

# 全件再構築
! python3 $PLUGIN_ROOT/skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py --registry $PLUGIN_ROOT/knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM --all

# ナレッジ同期（検知→抽出→JSON格納を一括実行）
/ubm-knowledge-sync
```

詳細は `agents/knowledge-extractor.md` および `$PLUGIN_ROOT/commands/ubm-knowledge-sync.md` を参照。
