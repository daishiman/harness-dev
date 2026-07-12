# workstream-inventory.json スキーマ設計 (正本)

> 本書は goal-spec checklist C2 (「workstream-inventory が component_kind をビルド対象語彙として保持しつつ、生成対象の分類軸を system workstream 語彙へ置換して記録する設計」) の正本設計であり、`component-inventory.json` (system-dev-planner 自身の build 軸) とは別スキーマである。混同してはならない。

## 固定13 task package

1 runは1つの`parent_feature`から、P01..P13に1件ずつ対応するexact 13 taskを生成する。13 lifecycle文書と可変N taskを別々に生成する旧モデルは廃止し、13 task specs自体を実行lifecycleとする。全entryは同じ`feature_package_id`/`parent_feature`を持ち、配列順もP01..P13で固定する。詳細は`feature-execution-package-contract.md`。

## 対象と非対象

- **対象**: C01 (`run-system-dev-plan`) が R2-decompose 責務で実行時に生成する `workstream-inventory.json`。system-dev-planner が呼び出されるたびに `<出力先>/workstream-inventory.json` として出力される、システム開発タスクの成果物実体目録。
- **非対象**: 本 plan (`plugin-plans/system-dev-planner/`) 自身の `component-inventory.json`。そちらは plugin-dev-planner と同型の標準 `component_kind` 5 値 (skill/sub-agent/slash-command/hook/script) のままであり、本書の対象ではない。

入力lineageは `system-spec-harness` version `0.1.0` の `run-system-spec-compile` と `assign-system-spec-completeness-evaluator` が確定したcaller-repository-local成果物に限定する。source version/entrypoint不一致、別repository path、未確定評価はfail-closed。

## 2 フィールド設計

`workstream-inventory.json` の各エントリ (workstream task 相当) は、分類軸を単一フィールドへ畳み込まず、以下 2 フィールドへ分離する。

### `workstream_kind` (9 値・主分類軸)

生成対象のシステム開発タスクを人間可読に分類する軸。`plugin-plans/dev-graph/templates/system-plan-contract.json` の `workstream_kinds` を継承する。

| 値 | 意味 |
|---|---|
| `frontend` | UI/クライアント側実装 |
| `backend` | サーバー側ロジック実装 |
| `api` | API 設計・実装 |
| `data` | データモデル・永続化・migration |
| `infrastructure` | インフラ・デプロイ・CI/CD |
| `security` | セキュリティ設計・監査対応 |
| `quality` | テスト・QA・カバレッジ |
| `documentation` | ドキュメント・runbook |
| `operations` | 運用・監視・rollback |

### `build_target_kind` (6 値・ビルド対象語彙として保持する分)

goal-spec C2 の「component_kind をビルド対象語彙として保持する」要求を満たすフィールド。`component_kind` の標準 5 値に、非 plugin-component (通常のアプリケーションコード変更) を表す汎用フォールバック `application-code` を加えた計 6 値を持つ。

| 値 | 意味 | 分岐先 |
|---|---|---|
| `skill` / `sub-agent` / `slash-command` / `hook` / `script` | plugin-dev-planner 側 component_kind と同一語彙 (plugin component 実体を指す場合) | plugin-dev-planner 同様の builder routing (`run-skill-create`/`run-build-skill`/`plugin-scaffold`) |
| `application-code` | plugin component ではない一般的な実装コード変更 (frontend コンポーネント・backend サービス・DB migration 等) | task-graph build / capability-build への汎用 handoff |

## 分岐ルール

1. `build_target_kind` が component_kind 5 値のいずれかの場合、その task はビルド対象が plugin-dev-planner が管理する buildable component であることを意味し、`route.builder`/`build_kind`/`build_args` を plugin-dev-planner の routing 語彙と同一形式で埋める。
2. `build_target_kind` が `application-code` の場合、その task は plugin component を持たない一般実装であり、`route.builder` を `task-graph-build` または `capability-build` に固定し、build_args は宛先ハーネスの handoff 契約 (task-graph.json ノード形式) に委ねる。
3. 上記 2 分岐以外の値は `schemas-draft/workstream-inventory.schema.json` の `build_target_kind` enum が拒否する (fail-closed)。C08 (`check-implementation-readiness.py`) の責務は readiness 判定であり、語彙の拒否は schema 層が担う。

## エントリ最小フィールド

`workstream-inventory.json` の各エントリは以下を最小限持つ (詳細スキーマは `schemas-draft/workstream-inventory.schema.json` を正本とする):

- `id` (task-spec id。dev-graph の `graph_node_id` 割当規約への接続は確定済み`dev-graph-registration-contract.json`と`schemas-draft/dev-graph-registration.schema.json`に従う)
- `feature_package_id` / `parent_feature` (同一runの13 taskで共通)
- `workstream_kind` (上記 9 値)
- `build_target_kind` (上記 6 値)
- `phase_ref` (P01..P13 exact-setの一意slot。欠落・重複・追加は禁止)
- `depends_on` (task-graph 射影の入力となる依存 id 配列)
- `implementation_readiness` (`complete`/`incomplete`。C08 判定を反映)
- `source_lineage` (system-spec-harness 確定成果物への引用元パス。内容複製ではなく参照であることの証跡)
- `owners` / `tags` / `related_nodes` / `classification` (dev-graph registration必須fieldの決定論producer)
- `github_publication` / `pr_completion_policy` (Issue/Projects publication intentとlinked-PR all/any policy)
- `branch_policy` (one-task-one-branch、worktree lease必須、default-branch reconciliation、assignment_owner=dev-graph-scheduler。具体branch名は登録後にC15が一意導出)
- `write_scope` / `deploy_unit` / `acceptance` / `verification` / `rollback` (L4 executorへ渡す実装境界)
- `graph_node_registration` (promotion後にdev-graphへ渡すstable id + repo-relative file_path)

全pathは `.dev-graph/config.json` のcaller repository root相対値で、C09のrealpath containmentを通過しなければならない。symlink物理元のpathやabsolute pathを保存しない。

## 混同防止の運用規約

- `component-inventory.json` を編集する responsibility (P02/R2 の component 分解) と、`workstream-inventory.json` を生成する responsibility (C01 の R2-decompose) は別コードパスであり、同じ変数名・同じ JSON キーを使い回さない。
- レビュー・決定論ゲートの双方で、"component_kind" という語が出現する箇所は本 plan 自身の inventory に限定し、"workstream_kind"/"build_target_kind" という語が出現する箇所は生成物側のスキーマに限定することを、`check-spec-frontmatter.py` 等では検査対象外 (機械検査は範囲外・人間可読ドキュメントの一貫性は本書と index.md のドメイン知識節が担保する) とする。
