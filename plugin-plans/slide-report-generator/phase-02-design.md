---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind へ写像し、N=25 実体(3 skill / 17 sub-agent / 1 hook / 2 slash-command / 2 script)を `component-inventory.json` へ分解する。既存全資産を漏れなく component か plugin-level surface(manifest/composition/harness_eval/schemas/references_config_assets/vendor/mcp_app_connector/notion_config)へ写像し、`envelope-draft/plugin.json` の manifest draft を設計する owner フェーズ。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。skill 偏重を避けるため 5 種の component_kind を必ず検討した上で N=25 実体へ分解し、既存 Node engine は `vendor` surface として byte 携行する(Python 化しない)。意匠/技術層は vendor + references + schemas の単一 SSOT で共有し、コンテンツ意図層のみ output_mode で分岐する。build_target/depends_on は inventory のみが保持し、phase は id 参照だけで紐づく(正規化)。

## 前提条件
- P01 の `goal-spec.json` と `source-inventory.md`(§3 分解案・§4 surface・§5 被覆)が確定している。
- 5 種の component_kind の写像規約(`references/component-domain.md`)と envelope 物理契約を参照できる。
- 同一 kind の複数実体(skill×3 / sub-agent×17 / slash-command×2 / script×2)はそれぞれ独立 component として扱う前提を共有している。

## ドメイン知識
- vendor 携行の不変条件: 初回whole-tree取込後、upstream非改変fileはsha256 pin、明示local overlayはmanifestのowner付きsemantic contract + tests/goldensで管理する。未宣言pin不一致を許可せず、stdlib scriptへ書き換えない。
- 共有 script の hoist: 複数 skill が使う validate-output-mode.py は placement_scope=plugin-root で plugins/slide-report-generator/scripts/ へ hoist する(install 携帯性)。
- 共通コア/2 モードの境界: 意匠/技術(vendor+schemas 共通コア=nodes/edges/groups/theme/aiVisual)は共有、コンテンツ意図(slide=1メッセージ vs report=読み物)のみ mode 別 rubric で分岐。

## 成果物
- `component-inventory.json`(build 軸の唯一 SSOT・全 25 component + 8 plugin-level surface)。
- `envelope-draft/plugin.json`(manifest draft・name==slide-report-generator)。

### report 構造化設計 (C9-C15・additive)

本 update の改善は既存 report component と 2 surface の additive 強化として設計する (新規 buildable component を増やさない・no-split)。schema/renderer は二層分離: **shape は schema/lint/renderer で機械凍結、意味の適合は C24 evaluator + report-narrative-logic.md に委ねる** (Goodhart 回避)。本再検証では読み物としての横断的読書体験の次元 (第7根因由来) を schema 1.2.0 additive + C15 で追加する。

- **schema `report-structure.schema.json` 1.0.0 → 1.1.0 (additive・後方互換)**:
  - `section.narrative`: `{essence(本質課題), approach(解決策), leverage(活用/含意)}` または `logic:[{role: claim|evidence|implication|action}]`。節内論理展開を宣言的に持たせ、reportType 骨格の節順序だけでなく節内部の論理構造を強制する (C9)。
  - `section.body[]` block 型: `{type: paragraph|table|code|ordered-list|bullet-list|subheading|key-point|stat-tile, ...}`。既存 `paragraphs[]` (string 配列) は温存し `body[]` を optional additive で並置。表/コード/番号リスト/小見出し/キーポイントを第一級で表現する (C10)。
  - inline highlight トークン + `key-point`/`stat-tile` block: 要点の色付き強調を意匠 accent (--section-accent) で render。新規配色トークンは足さない (C11)。
  - `placement`(既存の grid/zones/emphasis/focalPoint) を **live 化**: render-report.js が反映する契約を明記 (現状デッドフィールド → C12)。
