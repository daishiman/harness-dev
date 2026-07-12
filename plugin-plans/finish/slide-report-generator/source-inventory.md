# source-inventory — slide-report-generator (R2 分解指示・完全性 SSOT)

> 本ファイルは `plugin-dev-plan-architect` (R3) が component-inventory.json / 13 phase / index を生成する際の **R2 分解正本**。
> 既存 `presentation-slide-generator` (v8.4.2) の**全資産を1つ残らず**新 component / plugin-level surface へ対応づける（抜け漏れ = 平均回帰 = 禁止）。
> 実ソース: `~/dev/dev/ObsidianMemo/.claude/skills/presentation-slide-generator/`（architect は Read/Glob/Grep で実体も確認すること）。
> v8.4.2 時点の byte 正本 = `vendor-digest-manifest.json`（plan 同梱・195 files sha256 pin）。移植元 live tree が不在/更新された環境では、実ソースパスではなく manifest 照合で byte 検証する（live tree は比較基準ではない）。

---

## 0. 中核設計（不変原則）

1. **共通コア＋2モード**: 1 plugin 内で `output_mode = slide | report` を分岐。意匠/技術層は単一SSOT共有、コンテンツ意図層のみモード別。
2. **vendored Node engine（最重要・Python化禁止）**: 既存の Node.js/CJS 製レンダリング・画像・印刷エンジンは `vendor` surface として **byte 維持で携行**。skill/agent から `Bash(node *)` で起動する。stdlib script component へ書き換えない。
3. **slide↔report のコンテンツ区分**:
   - slide = 1スライド1メッセージ / chip強制 / 長文禁止(BP11-13) / 16:9 / 97 slideType
   - report = 読み物（文章多め可）/ セクション+段落 / 1項目1ビジュアル最適化 / HTMLレポート / 4 reportType
4. **抜け漏れ厳禁**: §5 の被覆チェックリストで既存全資産が component or surface に対応することを確認する。

---

## 1. 既存資産の全数（実測）

| 種別 | 数 | 移植先 |
|---|---|---|
| sub-agent (`agents/*.md`) | 13 | sub-agent component（§3 C04-C16） |
| references (`references/*.md`) | 42 (全名 = §1.1) | `references_config_assets` surface + report新規追加 |
| Node scripts (`scripts/*.js/.cjs`) | 30 | `vendor` surface（byte携行）+ report新規 |
| HTML templates (`scripts/templates/*.tpl`) | 118 | `vendor`/`references_config_assets` surface |
| schemas (`schemas/*.json`) | 7 (真 schema 4 + example fixture 3) | `schemas` surface (真 schema 4 本) + report-structure schema 新設で真 schema 計5。example fixture 3 本 (example.structure.json/example.v8.structure.json/example-full.structure.json) は `vendor/schemas-fixtures/` へ byte 携行 |
| assets (`assets/*`, d3-components, style genome) | 多数 | `references_config_assets`/`vendor` surface |
| feedback (`feedback/*.md`) | 数件 | `references_config_assets`（運用知見・移植任意） |

### 1.1 既存 references 42 本の名前正本（機械照合可能）

> upstream (移植元) references は数だけでは実装と突合できないため名前を列挙する。移植先 `plugins/slide-report-generator/references/*.md`（直下のみ・`feedback/` サブディレクトリは除外）は **46 本**で、うち report 新規 4 本（`report-types.md` / `report-writing-rules.md` / `report-visual-strategy.md` / `mermaid-integration.md`）を除いた **42 本**が既存移植分に一致する。すなわち `references/*.md − report新規4 == 下記42名` が成立する（差分が出たら本リストを先に更新＝spec-first）。実測 46 − 4 = 42（2026-07-05 Glob 実測。数の偽装なし）。

1. `agenda-navigation.md`
2. `ai-image-diagram-workflow.md`
3. `bp-classification.md`
4. `changelog.md`
5. `chart-types.md`
6. `color-strategy.md`
7. `composition-patterns.md`
8. `d3-integration.md`
9. `design-quality-guide.md`
10. `diagram-business.md`
11. `diagram-chart.md`
12. `diagram-comparison.md`
13. `diagram-cycle-flow.md`
14. `diagram-fabe.md`
15. `diagram-visual.md`
16. `full-image-deck-method.md`
17. `icons.md`
18. `image-format-guide.md`
19. `layout-visual.md`
20. `llm-script-separation.md`
21. `post-generation-evaluation.md`
22. `print-layout.md`
23. `resource-map.md`
24. `slide-components.md`
25. `slide-design-patterns.md`
26. `slide-interactions.md`
27. `slide-text-guidelines.md`
28. `slide-type-decision-tree.md`
29. `slide-types-basic.md`
30. `slide-types-extended.md`
31. `slide-types-overview.md`
32. `spec-registry.md`
33. `strategy.md`
34. `structure.md`
35. `style-genome-packaging.md`
36. `svg-design-spec.md`
37. `svg-diagram-primitives.md`
38. `theme-style.md`
39. `unit-system.md`
40. `v8-spec-fields.md`
41. `visual-hierarchy-principles.md`
42. `writing-rules.md`

