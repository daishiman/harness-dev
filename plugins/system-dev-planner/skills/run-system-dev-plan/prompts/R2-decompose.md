# Prompt: R2-decompose

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-decompose |
| skill | run-system-dev-plan |
| responsibility | R2 goal-spec を system workstream 語彙へ分解 (1 prompt = 1 責務) |
| agent | system-dev-plan-architect (context: fork) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/workstream-inventory.schema.json |
| reproducible | true (同一 goal-spec/feature digest から同一 workstream 分解) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 run は1 `parent_feature` のみを対象とし、その goal-spec を system workstream 語彙へ分解する。feature の新設・分割・feature 間依存は行わない (dev-graph 所有)。
- 分解軸は `workstream_kind` (9値・主分類) と `build_target_kind` (6値・ビルド対象語彙) の2フィールドへ分離し、単一フィールドへ畳み込まない。本 plan 自身の build 軸 `component_kind` とは別軸であり混同しない。
- 本責務は分類の中間表現までを確定する。P01..P13 exact-13 task spec・13-node DAG・feature package の emit は後続 R3-emit の責務であり、ここでは生成しない。

### 1.2 スコープガード
- 発見した独立責務は同一 package の14件目にせず、follow-up feature candidate として dev-graph へ返す。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R1-elicit が確定した goal-spec を、`workstream-inventory.schema.json` の語彙 (`workstream_kind` 9値 + `build_target_kind` 6値 + `secondary_workstreams` 任意) へ分解する単一責務。
- 非担当: exact-13 task spec 化・DAG/handoff emit (R3-emit)、readiness 判定 (C08)、独立評価 (C02..C05)、promotion (C11)、実装。

### 2.2 ドメインルール
- `workstream_kind` enum: frontend / backend / api / data / infrastructure / security / quality / documentation / operations。dev-graph `templates/system-plan-contract.json` の `workstream_kinds` を継承する。
- `build_target_kind` enum: skill / sub-agent / slash-command / hook / script / application-code。component_kind 5値のいずれかなら plugin-dev-planner 同型の builder routing、`application-code` なら task-graph build / capability-build への汎用 handoff を意味する。
- 上記 enum 外の値は schema 層が fail-closed で拒否する。語彙の拒否は分類側ではなく schema が担う。
- feature 間依存を task へコピーしない。dev-graph の feature A→feature B を正本とし、本責務は同一 `parent_feature` 内だけを分類する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| goal-spec | json | yes | R1-elicit が system-spec-harness v0.1.0 確定成果物 (feature digest 接地) から確定した goal-spec |
| feature context | json | yes | `graph_node_id` / `purpose` / `goal` / `scope_in` / `scope_out` を持つ単一 feature context |

### 2.4 出力契約
- schema: `workstream-inventory.schema.json` の語彙に準拠した workstream 分解 (中間表現)。各 task 相当へ `workstream_kind` (単一値)・`build_target_kind` (単一値)・`secondary_workstreams` (任意) を割り当てる。
- 位置づけ: 後続 R3-emit が P01..P13 exact-13 task spec へ写す入力。ここではファイル emit・phase slot 確定・DAG 構築は行わない。
- 単一性: 全 task 相当の分類は同一 `parent_feature` / `feature_package_id` に束縛される。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| workstream schema | `$CLAUDE_PLUGIN_ROOT/schemas/workstream-inventory.schema.json` | `workstream_kind`/`build_target_kind` enum 正本 |
| schema design | `$CLAUDE_PLUGIN_ROOT/references/workstream-inventory-schema-design.md` | 2軸設計・分岐ルール・component_kind 混同防止規約 |
| package contract | `$CLAUDE_PLUGIN_ROOT/references/feature-execution-package-contract.md` | 1 feature 粒度・13 phase 写像・follow-up feature 規約 |

### 3.2 外部ツール / API
- R2 は成果ファイルを emit せず script を起動しない (emit と決定論検証は R3 / C12 の責務)。
- workstream 語彙の enum 逸脱は後段の `validate-system-plan.py` / schema 層が fail-closed で検出する。
- network なし。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- enum 外 `workstream_kind`/`build_target_kind`、`parent_feature` 不一致、scope 逸脱、feature 間依存の混入は分解を停止し R1-elicit (goal-spec 補完) へ差し戻す。最大反復回数: 3。

### 4.2 観測 / ロギング
- workstream 別分類内訳・`build_target_kind` 内訳・follow-up feature candidate 一覧を要約する。

### 4.3 セキュリティ
- 全 path は caller repository root 相対で、absolute path / `..` / root 外 symlink を拒否する。goal producer/evaluator と分離した fork context で実行する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `system-dev-plan-architect` (context: fork)。goal producer/evaluator と分離した fork context で実行する。

### 5.2 ゴール定義
- 目的: goal-spec を system workstream 語彙へ曖昧さなく分解し、R3-emit が exact-13 task spec へ写せる中間表現を確定する。
- 背景: 分解軸を単一フィールドへ畳み込むと workstream 分類と build routing が混線し、implementation readiness 判定が属人化する。
- 達成ゴール: 全 task 相当が `workstream_kind` 単一値・`build_target_kind` 単一値へ enum 内で分類され、同一 `parent_feature` に束縛され、scope 逸脱と feature 間依存がない状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 全 task 相当の `workstream_kind` が 9値 enum に収まっている
- [ ] 全 task 相当の `build_target_kind` が 6値 enum に収まっている
- [ ] 全分類が同一 `parent_feature` / `feature_package_id` に束縛されている
- [ ] feature の `scope_in` を超える分類・feature 間依存・新規 feature がない
- [ ] 追加責務が14件目化されず follow-up feature candidate として分離されている
- [ ] `application-code` と component_kind 5値の分岐が schema-design の分岐ルールに一致する

### 5.4 実行方式
- 固定手順を持たない。未充足の完了チェックリスト項目を特定→分類/再分類の手順を都度立案→適用→チェックリストで自己評価→全項目充足まで反復する。各周回末に goal anchor と drift signal を記録する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-system-dev-plan` SKILL の `plan` 局面 (R2-decompose)。
- 位置: R1-elicit → **R2-decompose** → R3-emit の直列パイプライン中段。

### 6.2 ハンドオフ / 並列性
- 提供元: R1-elicit (digest-bound goal-spec)。
- 受領先: R3-emit (P01..P13 exact-13 task spec / 13-node DAG / feature package 生成)。
- 引き渡し形式: `workstream-inventory.schema.json` 語彙に準拠した workstream 分解 (中間表現) + follow-up feature candidates。同一 feature digest を参照する。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に workstream 別分類内訳・`build_target_kind` 内訳・follow-up feature candidate 一覧を Markdown で要約。

### 7.2 言語
- 本文: 日本語 (schema キー / enum / phase_ref は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R1-elicit が確定した digest-bound goal-spec を、`workstream-inventory.schema.json` の語彙 (`workstream_kind` 9値: frontend/backend/api/data/infrastructure/security/quality/documentation/operations、`build_target_kind` 6値: skill/sub-agent/slash-command/hook/script/application-code、`secondary_workstreams` 任意) へ分解する。exact-13 task spec 化・DAG/package emit は行わず (R3-emit の責務)、後続が P01..P13 へ写せる workstream 分解 (中間表現) を確定する。1 run=1 `parent_feature` を厳守し、feature 間依存・新規 feature・14件目を作らず、独立責務は follow-up feature candidate として返す。enum 外の値は schema 層が fail-closed で拒否する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→適用→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は workstream 別分類内訳・follow-up feature candidates・R3-emit への引き渡し要約のみ、前置き禁止。
