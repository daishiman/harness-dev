---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準(AC)を build 後の受け入れとして判定する。purpose「16 sub-agent に過重した手続き知識・rubricを plugin-root references/ 一層と共有 scripts/ へ委譲し、3 skill は SKILL.md ポインタへ薄化し、既存機能を変えず責務再均衡を実現する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート(lint/coverage)を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが責務再均衡という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。既存機能の非回帰(slide/report 生成・修正・横断検証が v1 と同等に動作すること)も AC で確認する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria(OUT1既存機能維持+OUT2 rebalance達成)が確定している。
- purpose(`goal-spec.purpose`)と 16 sub-agent の rebalance_disposition/rebalance_rationale を受入観点の正本として参照できる。

## ドメイン知識
- AC(受入基準)と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose(責務再均衡)を満たす」保証(両方必要・相互代替不可)。
- rebalance 達成の観測: 11 thin-adapter agent が実際に薄化され(本文行数が役割・起動条件・I/O契約相当まで縮退)、対応する昇格 references が plugin-root references/ に実在し(D2一本化・agent は ../references/ で読む)、resource-map.yaml が全帰属を宣言していることを確認する。
- 非回帰の観測: slide/report の生成(C01)・部分修正(C02)・横断検証(C03)が既存 v1 build 済 plugin と同等の入出力契約で動作することを確認する(責務再均衡は機能追加/削減ではない)。
- 降格状態の扱い: C24 waiver は `WAIVED_NON_MECHANICAL` とし、機械検証 PASS ではない。golden-pin waiver は `WAIVED_LIMITED_REGRESSION` とし、決定論経路限定の非回帰であり LLM 経路の v1 同等動作 PASS ではない。

## 成果物
- 全 24 component の AC 判定結果(PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装(P05 へ差し戻し)。
- 機械品質ゲートの実行(P09)・全域最終審査(P10)。
- 受入観点の新規発明(正本は `goal-spec.purpose` と rebalance_disposition・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01/C02/C03: 既存の生成/修正/横断検証機能が v1 と同等の入出力契約で動作すると判定できる(非回帰)。golden-pin waiver 時は `WAIVED_LIMITED_REGRESSION` として限定非回帰に降格し、通常 PASS と混同しない。
- [ ] 11 thin-adapter agent: 本文が役割・起動条件・I/O契約へ薄化され、対応する昇格 references が plugin-root references/ に実在すると判定できる(D2一本化・goal-spec C1)。
- [ ] resource-map.yaml が plugin-root content references 61件 (既存50=直下45+feedback/5 + 新設11・D2一本化) の全帰属を宣言し(自身は content 外の帰属メタ)、通常経路では lint-reference-attribution.py(C24)が PASS すると判定できる。C24 waiver 時は `WAIVED_NON_MECHANICAL` として人手帰属確認ログへ降格し、機械検証 PASS とは判定しない。
- [ ] 5 maintain agent の本文が無変更で既存機能を保っていると判定できる。

## 参照情報
- `goal-spec.purpose` / index「受入確認(build 後の見方)」章。
- 対象 component C01-C24。
- 後続 P08(refactoring)。
