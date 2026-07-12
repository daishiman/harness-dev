---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 25 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす(Green)状態にする。あわせて vendor surface(Node engine 一式)を byte 携行で plugin へ配置する。build routing は `component-inventory.json` の依存 top-sort 順に実行する(phase 順 ≠ build 順)。**本 update では report 構造化改善 (C9-C15) の実装 —— schema 1.1.0→1.2.0 additive・render-report.js 拡張・C24/C25 強化・references 新設/追補 —— を additive に実体化する** (既存 gate-green 実体と slide 経路を壊さない Edit 差分)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る(worker 群 + 共有 script → orchestrator skill → hook/command)。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果(到達状態)を宣言する。Node engine は Python 化せず vendor として byte コピーし、skill/agent は Bash(node *) で起動する。

## 前提条件
- P04 で C01/C02/C03 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている(worker sub-agent C04-C19 + report品質 C24 + 共有 script C23/C25 → skill C01/C02/C03 → hook C20 → command C21/C22 の依存順。C01 は C24/C25 にも依存)。
- 後段 builder(run-skill-create / run-build-skill / plugin-scaffold)が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順(依存先が常に先。phase 番号順ではない)。
- vendor 携行の実装規律: Node/CJS 製エンジンは byte 維持で plugin の vendor へ配置し、node_modules は install 時に再取得する。stdlib script へ書き換えない。
- 共有 script hoist: validate-output-mode.py(C23)は builder=plugin-scaffold で plugins/slide-report-generator/scripts/ 直下へ実体化する(単一 skill 配下に退化させない)。
- Green 判定の主体は P04 で固定した criteria(実装が判定基準を都合よく再定義しない)。

## 成果物
- 全 25 component の実体(skills/agents/commands/hooks/scripts)が build_target に生成された状態。
- vendor surface(Node engine + 118 templates + package.json)が byte 携行で配置された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest(後段 scaffold owner)。
- report 構造化改善の実体 (具体 build_target は inventory build_target / C19 build_contract / handoff surface_tasks が単一 SSOT・ここでは到達状態を component/surface id で宣言): (a) surface S-SCHEMAS = report-structure 1.1.0 additive (narrative/body block/highlight/placement live・plugin-root schemas/ の live 正本で vendor byte-parity 対象外)、(b) C19 = render-report.js の block レンダラ + inline highlight + placement 反映 (著者責務・additive)、(c) C17(narrative+block 設計)/C18(幾何配置 live placement)/C24(積極評価 RQ21-+負次元)、(d) C25 = block・narrative・highlight・二重充填/強調過多の追加機械チェック、(e) surface S-REFERENCES = report-narrative-logic.md 新設 + report-writing-rules/visual-strategy(plugin-root)・report-quality-checklist(skill-level) 追補、(f) report UI/UX (C16-C19・本更新第3次: report-uiux-layout-improvement): C19 = render-report.js の screen/print 二層 CSS(正本=inventory C19.build_contract: buildReportCss() inline 出力)+ sticky sidebar TOC + scrollspy(self-contained JS)+ タイポ/密度スケール調整、C18 = essence-visual 設計(形式三択に先行し節の論理構造→図種の写像・§0.5.1/VCONST_000)、C24 = RQ 次元(ナビゲーション成立/密度バランス/図解適合 + 周回2 追加: print/狭画面degrade成立)追加、C25 = screen レイアウトCSS/TOC+scrollspy/essence-visualカバレッジ(論理節のvisual.kind非none)検査 + 周回2 追加(R4 HIGH是正): `@media print` 出力存在/print時TOC・scrollspy無効化出力存在/狭画面breakpoint出力存在の3種、S-SCHEMAS = report-structure 1.2.0 据置(第3次UIは render CSS のみで schema 非依存・essence-visual は既存 role/visual.kind を使い schema bump なし)。

## スコープ外
- カバレッジ拡充・テスト網羅(P06)。
- purpose 受入判定(P07)・SSOT 重複整理(P08)。
- builder 自体の改修(harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存 top-sort 順に全 25 component が build され、skill loop の criteria が Green(受入テスト PASS)になる。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] vendor Node engine が byte 携行で配置され Python 化されていない(skill/agent が Bash(node *) で起動する)。
- [ ] 共有 script C23/C25 が plugin-root へ実体化されている(単一 skill 配下に退化していない)。
- [ ] render-report.js の block レンダラ (表→`<table>`・fenced code→`<pre><code>`・`1.`→`<ol>`・小見出し・key-point・stat-tile) + inline highlight + placement.grid/zones 反映が additive 実装され、markdown 表が `<br>` で潰れず・図が段落末尾全幅固定でなく該当箇所へ配置される。tests_min≥80 と C25 決定論ゲートで検証される。
- [ ] schema report-structure 1.1.0→1.2.0 が既存 paragraphs 後方互換を保ち (body[]/narrative/highlight に加え 1.2.0 の section.role/throughLine/transition/文書メタ/新block型/placement 正規化を optional additive)、slide 共通コアを複製しない。
- [ ] 実行環境 preflight (node --version / npm ci 成功 / playwright browser 取得 / codex exec 疎通※画像生成使用時) が exit0 (C23 validate-output-mode.py --preflight)。
- [ ] report UI/UX (C16-C19) が additive 実装され、screen で空白が本文幅を上回らない sidebar レイアウト・sticky TOC+scrollspy・タイポ/密度調整・essence-visual 設計(論理節への非none visual 割当)が render-report.js(buildReportCss() inline `<style>` 出力を正本責務とする report 読書 CSS・C19)・visual-strategist(C18) に反映され、print(190mm/A4)契約が退行しない。tests_min≥80 と C25 決定論ゲートで検証される。
- [ ] (周回2 追加・R4 HIGH是正) print/狭画面の非退行が C25 の3種 shape 検査(`@media print` ブロック出力存在/print時 sidebar TOC非適用・scrollspy無効化の出力存在/狭画面 breakpoint `@media (max-width: 900px)` 出力存在)と C24 の print/狭画面degrade成立 rubric の二層で検証され、緑のまま print 破壊を見逃す穴が塞がれている。
- [ ] (周回3 追加・C25 fail-open 封鎖) validate-report-visual.py が report gate 用途で `--structure <report-structure.json>` を必須化し、欠落時 exit2 (usage error) を返す実装になっている (--structure 無しの素通しを塞ぐ)。接合トークン (`.report-layout`/`--report-measure: 72ch`/`--report-sidebar-w: 15rem`/`--report-page-max: 1240px`/`@media (max-width: 900px)`/`.report-toc--sidebar`/`.is-active`) と `--fs-title: 2.2rem` が render-report.js buildReportCss() 出力に現れ C25 接合トークン pin・タイポレンジ検査と一致する。
- [ ] computed本文16-18px、card最小幅/1列degrade、hash-active+`aria-current`同期、font-ready再着地、beforeprint/afterprint復帰、essence-visual(論理節のvisual.kind非none) bundle評価がC01/C02実行経路まで実装される。

## 参照情報
- `handoff-run-plugin-dev-plan.json`(build routing)/ `component-inventory.json`(依存 DAG)。
- report 構造化実装の設計正本 = P02「report 構造化設計 (C9-C15・additive)」節、C19 build_contract.structuring_scope。
- 対象 component C01-C25、vendor surface。
- 後続 P06(test-run)。
