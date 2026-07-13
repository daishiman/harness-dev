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
E1/E2/E3 の断線をそれぞれ producer/consumer/gate 実体へ 5 種の component_kind (skill/sub-agent/slash-command/hook/script) で写像し、N=11 実体を `component-inventory.json` へ分解する。harness-creator は既存 plugin (`existing-plugin-update`) のため、envelope は新規 manifest でなく `plugins/harness-creator/.claude-plugin/plugin.json` の現状値を基にした consistency draft として設計する owner フェーズ。

## 背景
パイプラインのエッジは必ず 2 plugin (plugin-dev-planner / harness-creator) にまたがるため、consumer/producer 各修正は所有 plugin 側へ build_target を routing する (E1 consumer→plugin-dev-planner、E2 consumer→harness-creator、E3 emit→harness-creator、E3 consume→plugin-dev-planner)。両 plugin は repo-bundled かつ `distributable:false` であり、`check-runtime-portability.py` (plugins/ 始まり・`..` 禁止) を満たすため cross-plugin build_target は install 携帯性を毀損しない。単一 skill 偏重を避けるため 5 種を全て検討し、no-split threshold (複数 skill 共有/独立検証/280 行超のいずれか) に従い script の親畳み込み/plugin-root 昇格を判断する。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- 現行 `plugins/harness-creator/.claude-plugin/plugin.json` (ディレクトリ自動発見・entry_points 未使用) と `plugins/plugin-dev-planner/.claude-plugin/plugin.json` (entry_points 明示登録制) の manifest 方式の違いを把握している。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- E1/E2/E3 → component 対応: E1 consumer=C01(skill 更新)+C02(command 更新)、E1 gate=C04(情報漏れ検出)、E2 consumer=C06(skill 更新)+C07(command 更新)、E2 gate=C08(routes↔inventory 突合)、E3 emit=C09(改善成果物正規化)、E3 provenance gate=C05、横断 fail-closed=C11(hook)、改善反映の意味的忠実性レビュー=C10(sub-agent)。schema 更新 (source_intake/source_improvement 追加) は C03 に折り込む。
- no-split threshold: C03/C04/C05 は `run-plugin-dev-plan` (C01) の付随物として親 skill 配下 (`placement_scope: skill`, `requires_parent_scaffold: C01`) に畳む。C08/C09 は複数 consumer (build 実行入口/改善出力元 3 skill) から共有されるため `placement_scope: plugin-root` へ昇格する。
- manifest 差分の非対称性: envelope-draft/plugin.json は build handoff gate 用に inventory surface component の entry_points.skills/commands/agents を明示する。実 plugins/harness-creator/.claude-plugin/plugin.json への反映は envelope build 境界で扱う。plugin-dev-planner 側は entry_points.agents[] へ C10、hooks.PreToolUse へ C11 の登録が必要 (該当 component 自身の build スコープで処理)。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 11 component・plugin_level_surfaces 採否込み)。
- `envelope-draft/plugin.json` (harness-creator 現行 manifest の consistency draft・無変更を明示)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。plugin-dev-planner 側 manifest 差分 (entry_points/hooks 追加) の実施自体も build 時 (C10/C11 の build スコープ)。

## 完了チェックリスト
- [ ] 全 11 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces (manifest/composition/harness_eval/references_config_assets/schemas/vendor/mcp_app_connector/notion_config) の採否が明示されている。
- [ ] 要件 C10: 全 build_target が `plugins/` 始まりで `..` を含まず、E1/E2/E3 各修正が所有 plugin 側へ正しく routing されている。
- [ ] 要件 C11: いずれの build_target にも `plugin-plans/plugin-dev-planner/` / `plugin-plans/skill-intake/` 配下が含まれない。
- [ ] `envelope-draft/plugin.json` が inventory surface component の entry_points.skills/commands/agents を明示し、その旨が handoff / inventory note と整合している。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C11 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。