> 照合コマンド例: `ls -1 plugins/slide-report-generator/references/*.md | xargs -n1 basename | grep -vxE 'report-types\.md|report-writing-rules\.md|report-visual-strategy\.md|mermaid-integration\.md'` の 42 行が上記と一致する。

---

## 2. 既存 7フェーズ ワークフロー（移植対象・mode 分岐で再編）

```
P1 hearing → P2 structure設計 → P2.5 仕様確定ゲート → [承認] → P3 HTML生成(従来LLM / 決定論 render-slide.cjs 二経路)
  → P3.2 AI画像図解生成(Codex Image2・明示時のみ・全面画像デッキ) → P3.5 UI品質検証
  → P3.6 生成後評価ゲート(PostToolUseフック自動・30種思考法) → P4 修正 → P5 シリーズ横断検証
```

report モードは P2→P2.5→P3→P3.6 を report 版に射影（P3.2 画像/Mermaid は visual-strategist 経由、P5 横断は任意）。

---

## 3. buildable component 分解（24〜28本目標・architect はこれを inventory 化）

> id は暫定。architect が採番し `entities_covered` で phase に紐づける。各 component は core 規律 quality_gates + harness_coverage を携帯。skill loop kind は feedback_contract.criteria(inner/outer) を purpose 由来で焼く。sub-agent/skill(run/assign)は prompt_layer:7layer。

### SKILLS（run・user-invocable orchestrator）

| id | name | skill_kind | 責務 | depends_on |
|---|---|---|---|---|
| C01 | run-slide-report-generate | run | **主オーケストレータ**。output_mode(slide/report)確定→structure→検証ゲート→生成(HTML/決定論/画像)→生成後評価 を駆動。goal-seek + feedback-contract | 全 worker agent + vendor engine |
| C02 | run-slide-report-modify | run | 既存成果物(slide deck / report)の修正。独立起動。P4相当 | C15(modifier agent) + vendor engine |
| C03 | run-cross-deck-review | run | シリーズ横断整合性検証(複数 deck/report)。独立起動。P5相当 | C16(cross-deck agent) |

### SUB-AGENTS（worker・independent context・既存13体を移植）

| id | name | 移植元 | 責務 | mode |
|---|---|---|---|---|
| C04 | hearing-facilitator | hearing-facilitator.md(P1) | ヒアリング。**mode確定(slide/report)+ 全面画像化ゲート(CONST_006) + report固有ヒアリング(reportType/読者/長さ/ビジュアル方針)** を追加 | both |
| C05 | structure-designer | structure-designer.md(P2) | slide 構成設計(1メッセージ分解・共通仕様セクション・structure.json) | slide |
| C06 | structure-validator | structure-validator.md(P2.5) | 仕様確定ゲート(validate-structure V-001〜043・phase-gate・spec-registry SR-ID 62) | slide(+report射影) |
| C07 | d3-diagram-designer | d3-diagram-designer.md | D3インタラクティブ図解設計 | both |
| C08 | data-visualizer | data-visualizer.md | データ可視化(グラフ・chart) | both |
| C09 | html-generator | html-generator.md(P3従来) | slide HTML生成(LLM経路) | slide |
| C10 | slide-renderer | slide-renderer.md(P3決定論) | 決定論経路 driver(render-slide.cjs 呼出) | slide |
| C11 | layout-optimizer | layout-optimizer.md | レイアウト最適化 | both |
| C12 | ui-quality-reviewer | ui-quality-reviewer.md(P3.5) | UI品質検証(テキスト切れ・改行・バランス S1-S26) | both |
| C13 | deck-evaluator | deck-evaluator.md(P3.6) | **生成後評価(30種思考法・mode-aware)**。slide=視覚崩れ/1メッセージ、report=可読性/図解適合/情報密度 の mode 別 rubric 次元で区分評価(30種コアは共有) | both |
| C14 | ai-image-diagram-producer | ai-image-diagram-producer.md(P3.2) | Codex Image2 全面画像/差替生成(build-image-prompts→generate-images-codex→build-deck-html→validate・PNG署名回収) | both |
| C15 | slide-report-modifier | slide-modifier.md(P4) | 既存成果物修正の worker(C02配下) | both |
| C16 | cross-deck-reviewer | cross-deck-reviewer.md(P5) | シリーズ横断検証 worker(3並列分析×4条件・C03配下) | both |

