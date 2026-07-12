---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
既存 presentation-slide-generator(v8.4.2)の全機能を xl-skills plugin へ抜け漏れなく移植し、共通コア + output_mode=slide/report の 2 モード + report 新規機能を持つビジュアル生成ハーネスを目的ドリブンに要件化して、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`slide-report-generator` を固定する。**本 update では追加要件として、report モードの出力を『情報の羅列』から『構造化された読み物レポート』へ引き上げる改善 (C9-C14) を要件化する** (既存 gate-green baseline への additive・slide 経路と意匠/技術 SSOT は無改変)。**本 update (第3次: report-uiux-layout-improvement) では、report 出力の『読み物の中身』(C9-C15) に続き『読み物の器 = 画面表示 UI/UX』を要件化する** (screen/print 幅二層化 C16・sticky sidebar TOC+scrollspy C17・タイポグラフィ/密度再調整 C18・本質図解(essence-visual)第一級化 C19)。既存 gate-green baseline への additive であり、新規 buildable component は増やさず C18 visual-strategist(essence-visual/図種写像 設計 owner)・C19 report-composer(render-report.js/report 読書 CSS[正本=inventory C19.build_contract: buildReportCss() inline 出力] 著者責務)・C24 report-quality-reviewer(積極評価)・C25 validate-report-visual.py(決定論検査)の強化と、第3次UI(C16-C19)は render CSS のみで schema 非依存ゆえ schema は 1.2.0 のまま(essence-visual は既存 role/visual.kind を使い schema bump 不要)で実現する。

## 改善要件 (report 構造化・C9-C14)

> 本節は goal-spec.source_improvement.ref の詳細正本。現状 report は「破綻しない HTML を決定論生成」には成功しているが、schema か renderer のどちらかで下記が欠落/デッド化しており「情報の羅列」に見える。6 根因 → 6 要件 (C9-C14) で 1:1 に閉じる。加えて本再検証 (30思考法) の再問いで、当初の defect-repair 分解 (欠落を直す 6 根因) の枠外にあった第7根因『読み物としての横断的読書体験 (節間フロー/読書タイポグラフィ/文書メタ/色覚アクセシビリティ/新 block 表現機構) が未評価』を発掘し、C15 (節間フロー throughLine/transition) 新設 + C9-C14 の additive 次元拡張 (schema 1.2.0) へ広げる。in-scope = C17/C18/C19/C24/C25 + schemas(report-structure additive 1.1.0→1.2.0)/references。新規 buildable component は増やさない (責務は既存 design/render/verify の分担に収まる no-split)。

| 根因 (現状の欠落) | 対応要件 | 焼き先 |
|---|---|---|
| 節内論理展開テンプレート不在 (`paragraphs[]` が自由文字列・narrative フィールド無し → 論理が LLM 自由作文任せで羅列退化) | C9 | schema `section.narrative` + C17 設計 + report-narrative-logic.md 正本 |
| block 構造 (markdown表/フェンスドコードブロック/番号リスト/小見出し) が render-report.js 未実装で潰れる (表が `<br>` 化) | C10 | schema `section.body[]` block 型 + C19 render-report.js 実装 |
| 強調が `**bold**`→accent 1種のみ (色付きハイライト/キーポイント/統計タイルが schema・renderer 双方に無い) | C11 | schema inline highlight/key-point/stat-tile トークン + C19 render + 意匠 accent 流用 |
| `placement.grid/zones/emphasis` が schema にあるが render-report.js が無視するデッドフィールド (図は常に段落末尾全幅) | C12 | C18 が決定・C19 render-report.js が反映 (placement live 化) |
| 品質ゲートが減点型 (空節/図解過多/順序崩れ/letterbox の破綻検出のみ)。「羅列でも破綻ゼロなら PASS」 | C13 | C24 積極評価 RQ21- + C25 機械チェック追加 |
| reportType 骨格が節順序どまりで「本質課題→解決→活用」と横断的な必須要素を全型で強制しない | C14 | report-narrative-logic.md の**開いた読書体験カタログ(再問い由来)** + 4 reportType 骨格へ additive 反映。文書メタ/per-section recap/表現機構(定義リスト・脚注引用・タスクリスト)を横断要素へ拡張 |
| **(第7根因・再問い由来)** 読み物としての横断的読書体験(文書全体の通し筋=節間フロー・読書タイポグラフィ・文書メタ・色覚アクセシビリティ・新 block 表現機構)が当初の defect-repair 6 根因分解の枠外で未評価 | C15 + C9-C14 additive | C15=throughLine/transition(C17 設計・C24 積極評価・C25 throughLine 非空機械検査)。C9-C14 additive= schema 1.2.0(section.role/文書メタ/新 block/highlight 第2チャネル/placement 正規化)+ report読書CSS(C19)+ 色覚非依存の強調(C11/C24/C25) |