- **schema `report-structure.schema.json` 1.1.0 → 1.2.0 (additive・1.1.0 を全温存し後方互換)**:
  - `section.role`: enum {analysis, argument, reference, procedure, summary}。narrative を role 条件付き optional 化し、narrative 必須は role∈{analysis,argument} のみ、reference/procedure/summary は narrative 不要で category error を回避する (未指定既定は analysis)。C17 が role 判定 owner (Grp F: MD-M1/A2-F7)。
  - `meta.throughLine`: 文書全体の通し筋 (冒頭=本質課題→本論=解決→結=活用のアーク) + 任意 `section.transition` (次節への橋渡し1文)。節間フローを宣言的に持たせ節を弧で連結する (C15・Grp C: MD-H2)。
  - `meta` 文書メタクラスタ: version / updatedDate / readingTime (本文語数から決定論導出) / audience (対象読者)(Grp E: MD-M8)。
  - `section.body[]` block 型 additive: definition-list (用語定義 term↔def) / footnote+citation (末尾 reference-list 自動生成) / task-list (次アクション `- [ ]`)。details/collapsible は任意 opt-in additive (Grp E: MD-M7)。
  - inline highlight の非色冗長化: highlight トークンに font-weight/underline/border 等の第2チャネル属性を必須付与 (色単一チャネル脱却=色覚アクセシビリティ・Grp E: MD-M3)。
  - placement field 正規化: producer(C18)/consumer(C19)/schema で field 集合を {grid, zones, emphasisZone, readingOrder, focalPoint} に統一。旧 emphasis は inline highlight と字面衝突するため emphasisZone へ改名 (1.1.0 emphasis は alias 後方互換残置)、readingOrder を consumer 側にも配線 (Grp H: A4-F5)。
  - narrative 語彙の弧保存: 第1語彙(essence/approach/leverage)/第2語彙(claim/evidence/implication/action) いずれも『活用/含意/行動』相当の終端 role を必須とし本質課題→解決→活用の弧を全 reportType で保存する。reportType→narrative binding は report-narrative-logic.md が正本 (Grp F: A2-F7)。
- **renderer 拡張 (1.2.0・C19 著者責務)**: render-report.js に定義リスト/脚注/タスクリスト block・inline highlight 第2チャネル・emphasisZone/readingOrder 反映・throughLine/transition render を additive 実装し、read 用の report 読書 CSS (block 装飾/reading measure ~65-75ch/縦リズム/section spacing) を拡張する。**周回2 是正 (R4 MEDIUM)**: report 読書 CSS の正本責務は render-report.js の buildReportCss() (inline `<style>` 出力) であり、独立ファイル `vendor/assets/report.css` への分離は将来オプション(必須生成物ではない)。
- **placement 配置一本化 (Grp I/A4-F4)**: 真 schema 4本(structure/image-deck-plan/evaluation-report/image-asset-manifest)+新設 report-structure は plugin-root schemas/ が唯一 live SSOT。vendor/schemas-fixtures は example fixture 3本+README のみ (vendor-digest 191 files pin=従来 195 から真 schema 4本を非 pin 化で減算)。
- **renderer `vendor/scripts/render-report.js` (C19 著者責務・manifest管理local overlay)**: 既存 `renderParagraphs`/`inlineMd` を additive 拡張し、block レンダラ (table→`<table>`・fenced code→`<pre><code>`・`1.`→`<ol>`・小見出し・key-point ハイライトボックス・stat-tile) + inline highlight + placement.grid/zones 反映を実装する。semantic contract + `npm test` coverage 80%以上で検証する。
- **references (S-REFERENCES)**: `report-narrative-logic.md` を新設し、節内論理展開 (本質課題→解決→活用 / claim-evidence-implication) の語彙と「本質的に含むべき横断要素」カタログ (エグゼクティブ要約/キーテイクアウェイ/意思決定・次アクション/根拠・出典/リスク・留保/TL;DR) の正本にする。`report-writing-rules.md`(block content-regime・強調トークン規律)・`report-visual-strategy.md`(placement 意味的配置)・`report-quality-checklist.md`(積極評価 RQ21-) を additive 追補する (C13/C14)。
- **reportType 骨格の additive**: 既存 4 骨格の節順序を壊さず、各型に narrative と横断要素を適合させる (internal-analysis も現状記述どまりでなく本質課題→示唆→次アクションの論理を通す)。
- **経路非対称の明文化 (MD-I3・backlog 軽微)**: report は決定論 render-report.js の単一経路 (LLM 自由作文経路を持たない)、slide は LLM(html-generator C09) + 決定論(slide-renderer C10) の 2 経路。report content 意図層の品質は schema 1.2.0 + C24/C25 の二層で担保し、slide の 2 経路対称を report に強制しない (report の読み物粒度は decode より compose 寄りゆえ単一 compose 経路で足りる・非対称は設計意図)。

### report UI/UX 設計 (C16-C19・additive)

本更新 (第3次: report-uiux-layout-improvement) は『読み物の中身』(C9-C15) に続き『読み物の器 = 画面表示 UI/UX』を additive に設計する。新規 buildable component は増やさず、レイアウト/TOC/scrollspy/タイポ = C19(render-report.js の buildReportCss() inline `<style>` 出力を正本責務とする著者責務。独立ファイル report.css への分離は将来オプション)、本質図解(essence-visual)/図種写像 設計 = C18 visual-strategist、積極評価 = C24、決定論検査 = C25 の強化で実現する (no-split)。

