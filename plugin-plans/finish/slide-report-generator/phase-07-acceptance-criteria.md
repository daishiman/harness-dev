---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
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
- 全 23 component の AC 判定結果(PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装(P05 へ差し戻し)。
- 機械品質ゲートの実行(P09)・全域最終審査(P10)。
- 受入観点の新規発明(正本は `goal-spec.purpose` と source-inventory §5・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01: slide/report 双方で mode 別に生成でき、生成後評価が視覚崩れ0(slide)/可読性・図解適合(report)で PASS すると判定できる。
- [ ] C02: 指定箇所のみ修正され非対象箇所が不変・再評価崩れ0 と判定できる。C03: 既知の横断不整合を全件検出すると判定できる。
- [ ] 既存全資産(13 agents / Codex Image2 / 30種思考法 / A4印刷 / GAS / 決定論レンダラ)が移植先 component/surface で機能すると判定できる。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

## 参照情報
- `goal-spec.purpose` / `source-inventory.md` §5 / index「受入確認(build 後の見方)」章。
- 対象 component C01-C23。
- 後続 P08(refactoring)。
