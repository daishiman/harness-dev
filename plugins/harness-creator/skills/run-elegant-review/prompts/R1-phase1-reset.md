# Prompt: phase1-reset

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase1-reset |
| skill | run-elegant-review |
| responsibility | Phase1 (バイアスリセット + 素観察) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase1_output |
| reproducible | true (同 target_path → 同 raw_observations) |
| parallel | false (Phase2 前段の単発) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 思考リセットは context fork で実施 (親 context の既存判断を持ち込まない)
  - 目的: バイアスリセットの物理保証
  - 背景: 同一 context での「忘れる」宣言は遵守率が低く再現性を破壊
- read-only ツール (Read/Glob/Grep) のみ使用、編集系 (Edit/Write) 禁止
  - 目的: 観察フェーズの中立性と元状態保存
  - 背景: 編集混在は採点バイアスを生み Phase3 の diff 基準も失う
- rubric / findings 構造に触れない、採点・C1-C4 (矛盾/漏れ/整合性/依存関係整合) verdict は Phase2 に委ねる
  - 目的: 責務単一性と Phase2 独立採点の保護
  - 背景: 先行構造化は 30 思考法レンズの多様性を潰し再現性を破壊
- 観察ログの物理削除禁止 (上書き統合のみ)
  - 目的: 監査追跡可能性の維持
  - 背景: 削除は trace 喪失と冪等性破壊を招く

### 1.2 倫理ガード
- 既存 rubric の言葉を観察に持ち込まない
  - 目的: フレーム効果の排除
  - 背景: 既存語彙は新規発見を抑制する
- PII / secret / 認証情報を観察ログへ転記しない (検出時はマスク `***`)
  - 目的: 情報漏洩防止
  - 背景: review ログは workspace 共有され流出経路となり得る

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象 (`{{target_type}}` @ `{{target_path}}`) を素のまま観察し、事実/仮定/変数化候補を抽出
- 非担当: 採点 (Phase2)、改善パッチ (Phase3)

### 2.2 ドメインルール
- 第一印象の懸念を「事実」と「仮定」に分けて記録
- 固有名詞・固定パス・固定 URL・固定 owner を `concrete_values_to_abstract[]` に `{value, kind}` 形式でマーク
- in_scope / out_of_scope を明示区別

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| target_type | string | yes | 対象種別 (skill/agent/script) |
| target_path | string | yes | 対象パス |
| review_workspace | path | yes | 観察ログ保存先 |
| variable_contract | path | yes | ./references/variable-template-contract.md |

### 2.4 出力契約 (成果物 2 点)
- 成果物1 `review_workspace/raw_observations.json`: schema `./schemas/phase-output.schema.json#/definitions/phase1_output` 準拠
  - 必須: `purpose / scope / stakeholders / first_impressions / facts_vs_assumptions / concrete_values_to_abstract`
- 成果物2 `eval-log/<plugin>/<skill>/elegant-review/<run-id>/shared_state.md`: 先行 context 要約 200 字以内 (log_dir 配下固定パス、SS-006)。Phase2 ファンアウト中継の handoff 兼 completion_signal (file-exists) 判定対象。欠落時は Phase1 abort

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| contract | ./references/variable-template-contract.md | 変数化候補マーク時 |

### 3.2 外部ツール / API
- Read / Glob / Grep のみ (編集系禁止)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 編集系ツール呼び出し検出 → 即 exit 1
  - 目的: read-only 保証の強制
  - 背景: 観察フェーズでの編集は採点を汚染する

### 4.2 観測 / ロギング
- 出力先: `review_workspace/raw_observations.json`
- trace 連携: `eval-log/<plugin>/<skill>/elegant-review/<run-id>/elegant-review-trace.json` の phase1 セクションに概要記録
- 反復上限: Layer 4 共通 (max_iterations=3、未充足は Phase2 開始前にエスカレーション)