### SUB-AGENTS（report 新規）

| id | name | 責務 |
|---|---|---|
| C17 | report-structure-designer | report 構成設計。**4 reportType 骨格**(社内報告分析=要約→背景→現状分析→所見→次アクション / 顧客提案WP=課題→解決策→効果実績→導入ステップ→CTA / 技術ドキュメント=概要→前提→手順構造→注意点→参照 / 学習解説=問い→核心概念→図解理解→例応用→まとめ)で報告 structure(セクション+段落+1項目1ビジュアル指定)を設計。読み物粒度(文章多め可) |
| C18 | visual-strategist | 各セクションで **SVG図解 / Mermaid / Codex生成画像 を三択最適化**し配置(grid/zones/readingOrder/focalPoint)を決める意思決定層。固定比率なし。両モードに波及可 |
| C19 | report-composer | report HTML/prose 生成(LLM経路・文章多め・Markdown本文→HTML・visual-strategist 指定ビジュアルを埋込)。slide の html-generator に対応する report 版 |

### HOOKS

| id | name | event | 責務 |
|---|---|---|---|
| C20 | hook-postgen-eval | PostToolUse(Write\|Edit\|MultiEdit) | deck/report 中核ファイル(index.html/report.html/styles.css/scripts.js/structure.*/report-structure.*)書込を検知し **mode 判定して**生成後評価(deck-evaluator)の起動を促す(fail-soft・常に exit 0・非ブロッキング)。既存 deck-postgen-hook.js を移植(mode-aware化) |

### SLASH-COMMANDS

| id | name | 責務 |
|---|---|---|
| C21 | slide-report-generate | 生成を手動起動(--mode slide\|report) |
| C22 | slide-report-status | 進行状況/フェーズ確認(既存 workflow-manager.js 相当) |

### SCRIPTS（plugin-root Python・新規ガバナンス glue のみ・任意）

> 既存の検証ロジックは Node 製で `vendor` surface に携行し `Bash(node *)` 起動する（validate-structure.js / verify-slides.js / evaluate-deck.js / validate-ai-image-assets.js / validate-print.js 等）。
> **新規 Python script component は、harness 側で必要な最小の glue のみ**。候補（architect が要否判断）:

| id | name | 用途 |
|---|---|---|
| C23 | (任意) validate-output-mode.py | output_mode と reportType の値域を送信前検証する薄い stdlib gate（skill deterministic_checks 用） |

> ※ C23 は harness_coverage の deterministic_checks を Python で1本持たせたい場合のみ。無理に増やさない。既存 Node validator を vendor 経由で deterministic_checks に据えるのを既定とする。

---

## 4. plugin-level surfaces（component でなく index.plugin_meta / inventory surface）

| surface | required | 内容 |
|---|---|---|
| manifest | true | `.claude-plugin/plugin.json`（name==slide-report-generator・folder一致・no placeholder・validate_plugin） |
| marketplace | true | xl-skills personal marketplace 既定・policy(installation/authentication/category=Productivity)・cachebuster |
| composition | true | `plugin-composition.yaml`（skill/agent/command/hook の合成宣言） |
| harness_eval | true | `EVALS.json`（mechanical + llm_eval。slide/report 両モードの受入を配線） |
| schemas | true | structure.schema.json(移植) + **report-structure.schema.json(新設)** + image-deck-plan.schema.json + evaluation-report.schema.json + image-asset-manifest.schema.json。structure と report-structure は共通コア(nodes/edges/groups/theme/aiVisual)を共有 |
| references_config_assets | true | 既存 42 references + **report新規 references**(report-types・report-writing-rules・report-visual-strategy・mermaid-integration) + 118 templates + pagination + style-genome + d3-components |
| vendor | true | **Node engine 一式を byte 携行**: render-slide.cjs / template-engine.cjs / style-builder.cjs / svg-builder.cjs / d3-bootstrap.cjs / 画像チェーン(build-image-prompts.js/generate-images-codex.js/build-deck-html.js/build-image-manifest.js/build-single-html.js/convert-to-webp.js/validate-ai-image-assets.js/evaluate-image-consistency.js) / 検証(validate-structure.js/verify-slides.js/evaluate-deck.js/validate-print.js/validate-d3.js/sync-checker.js/precheck-layout.js/phase-gate.js/cross-deck-consistency.js/check-consistency.js/auto-linebreak.js/layout-calculator.js) / hooks/deck-postgen-hook.js の移植元 / package.json / node_modules(要再install) / **report新規 Node**(render-report.js / mermaid-render.js) |
| mcp_app_connector | false | omitted_reason: 画像生成は `codex exec`(Bash)経由。MCP/app connector を新設しない |
| notion_config | false | omitted_reason: Notion DB を読み書きしない(ローカルHTML出力のみ) |

