# Prompt: phase2-parallel

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase2-parallel |
| skill | run-elegant-review |
| responsibility | Phase2 (3 エージェント並列 30 paradigm findings 生成) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase2_output |
| reproducible | true (同 phase1_output → 同 findings 並び) |
| parallel | true (3 agent 完全独立 context-fork) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 各 agent は独立 context-fork で起動し、互いの中間結果を参照しない
  - 目的: 30 思考法レンズの独立性と多様性確保
  - 背景: 相互参照や同一 context 実行は paradigm 多様性を均質化し採点バイアスを生む
- 30 思考法すべてを担当配分どおり網羅 (logical_structural=10 / meta_divergent=9 / system_strategic=11、正本: `references/thought-methods.yaml`)
  - 目的: paradigm 網羅の機械的保証
  - 背景: 欠落は false-pass の主原因
- C1-C4 (矛盾/漏れ/整合性/依存関係整合) を全 finding で評価し verdict を付与
  - 目的: 4 条件の機械的網羅
  - 背景: 暗黙 skip は採点 bias の温床
- 編集禁止、Read/Glob/Grep のみ。findings の物理削除禁止 (上書き統合)
  - 目的: read-only 保証継続と監査追跡可能性
  - 背景: 編集混在は採点汚染、削除は trace 喪失
- 問題なしの条件は `issues: []` で明示 (黙示の skip 禁止)
  - 目的: 省略と未評価の区別
  - 背景: 黙示 skip は false-pass を生む

### 1.2 倫理ガード
- 他エージェントの出力を覗かない
  - 目的: 独立評価の確保
  - 背景: のぞき見は paradigm 多様性の損失
- PII / secret / 認証情報を findings へ転記しない (検出時 `***` マスク)
  - 目的: 情報漏洩防止
  - 背景: findings.json は後続 phase / trace で共有される

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Phase1 raw_observations を入力に、3 エージェント並列で 30 件 paradigm_findings を生成
- 非担当: バイアスリセット (Phase1)、改善パッチ (Phase3)

### 2.2 ドメインルール
- 3 エージェント構成 (正本: `./references/thought-methods.yaml`、配分 A2=10 / A3=9 / A4=11):
  - `elegant-logical-structural-analyst`: thought-methods.yaml `logical_structural.methods` 参照 (10 paradigm)
  - `elegant-meta-divergent-analyst`: thought-methods.yaml `meta_divergent.methods` 参照 (9 paradigm)
  - `elegant-system-strategic-analyst`: thought-methods.yaml `system_strategic.methods` 参照 (11 paradigm)
- 4 条件 (正本: `./references/4-conditions.json`): **C1 矛盾なし** / **C2 漏れなし** / **C3 整合性あり** / **C4 依存関係整合**
- 各 finding に `observations(>=1) / issues / score` を含む
- 具体値は `variable_abstraction[]` に分離し `{{VAR}}` 形式で抽象化

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| phase1_output | path | yes | raw_observations.json |
| paradigms_ref | path | yes | ./references/30-paradigms-full.md |
| conditions_ref | path | yes | ./references/4-conditions.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |
| findings_schema | path | yes | ./schemas/findings.schema.json |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase2_output`
- 各 paradigm_finding: `./schemas/findings.schema.json#/definitions/paradigm_finding` 準拠
- 必須: paradigm_findings (合計 30) / variable_abstraction[]

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| paradigms | ./references/30-paradigms-full.md | 思考法レンズ適用時 |
| conditions | ./references/4-conditions.json | C1-C4 verdict 付与時 |
| contract | ./references/variable-template-contract.md | 変数化時 |

### 3.2 外部ツール / API
- `scripts/validate-paradigm-coverage.py` — count==30 確認
- `scripts/build-paradigm-scorecard.py` — matrix 生成

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- paradigm count != 30 → 該当エージェント再実行
  - 目的: 30 思考法の網羅性確保
  - 背景: 欠落は採点 bias を生む