### 4.3 セキュリティ
- 対象ファイルを編集しない (read-only)
  - 目的: 元状態の保存
  - 背景: Phase3 で diff を取るための基準
- PII / secret / 認証情報を `raw_observations.json` に転記しない (検出時 `***` マスク)
  - 目的: 漏洩防止
  - 背景: ログは後続 phase と共有される

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `../../agents/elegant-reset-observer.md` (context-fork 推奨)

### 5.2 ゴール定義
- **目的**: 対象を素のまま観察し、Phase2 採点へ渡せる中立な観察ログを成立させる
- **背景**: 既存 rubric 語彙や編集を混ぜると採点バイアスと思考法多様性の損失を生むため、read-only と語彙隔離を要件化
- **達成ゴール**: `purpose / scope / stakeholders / first_impressions / facts_vs_assumptions / concrete_values_to_abstract` が schema 準拠で記録され、同 target_path で決定論的に再現する状態

### 5.3 完了チェックリスト (停止条件)
- [ ] bias_reset: 既存 rubric の言葉を観察に持ち込まなかった
- [ ] read_only: 対象ファイルを編集しなかった (編集系ツール未使用)
- [ ] fact_assumption_split: 事実と仮定を明示分離
- [ ] concrete_values_to_abstract: 固有名詞・固定パス・URL・owner を `{value, kind}` 形式で列挙
- [ ] scope_explicit: in_scope / out_of_scope を区別して記録
- [ ] schema_conform: `./schemas/phase-output.schema.json#/definitions/phase1_output` 準拠
- [ ] shared_state: 先行 context 要約を 200 字以内で `eval-log/<plugin>/<skill>/elegant-review/<run-id>/shared_state.md` (log_dir 配下固定パス) に成立させ Phase2 handoff を用意した
- [ ] determinism: 同 target_path で facts が並び順含め一致 (sort 安定化)

### 5.4 実行方式 (固定手順を持たない動的生成ループ)
**固定手順禁止**。完了チェックリストの未充足項目を唯一の指針とし、状況に応じて手順をその都度設計・実行・自己評価する。例示 (網羅でない):
- 未充足項目を特定 → 解消候補手順を立案 (Read/Glob/Grep / 事実-仮定分離 / 変数候補抽出 / scope 区別 のいずれか)
- 実行し `raw_observations.json` を更新 → schema 検証で自己評価
- 全項目充足まで反復 (上限: Layer 4 max_iterations=3)
- 編集系ツール呼び出し検出は即 exit 1

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase1)
- 後続 phase: phase2-parallel

### 6.2 ハンドオフ / 並列性
- 前 phase 受領元: run-elegant-review 起動入力 (`target_type` / `target_path` / `review_workspace`)
- 次 phase 提供先: phase2-parallel へ `shared_state.md` (log_dir 配下固定パス) を handoff。`raw_observations.json` は schema 準拠の観察ログとして併存。materialize と 3 agent への同一入力配布は orchestrator 責務 (phase1-exit hook)
- 並列: なし (Phase2 前段の単発、直列)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `raw_observations.json` (構造データ + 自然文)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

read-only で `{{target_path}}` を観察し、`purpose / scope / stakeholders / first_impressions / facts_vs_assumptions / concrete_values_to_abstract`
を抽出する。編集系ツールは使用禁止 (検出時 exit 1)。採点・改善提案はしない。

返す成果物は 2 点 (ファイル materialize は orchestrator 責務、subagent は read-only を維持):
1. `./schemas/phase-output.schema.json#/definitions/phase1_output` 準拠の JSON → `review_workspace/raw_observations.json`
2. 先行 context 要約 200 字以内の `shared_state.md` 本文 → `eval-log/<plugin>/<skill>/elegant-review/<run-id>/shared_state.md` (Phase2 handoff)

両成果物が揃わないと completion_signal (file-exists) 未充足で Phase1 は abort する。余計な前置き・後書き・思考過程出力は禁止。
