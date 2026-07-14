<!--
  POINTER (SSOT)。このファイルは独立テンプレートではない。
  system 開発の実行タスク仕様 (runtime task spec) を emit する正本は system-dev-planner:
    - plan 正本   : plugin-plans/system-dev-planner/references/system-task-spec-template.md (template_version 1.0.0)
    - build 後資産 : plugins/system-dev-planner/references/system-task-spec-template.md
  dev-graph は system 実行タスク仕様を emit しない (登録・投影・完了収束のみ担う)。
  かつて本ファイルに存在した draft body は正本へ統合済み (SSOT 重複解消・EV-BK07 / system-dev-planner phase-08,phase-12)。
  正本は本 draft の上位互換で、次を追加保持する:
    Machine-readable registration fields / Source pin / Repository context /
    Branch and worktree execution / implementation-readiness 判定。
-->

# System task overlay — POINTER

> **正本 = `plugin-plans/system-dev-planner/references/system-task-spec-template.md`。**
> このファイルは後方互換のための pointer であり、内容の source of truth ではない。
> system 開発タスク仕様の節構成・必須フィールド・implementation-readiness 判定は上記正本を参照すること。

## 責務境界 (なぜ pointer なのか)

- **emit する主体**: system-dev-planner (ミクロ層) が 1 feature → P01..P13 exact 13 executable task specs を正本テンプレートで生成する。
- **dev-graph の役割**: 生成された 13 task を parent_feature 付きで atomic 登録し (§8 `references/execution-tracker-contract.md`)、tracker_binding を解決して beads/GitHub へ投影する。**dev-graph 自身は runtime task spec を emit しない**。
- したがって本 overlay は dev-graph の scaffolding 上は vestigial であり、正本へのリダイレクトのみを担う。

## dev-graph overlay 節 → 正本節の対応 (参照用・重複記述しない)

| dev-graph overlay 節 (旧 draft) | 正本 (system-task-spec-template.md) の対応節 |
|---|---|
| Workstream applicability | Workstream applicability |
| Architecture and deploy unit | Architecture and deploy unit |
| Verification and evidence | Verification and evidence |
| Rollout and rollback | Rollout and rollback |
| Tracker publication and completion intent | Tracker publication and completion |
| (正本のみ) | Machine-readable registration fields / Source pin / Repository context / Branch and worktree execution / implementation-readiness 判定 |

> beads/GitHub 投影に要する id (=graph_node_id・登録時採番) / depends_on (task-graph DAG) / status (registration schema const) / parent (parent_feature) は、正本テンプレート + `dev-graph-registration.schema.json` + `task-graph.json` の合成で充足する (`references/execution-tracker-contract.md` §2 状態写像表が正本)。