---

## 5. 被覆チェックリスト（既存全資産 → 移植先。抜け漏れ 0 を保証）

- [ ] 13 agents → C04-C16（1:1）
- [ ] structure.schema.json / image-deck-plan.schema.json / evaluation-report.schema.json / image-asset-manifest.schema.json → schemas surface
- [ ] 30 Node scripts → vendor surface（byte携行・byte 一致の比較基準=`vendor-digest-manifest.json`）
- [ ] 118 templates → references_config_assets/vendor surface
- [ ] 42 references → references_config_assets surface
- [ ] style-genome-kanagawa-comic-diagram.json / d3-components / pagination(.html/.css/.js) → references_config_assets/vendor
- [ ] Codex Image2 チェーン(build-image-prompts→generate-images-codex→build-deck-html→validate-ai-image-assets・PNG署名`89504e47`回収・style genome) → C14 + vendor
- [ ] 30種思考法 生成後評価ゲート(evaluate-deck.js + deck-evaluator.md + post-generation-evaluation.md + evaluation-report.schema.json + deck-postgen-hook.js) → C13 + C20 + vendor + schemas
- [ ] A4印刷/letterbox/box-shadow・グラデ文字 印刷対策 → vendor(print-styles.css/style-builder.cjs) + references(print-layout.md)
- [ ] GASデプロイ(build-single-html/build-image-manifest/gas-deploy-guide) → vendor + references
- [ ] 決定論レンダラ(render-slide.cjs/template-engine/style-builder/svg-builder + 24テンプレ) → C10 driver + vendor
- [ ] spec-registry(SR-ID 62)/slide-type-decision-tree(DT 98)/unit-system/bp-classification → references + C06 gate
- [ ] 16:9/Kanagawa/最小1.4rem/GSAP/FontAwesome/WCAG → 共通コア(vendor theme + references/theme-style,design-quality-guide)

### report 新規（既存に無い純増）
- [ ] report-structure schema(4 reportType) → schemas + C17
- [ ] visual-strategist(三択最適化) → C18
- [ ] Mermaid統合 → vendor(mermaid-render.js) + references(mermaid-integration.md) + C18
- [ ] report HTMLレンダラ/composer → C19 + vendor(render-report.js)
- [ ] report content-regime(読み物・BP緩和) → references(report-writing-rules.md) + C13 report rubric
- [ ] output_mode 分岐 → C01 orchestrator + C04 hearing

---

## 6. architect への指示要点

1. `component-inventory.json` を上記 §3 で生成。各 component は golden例(`examples/sample-plan/component-inventory.json`)の kind別構造キーに厳密準拠。
2. **skill(C01/C02/C03)** は skill-brief base 14 + 条件付き(goal/purpose_background/checklist/responsibilities) + combinators + goal_seek + feedback_contract(criteria は各 skill の goal/checklist 由来 = purpose-acceptance・汎用ゲート言い換え禁止) + prompt_layer:7layer。
3. **sub-agent(C04-C19)** は name/description/tools(最小権限)/independent_context:true/responsibility_anchor/prompt_layer:7layer。
4. **hook(C20)** は event/matcher/exit_semantics/settings_wiring/fail_closed。**command(C21/C22)** は name/description/argument-hint/allowed-tools/disable-model-invocation。
5. depends_on DAG を非循環に（C01→workers、C02→C15、C03→C16、workers→vendor は surface 参照で表現）。
6. plugin-level surfaces を §4 で inventory に記録（vendor:true を必ず立て、Python化しない旨を derivation に明記）。
7. index.plugin_meta に manifest/marketplace/ci/feedback_deploy(core) + pkg_contract/governance/ssot_dedup(条件付き・N/A可) を焼く。
8. 13 phase ファイルは lifecycle 軸（要件→…→リリース）。各 phase の entities_covered で §3 component を紐づけ、§5 本文8節の床を満たす。
9. envelope-draft/plugin.json に貼れる manifest ドラフト（name==slide-report-generator）を emit。
10. handoff-run-plugin-dev-plan.json に component 由来 routes[]（skill→run-skill-create / agent・command・hook→run-build-skill / vendor script→plugin-scaffold or 親skill畳み込み）を emit。
