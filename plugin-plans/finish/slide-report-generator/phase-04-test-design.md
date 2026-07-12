---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component(C01 generate / C02 modify / C03 cross-deck-review)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達(Red)であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え(lint exit0 / 4 条件 PASS)に退化した criteria は purpose を一度も受入検証しないため、各 skill の goal/checklist 語彙由来であることを設計時に担保する(`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。とりわけ output_mode 分岐の受入(slide=1メッセージ/report=読み物)を criteria に焼く。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C02/C03 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約(inner/outer 各 1 件以上・id/verify_by enum)を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点(validate-output-mode / cross-deck-consistency 等)、outer=build 後の受入観点(mode 別成果物品質)。各 1 件以上が契約。
- Red = 実装前に criteria が未達であること(実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が各 skill の goal/checklist の語彙(output_mode / 視覚崩れ / 横断整合 等)を参照していること(汎用ゲート言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria`(inner+outer 各 1 件以上)が inventory に確定した状態。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・kind 別観点はそちらで扱う)。
- 非 skill component(sub-agent/hook/command/script)の受入(output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] C01 は「slide=1メッセージ/report=1項目1ビジュアルで視覚崩れ0の生成後評価 PASS」、C02 は「指定箇所のみ修正で非対象不変・再評価崩れ0」、C03 は「既知の不整合を全件検出」を outer criterion に持つ。
- [ ] 実装前は criteria が未達(Red)であることが確認できる。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- 対象 component C01(生成)/ C02(修正)/ C03(横断レビュー)。
- 後続 P05(implementation)。