- **screen/print 幅二層化 (C16・C19 owner)**: 現状 `buildReportCss()` は `--report-width: 190mm` を `.report { max-width: var(--report-width) }` として screen にも流用し、広画面で両サイド余白が本文幅を超える。screen 用に reading measure 基準の本文カラム + sidebar (TOC 等) を含む grid レイアウトを新設し、`@media print` ブロックで従来 190mm/A4 レイアウトを温存する (print 退行なし)。外部 CDN/ライブラリ依存なしの self-contained CSS とする。
- **sticky sidebar TOC + scrollspy (C17・C19 owner)**: 現状 `.report-toc` (冒頭静的2カラム) を sticky 化し、`IntersectionObserver` ベースの self-contained JS で現在位置・読了進捗・下部スクロール時の常時可視性を実装する。print では JS を無効化し無害。狭画面 (`@media (max-width: 900px)`) は本文を1カラム化しつつ、TOC を details/summary で折り畳める sticky navigation として維持する。
- **タイポグラフィ/密度再調整 (C18・C19 owner)**: `--fs-title: calc(2.6rem * var(--font-scale))` 等、狭カラム相対で過大な見出しスケールと縦リズム/section spacing を調整する。意匠 SSOT (Kanagawa 配色・フォントファミリ `--font-base`/`--font-mono`) は無改変とし、スケール比・spacing 変数 (`--space-*`) のみを調整する。
- **本質図解 (essence-visual) 第一級化 (C19要件・C18 visual-strategist owner)**: schema は 1.2.0 のまま (essence-visual は既存 role/visual.kind を使い schema bump 不要・第3次UIは render CSS のみで schema 非依存)。C18 visual-strategist が形式三択 (`visual.kind`: svg|mermaid|codex-image|none) の決定に先立って節の論理構造→図種の写像を行い、論理構造を展開する実質節 (role∈{分析/主張/課題/解決/所見/影響}=_ESSENCE_REQUIRED_ROLES) へ非none visual (visual.kind!=none) を必ず1枚割り当てる owner になる (写像規律=reference report-visual-strategy.md §0.5.1・visual-strategist VCONST_000。要件 id と component id が字面一致するが指す対象は異なる点に注意: 要件 C19 の owner は component C18)。図解すべき論理節での visual 省略 (『なんとなく表』) または本文主張と乖離した装飾目的の図解は C24 が負値評価する。
- **積極評価の拡張 (C24)**: RQ 次元へ「ナビゲーション成立 (sticky TOC+scrollspy でいま文書のどこを読んでいるか常時把握でき任意の節へ1クリックで戻れるか)」「読み物としての密度バランス (screen で本文と余白の比率・見出し階層の視覚差が適正か)」「図解適合 (本文の主張と本質図解(essence-visual)の一致・図だけ見て節の要旨が掴めるか)」を追加する。**周回2 追加 (R4 HIGH是正)**: 「print/狭画面 degrade の成立 (print で従来 190mm/A4 読了体験が退行しない・狭画面でインライン TOC が探索性を損なわず成立するか)」を追加する。
- **決定論検査の拡張 (C25)**: (i) screen 用レイアウト CSS (サイドバー用 grid/reading measure/breakpoint に相当する出力) の存在、(ii) TOC nav 要素 + scrollspy スクリプトの出力存在、(iii) essence-visual カバレッジ (論理節=role∈{分析/主張/課題/解決/所見/影響} が非none visual=visual.kind!=none を1枚持つ) の機械検査、を行う。意味の適合 (密度バランスが適正か/図が本文の論理構造を一目化するか) は C24 に委ねる二層分離 (Goodhart 回避)。**周回2 追加 (R4 HIGH是正)**: 従来の shape 検査が screen 新挙動の「存在」検査に留まり print/狭画面を検査しない穴があったため、(iv) `@media print` ブロックの出力存在 (従来 190mm レイアウト温存の検査可能表現)、(v) print 時の sidebar TOC 非適用/scrollspy 無効化の出力存在 (`@media print` 内での nav 非表示 or JS の print ガード)、(vi) 狭画面 breakpoint (`@media (max-width: ...)` 系) の出力存在、を追加する。degrade が読みやすいかの意味適合は C24 に残す (二層分離を維持)。
- **意匠/技術 SSOT 無改変**: Kanagawa 配色・16:9・最小1.4rem・GSAP・印刷CSS 等は無改変。screen レイアウトは外部依存なし (self-contained CSS/JS) でローカル `file://` 開封でも成立する。
- **computed layout 契約**: report screen専用scaleで本文16-18px/line-height比1.6-1.8/title-body比<=2.2、本文幅40em、sidebar 16rem、全体上限1160pxを満たす。cardは最小28rem相当+`minmax()`+`overflow-wrap`、899/900/901px境界を検査する。
- **navigation lifecycle**: 初期hash/TOC click/manual scroll/font ready/historyでtargetと`aria-current=location`を一致させ、`beforeprint`停止後は`afterprint`でidempotent復帰する。
- **essence-visual評価入力**: C24は`report-structure.json + wide/narrow/print render + metrics/navigation log`をbundleで受け、本質図解(essence-visual)の意味適合と図解不足の両方を評価する。

