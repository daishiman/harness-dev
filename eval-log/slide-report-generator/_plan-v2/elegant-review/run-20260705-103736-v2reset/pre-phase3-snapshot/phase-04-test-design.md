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
skill loop 系 component(C01 generate / C02 modify / C03 cross-deck-review)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。既存機能維持の criteria(OUT1: 生成/修正/横断検証の既存挙動)に加え、本計画固有の rebalance 達成 criteria(OUT2: 委譲した手続き知識が references/ へ progressive disclosure され lint-reference-attribution.py が PASS すること)を各 skill に追加する。実装前は criteria が未達(Red)であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。責務再均衡という性質上、既存機能が壊れていないこと(回帰なし)と、rebalance 自体が実際に達成されたこと(references/ 新設・agent 薄化)の両方を criteria として明示する必要がある。汎用ゲートの言い換え(lint exit0 / 4 条件 PASS)に退化した criteria は purpose を一度も受入検証しないため、各 skill の goal/checklist 語彙由来であることを設計時に担保する。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C02/C03 の goal/checklist/progressive_disclosure が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約(inner/outer 各 1 件以上・id/verify_by enum)を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成/修正/横断検証時の自己検証観点(validate-output-mode / cross-deck-consistency 等・既存 v1 から不変)、outer=build 後の受入観点(既存機能維持 OUT1 + rebalance 達成 OUT2)。各 skill 最低 3 件(inner1+outer2)を契約する。
- Red = 実装前に criteria が未達であること(実装後に緑になることで criteria が実効だったと証明される)。references/ 新設ファイルは build 前には存在しないため OUT2 は自明に Red である。
- purpose-traceability = criteria が各 skill の goal/checklist の語彙(output_mode / 視覚崩れ / 横断整合 / progressive disclosure / lint-reference-attribution 等)を参照していること(汎用ゲート言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria`(inner1件 + outer2件: 既存機能維持OUT1 + rebalance達成OUT2)が inventory に確定した状態。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・kind 別観点はそちらで扱う)。
- 非 skill component(sub-agent/hook/command/script)の受入(output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] C01/C02/C03 それぞれが既存機能維持の outer criterion(OUT1)を保持している(責務再均衡が回帰を伴わないことの受入設計)。
- [ ] C01/C02/C03 それぞれが rebalance 達成の outer criterion(OUT2: 委譲手続き知識の references/ 反映 + lint-reference-attribution.py PASS)を保持している(goal-spec C2)。
- [ ] 実装前は criteria(特に OUT2)が未達(Red)であることが確認できる(references_new が build 前には存在しない)。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- 対象 component C01(生成)/ C02(修正)/ C03(横断レビュー)。
- 後続 P05(implementation)。