- 他エージェント参照検出 → exit 1
  - 目的: 独立性の強制
  - 背景: 参照は paradigm 多様性を均質化

### 4.2 観測 / ロギング
- 出力先: `findings.json`
- trace 連携: `eval-log/<plugin>/<skill>/elegant-review/<run-id>/elegant-review-trace.json` の phase2 セクションに各 agent の paradigm coverage / verdict 件数を記録
- 反復上限: Layer 4 共通 (max_iterations=3、coverage 不達は該当 agent のみ再実行)

### 4.3 セキュリティ
- 対象ファイルを編集しない (read-only)
- PII / secret / 認証情報を findings.json へ転記しない (検出時 `***` マスク)
  - 目的: 漏洩防止
  - 背景: findings は trace と共有される

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `elegant-logical-structural-analyst` / `elegant-meta-divergent-analyst` / `elegant-system-strategic-analyst` (3 並列起動)

### 5.2 ゴール定義
- **目的**: 各 agent が独立思考法レンズで paradigm_findings を生成し、合計 30 件の網羅性を成立させる
- **背景**: 中間結果の覗き見は paradigm 多様性を均質化し、編集混在は採点バイアスを生むため、独立性と read-only を要件化する
- **達成ゴール**: 担当思考法 (9 / 10 / 11) の findings が C1-C4 verdict 付き + 具体値変数化済みで findings.json に格納された状態

### 5.3 完了チェックリスト (停止条件)
- [ ] paradigm_coverage: 担当思考法をすべて埋めた (10 / 9 / 11)
- [ ] condition_matrix: 各 finding で C1-C4 全てに言及
- [ ] issue_structure: severity / bucket / recommended_intervention が揃う (issues なしは `issues: []` 明示)
- [ ] variable_extracted: 具体値が `{{VAR}}` で variable_abstraction に登録、source_trace あり
- [ ] independence: 他エージェント出力を参照していない (検出時 exit 1)
- [ ] read_only: 対象ファイルを編集しなかった
- [ ] determinism: 同 phase1_output 再実行で findings の (paradigm, observations) が並び順含め一致

### 5.4 実行方式 (固定手順を持たない動的生成ループ)
**固定手順禁止**。各 agent は自身の完了チェックリストを唯一の停止条件とし、状況に応じて手順をその都度設計・実行・自己評価する。例示 (網羅でない):
- 担当 paradigm 内の未充足項目を特定 → 解消候補手順を立案 (担当レンズで観察 / C1-C4 verdict 付与 / 変数化登録 のいずれか)
- 実行し自身の findings 出力を更新 → チェックリストで自己評価
- 全項目充足まで反復 (上限: Layer 4 max_iterations=3)
- 他 agent の中間結果を覗いた場合は exit 1

> **責務直交**: 30 件集約後の `validate-paradigm-coverage.py` / `build-paradigm-scorecard.py` は `workflow-manifest.json` の `phase2-exit` hook 責務であり、並列 agent 内で実行しない (中間結果共有と 3 重実行を誘発するため禁止 / G5)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase2, Phase1 完了後)
- 後続 phase: phase3-execute

### 6.2 ハンドオフ / 並列性
- 前 phase 受領元: phase1-reset (`raw_observations.json`)
- 次 phase 提供先: phase3-execute (`findings.json` + paradigm-scorecard)
- 並列: 3 エージェント完全独立並列 (context-fork 必須、相互参照禁止)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `findings.json` + paradigm-scorecard matrix

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

各エージェントは独立に担当 paradigm のレンズで `{{phase1_output}}` を観察し、
各 paradigm finding の `condition_matrix.C1..C4` に PASS/FAIL/PARTIAL と evidence を付与し、具体値を `variable_abstraction` に登録する。
集約後 30 件の `validate-paradigm-coverage.py` / `build-paradigm-scorecard.py` 実行は `phase2-exit` hook / orchestrator の責務であり、並列 agent 内では実行しない。
他エージェントの中間結果を覗かない (検出時 exit 1)。

出力は `./schemas/phase-output.schema.json#/definitions/phase2_output` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