### 図解移植設計 (C20-C28・additive)

本更新 (第4次: diagram-design-migration) は既存 component の additive 強化として設計する (新規 buildable component を増やさない・no-split)。新規物は全て plugin-root 側 (references_config_assets 配下) に置き vendor/ は無改変。

- **C20 スタイル契約 SSOT 化**: 新設 `diagram-style-tokens.md` にセマンティックロール表 (paper/ink/rule/accent/link 等) を定義するが、値は `svg-kit.cjs` TOKENS / `style-builder.cjs` SPEC の既存 Kanagawa 値を索引参照するのみで新規に定義しない (二重 SSOT 回避・`lint-contract-drift.py` の G チェックで整合担保)。owner=C18 visual-strategist(consumes_references)。
- **C21 数値化リファレンス**: 既存 `diagram-layout-contract.md` (D0-D13 憲法) を augmented し、4px グリッド・複雑度予算・コネクタ5原則・focal rule・annotation 文法を追補する。owner consumers=C07(d3-diagram-designer)/C18。
- **C22 型統一対応表**: 新設 `diagram-type-crosswalk.md` に 38決定論/29 CSS/128 tpl の対応表 + 選択ガイドを置く。`ref-diagram-system` SKILL.md §2 ルーティング表・`diagram-type-catalog.md` は値を複製せず本表へ相互参照する (索引は値を持たない思想を維持)。owner=C07/C18 consumes_references。
- **C23 叩き台テンプレート**: plugin-root `assets/diagram-templates/*.html` を新設 (vendor integrity対象外のplugin-root live領域)。C09 html-generator が「テンプレートをコピーして図解本体だけ書く」フローの起点として consume する。
- **C24(要件) プロンプト配線修復**: 図解関連 reference を resource-map.md(skill私有分の read_when[])・workflow-manifest.json resources[]・各 prompt(`skills/run-slide-report-generate/prompts/R*.md`) Layer 6 参照表へ明記する (plugin-root references は lint-reference-attribution.py 対象外=G6 のため配線漏れは目視+本チェックリストで担保)。
- **C25(要件) CSS/HTML 図解 lint 新設**: `validate-svg-diagram.py` (governance glue・非 buildable) を拡張し D14 以降のコードで CSS/HTML 図解 (`<svg>` 以外) の 4px グリッド・複雑度予算・accent 個数・コネクタ幾何 (斜め線検出) を機械検証する。テンプレート自体 (`assets/diagram-templates/*.html`) も lint 対象にする。
- **C26 ゴールデン実例**: C09/C19 の skill-private `examples/` 配下に主要図解型の「入力→完成HTML」実例ペアを追加し type reference 末尾からリンクする (few-shot + 回帰基準線)。
- **C27 不足図解型**: diagram-design の27型と既存型を突合し欠落型 (quadrant/radar/venn/org-chart/loop等) を LLM 手書き経路 (references/diagram-*.md) へ additive 追加する。既存 `var(--x, fallback)` トークン方式で記述し hex 直書きしない (vendor 決定論経路は無改変)。
- **C28 溶け込み契約 (R9・最重要)**: 3 サブ契約を以下へ機械的に割り当てる:
  - ①配置契約: C18 visual-strategist が型ごとの配置規約 (C21 数値化リファレンス連動) を配置決定と型選定に接続する owner。
  - ②重複禁止契約: 図解内容と本文の重複禁止 (図が語ることを本文で繰り返さない・逆も禁止)。slide 側は C12 ui-quality-reviewer 新規チェック項目 S27 (1スライド1メッセージとの整合) が積極評価、report 側は C24 report-quality-reviewer が積極評価、機械層は C25 validate-report-visual.py の文字列重複検出 (図キャプション/隣接本文の重複語検出) が担う二層分離。
  - ③文脈適合契約: 図解の密度/サイズ/トーンが周囲コンテンツと調和すること。slide 側は C12 の S28(密度/サイズ/トーン)・S29(assets/diagram-templates(C23)埋め込み用骨格準拠)、report 側は C24 の積極評価 + C19 render-report.js の占有率 render(C21 許容レンジ内)、機械層は C25 の図解占有率(node面積/section面積比)範囲検査が担う。
  - テンプレート骨格 (C23) は「成果物埋め込み用」を正としスタンドアロンページ用にしない。

