# Prompt: phase3-execute

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase3-execute |
| skill | run-elegant-review |
| responsibility | Phase3 (findings に基づく最小パッチ適用) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase3_output |
| reproducible | true (validation 必須 / 同 findings + iter で同 patch 順) |
| parallel | conditional (独立 finding は Agent Team 並列、依存ありは直列) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 編集スコープは findings に紐づく最小パッチのみ、findings 外の周辺リファクタ禁止
  - 目的: スコープ逸脱と回帰の防止、パッチ追跡可能性確保
  - 背景: 周辺リファクタ混入は review 再現性を破壊し監査困難
- 物理削除禁止 (上書き統合、history は trace 保持)
  - 目的: 監査追跡可能性と冪等更新の保証
  - 背景: 削除は trace 喪失と再現性破壊を招く
- C1-C4 (矛盾/漏れ/整合性/依存関係整合) 全条件を検証コマンドで再評価してから収束判定
  - 目的: 4 条件の機械的網羅
  - 背景: 部分判定は false-pass の温床
- `iteration_count >= 3 (max)` で C1-C4 未達なら `force_pass` 禁止、`convergence_status: human_escalate`
  - 目的: 自動収束の暴走防止
  - 背景: 過去に強制 pass で品質崩壊事例あり

### 1.2 倫理ガード
- 検証を実行せず pass を宣言しない
  - 目的: 自己申告の不正排除
  - 背景: validation_commands が唯一の客観判定
- PII / secret / 認証情報を patch / verdict / trace へ転記しない (検出時 `***` マスク)
  - 目的: 漏洩防止
  - 背景: verdict.json と trace は共有される

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Phase2 集約 findings の C1-C4 FAIL 項目に最小パッチを適用
- 非担当: 観察 (Phase1)、採点 (Phase2)

### 2.2 ドメインルール
- 独立変更は分けて適用、依存変更は順序を守る
- 具体値直書きは `variable_abstraction` に基づき `{{VAR}}` へ置換し source_trace を保持
- パッチ適用後、`validation_commands` (validate-paradigm-coverage.py 等) を実行
- **claim_vs_reality_audit (MED-3)**: 前回 run の `changed_paths[]` を実 file に対し `grep -F` で再検証し、gap があれば severity=contradiction の finding として再起票

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| phase2_output | path | yes | findings.json |
| convergence_policy | path | yes | ./references/convergence-policy.json |
| amplified_patterns | path | yes | ./references/amplified-patterns.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase3_output`
- 必須: changed_paths / validation_commands / residual_risks / convergence_status (任意: iteration_count / four_conditions)
- 追加成果物: `verdict.json` (`./schemas/verdict.schema.json` 準拠) を `eval-log/<plugin>/<skill>/elegant-review/<run-id>/` に生成

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| policy | ./references/convergence-policy.json | 収束判定時 |
| patterns | ./references/amplified-patterns.json | パッチ生成時 |
| contract | ./references/variable-template-contract.md | 変数化適用時 |

### 3.2 外部ツール / API
- Edit / Write (最小スコープ)
- `scripts/validate-paradigm-coverage.py` 等 (validation_commands)
- Agent Team: 独立 finding は SubAgent 並列起動、依存 finding は直列 (依存関係整合を保つ)
- Codex 委譲 (任意): 大規模 patch / 専門領域は `delegate-codex-skill-review` 経由で外部委譲可能

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `max_iterations (3)` 超過 → `convergence_status: human_escalate` (force_pass 禁止)
  - 目的: 暴走防止と人間介入の明示
  - 背景: 自動収束失敗は構造的問題のシグナル

### 4.2 観測 / ロギング
- 出力先: `changed_paths` / `validation_commands` / `residual_risks` を JSON で記録
- trace 連携: `eval-log/<plugin>/<skill>/elegant-review/<run-id>/elegant-review-trace.json` の phase3 セクションに patch diff 要約 / validation 結果 / iteration_count を記録
- 反復上限: `max_iterations=3` 超過で `human_escalate` (Layer 1 不変ルール参照)

### 4.3 セキュリティ
- findings 外の編集禁止
  - 目的: スコープ漏れの防止
  - 背景: 監査追跡可能性の維持
- PII / secret / 認証情報を patch / verdict / trace へ転記しない (検出時 `***` マスク)
  - 目的: 漏洩防止
  - 背景: trace と verdict.json は共有される

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `elegant-improvement-executor` (`workflow-manifest.json` resources `subagent-improvement-executor` で解決)

### 5.2 ゴール定義
- **目的**: Phase2 findings の C1-C4 FAIL を最小パッチで解消し、検証通過した verdict.json を成立させる
- **背景**: 周辺リファクタ混入と検証未実行の自己申告は review 再現性を破壊するため、スコープ最小化と validation_commands 必須化を要件化
- **達成ゴール**: changed_paths / validation_commands / residual_risks / convergence_status が記録され、verdict.json が schema 準拠で出力された状態

### 5.3 完了チェックリスト (停止条件)
- [ ] severity_order: high/critical から順に適用
- [ ] scope_minimal: findings 外の変更を混ぜていない
- [ ] variable_abstraction_applied: 直書き具体値を `{{VAR}}` へ昇格、source_trace 保持
- [ ] validation_run: `validation_commands` を実行し結果を記録 (未実行のまま pass 宣言禁止)
- [ ] safety_valve: `max_iterations=3` 超過時 `convergence_status: human_escalate` を選択 (force_pass 禁止)
- [ ] verdict_emit: `verdict.json` を `./schemas/verdict.schema.json` 準拠で生成、`emit-observable.py` を PASS/FAIL 双方で実行
- [ ] determinism: 同 findings + iteration_count で changed_paths の順序と内容が一致

### 5.4 実行方式 (固定手順を持たない動的生成ループ)
**固定手順禁止**。完了チェックリストと `convergence-policy.json` の Δneg/Δpos 閾値を唯一の停止条件とし、状況に応じて手順をその都度設計・実行・自己評価する。例示 (網羅でない):
- 未充足項目を特定 (未解消 finding / 未実行検証) → 解消候補手順を立案 (severity 順グルーピング / 独立 finding の SubAgent 並列起動 / 最小パッチ適用 / validation_commands 実行 / 収束判定 / verdict emit のいずれか)
- 実行し `changed_paths` / `validation_commands` を更新 → 閾値で自己評価
- 未達なら次周回 (上限: max_iterations=3)
- 到達後も C1-C4 未達なら `convergence_status: human_escalate` を選択 (`force_pass` 禁止)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase3, Phase2 完了後)
- 後続 phase: 完了レポート

### 6.2 ハンドオフ / 並列性
- 前 phase 受領元: phase2-parallel の `findings.json`
- 次 phase 提供先: run-elegant-review 完了レポート / `verdict.json`
- 並列: 独立 finding は Agent Team で SubAgent 並列、依存ありは直列 (依存関係整合を保つ)、Codex 委譲は任意

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `changed_paths` diff + `validation_commands` + `convergence_status`

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{phase2_output}}` の C1-C4 FAIL 項目に対し、`{{variable_contract}}` と
`{{amplified_patterns}}` に基づき最小パッチを順に適用する。適用後
`validation_commands` を実行し C1-C4 を再評価する。`{{convergence_policy}}` の
Δneg/Δpos 閾値で収束判定。`max_iterations=3` 超過時は `human_escalate` を選択
(force_pass 禁止)。

出力は `./schemas/phase-output.schema.json#/definitions/phase3_output` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
