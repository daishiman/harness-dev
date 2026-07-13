---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop component(C01 run-mf-invoice-report)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達(Red)であることを確認する tdd-red gate。C02 の偽陽性/偽陰性検出、C06 の fetch_trace 入力、C04 の既存8列互換も fixture 化する。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。C01 は本改善の唯一の skill であり、fetch fidelity 監査(inner)とゴールデン fixture 回帰(outer, 症状①〜⑦)を criteria として固定することで、汎用ゲートの言い換えに退化していないことを担保する。

## 前提条件
- P03 の design-gate を通過している。
- C01 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約(inner/outer 各 1 件以上・id/verify_by enum)を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点(C01 では fetch fidelity 監査の fail-closed 動作)、outer=build 後の受入観点(症状①〜⑦ゴールデン fixture 回帰)。C02 は fixture 上で「両月発行済なのに要対応」(偽陽性)と「今月未発行なのに正常☑」(偽陰性)を少なくとも各1件検出する。
- Red = 実装前に criteria が未達であること(実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が goal/checklist の語彙(実績/漏れ/fidelity)を参照していること。
- C05(`scripts/mfk_actuals.py`)由来の取引先×商品粒度 issued/実額抽出が、症状③(金額一致なのに未☑)・症状⑦(会社名だけ取得で金額空白)を根治する中核メカニズムである(契約突合から独立した実額が常に得られるため)。
- 症状⑤(請求ありなのに今月金額空白)は原因二分の多層原因であり、evidence-gate由来(C05で実額を埋めれば解消)と fetch欠落由来(C06 fail-closedで検出すべきだが解消はしない=データ欠損そのもの)を別ケースとして扱う。
- characterization回帰(退行検知): 既存 `SUPPRESS_ANNUAL`(年契約抑制)・`MATCH_ENDED_FINAL`(契約終了最終請求判定)・J1名寄せ偽陰性封鎖の verdict は本改善が判定入力をMF実績へ切替えても不変でなければならない。これらは新機能ではなく「壊さないことを凍結する」fixture であり、OUT1 とは別観点として扱う。

## 成果物
- C01 の `feedback_contract.criteria`(IN1=fidelity監査fail-closed、OUT1=症状①〜⑦ゴールデンfixture回帰)が inventory に確定した状態。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・script/sub-agent/slash-command の kind 別観点はそちらで扱う)。
- 非 skill component(C02-C07)の受入(output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] C01 の criteria が purpose 由来で inner(IN1)/outer(OUT1)を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] OUT1 は「症状①今月金額空白/②MF無し情報残存/③金額一致なのに未☑/④先月空白今月ありの新規判断/⑤請求ありなのに空白/⑥金額相違/⑦会社名だけ取得」を各1件以上再現するゴールデン fixture 回帰であることが明記されている。特に症状③・⑦は C05(mfk_actuals)由来の issued/実額抽出で解消されることが fixture 期待値に反映されている。症状⑤は evidence-gate由来(C05で実額埋め)と fetch欠落由来(C06 fail-closed)の**2ケースを各1件凍結**する。
- [ ] OUT2(characterization回帰): `SUPPRESS_ANNUAL`/`MATCH_ENDED_FINAL`/J1名寄せ偽陰性封鎖の既存verdictが改修前後で不変であることを固定 fixture で凍結する(C01 feedback_contract に OUT2 として登録)。
- [ ] C06 の Red fixture は `fetch_trace` 欠落時にも失敗し、`lib/mfk_api.py`/R1 collect が pagination metadata を保存していない実装を通さない。
- [ ] C04 の Red fixture は新物理列追加ではなく既存8列の `先月の金額`/`今月の金額` が MF実額で埋まり、金額差フラグが `先月と今月の比較`/`コメント` に現れることを検証する。
- [ ] OUT2 追加(K2 carrier一意化・温存): `REVIEW_AMOUNT_MISMATCH`/`no_supply` 行の `evidence` と別 skill `run-mf-invoice-reconcile` の DB2 `matched_amount`(reconcile_invoices.py:348 `build_sink_rows` 経由)が改修前後で **byte 不変**であることを characterization fixture 1 件で凍結する(canonical carrier は行 top-level `actual_amount` 単一・`find_mf_match` の `evidence:None` は据え置き)。
- [ ] OUT2 追加(K3 取消明細の偽陰性隔離): 取消前額を持つ `REVIEW_CANCELED`(`supply_state=inactive_canceled`)行が漏れチェック☑にも金額列表示にもならない fixture を追加する(`_is_issued`/`_amount_of` の `evidence.amount` fallback を `supply_state==active` に限定し取消前額を issued 化しない)。
- [ ] C04 fixture 追加(K4 cross-run 訂正): 前run要対応☐→今run で reliable MF-issued(C05 issued=True)により☑へ訂正される cross-run ケースを追加する(reliable MF-issued を `_STRUCTURAL_NORMAL_MARKERS` と同格の guard bypass 事由にした場合のみ既persist済み誤☐行へ訂正が届く)。
- [ ] C04 fixture 追加(K6 真orphan是正): 旧run の phantom/誤☑行(今月MFにも契約在籍にも無い真の orphan)が新run で残置理由付き(`先月と今月の比較`/`コメント`)に是正される fixture を追加する(行削除はせず注記のみ・`query_month` で対象月既存行を列挙し incoming キー差集合を PATCH)。
- [ ] 実装前は criteria が未達(Red)であることが確認できる。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- 対象 component C01(run-mf-invoice-report)。
- 後続 P05(implementation)。
