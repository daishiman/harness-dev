# ワークフロー詳細ガイド (宣言核)

Phase 1〜5 の**ゴール (到達状態)・完了条件・判断基準**を宣言する。
実行順・依存関係・fatal exit code の機械正本は `../workflow-manifest.json` (phases[].dependsOn)。
手順は各 Phase のゴールへ向けてゴールシークループで都度立案する (固定ステップ表を持たない)。

## 呼出モード (全 Phase 共通の前提)

| モード | 条件 | ユーザー対話 |
|--------|------|-------------|
| brief 供給 (orchestrator / run-build-skill 呼出) | skill-brief / hearing-result が入力に含まれる | **Phase 1-3 の全ユーザー対話を skip**。導出確認は brief の `user_confirmed` に委譲 |
| 単独起動 | ユーザーが直接起動し brief なし | Phase 1-3 で対話可 (下記の各 Phase 記述は単独起動時のみ適用) |

## Phase 1: ヒアリング

- **ゴール**: 検証済み hearing-result が存在する状態。
- **完了条件**: `validate-prompt.py --phase hearing` exit 0。
- **判断基準**:
  - hearing-result / brief 供給時は本 Phase を skip する。
  - 無ければ **run-prompt-elicit へ委譲**する (interview-user agent を直接呼ばない。収集経路を一本化しドリフト源を作らないため)。
  - 質問設計・ラウンド運用・導出確認の正本は run-prompt-elicit 側 (`run-prompt-elicit/SKILL.md` / `references/elicit-question-bank.md`)。

### 収集すべきゴール材料 (委譲先が満たすべき情報要件)

| # | 情報 | 使い先 |
|---|------|--------|
| 1 | 目的・ゴール (何をしたいか) | Layer 1 最上位目的 |
| 2 | 利用者像 | Layer 1 / Layer 7 |
| 3 | 背景・課題 | Layer 1 / Layer 2 |
| 4 | 出力イメージ | Layer 5 インターフェース |
| 5 | 達成状態と完了条件 (**手順ではない**。手順は実行時に AI が自律生成) | Layer 5 ゴール定義・完了チェックリスト |
| 6 | 制約・注意点 | Layer 4 |
| 7 | 評価優先度 | 動的評価基準 (Pass 0) の材料 |

### 評価優先度 (evaluation_priorities) — SSOT 従属注記

選択肢の語彙と上限の正本は `../../run-prompt-elicit/schemas/hearing-result.schema.json` の
`evaluation_priorities` enum (日本語 5 値・最大 2)。`quality-criteria.md` §7.2 の
Pass 強化マッピングも同 enum に従属する。**本書では値を再定義しない** (経路間の語彙分裂防止)。

---

## Phase 2: Prompt作成シート生成 + 導出確認

- **ゴール**: goals / checklist を含む内部正規形材料が確定し、AI の設計判断がユーザー (または brief) に承認された状態。
- **完了条件**: `generate-sheet.py` + `validate-sheet.py` exit 0 (未充足フィールド・ゴール手順列挙なし)。
- **判断基準**:
  - 未充足フィールドは追加質問を設計する前に AI 最尤仮説での補完可否を検討する。
  - **導出確認** (単独起動時のみ): AI が推定・仮定した設計判断を「あなたの入力 → AI の設計判断 → 根拠」の形で透明化し最終承認を得る。承認 → Phase 3 / 修正指示 → 該当箇所を修正して再確認。導出確認は最終承認を兼ねる。
  - **brief 供給時**: `brief.user_confirmed` が承認済みを意味するため導出確認を skip する。

参照: [references/prompt-sheet-template.md](prompt-sheet-template.md)

---

## Phase 3: フォーマット・出力先選択

- **ゴール**: 出力フォーマットと出力先パスが一意に確定した状態。
- **完了条件**: format ∈ {md, yaml, json, xml} (md 既定)、出力先パスが規約または指定で解決済み。
- **判断基準**:
  - **brief 供給時 / ループ呼出時**: md 既定・規約パス (skill-local-v1) で skip。
  - **単独起動時のみ**: AskUserQuestion でフォーマット・出力先パス・エージェント数 (単一/複数) を確認する。
  - YAML は内部正規形または legacy 互換に限定する。

---

## Phase 4: 構造化プロンプト生成

### Phase 4-A: Layer 単位生成

