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
| parallel | conditional (orchestrator が非重複 scope を並列割当、各 executor は単独実行) |

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
- `iteration_count >= 3 (max)` で C1-C4 未達なら `force_pass` 禁止、`convergence_status: incomplete` (human_review 必須)。Δneg/Δpos が閾値未満で改善が止まっても C1-C4 に FAIL が残るなら同じく `incomplete` (`complete` は 4 条件 PASS のときだけ)。Δneg が 2 周連続で増えたら `convergence_status: diverging` (orchestrator が human_escalate へ写す)
  - 目的: 自動収束の暴走防止
  - 背景: 過去に強制 pass で品質崩壊事例あり
- git commit は `commit_authorized=true` が明示された場合だけ許可する。既定は patch 適用と検証まで

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
- 具体値直書きは `variable_abstraction[].name` に基づき `{{VAR}}` へ置換し、meaning/default/required/not_applicable_when/source_trace を保持
- `dry_run=true` は対象を Edit / Write せず、適用予定の patch と検証結果のみを返す。`dry_run=false` でも commit / PR は後続の明示依頼がなければ行わない
- パッチ適用後、`validation_commands` (validate-paradigm-coverage.py 等) を実行
- 差分再評価と PASS 証拠の再利用は `../run-build-skill/references/verification-obligation-protocol.md` の exact obligation fingerprint + current PASS receipt DAG にだけ従う。`changed_paths[]` や自然文の自己申告で判定を省略しない

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| phase2_output | path | yes | findings.json |
| dry_run | bool | yes | true は対象への Edit / Write を禁止 |
| convergence_policy | path | yes | ./references/convergence-policy.json |
| amplified_patterns | path | yes | ./references/amplified-patterns.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |
| commit_authorized | boolean | yes | 既定 false。true の明示時だけ git commit 可 |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase3_output`
- 必須: changed_paths / validation_commands / residual_risks / convergence_status (任意: iteration_count / four_conditions)
- 追加成果物: `verdict.json` (`./schemas/verdict.schema.json` 準拠) は executor が書かない。orchestrator が `convergence_status` を `findings.json` の `run_status` へ写し (complete→`complete`、diverging・human_escalate→`human_escalate`、in_progress・incomplete→`incomplete`)、`python3 scripts/build-verdict.py --findings <log_dir>/findings.json --verdict <log_dir>/verdict.json` で `eval-log/<plugin>/<skill>/elegant-review/<run-id>/` に導出する (手書き禁止)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| policy | ./references/convergence-policy.json | 収束判定時 |
| patterns | ./references/amplified-patterns.json | パッチ生成時 |
| contract | ./references/variable-template-contract.md | 変数化適用時 |
| verification | ../run-build-skill/references/verification-obligation-protocol.md | 差分再評価・PASS 証拠再利用判定時 |

### 3.2 外部ツール / API
- Edit / Write (`dry_run=false` の最小スコープだけ)
- `scripts/validate-paradigm-coverage.py` 等 (validation_commands)
- `git diff` / `git grep` (scope と残存 literal の read-only 監査)
- 並列化は orchestrator が所有する。独立 finding は非重複 write scope の executor へ並列割当し、依存 finding は直列化する。executor 自身は SubAgent を再帰起動しない
- Codex 委譲判定も orchestrator が所有し、executor は割り当て済み scope だけを処理する

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `max_iterations (3)` 超過 → `convergence_status: incomplete` (human_review 必須・force_pass 禁止)。発散は `diverging`
  - 目的: 暴走防止と人間介入の明示
  - 背景: 自動収束失敗は構造的問題のシグナル

### 4.2 観測 / ロギング
- 出力先: `changed_paths` / `validation_commands` / `residual_risks` を JSON で記録
- trace 連携: `eval-log/<plugin>/<skill>/elegant-review/<run-id>/elegant-review-trace.json` の phase3 セクションに patch diff 要約 / validation 結果 / iteration_count を記録
- 反復上限: `max_iterations=3` 超過で `incomplete` + human_review (Layer 1 不変ルール参照)

### 4.3 セキュリティ
- findings 外の編集禁止
  - 目的: スコープ漏れの防止
  - 背景: 監査追跡可能性の維持
- `commit_authorized=false` で `git commit` / `git push` / PR 作成を実行しない
- PII / secret / 認証情報を patch / verdict / trace へ転記しない (検出時 `***` マスク)
  - 目的: 漏洩防止
  - 背景: trace と verdict.json は共有される

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `elegant-improvement-executor` (`workflow-manifest.json` resources `subagent-improvement-executor` で解決)

### 5.2 ゴール定義
- **目的**: Phase2 findings の C1-C4 FAIL を最小パッチで解消し、検証通過した verdict.json を成立させる
- **背景**: 周辺リファクタ混入と検証未実行の自己申告は review 再現性を破壊するため、スコープ最小化と validation_commands 必須化を要件化
- **達成ゴール**: changed_paths / validation_commands / residual_risks / convergence_status が記録され、orchestrator が `build-verdict.py` で verdict.json を導出できる状態

### 5.3 完了チェックリスト (停止条件)
- [ ] severity_order: high/critical から順に適用
- [ ] scope_minimal: findings 外の変更を混ぜていない
- [ ] dry_run_guard: `dry_run=true` で対象を Edit / Write していない
- [ ] variable_abstraction_applied: 直書き具体値を `{{VAR}}` へ昇格、source_trace 保持
- [ ] validation_run: `validation_commands` を実行し結果を記録 (未実行のまま pass 宣言禁止)
- [ ] safety_valve: `max_iterations=3` 超過時 `convergence_status: incomplete` を選択 (human_review 必須・force_pass 禁止)
- [ ] git_authority: `commit_authorized` を記録し、false なら patch までで停止
- [ ] signal_strict: `python3 scripts/validate-paradigm-coverage.py --strict-signal <log_dir>/findings.json` が exit 0 (smell の便宜値 condition と condition/condition_signal 不一致が 0 件)
- [ ] verdict_handoff: `convergence_status` を enum で一意に返す。`verdict.json` は書かず、orchestrator が `run_status` へ写して `build-verdict.py` で導出し、`emit-observable.py` を PASS/FAIL 双方で実行する
- [ ] determinism: 同 findings + iteration_count で changed_paths の順序と内容が一致

### 5.4 実行方式 (固定手順を持たない動的生成ループ)
**固定手順禁止**。完了チェックリストと `convergence-policy.json` の Δneg/Δpos 閾値を唯一の停止条件とし、状況に応じて手順をその都度設計・実行・自己評価する。例示 (網羅でない):
- 未充足項目を特定 (未解消 finding / 未実行検証) → 解消候補手順を立案 (severity 順グルーピング / 受領 scope の最小パッチ適用 / validation_commands 実行 / 収束判定 / verdict emit のいずれか)
- 実行し `changed_paths` / `validation_commands` を更新 → 閾値で自己評価
- 未達なら次周回 (上限: max_iterations=3)
- 到達後も C1-C4 未達なら `convergence_status: incomplete` を選択 (human_review 必須・`force_pass` 禁止)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase3, Phase2 完了後)
- 後続 phase: 完了レポート

### 6.2 ハンドオフ / 並列性
- 前 phase 受領元: phase2-parallel の `findings.json`
- 次 phase 提供先: run-elegant-review 完了レポート / `verdict.json`
- 並列: orchestrator が独立 finding を非重複 scope の executor へ並列割当し、依存ありは直列化する。executor は再帰起動せず、Codex 委譲も orchestrator が判断する

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
Δneg/Δpos 閾値で収束判定。`max_iterations=3` 超過時は `incomplete` を選択
(force_pass 禁止)。

出力は `./schemas/phase-output.schema.json#/definitions/phase3_output` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
