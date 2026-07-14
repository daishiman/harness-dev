# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-elicit |
| skill | run-system-dev-plan |
| responsibility | R1 goal-spec の確定 (system-spec-harness v0.1.0 確定成果物 + dev-graph 呼出し引数から) (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| input_schema | ../../../schemas/feature-context.schema.json |
| output | staging `goal-spec.json` (R2-decompose が消費する digest-bound handoff) |
| reproducible | true (同一 feature-context + confirmed source digest から同一 goal-spec 写像) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- goal-spec は system-spec-harness v0.1.0 の confirmed 成果物と feature-context を lineage で引用して確定する。仕様を再生成・再構築しない。
- feature の新設・分割・14 件目 task 生成は行わない (それは dev-graph マクロ層の責務)。R1 は 1 feature の goal-spec 確定に責務を限定する。
- feature-context の `graph_node_id` と `--feature-id` が一致しなければ staging 作成前に fail-closed で停止する。

### 1.2 倫理ガード
- 推定値を confirmed と表示しない。confirmed / evaluation PASS でない仕様を根拠にしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: system-spec-harness confirmed 成果物 + dev-graph 呼出し引数 (`--feature-id` / `--feature-context`) から purpose/goal/scope_in/scope_out/acceptance/architecture_refs を単一 feature の goal-spec へ写像し、source lineage を接地する。
- 非担当: feature 分割 (dev-graph)、workstream 分解 (R2-decompose)、P01..P13 task 生成 (R3-emit)、readiness promotion (R5-promote)。

### 2.2 ドメインルール
- goal-spec の全値は単一 feature と confirmed source digest に追跡できること。欠落値を推測補完しない (欠落は fail-closed)。
- architecture_refs は caller repository 内で解決できる参照だけを引用する。絶対 path・`..`・root 外 symlink を拒否する (C09 realpath containment 前提)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| graph_node_id | string | yes | 起動元 dev-graph feature ノード id。`--feature-id` と一致必須 |
| artifact_kind | const=feature | yes | 単一 feature タグ。feature 以外は対象外 |
| purpose | string | yes | goal-spec の purpose へ写像 (非空必須) |
| goal | string | yes | goal-spec の goal へ写像 (非空必須) |
| scope_in | string[] | yes | 含む範囲。exact-13 task 拡散防止の境界 (非空必須) |
| scope_out | string[] | yes | 含まない範囲。追加責務は 14 件目にせず follow-up feature candidate へ (非空必須) |
| acceptance | string[] | yes | goal-spec の acceptance へ写像 (非空必須) |
| architecture_refs | string[] | yes | caller repo 内で解決する system-spec/architecture 参照。lineage で引用 (非空必須) |
| updated_at | date-time | yes | feature context 更新日時 (RFC 3339 / ISO 8601) |
| --feature-id | arg | yes | dev-graph 呼出し引数。`graph_node_id` と一致必須。不一致は staging 前停止 |

### 2.4 出力契約
- 確定した goal-spec (staging `goal-spec.json`)。purpose/goal/scope_in/scope_out/acceptance/architecture_refs の写像 + source path/plugin version/digest の lineage を持つ。
- 後続 R2-decompose が消費する digest-bound handoff。schema ファイルは持たない内部成果物だが、全値を単一 feature と confirmed digest へ追跡可能に保つ。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| elicitor agent | `$CLAUDE_PLUGIN_ROOT/agents/system-dev-plan-elicitor.md` | goal-spec 抽出委譲 |
| feature-context schema | `$CLAUDE_PLUGIN_ROOT/schemas/feature-context.schema.json` | 入力 9 フィールド正本 |
| package contract | `$CLAUDE_PLUGIN_ROOT/references/feature-execution-package-contract.md` | macro/micro 境界・非担当 |
| feature-context (caller) | `--feature-context` の repo-relative JSON | feature identity/purpose/goal/scope/acceptance/refs |
| confirmed system-spec (caller) | architecture_refs が指す caller repo 内 artifact | lineage 引用元 |

### 3.2 外部ツール / API
- Task ツールで `system-dev-plan-elicitor` を独立 context (fork) 起動する。
- 事前に C09 (`resolve-project-context.py`) が repo root / realpath containment を確定し、C08 (`check-implementation-readiness.py`) が system-spec index/requirements/architecture graph を `complete` と判定している前提。
- network なし。Read は caller repo 内 feature-context / confirmed artifacts、Write は現在 run の staging `goal-spec.json` に限定。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- feature id / repository id / purpose / goal / scope / acceptance / architecture refs / source path/version/digest の欠落・不一致は fail-closed。`graph_node_id` と `--feature-id` 不一致、絶対 path / traversal、別 repository の context を拒否し、missing fields を caller へ返す。最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に確定 goal-spec の staging path と source digest、充足した checklist 項目サマリ。JSON key は英語、根拠説明は日本語。

### 4.3 セキュリティ
- caller repository 内の feature-context と confirmed system-spec だけを Read。Write は現在 run の staging `goal-spec.json` に限定。symlink 物理元 / 別 repo の read/write と絶対 path / traversal を拒否する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `system-dev-plan-elicitor` (independent context / fork)。caller context の思い込みを避けるため fork で実行する。

### 5.2 ゴール定義
- 目的: 1 feature の実行計画に必要な goal と出典を確定する。
- 背景: feature scope と仕様出典が曖昧だと後続の exact-13 task が別責務へ拡散する。
- 達成ゴール: goal-spec の全値が単一 feature と confirmed source digest に追跡でき、feature digest に接地して確定している状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] feature-context の `graph_node_id` と `--feature-id` (feature identity) が一致している
- [ ] purpose / goal / scope_in / scope_out / acceptance 由来値がすべて非空である
- [ ] architecture_refs が caller repository 内で解決できる
- [ ] system-spec source が confirmed / evaluation PASS である
- [ ] lineage が source path / plugin version / digest を持ち feature digest へ接地している
- [ ] scope_in / scope_out が goal-spec に明示され、feature 分割・workstream 分解・task 生成を行っていない