- **ゴール**: 7 層 (または brief.layers_required サブセット) の Layer 別 artifact が揃い、`merge-layers.py` で 1 つの正規形に統合された状態。
- **完了条件**: 各 layer artifact 実在 + `merge-layers.py` exit 0。
- **判断基準 (生成ルール)**:
  - **1 Layer = 1 出力**: 独立した LLM 呼び出しで生成 (一括生成禁止)。
  - **要素原子性**: 1 フィールド = 1 概念 = 1 短文 (目安 50 文字以内)。複合内容はリスト・テーブル・サブキーに分解。
  - **前 Layer 参照**: Layer N 生成時に Layer 1〜(N-1) を参照して整合性確保。省略記法 (「以下同様」) 禁止。
  - **ゴールシーク (Layer 5)**: 達成ゴールは成果状態で記述。固定手順を書かず、実行方式 (6 ステップ+Anchor のループ) に委ねる。サブ構造の正本: `seven-layer-format.md`「Layer 5 契約」(l5-contract v2.0.0)。
  - **ハンドオフ (Layer 5/6)**: 出力(受領先)→次の入力(提供元)を接続し、直列/並列の連鎖を明示。

### Phase 4-B: 多段階検証 (4 パスレビュー)

- **ゴール**: Pass 0 (evaluation_priorities からの動的基準生成) と Pass 1 網羅性 / Pass 2 整合性 / Pass 3 深度 / Pass 4 実用性の findings が確定した状態。
- **完了条件**: `validate-prompt.py` exit 0 + 全 Pass PASS (NG は該当 Pass の修正指示付き findings)。
- **判断基準**: 各 Pass の判定質問・合格条件の正本は `quality-criteria.md` (§1-§7)。derivation_log 反映は Pass 1 で確認する。

### Phase 4-C: AI 自律評価・改善

- **ゴール**: 完了チェックリスト (evaluation_priorities 基づく自己評価含む) が全充足、または上限到達で差し戻し判断が確定した状態。ユーザー介入不要 (結果のみ最終報告に含める)。
- **完了条件**: `verify-completeness.py` (+ layers_required サブセット時は `--layers`) + `validate-prompt.py --phase prompt` exit 0。反復上限 3 回。
- **Anchor 契約 (必須)**: 各周回末に `eval-log/prompt-creator-intermediate.jsonl` へ `original_goal` (不変) / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を append する。schema 正本: harness-creator `run-build-skill/schemas/goal-seek-loop.schema.json` の `intermediate_artifacts[]` (再宣言しない)。次周回の手順立案は直前行の `merged_directive_for_next` + `original_goal` を必須入力とする。
- **戻り先判断基準**:

| 修正の種類 | 戻り先 | 理由 |
|-----------|--------|------|
| 内容の追加・変更 (Layer の中身を書き換え) | Phase 4-A (該当 Layer 再生成) | Layer 再生成が必要 |
| 品質の改善 (表現の曖昧さ・整合性) | Phase 4-B (該当 Pass 再実行) | 再検証で改善可能 |

- **評価結果の記録**: 評価項目ごとの PASS/修正済みと改善回数 (N 回 / 最大 3 回) を最終報告 (Phase 4-D) に含める。

### Phase 4-D: フォーマット変換・ファイル出力

- **ゴール**: 指定フォーマットの最終成果物が出力先に書き出され、再検証済みの状態。
- **完了条件**: `convert-format.py` exit 0 + 変換後の `validate-prompt.py` exit 0 + ファイル実在。
- **判断基準**: owner_agent 指定時の注入 diff は inject-sections (Prompt Templates / Self-Evaluation。呼出元非依存の不変契約) 内に閉じること。

---

## Phase 5: 戻り検証 + 設計ゲート

- **ゴール**: 全機械ゲートと C1-C4 設計ゲートが PASS し、利用記録が残った状態。
- **完了条件**: `lint-agent-prompt-section.py` exit 0 + C1-C4 設計評価 (`assign-prompt-design-evaluator` fork・findings 出力のみ) PASS + `log-usage.py` で LOGS.md 記録。
- **判断基準**:
  - FAIL は Phase 4-A 再起動 (最大 3 周)。超過時は orchestrator へ差し戻す。
  - 設計ゲートの免除は、呼出元が同等ゲート (例: run-prompt-create Step 3b) を機械証跡 (design-findings JSON パス) で保証する場合のみ。
  - 単独起動時は必要に応じて Prompt 作成シートも同じディレクトリに保存する。