## 改善要件 (report UI/UX・C16-C19)

> 本節は goal-spec.source_improvement.ref (第3次: report-uiux-layout-improvement) の詳細正本。実運用レポート `plugin-plans/plugin-dev-planner/reports/task-graph-build-20260711/report.html` (決定論レンダラ実装 = `plugins/slide-report-generator/vendor/scripts/render-report.js`) の目視で 4 根本課題を確認した。上記 C9-C15 が「読み物の中身」(節内論理/block/強調/配置/積極評価/横断要素/節間フロー)を扱ったのに対し、本節は「読み物の器 = 画面表示 UI/UX」を扱う。in-scope = C18/C19/C24/C25 + references(schema は 1.2.0 のまま=第3次UIは render CSS のみで schema 非依存・essence-visual は既存 role/visual.kind を使う)。新規 buildable component は増やさない (責務は既存 render/design/verify の分担に収まる no-split)。

| 根因 (現状の欠落・実運用レポートの目視で確認) | 対応要件 | 焼き先 |
|---|---|---|
| `--report-width: 190mm` が print 用 A4 契約を screen にも流用(`buildReportCss()` の `.report { max-width: var(--report-width) }`)し、広画面で両サイド余白が本文幅を超える『空白 > 本文』逆転が起きる | C16 | C19 render-report.js(report 読書 CSS の正本=inventory C19.build_contract: buildReportCss() inline 出力)の著者責務で screen/print 二層 CSS 化(screen=可読幅本文カラム+sidebar・print=190mm を `@media print` で温存)。print 側の非退行(`@media print` ブロック出力存在)は C25 shape 検査 + C24 積極評価の二層で担保する (周回2 追加) |
| `.report-toc`(render-report.js の CSS 定義)が冒頭静的2カラムのみで、下部スクロール時にインデックスが失われる | C17 | C19 render-report.js が sticky sidebar TOC + scrollspy(self-contained JS・print 無効)を追加実装。狭画面はインライン TOC へ graceful degrade。print 時の TOC/scrollspy 無効化出力と狭画面 breakpoint 出力の存在は C25 shape 検査、degrade の読みやすさは C24 積極評価が担う (周回2 追加) |
| `--fs-title: calc(2.6rem * var(--font-scale))` 等の見出しスケールが狭カラム相対で過大(実運用指摘=文字が大きすぎる/バランスが悪い) | C18 | C19 render-report.js(buildReportCss() inline <style> 出力が正本責務の report 読書 CSS)のスケール/spacing 変数調整(意匠 SSOT Kanagawa 配色/フォントは無改変) |
| visual-strategist(component C18)が SVG/Mermaid/画像の形式三択を先に決め、『本文のどの概念構造を図解すべきか』の抽出が後回しになり装飾目的の図解が混入し得る | C19 | C18 visual-strategist が形式三択より先に節の論理構造→図種の写像(essence-visual)を行い、論理節(role∈{分析/主張/課題/解決/所見/影響})に非none visual(visual.kind!=none)を必須設計(写像規律=reference report-visual-strategy.md §0.5.1・VCONST_000)。schema は 1.2.0 のまま(essence-visual は既存 role/visual.kind を使い schema bump 不要)。要件 C19 の設計 owner は component C18 であり component C19(report-composer)ではない点に注意 |

Phase1の実測で、現行差分後も本文 `21.84px`、`#section-route-build` の着地が viewport `y=1017.7`、active TOCが別節、個別2列カードの可読幅未定義を追加確認した。したがって C16-C19 は「CSS/DOMが存在する」だけでなく、computed本文16-18px、hash/active一致、card最小幅、essence-visual(論理節のvisual.kind非none・図が節の要旨を一目化するか)とrenderの意味一致までを受入境界とする。

### 枠外再問いの採否 (report UI/UX・周回3 追加)

上表 4 根因の枠外で検討した周辺候補の採否を証跡として残す (枠外再問いの証跡):

| 候補 | 採否 | 理由/結線 |
|---|---|---|
| 狭画面での table/code/stat-tile overflow 処理 | 採用 | C19 実装 + C25 shape 結線 (狭画面 breakpoint 内のレイアウト変更規則として検査可能) |
| 図解/画像の responsive 最大幅契約 | 採用 | C19 実装 (render-report.js の visual 幅契約) |
| 新 block (table/code) の print page-break 制御 | 採用 | C19 実装 + C25(j) の最小実質条件へ結線 |
| 見出しアンカー着地 (scroll-margin-top) | 採用 | C19 実装 (sticky TOC からの節ジャンプ着地) |
| 読了進捗バー / ダークモード | 不採用 | 意匠 SSOT 無改変制約に抵触し得るため第4次 update 候補として見送り |
| コントラスト機械検査 | 不採用 | 要件 C11 (色覚非依存の非色第2チャネル既定) で部分被覆済みのため専用検査は追加しない |

