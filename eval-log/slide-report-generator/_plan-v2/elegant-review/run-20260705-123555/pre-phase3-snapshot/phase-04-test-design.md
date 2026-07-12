---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C05, C07, C08, C09, C11, C12, C13, C14, C15, C16, C17]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component(C01 generate / C02 modify / C03 cross-deck-review)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。既存機能維持の criteria(OUT1: 生成/修正/横断検証の既存挙動)に加え、本計画固有の rebalance 達成 criteria(OUT2: 委譲した手続き知識が plugin-root references/ へ progressive disclosure され lint-reference-attribution.py が PASS すること)を各 skill に追加する。さらに、最高リスクの本体手術である 11 thin-adapter agent の薄化について per-agent 非回帰 golden fixture を設計する(薄化前の代表入力→出力を凍結し、薄化後 agent が plugin-root reference 参照込みで同一出力を再現するか差分検証する)。段階化として html-generator(C09・990行=最大過重)を pilot 先行薄化 → ref 到達 + golden diff 合格を確認 → 合格後に残 10 thin-adapter へ展開する。実装前は criteria/golden が未達(Red)であることを確認する tdd-red gate。

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
- per-agent 非回帰 golden fixture(11 thin-adapter): 薄化前の agent に代表入力を与えた出力を golden として凍結し、薄化後 agent(本文=役割/起動条件/I/O契約 + plugin-root reference 参照)が同一入力で golden と一致する出力を再現できるかを差分検証する。reference 到達(`../references/<file>` の実行時 read)と出力等価の 2 点を 1 fixture で担保する。
- pilot 段階化: html-generator(C09・990行=最大過重・最大リスク)を pilot として先行薄化し、golden diff が PASS した設計・移設パターンを確立してから残 10 thin-adapter(C05/C07/C08/C11/C12/C13/C14/C15/C16/C17)へ横展開する(一括薄化による同時破壊を避ける)。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria`(inner1件 + outer2件: 既存機能維持OUT1 + rebalance達成OUT2)が inventory に確定した状態。
- 11 thin-adapter agent(C05/C07/C08/C09/C11/C12/C13/C14/C15/C16/C17)の per-agent 非回帰 golden fixture(薄化前 代表入力→出力 の凍結 + 薄化後 reference 参照込み出力の差分検証)が設計され、html-generator(C09)を pilot とする段階化手順が明文化された状態。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・kind 別観点はそちらで扱う)。
- hook/command/script component の受入(output_contract ベースで P07 が判定・本フェーズの golden fixture は 11 thin-adapter agent の非回帰に限定)。

## 完了チェックリスト
- [ ] 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] C01/C02/C03 それぞれが既存機能維持の outer criterion(OUT1)を保持している(責務再均衡が回帰を伴わないことの受入設計)。
- [ ] C01/C02/C03 それぞれが rebalance 達成の outer criterion(OUT2: 委譲手続き知識の references/ 反映 + lint-reference-attribution.py PASS)を保持している(goal-spec C2)。
- [ ] 実装前は criteria(特に OUT2)が未達(Red)であることが確認できる(references_new が build 前には存在しない)。
- [ ] 11 thin-adapter agent の per-agent 非回帰 golden fixture が設計され、reference 到達 + 出力等価の 2 点を検証する構成になっている。
- [ ] html-generator(C09)を pilot 先行薄化 → golden diff 合格 → 残 10 thin-adapter へ展開、の段階化手順が明文化されている(一括薄化を避ける)。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- 対象 component C01(生成)/ C02(修正)/ C03(横断レビュー)+ 11 thin-adapter agent(C05/C07/C08/C09/C11/C12/C13/C14/C15/C16/C17・per-agent golden fixture)。
- 後続 P05(implementation)。
