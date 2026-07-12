# source-inventory — slide-report-generator (R2 分解指示・完全性 SSOT)

> 本ファイルは `plugin-dev-plan-architect` (R3) が component-inventory.json / 13 phase / index を生成する際の **R2 分解正本**。
> 既存 `presentation-slide-generator` (v8.4.2) の**全資産を1つ残らず**新 component / plugin-level surface へ対応づける（抜け漏れ = 平均回帰 = 禁止）。
> 実ソース: `~/dev/dev/ObsidianMemo/.claude/skills/presentation-slide-generator/`（architect は Read/Glob/Grep で実体も確認すること）。
> v8.4.2 時点の byte 正本 = `vendor-digest-manifest.json`（plan 同梱・191 files sha256 pin）。真 schema 4本は plugin-root `schemas/` の live SSOT とし、vendor parity は example fixtures + README のみを固定する。移植元 live tree が不在/更新された環境では、実ソースパスではなく manifest 照合で byte 検証する（live tree は比較基準ではない）。

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
| C17 | report-structure-designer | report 構成設計。**4 reportType 骨格** + **節内論理展開(本質課題→解決策→活用=section.narrative)** + **block構造(表/コード/番号リスト/小見出し/キーポイント強調 + 定義リスト/脚注引用/タスクリスト)の設計** + **文書アーク(meta.throughLine)と節間接続(section.transition)と section.role 判定の owner** + 1項目1ビジュアルの意味的スロット割当(幾何配置は C18)。節順序・節内部論理に加え文書全体の弧を強制し羅列退化を防ぐ。読み物粒度(文章多め可) |
| C18 | visual-strategist | 各セクションで **SVG図解 / Mermaid / Codex生成画像 を三択最適化**し**幾何配置(正規化 field {grid/zones/emphasisZone/readingOrder/focalPoint} = render-report.js が反映する live placement)の唯一 owner**として決める意思決定層。emphasisZone(旧 emphasis 改名・inline highlight との字面衝突回避)。固定比率なし。両モードに波及可 |
| C19 | report-composer | report HTML/prose 生成 + **決定論 render-report.js の著者責務(block レンダラ[表→table/コード→pre-code/番号リスト→ol/小見出し/key-point/stat-tile/callout/blockquote + 定義リスト/脚注引用/タスクリスト] + inline highlight[色付き強調・色覚非依存の第2チャネル weight/underline] + placement[emphasisZone/readingOrder] 反映 + throughLine/transition render を additive 実装) + report 読書 CSS(report.css)新設 + mermaid 依存の package.json additive**。render-report.js/mermaid-render.js は tests/test-render-report.js/test-mermaid-render.js で coverage(tests_min>=80)。slide の html-generator に対応する report 版 |
| C24 | report-quality-reviewer | report 品質検証(RQ1-20 = 読み物文体/段落密度/1項目1ビジュアル/reportType 骨格順守) + **積極評価 RQ21-(論理展開 本質課題→解決→活用 の成立/節間の論理接続・流れの成立[through-line]/内容が要求する範囲での block 適合[多様性 < 適合性]/強調の効きと過剰でなさ・色覚非依存/意味的配置/reportType 横断要素の充足/見出し整形)**。減点型と積極評価の双方向で『羅列でも破綻ゼロなら PASS』も『構造過剰でも多様性ありなら PASS』も塞ぐ。slide の ui-quality-reviewer 対称(post-plan Tier2 追加) |

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
| C23 | validate-output-mode.py | output_mode と reportType の値域を送信前検証する薄い stdlib gate（skill deterministic_checks 用・+--preflight 環境検査） |
| C25 | validate-report-visual.py | report 決定論視覚ゲート(section 構造/1項目1ビジュアル/段落密度/印刷 + **本 update: block型多様性/narrative 非空/highlight 表現/表・コード・番号リストの正 HTML 化 + 二重充填・強調過多の上限** + **本再検証: (a)reportType別必須横断要素の存在/(b)placement.grid/zones の render live 反映[DOM 位置 vs placement 指定一致]/(c)長尺 throughLine 非空/(d)narrative 非空を section.role∈{analysis,argument}条件に限定/(e)block多様性の決定論閾値/(f)doc-level highlight 密度上限/(g)inline highlight の非色属性 weight/underline 存在/(h)report読書CSS class 出力の存在**)。slide の verify-slides.js/validate-print.js に対称(post-plan Tier2 追加) |

> ※ C23/C25 は harness glue を Python で持つ buildable script component(2本)。既存 Node validator は vendor 経由で deterministic_checks に据えるのを既定とし、Python は harness 側の最小 glue のみに留める。

---

## 4. plugin-level surfaces（component でなく index.plugin_meta / inventory surface）

