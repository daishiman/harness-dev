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
改善要件をN=9実体へ分解し、provider-neutral取込、自動sync、relation producer、knowledge DAG、harness artifact index、consult(harness artifact + 相談orchestrator)のproducer-consumerを閉じる。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。YouTube 3経路を 3 skill に水増しせず単一 skill (`run-ubm-youtube-ingest`) のモード分岐へ統合し、全量性の二値判定のみを独立 script に分離するなど、SRP と非水増しの両立を判断する。既存 2 skill (`run-ubm-goal-setting`/`run-ubm-knowledge-sync`) は inventory に含めず (無改変) 参照のみとし、新設 component が additive に接続する設計とする。

## 前提条件
- P01 の `goal-spec.json` (checklist C1-C11) が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と既存 plugin envelope (`.claude-plugin/plugin.json`) の現状 (entry_points フィールド不在) を参照できる。
- 既存 knowledge-extractor (agent)・router.json/registry.json (既存 knowledge 基盤) を無改変で再利用する前提を共有している。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- placement_scope: C03はC02専用のskill scope。C05/C06/C07は複数flow共有または既存親route外のためplugin-rootへhoistする。
- requires_parent_scaffoldはC03→C02だけに適用する。C07はplugin-scaffold routeとして既存親不在問題を持たない。

## 成果物
- `component-inventory.json` (全11 component: C01,C08 sub-agent / C02,C09 skill / C04,C10 command / C03,C05,C06,C07,C11 script)。
- `envelope-draft/plugin.json` (既存 plugin.json を土台に entry_points を新設した manifest draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全11 componentがbuild_target非空・builder/build_kind整合・DAG非循環である。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces (8 種) の採否が明示されている。
- [ ] `envelope-draft/plugin.json` に既存3 skill/5 agent/2 commandと新設5 entry point (skill 2/agent 2/command 1) が設計されている。

### 受入例
inventoryが11実体でC08→C06→C02、C06→C05→C07、C07/C11→C09→C10の非循環DAGになる。

### 事前解決済み判断
scheduler helperはC02へ畳み、hookは新設しない。C07はplugin-rootへ置く。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C11 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。