owner表 (図解移植 C20-C28): C20→C18 / C21→C07・C18 / C22→C07・C18 / C23→C09 / C24(要件)→C07・C09・C17・C18 / C25(要件)→validate-svg-diagram.py(governance glue) / C26→C09・C19 / C27→C09(LLM手書き経路) / C28→C18(①)・C12/C24(②③積極評価)・C25/validate-svg-diagram.py(②③機械層)。

## スコープ外
- 設計の合否判定(P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出(P04 へ委譲)。
- 実体の生成(P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 25 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、8 plugin_level_surfaces の採否(vendor:true / mcp_app_connector:false / notion_config:false)が明示されている。
- [ ] vendor surface に「Node engine は byte 携行・Python 化しない」旨が derivation として記録されている。
- [ ] source-inventory §5 の既存全資産が component or surface へ 1 つ残らず対応づいている(抜け漏れ 0)。
- [ ] `envelope-draft/plugin.json` に manifest draft(entry_points / hooks 配線 / distribution)が設計されている。
- [ ] report 構造化 (C9-C15) が schema 1.1.0→1.2.0 additive (narrative/body block/highlight 第2チャネル/placement 正規化 live 化/section.role/throughLine/transition/文書メタ/新block型) + render-report.js・report 読書 CSS(buildReportCss() inline `<style>` 出力が正本責務)拡張 (C19) + references (report-narrative-logic 新設/追補) として設計され、既存 paragraphs/body 後方互換と slide 共通コア無改変を保つ。
- [ ] C15 節間フロー (throughLine/transition) が C17 設計 owner・C24 積極評価・C25 throughLine 非空機械検査へ結線され、真 schema 4本+report-structure が plugin-root schemas/ live SSOT で vendor-digest 191 files と整合する (Grp I)。
- [ ] C24 (積極評価 RQ21-) / C25 (block・narrative・highlight の機械チェック) の強化が設計され、両者が entities_covered と handoff route に結線されている (baseline orphan 是正済み)。
- [ ] report UI/UX (C16-C19) が screen/print 二層 CSS・sticky sidebar TOC+scrollspy・タイポ/密度スケール調整・essence-visual (schema は 1.2.0 のまま=既存 role/visual.kind を使い schema bump なし・第3次UIは render CSS のみで schema 非依存) として設計され、C19(render/CSS/JS 著者)・C18(essence-visual/図種写像 設計 owner)・C24(積極評価拡張・print/狭画面degrade成立を含む)・C25(決定論検査拡張・`@media print`/print無効化/狭画面breakpoint出力存在を含む) へ結線され、print 契約(190mm/A4)と意匠 SSOT が無改変である (周回2 で print/狭画面 shape 検査の穴を是正済み)。
- [ ] 図解移植 (C20-C28) が新規 buildable component を増やさず C07/C09/C12/C17/C18/C19/C24/C25 + `validate-svg-diagram.py`(governance glue) の additive 強化として設計され、新規物 (`diagram-style-tokens.md`/`diagram-type-crosswalk.md`/`assets/diagram-templates/*.html`) が plugin-root 側(vendor 非改変)に配置され、既存 Kanagawa トークン/`var(--x, fallback)` 方式・`ref-diagram-system`「索引は値を持たない」思想が維持されている。C28 溶け込み契約の3サブ契約(配置/重複禁止/文脈適合)が owner(C18/C12・C24/C25・validate-svg-diagram.py)へ明確に結線されている。

## 参照情報
- `source-inventory.md` §3(component 分解)/ §4(surface)/ §5(被覆)。
- `references/component-domain.md` / `references/io-contract.md`。
- report 構造化改善の要件正本 = P01「改善要件 (report 構造化・C9-C14)」節、語彙正本 = references/report-narrative-logic.md (新設)。
- 対象 component C01-C25(`component-inventory.json`)、後続 P03(design-gate)。
