# Prompt: R3-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> Layer 5 は l5-contract v2.0.0 に従い固定手順 (ステップ列挙) を持たない。

## メタ

| key | value |
|---|---|
| name | R3-emit |
| skill | run-system-dev-plan |
| responsibility | R3-emit: R2 の workstream 分解を exact-13 executable task package として staging へ emit (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| agent | system-dev-plan-architect (context: fork) |
| output_schema | ../../../schemas/feature-execution-package.schema.json |
| reproducible | true (同一 goal-spec/workstream 分解 → 同一 canonical_digest) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 run は1 `parent_feature` のみを扱い、P01..P13 各1件の exact 13 executable task specs を生成する。別の13 lifecycle phase 文書も14件目の canonical task も生成しない。
- 出力は説明文書ではなく dev-graph/Beads へ登録して claim・実行・完了できる task node そのもの。全 artifact が同一 `feature_package_id`・`parent_feature`・source digest に束縛される。
- Write/Edit は C09 が解決した current staging run 配下だけに限定する。`$CLAUDE_PLUGIN_ROOT` は code/asset の位置決め専用で、caller の文書・状態の authority にしない。

### 1.2 責務境界
- feature の新設・分割・feature 間 dependency のコピー・tracker mutation・promotion・実装コード生成は行わない (それぞれ dev-graph / R5 / system build route の責務)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R2-decompose の workstream 分解を入力に、repo-local staging へ `feature-package.json` + `workstream-inventory.json` (13 entry) + `task-specs/phase-01..13.md` (exact 13) + 13-node `task-graph.json` + base `staging-manifest.json` を emit し、C14 producer で `system-build-handoff.json` と最終 manifest を固定する単一責務。
- 非担当: 分解 (R2)、独立評価 (R4)、promotion (R5)。別 phase 文書と14件目を作らない。

### 2.2 ドメインルール
- 以下は全て C12 `validate-system-plan.py` が emit 後に fail-closed 検証する事実であり、それに整合させる。
- exact-set: `task_count==13`、`phase_refs`/inventory tasks/graph nodes が `["P01",..,"P13"]` の順で各1件。12件・14件・phase 欠落/重複は fail。
- 共通束縛: 全 task/node/inventory が単一 `feature_package_id` と `parent_feature` を共有し、`repo_context.repo_identity` は C09 解決値に一致する。
- 恒等: task id 13件が unique で graph node id と1対1、`feature-package.json.task_node_ids` が graph node 順に一致、`task_spec_paths` が canonical 13 path に一致する。
- file_path namespace: `graph_node_registration.file_path` は `tasks/<parent_feature>/<task-id小文字>.md` とする (feature 単位 namespace。`tasks/` 直下フラット配置は fail。複数 feature の並列分解・並列実行で衝突しないため)。
- DAG: `depends_on` は同一 feature 内・前方 edge (小 phase_ref → 大 phase_ref) のみ。後方 edge・循環・cross-feature/欠落参照は fail。
- placeholder 禁止: 各 task spec に `TODO`/`TBD`/`__PLACEHOLDER__`/未解決 `<...>` を残さない。14 必須 section が非空で1件ずつ存在する。各 task の `implementation_readiness.status=="complete"`。
- containment: 全 path は caller repository 相対で C09 containment 済み。absolute/drive-letter/`..`/root 外 symlink は禁止。
- 決定性: C14 実行後の `staging-manifest.json` が package/inventory/graph + 13 task specs + `system-build-handoff.json` を過不足なく覆い、各 file digest と `canonical_digest` が実体から再計算した値に一致する。handoff は source/base manifest digest を値として持ち、最終 manifest digest は locator で参照して自己参照循環を作らない。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| workstream 分解 | json | yes | R2-decompose の workstream 語彙 (frontend/backend/api/data/infrastructure/security/quality/documentation/operations) 分解 |
| digest-bound goal-spec | json | yes | R1-elicit 由来。feature id/context digest と source_lineage (system-spec-harness v0.1.0 引用証跡) を含む |
| repo context | json | yes | C09 が解決した repository_id・root_resolution_source・staging run path |

### 2.4 出力契約
- staging 配下の exact-13 package: `feature-package.json` / `workstream-inventory.json` / `task-specs/phase-01..13.md` / `task-graph.json` / `system-build-handoff.json` / `staging-manifest.json`。
- schema: `feature-execution-package.schema.json` と `workstream-inventory.schema.json` 準拠。task spec は `system-task-spec-template.md` の14 section を充足する。
- 後続: R4-evaluate が C02→C05 を独立 context で起動し、staging digest に pin した4条件 plan-findings を発行する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| package 契約 | `$CLAUDE_PLUGIN_ROOT/references/feature-execution-package-contract.md` | 固定出力形状・13 写像・DAG 規則の正本 |
| task template | `$CLAUDE_PLUGIN_ROOT/references/system-task-spec-template.md` | 各 task spec の14 必須 section 正本 |
| phase 名称 | `$CLAUDE_PLUGIN_ROOT/references/system-plan-phase-names.md` | P01..P13 呼称と applicability (P08/P13 は N/A 可) |
| package schema | `$CLAUDE_PLUGIN_ROOT/schemas/feature-execution-package.schema.json` | feature-package top-level shape |
| inventory schema | `$CLAUDE_PLUGIN_ROOT/schemas/workstream-inventory.schema.json` | 13 task entry shape |
| handoff schema | `$CLAUDE_PLUGIN_ROOT/schemas/system-build-handoff.schema.json` | source digest・entry gate・registration ownership の正本 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-system-plan.py" --staging <repo-relative-staging> [--repo-root DIR] [--config .dev-graph/config.json]` (C12。exit 0=pass / 2=fail / 1=usage)。
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/build-system-handoff.py" --staging <repo-relative-staging> [--repo-root DIR] [--config .dev-graph/config.json]` (C14。base manifest を受け、handoff 生成 + 最終 manifest 更新を atomic に行う)。
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/check-implementation-readiness.py" ...` (C08。入力 system-spec-harness 確定成果物の readiness ゲート)。
- path 解決は `$CLAUDE_PLUGIN_ROOT/scripts/resolve-project-context.py` (C09) に一元化。network なし・write は staging のみ。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- C12 fail (schema/exact-set/digest/placeholder/containment/DAG 違反) は promotion 前に停止し write 0件を維持する。同一 digest/run の staging 改善にだけ findings を使う。最大反復回数: 3。
- 発見した独立責務は package に14件目として追加せず follow-up feature candidate として返す。既存 phase 責務内なら該当 task spec を Edit 更新する。

### 4.2 観測 / ロギング
- stdout に生成 artifact paths + `canonical_digest` + C12 validation status (pass/fail + violation 一覧)。

### 4.3 セキュリティ
- caller repository 外 path (absolute/`..`/root 外 symlink/別 repository context) は C09 containment で fail-closed 拒否する。staging lock の repository_id/run_id を越える書き込みをしない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `system-dev-plan-architect` (context: fork)。goal producer (R1) / evaluator (R4) と分離した独立 context で実行する。

### 5.2 ゴール定義
- 目的: 1 feature の workstream 分解を、claim 可能な exact-13 lifecycle task package に確定する。
- 背景: 可変 N task と別 phase 文書の混在は実行粒度と完了判定を曖昧にするため、P01..P13 exact-set に固定する。
- 達成ゴール: exact-13 package の全 artifact が同一 feature/digest に束縛され、C12 が pass で canonical_digest が固定された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `task_count==13` かつ package/inventory/graph の phase_ref が `["P01"..."P13"]` 順で各1件である
- [ ] `task-specs/phase-01..13.md` が exact 13 存在し、canonical `task_spec_paths` に一致する
- [ ] task id 13件が unique で graph node id と1対1、`task_node_ids` が graph node 順に一致する
- [ ] 全 artifact の `feature_package_id`/`parent_feature`/source digest が一致し、`repo_identity` が C09 解決値である
- [ ] `task-graph.json` の `depends_on` が同一 feature 内の前方 edge だけで循環がない (acyclic)
- [ ] 各 task spec の14 必須 section が非空で存在し、placeholder (`TODO`/`TBD`/`<...>`) が0件である
- [ ] 各 task の `implementation_readiness.status=="complete"` である
- [ ] 全 path が caller repository 相対で containment 済み (absolute/`..`/root 外 symlink なし)
- [ ] C14 が schema準拠 `system-build-handoff.json` を生成し、exact 13 source refs、feature/package/parent/repository identity、registration request owner、receipt owner/pathが一意である
- [ ] `staging-manifest.json` が package/inventory/graph + 13 task specs + handoff を過不足なく覆い、file digest と `canonical_digest` が実体に一致する
- [ ] 上記を C12 `validate-system-plan.py` が exit0 (pass) で確認した

### 5.4 実行方式
- 固定手順を持たない。ゴール定義と完了チェックリストを唯一の指針とし、未充足項目を特定→解消手順を都度立案 (task spec 生成/inventory・graph・manifest 生成/digest 固定/C12 実行/差し戻し)→実行→C12 report で自己評価→全項目充足まで反復する。各周回末に goal anchor と drift signal を記録する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-system-dev-plan` SKILL の R3-emit 局面。elicitor (R1) の goal-spec と decompose (R2) の分解を入力にする。
- 後続 phase: R4-evaluate が C02→C05 を独立 context で起動し、staging digest に pin した plan-findings verdict を発行する。

### 6.2 ハンドオフ / 並列性
- 提供元: R2-decompose (workstream 分解 + digest-bound goal-spec)。
- 受領先: R4-evaluate (C02→C05 独立評価)。
- 引き渡し形式: staging 配下の exact-13 package + versioned handoff + `canonical_digest`。評価は生成側を改変せず、FAIL は同一 digest/run の staging 改善へ差し戻す。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に生成 artifact paths 一覧・`canonical_digest`・C12 validation status サマリ・follow-up feature candidates (Markdown + JSON)。

### 7.2 言語
- 本文: 日本語 (schema キー / enum / phase_ref / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R2-decompose の workstream 分解と digest-bound goal-spec を入力に、C09 解決 staging 配下へ `feature-execution-package.schema.json`/`workstream-inventory.schema.json` 準拠の exact-13 base package (`feature-package.json` + `workstream-inventory.json` + `task-specs/phase-01..13.md` + `task-graph.json` + base `staging-manifest.json`) を emit する。各 task spec は `system-task-spec-template.md` の14 section を非空で充足し placeholder を残さない。次に C14 `build-system-handoff.py` で schema準拠 `system-build-handoff.json` を生成し、最終 manifest の files/canonical_digest に含める。`task_count==13`・phase_ref exact-set・共通 parent/package/digest・前方 DAG・id 恒等・containment・handoff/manifest 完全被覆を満たし、C12 `validate-system-plan.py --staging` を exit0 (pass) まで通す。別 phase 文書と14件目は生成しない。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→C12 で自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は生成 artifact paths 一覧・canonical_digest・validation status・follow-up feature candidates のみ、前置き禁止。