### 5.4 実行方式
- 固定手順を持たない。未充足 field と source evidence を特定→必要な read/write を都度立案 (feature-context read / confirmed artifact 接地 / goal-spec write / 差し戻し)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。各周回末 (Anchor) に original goal / current snapshot / delta / next directive / drift signal を記録し、次周回の入力にする。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-system-dev-plan` SKILL の `plan` 局面 R1-elicit。C09 repo context 確定 + C08 readiness=complete + feature-context preflight 後に起動。
- 後続 phase: R2-decompose が goal-spec を workstream 語彙へ分解する。

### 6.2 ハンドオフ / 並列性
- 提供元: R0-resolve (C09 repo context / feature identity)。
- 受領先: R2-decompose (goal-spec を消費)。単一 feature の直列 elicit で並列性なし。
- 引き渡し形式: digest-bound goal-spec (staging `goal-spec.json`)。architect (R2/R3) が同一 feature digest を参照する。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に確定 goal-spec の staging path・source digest・充足 checklist サマリ (Markdown)。対話なし。

### 7.2 言語
- 本文: 日本語 (JSON key / enum / path / 識別子は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Task ツールで `system-dev-plan-elicitor` を独立 context (fork) 起動し、`--feature-id` と `--feature-context` (9 フィールド JSON) と confirmed system-spec を読んで、単一 feature の digest-bound goal-spec を staging `goal-spec.json` へ確定する。`graph_node_id` と `--feature-id` が不一致、または purpose/goal/scope_in/scope_out/acceptance/architecture_refs のいずれかが欠落・root 外なら fail-closed で停止し missing fields を caller へ返す (feature 分割・workstream 分解・task 生成はしない)。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は goal-spec の staging path・source digest・充足 checklist サマリのみ、前置き禁止。
