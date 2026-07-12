---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準(AC)を build 後の受け入れとして判定する。purpose「既存全機能を抜け漏れなく移植した output_mode=slide/report の 2 モード・ビジュアル生成ハーネス」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート(lint/coverage)を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが 2 モード生成という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。既存機能の移植網羅性(13 agents / Codex Image2 / 30種思考法 / A4印刷 / GAS)も AC で確認する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose(`goal-spec.purpose`)と source-inventory §5 被覆チェックリストを受入観点の正本として参照できる。

## ドメイン知識
- AC(受入基準)と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証(両方必要・相互代替不可)。
- mode 別受入観点: slide=1スライド1メッセージ/長文なし/視覚崩れ0、report=読み物/1項目1ビジュアル/可読性。deck-evaluator(C13)の mode 別 rubric で判定する。
- 移植網羅性の観測: 既存 13 agents が C04-C16 として、Codex Image2 が C14+vendor として、30種思考法が C13+C20+vendor として機能することを確認する。

## 成果物
- 全 25 component の AC 判定結果(PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装(P05 へ差し戻し)。
- 機械品質ゲートの実行(P09)・全域最終審査(P10)。
- 受入観点の新規発明(正本は `goal-spec.purpose` と source-inventory §5・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01: slide/report 双方で mode 別に生成でき、生成後評価が視覚崩れ0(slide)/可読性・図解適合(report)で PASS すると判定できる。
- [ ] C01 の report 構造化受入 (C9-C15 / OUT2): 生成 report が節内論理展開(本質課題→解決→活用)・文書アーク(throughLine)と節間接続(transition)による節間フロー(C15)・block構造(表/コード/番号リスト/小見出し/強調 + 定義リスト/脚注引用/タスクリスト)・要点の色付き強調(色覚非依存の第2チャネル)・図解の意味的配置・reportType別必須横断要素(C14: 要約/キーテイクアウェイ/次アクション/根拠出典/リスク/TL;DR + 文書メタ)を備え、C25 決定論視覚ゲート(block多様性/narrative非空[role条件]/highlight と非色属性/表・コード・番号リストの正 HTML 化 + 二重充填・強調過多の上限 + reportType別横断要素の存在 + placement.grid/zones の live 反映[C12: 図が section 末尾全幅固定へ退化していない=DOM 位置 vs placement 指定一致の機械検査] + throughLine 非空)が exit0 かつ C24 RQ21- 積極評価(through-line/色覚非依存/reportType横断/多様性<適合性)が PASS すると判定でき、『情報の羅列』でないことが orchestrator 層で受入検証される。
- [ ] C01 の report UI/UX 受入 (C16-C19): C25 の shape 検査 —— (i) screen レイアウト CSS の接合トークン (`.report-layout` grid class/`--report-measure`(72ch) 変数/`--report-sidebar-w`/`--report-page-max`/`@media (max-width: 900px)` breakpoint)、(ii) TOC nav 要素 (`.report-toc--sidebar`) + scrollspy スクリプト (`.is-active`) 出力、(iii) essence-visual カバレッジ (論理節=role∈{分析/主張/課題/解決/所見/影響} が非none visual=visual.kind!=none を1枚持つ・非論理節は非該当=vacuous PASS)、(j) `@media print` 内の `.report` 幅規則 (190mm 相当) + 新 block の page-break 制御、(k) print 内 nav 非表示規則 or JS print ガードの実体、(l) 狭画面 breakpoint 内のレイアウト変更規則 —— が exit0、かつ report gate 呼び出しが `--structure` 欠落時に exit2 (fail-open 封鎖) となり、C24 積極評価 (ナビゲーション成立/密度バランス/図解適合/print・狭画面 degrade の成立) が PASS すると判定できる。
- [ ] C01/C02の実ブラウザ受入でcomputed本文16-18px、長文cardの最小幅/横overflow0、初期hashと`aria-current`一致、font-ready/history/afterprint後の同期、`report-structure.json + render`におけるessence-visual(論理節のvisual.kind非none)と本文論理構造の意味一致がPASSする。
- [ ] C02: 指定箇所のみ修正され非対象箇所が不変・再評価崩れ0 と判定できる。C03: 既知の横断不整合を全件検出すると判定できる。
- [ ] 既存全資産(13 agents / Codex Image2 / 30種思考法 / A4印刷 / GAS / 決定論レンダラ)が移植先 component/surface で機能すると判定できる。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

## 参照情報
- `goal-spec.purpose` / `source-inventory.md` §5 / index「受入確認(build 後の見方)」章。
- 対象 component C01-C25。
- 後続 P08(refactoring)。
