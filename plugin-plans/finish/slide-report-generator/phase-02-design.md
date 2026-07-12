---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind へ写像し、N=23 実体(3 skill / 16 sub-agent / 1 hook / 2 slash-command / 1 script)を `component-inventory.json` へ分解する。既存全資産を漏れなく component か plugin-level surface(manifest/composition/harness_eval/schemas/references_config_assets/vendor/mcp_app_connector/notion_config)へ写像し、`envelope-draft/plugin.json` の manifest draft を設計する owner フェーズ。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。skill 偏重を避けるため 5 種の component_kind を必ず検討した上で N=23 実体へ分解し、既存 Node engine は `vendor` surface として byte 携行する(Python 化しない)。意匠/技術層は vendor + references + schemas の単一 SSOT で共有し、コンテンツ意図層のみ output_mode で分岐する。build_target/depends_on は inventory のみが保持し、phase は id 参照だけで紐づく(正規化)。

## 前提条件
- P01 の `goal-spec.json` と `source-inventory.md`(§3 分解案・§4 surface・§5 被覆)が確定している。
- 5 種の component_kind の写像規約(`references/component-domain.md`)と envelope 物理契約を参照できる。
- 同一 kind の複数実体(skill×3 / sub-agent×16 / slash-command×2)はそれぞれ独立 component として扱う前提を共有している。

## ドメイン知識
- vendor 携行の不変条件: Node/CJS 製エンジン(render-slide.cjs/template-engine.cjs/style-builder.cjs/svg-builder.cjs/画像チェーン/検証 js/118 templates/print + report 新規 render-report.js/mermaid-render.js)は byte 維持で vendor surface に置き stdlib script へ書き換えない。
- 共有 script の hoist: 複数 skill が使う validate-output-mode.py は placement_scope=plugin-root で plugins/slide-report-generator/scripts/ へ hoist する(install 携帯性)。
- 共通コア/2 モードの境界: 意匠/技術(vendor+schemas 共通コア=nodes/edges/groups/theme/aiVisual)は共有、コンテンツ意図(slide=1メッセージ vs report=読み物)のみ mode 別 rubric で分岐。

## 成果物
- `component-inventory.json`(build 軸の唯一 SSOT・全 23 component + 8 plugin-level surface)。
- `envelope-draft/plugin.json`(manifest draft・name==slide-report-generator)。

## スコープ外
- 設計の合否判定(P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出(P04 へ委譲)。
- 実体の生成(P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 23 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、8 plugin_level_surfaces の採否(vendor:true / mcp_app_connector:false / notion_config:false)が明示されている。
- [ ] vendor surface に「Node engine は byte 携行・Python 化しない」旨が derivation として記録されている。
- [ ] source-inventory §5 の既存全資産が component or surface へ 1 つ残らず対応づいている(抜け漏れ 0)。
- [ ] `envelope-draft/plugin.json` に manifest draft(entry_points / hooks 配線 / distribution)が設計されている。

## 参照情報
- `source-inventory.md` §3(component 分解)/ §4(surface)/ §5(被覆)。
- `references/component-domain.md` / `references/io-contract.md`。
- 対象 component C01-C23(`component-inventory.json`)、後続 P03(design-gate)。