積極評価(意味の適合)は C24 report-quality-reviewer(ナビゲーション成立/密度バランス/図解適合/print・狭画面degradeの成立)、決定論検査(shape/存在)は C25 validate-report-visual.py(screenレイアウトCSS出力/TOC+scrollspy出力/essence-visualカバレッジ[論理節のvisual.kind非none]/`@media print`出力/print時TOC・scrollspy無効化出力/狭画面breakpoint出力)の二層分離で担保する(Goodhart 回避)。**周回2 追加 (R4 HIGH是正)**: C16 の print 非退行・C17 の scrollspy print無効/狭画面 graceful degrade は screen 新挙動の shape 検査だけでは検査できないため、C25 に上記 3 種の print/狭画面 shape 検査を追加し C24 に print/狭画面 degrade の意味適合を追加した(緑のまま print 破壊を見逃す穴の是正)。

## 背景
本プラグインは、単一 SKILL の巨大ハーネス(13 sub-agent / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 チェーン / 30種思考法評価 / A4印刷 / GASデプロイ)を plugin 化する構想から出発する。機能削減・平均回帰・オミットを禁じ、既存全資産が component か plugin-level surface に必ず対応することを要件の第一に据える。同一構想は常に同一 `PLAN_DIR` へ解決され(再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- 既存 presentation-slide-generator の実ソース(SKILL.md / agents / references / scripts / schemas / assets)が参照可能である。
- 移植元 root が存在する、または plan 同梱 `vendor-digest-manifest.json` (v8.4.2 byte 正本) で照合可能である(移植元不在環境では manifest 照合を代替とする)。
- 汎用の `run-goal-elicit`(harness-creator)で purpose/background/goal/checklist を抽出できる(再実装しない)。
- このフェーズは特定 component へ紐づかない(責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- output_mode = slide | report の 2 分岐。意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみモード別(purpose の中核語)。
- vendored Node engine = Node/CJS 製レンダリング/画像/印刷/検証エンジンを byte 維持で携行し Python 化しない不変原則(既存資産の毀損回避)。
- 抜け漏れ厳禁 = source-inventory §5 被覆チェックリストで既存全資産が component or surface へ対応することを保証する。
- その他の plan 全体用語(component_kind / 5 種 buildable / 2 軸直交等)は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json`(purpose/background/goal/checklist/constraints/handoff_targets)。移植要件 C1-C8 に加え report 構造化改善 C9-C15(C15=節間フロー・再問い由来)・report UI/UX改善 C16-C19(screen/print二層化/sticky TOC+scrollspy/タイポ密度/本質図解(essence-visual)第一級化)と `source_improvement` を保持する。
- target_plugin_slug=`slide-report-generator` と plan_dir=`plugin-plans/slide-report-generator` の確定値。
- `source-inventory.md`(既存全資産 → component/surface の R2 分解正本・被覆チェックリスト)。

## スコープ外
- component 分解・schema 設計(P02 へ委譲)。
- ヒアリング機構の再実装(`run-goal-elicit` を引用するのみ)。
- 実装・build(P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている(要件 C1-C8 の被覆が確認できる)。
- [ ] report 構造化改善の要件 C9-C15 (節内論理展開/block構造/色付き強調/意味的図解配置/積極評価ゲート/本質的横断要素/節間フロー through-line) が goal-spec.checklist に明記され、根因→要件→焼き先(第7根因 C15 含む)が本 phase の「改善要件」節で追跡できる。
- [ ] report UI/UX改善の要件 C16-C19 (screen/print幅二層化/sticky sidebar TOC+scrollspy/タイポグラフィ密度再調整/本質図解(essence-visual)第一級化) が goal-spec.checklist に明記され、根因(実運用レポート実測)→要件→焼き先が本 phase の「改善要件 (report UI/UX・C16-C19)」節で追跡できる。
- [ ] target_plugin_slug が ASCII kebab(`slide-report-generator`)で確定し以降のフェーズが参照できる。
- [ ] 既存全資産(13 agents / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 / 30種思考法 / A4印刷 / GAS)が移植対象として goal-spec に明記されている。
- [ ] `check-plugin-goal-spec.py` が exit0(R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `source-inventory.md`(R2 分解正本・被覆チェックリスト §5)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02(この goal-spec を component 分解の入力とする)。
