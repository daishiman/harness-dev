---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
12 buildable component (skill×2 / sub-agent×3 / slash-command×1 / hook×1 / script×5) への分解を確定し、共有 script hoist・依存 DAG・`workstream_kind`/`build_target_kind` 二重フィールド設計を固める。intake時点の4論点 (13 phase 正式名称・workstream-inventory スキーマ・dev-graph 登録規約・buildable component 構成) は本フェーズで全て確定済みで、現行`goal-spec.open_questions=[]`である。script 5 種のうち C09 (resolve-project-context.py) は caller repository root 解決と containment、C10 (init-project-layout.py) は repo-local 冪等 init、C11 (promote-system-plan.py) は same-digest atomic promotion、C12 (validate-system-plan.py) は staging 生成物の決定論検証 (promotion gate2 の判定入力) を担い、goal-spec checklist C9/C10 (source pin・multi-repo isolation) の物理的な受け皿になる。

## 背景
goal-spec checklist C2 は「component_kind をビルド対象語彙として保持しつつ、生成対象の分類軸を system workstream 語彙へ置換する」という一見二重の要求を課す。これは 2 つの異なる SSOT を混同すると破綻する: (a) **本 plan 自身の build 軸** (`component-inventory.json` の `component_kind`。plugin-dev-planner と同型の 5 種のまま) と、(b) **system-dev-planner が実行時に生成する `workstream-inventory.json` のスキーマ** (workstream 語彙へ置換される側)。本フェーズはこの二層を `workstream_kind` (9 値・主分類軸=frontend/backend/api/data/infrastructure/security/quality/documentation/operations) と `build_target_kind` (6 値=`application-code` + component_kind 5 値・ビルド対象語彙として保持する分) の 2 フィールド設計で両立させ、後者に混同しない。

## 前提条件
- P01 の goal-spec が確定している。
- `component-domain.md` (2 軸直交・5 種 component_kind・粒度原則) / `phase-lifecycle.md` (13 phase 写像) が参照可能。
- `plugin-plans/dev-graph/templates/system-plan-contract.json` (draft) の `workstream_kinds` (9 値) が先行参照として存在する。

## ドメイン知識
- **メタ/実行分離**: 本plugin planのlifecycle=13 phaseとbuild=12 componentはメタ層。runtimeは1 featureをP01..P13 exact 13 executable tasksへ1:1変換し、別phase documentsを生成しない。
- **workstream_kind / build_target_kind 二重フィールド設計** (本 plan の生成物側スキーマ、`references/workstream-inventory-schema-design.md` が正本): `workstream_kind` は system-dev-planner が生成するタスク仕様書の分類軸、`build_target_kind` は component_kind 5 値 + `application-code` (非 plugin-component の実装コード全般を指す汎用フォールバック) の計 6 値で、build_target_kind ∈ {skill,sub-agent,slash-command,hook,script} のときは plugin-dev-planner 同様の builder routing、`application-code` のときは task-graph build/capability-build への汎用 handoff とする。
- **共有 script hoist 原則**: `check-implementation-readiness.py` (C08) は C01 (R3 emit 時ゲート) と C07 (tool-call 時ゲート) の 2 箇所から呼ばれる (第二消費者あり) ため単一 skill 配下に畳まず `placement_scope=plugin-root` で hoist する。
- **assign kind の feedback_contract 省略**: `skill_kind=assign` (C02) は `FEEDBACK_LOOP_SKILL_KINDS` (run/wrap/delegate) に含まれないため `feedback_contract` を構造上省略できる (`assign-plugin-plan-evaluator` の実際の frontmatter で feedback_contract キーが存在しないことを precedent として確認済み)。
- **repo-local runtime**: C09 root resolver/containment、C10 no-overwrite init、C11 same-digest promotionをC08 readinessから分離する。symlink sourceはcode/assetsだけ、contentはcaller repoだけ。

## 成果物
- `component-inventory.json` (N=12。`considered_component_kinds` に 5 種全て検討証跡・`plugin_level_surfaces` 採否)。
- `references/workstream-inventory-schema-design.md` (workstream_kind/build_target_kind 二重フィールド設計。本 inventory の component_kind とは別スキーマである旨を明記)。
- `references/repo-local-runtime-contract.md` / `references/atomic-promotion-contract.md` / `dev-graph-registration-contract.json`。

## スコープ外
- 実装・build (P05)。
- criteria の Red 確定 (P04)。
- system-spec-harness の内容ロジック複製 (常に引用専用)。

## 完了チェックリスト
- [ ] `component-inventory.json` が 5 component_kind の検討証跡と plugin-level surfaces の採否を記録している。
- [ ] 全 12 component が build_target 非空・builder/build_kind 整合・依存 DAG 非循環 (`C09→{C12,C08,C10,C03}→{C05,C04,C07}→C02→C11→C01→C06`) で core 規律を携帯し、全repo-local readerがC09を直接または推移的に先行し、C01からC02/C05独立評価producerへ到達する。
- [ ] `workstream_kind`/`build_target_kind` 二重フィールド設計が `references/workstream-inventory-schema-design.md` に記載され、本 inventory の `component_kind` と混同されない設計になっている。
- [ ] root precedence、repo-relative config、realpath containment、repo別state/cache/lock、idempotent init、atomic promotionが独立componentへ割り当てられている。

## 参照情報
- `component-domain.md` (2 軸直交・粒度原則) / `phase-lifecycle.md` (13 phase 写像)。
- `plugin-plans/dev-graph/templates/system-plan-contract.json` (workstream_kinds 先行参照)。
- 対象 component C01-C12。
- 後続 P03 (design-review gate)。
