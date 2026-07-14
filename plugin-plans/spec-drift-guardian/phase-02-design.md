---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し、N=11 実体を `component-inventory.json` へ分解する。各 component の build_target・依存 DAG・品質機構を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。

## 背景
P01 で確定した goal-spec (checklist C1-C6) を、実際に build 可能な実体へ落とす最初の設計フェーズ。トリアージ・更新提案・独立検証・手動起動・close ゲート・共有決定論処理をそれぞれ独立 component として分解し、単一 skill への押し込み (skill 偏重) を避けるため 5 種の component_kind を必ず検討する。ライフサイクル軸 (13 phase) と成果物実体軸 (inventory) を二重に持たない正規化を敷き、build_target/depends_on は inventory のみが保持し phase は id 参照だけで紐づく。

## 前提条件
- P01 の `goal-spec.json` (checklist C1-C6) が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- harness-creator は通常解析/propose時read-only。C02 apply modeのみC04 PASSとユーザー明示承認後にallowlist対象へ書ける境界を共有している。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- kind 写像の判定核: 独立検証→sub-agent(C03/C04)、close前block→hook(C07)、完全diff再構成/決定論変換/完了判定→script(C11/C08/C09/C10)、手動起動→command(C05/C06)、goal-seek→skill(C01/C02)。
- `placement_scope`: script のみ持つ配置属性。C11 (aggregate-issue-diffs.py) は C01 skill + C10 script、C08 (parse-spec-diff.py) は C01 skill + C03 sub-agent、C09 (map-field-impact.py) は C01/C02 skill + C03 sub-agent、C10 (check-triage-complete.py) は hook C07 + command C06 から共有され、いずれも単一の親 skill が存在せず 2 消費者以上を持つため plugin-root へ hoist する。
- closeゲートはC10が4 artifactと実ファイルを突合し、`applied_verified` または `independently_verified_no_change` だけを許可する。C07はローカル`gh issue close`を遮断し、Web/API/Actionsの権威的gateは構造変更を要する未解決gapとして保持する。
- 内部artifactは triage-report / triage-verdict / sync-proposal / sync-audit-verdict の4 schema。C03/C04の独立判断をC02 applyとC10/C07へ必ず配線する。references/field-impact-mapと4 schemaはhandoff envelopeでownerを持つ。
- 依存DAGは C11→C08→C09→C01、C01→C03、C01→C02→C04、C03+C04+C11→C10、C02+C03+C04+C10→C06、C10→C07 を満たし非循環である。
- 責務境界: 検知 (fetch/diff/issue 起票) は既存 workflow/`ref-yaml-spec-fetcher` の責務であり本 inventory には含めない (C6)。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 11 component: C01 run-spec-drift-triage / C02 run-rubric-sync / C03 spec-impact-verifier / C04 rubric-sync-auditor / C05 spec-drift-triage command / C06 rubric-sync command / C07 guard-spec-drift-close hook / C08 parse-spec-diff.py / C09 map-field-impact.py / C10 check-triage-complete.py / C11 aggregate-issue-diffs.py)。
- `envelope-draft/plugin.json` (manifest draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 11 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces (manifest/composition/harness_eval/references_config_assets/schemas/vendor/mcp_app_connector/notion_config) の採否が明示されている (schemas は内部 artifact 契約のため required)。
- [ ] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線 / distribution) が設計されている。
- [ ] requiredなreferences_config_assetsとschemasにhandoff envelope ownerがあり、4 artifactのproducer/consumerが閉じている。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C11 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。
