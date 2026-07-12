---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C24, C25, C26, C27, C28]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
L3 planとして、全buildable componentを後段L4 builderへ委譲できるrouting契約を確定する。実体化やGreen実測は後段build lifecycleの責務であり、本phaseの完了条件にはしない。

## 背景
後段buildはphase順でなくcomponent依存top-sort順に走る。phase軸とbuild軸を分離し、本phaseは実行結果ではなく、routes・builder・build_target・criteriaを揃えた「後段が実行可能な契約状態」を宣言する。

## 前提条件
- P04 でskill criteriaとC25-C27のhook/lifecycle/worktree fixture、external system-dev-planner引用の受入が契約として確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている (build 順は routes / `component-inventory.json` の依存 DAG top-sort が SSOT・散文で個別列挙を二重維持しない)。
- 後段builderの利用可否とcontract-only gapがhandoffに明示されている。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順 (依存先が常に先。phase 番号順ではない)。
- builder 3 種の実行実体差: `builder_status` が executor-backed (実行 skill 実在) / contract-only (routing 語彙のみ・`gap_ref` 必須) を区別する (解決表は io-contract §9)。
- couples_with (C03↔C04) の実現: derive-task-graph が同一 phase 直列化 depends_on へ展開し、validate-task-graph (j) が実現を検査する。
- Green 判定の主体は P04 で固定した criteria (実装が判定基準を都合よく再定義しない)。
- route固有criteriaはhandoffへ複製せず、`route.id`と同じinventory component idの`quality_gates/harness_coverage/feedback_contract.criteria`を参照する。1:1 parityが参照解決を保証する。

## 成果物
- 全24 componentのtop-sort可能なroutesと、後段build時の停止条件。
- `envelope-draft/plugin.json` とschema draftのmanual-apply契約。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT 重複整理 (P08)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。
- 実タスクの実装コード生成 (capability-build / task-graph build へ handoff・本 plan の責務外)。

## 完了チェックリスト
- [ ] 全routeが依存top-sort可能でbuilder/build_kind/build_args/build_targetとcriteriaを持つ。
- [ ] C09の正式verb集合とdepends_onがinventory/handoffで一致する。
- [ ] C01/C02/C03/C11/C14/C18にhybrid directory・自動routing・migration契約が焼かれている。
- [ ] C19がsystem-spec-harness引用を持ち、system task plan contractとreadiness停止条件はexternal system-dev-planner引用 (C04/C09/C14の統合記述 + external_contract_ref) が搬送する。
- [ ] C25-C27がClaude hook→GitHub lifecycle→worktree leaseの責務を分離し、plugin/project hook source一意性とdefault-branch-only durable updateを搬送する。
- [ ] 実体化・Green実測は後段L4 build reportで確認することが明記され、本L3 planのPASS条件と混同されていない。

### 受入例
- 満たす例: handoffの24 routeがinventoryと1:1で、後段がC24→C28→C27→C11/C12→C26→C25→C01/C02の依存順を計算できる。
- 満たす例: C02の分類previewとC18のread-only条件がcriteriaとしてroute先へ搬送される。
- 満たさない例: C09 (command) が依存先 C18 より先に build される → top-sort 違反として `check-build-handoff.py` が exit1 で検出する。

### 事前解決済み判断
- build 順は phase 番号順ではなく `component-inventory.json` の依存 DAG top-sort 順を唯一の正本とする (散文の個別列挙は二重維持しない)。
- builder 3 種 (executor-backed/contract-only) の判定は `builder_status` フィールドで固定し、contract-only は `gap_ref` 必須とする。
- couples_with (C03↔C04) は同一 phase 直列化として derive-task-graph が展開し、C14↔C15 は疎結合 (couples_with 非使用) のまま depends_on のみで連携する。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing) / `component-inventory.json` (依存 DAG)。
- 対象 component C01-C19・C24-C28 (計24)。
- 後続 P06 (test-run)。