| surface | required | 内容 |
|---|---|---|
| manifest | true | `.claude-plugin/plugin.json`（name==slide-report-generator・folder一致・no placeholder・validate_plugin） |
| marketplace | true | xl-skills personal marketplace 既定・policy(installation/authentication/category=Productivity)・cachebuster |
| composition | true | `plugin-composition.yaml`（skill/agent/command/hook の合成宣言） |
| harness_eval | true | `EVALS.json`（mechanical + llm_eval。slide/report 両モードの受入を配線） |
| schemas | true | 真 schema 5本は **plugin-root schemas/ が唯一 live SSOT**: structure.schema.json(移植) + **report-structure.schema.json(新設・1.1.0→1.2.0 additive)** + image-deck-plan.schema.json + evaluation-report.schema.json + image-asset-manifest.schema.json。structure と report-structure は共通コア(nodes/edges/groups/theme/aiVisual)を共有。真 schema は vendor-digest 非 pin(live・additive-bump 可能)、vendor/schemas-fixtures は example fixture3本+README のみ byte-frozen(Grp I/A4-F4) |
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

### report 構造化改善（C9-C15・本 update additive・『羅列→構造化された読み物』）
> post-plan の report 品質補正(C24/C25)確定後、report 出力を情報の羅列から構造化された読み物へ引き上げる additive 改善。in-scope=C17/C18/C19/C24/C25 + schemas(1.1.0→1.2.0)/references。新規 component は増やさない(no-split)。本再検証(30思考法)で第7根因『横断的読書体験の未評価』を発掘し C15(節間フロー) + C9-C14 additive 次元(schema 1.2.0)へ拡張した。

- [ ] C9 節内論理展開(本質課題→解決→活用=section.narrative・終端 role で弧保存) → schemas(report-structure 1.2.0) + C17 設計 + references(report-narrative-logic.md 新設)
- [ ] C10 block構造(段落/markdown表/コードブロック/番号リスト/小見出し/key-point/stat-tile/callout/blockquote + 1.2.0 定義リスト/脚注引用/タスクリスト) + 読書CSS(report.css) → schemas(section.body[]) + C19(render-report.js block レンダラ + report.css) + C25(pre-render gate: block多様性/新block/読書CSS class 被覆)
- [ ] C11 要点の色付き強調(inline highlight + key-point/stat-tile・意匠 accent 流用・過剰抑制・色覚非依存の第2チャネル weight/underline) → schemas(highlight トークン) + C19(render) + references(report-writing-rules.md 密度上限追補) + C25(非色属性の機械検査)
- [ ] C12 図解の意味的配置(正規化 placement {grid/zones/emphasisZone/readingOrder/focalPoint} の live 化) → C18(幾何配置 owner) + C19(render-report.js 反映) + references(report-visual-strategy.md 追補) + C25(placement live 反映=DOM 位置 vs 指定一致の機械検査)
- [ ] C13 積極評価型品質ゲート(羅列/構造過剰の双方向を塞ぐ) → C24(RQ21- 積極[through-line/色覚非依存/reportType横断/多様性<適合性]+負次元) + C25(block多様性/narrative非空[role条件]/highlight・非色属性/二重充填・強調過多/reportType別横断要素/placement live/throughLine非空の機械チェック) + references(report-quality-checklist.md 追補・skill-level)
- [ ] C14 本質的に含むべき横断要素の開いた読書体験カタログ(共通=要約/テイクアウェイ/次アクション/根拠出典/リスク/TL;DR/図表番号キャプション/長尺TOC・相互参照/callout + 文書メタ[version/updatedDate/readingTime/audience] + per-section recap + 表現機構[定義リスト/脚注引用/タスクリスト] + reportType別=技術ドキュメント[前提/用語/手順/既知問題]・学習解説[目標/要点/演習]) → references(report-narrative-logic.md) + 4 reportType 骨格 additive + C25(reportType別横断要素の存在検出)
- [ ] C15 節間フロー(文書アーク meta.throughLine[冒頭=本質課題→本論=解決→結=活用] + 節間接続 section.transition + section.role) → schemas(report-structure 1.2.0) + C17(throughLine/transition/section.role 設計 owner) + C24(through-line 積極評価) + C25(長尺 throughLine 非空機械検査)
- [ ] schema 配置一本化(Grp I): 真 schema 4本 + report-structure は plugin-root schemas/ が唯一 live SSOT・vendor/schemas-fixtures は example fixture3+README のみ(vendor-digest 191 files pin=従来 195 から真 schema 4本を非 pin 化で減算)
- [ ] baseline 潜在 gate 赤の是正: C24/C25 の phase entities_covered 割当 + handoff route + manifest entry_points(report-quality-reviewer) + C01 depends_on/deterministic_checks/feedback_contract 結線 + requires_surfaces/change_surface の機械エッジ化

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
