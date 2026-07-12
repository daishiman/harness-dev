---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: 
---

# P07 — acceptance-criteria (判定)

## 目的
goal-spec.json の checklist (C1-C14) を各 component (C01-C07) の受入 observable な二値基準へ写像し、build 後に「発行漏れレポート根治が purpose を満たしたか」を判定できる状態を確立する。写像の正本は index.md 受入確認テーブルとし、本節はそれと一致する要約である (値の二重記述を避け、齟齬時は index.md を正とする)。

## 背景
P06 で harness coverage 設計が確定した後、本フェーズは旧「AC matrix 判定」の精神 (二値 AC を各 component の受入 checklist へ) を keep する (phase-lifecycle.md §7 P7行)。goal-spec C1-C7 は確定6要因の直接受入基準、C8-C12 は非退行/安全性ガードレール、C13 は本 plan 自体のスコープ確認、C14 は対症療法 (個社会社名ハードコード) 禁止の一般解ガードである。

## 前提条件
component-inventory.json の各 component の quality_gates と C07 の `feedback_contract.criteria` (IN1/OUT1/OUT2) が確定済み。goal-spec.json checklist 全 13 項目が verify_by 付きで宣言されていること。

## ドメイン知識
RTM (要件トレーサビリティ) として goal-spec C1-C13 の各 id は index の完了チェックリスト/受入確認、または component 単位の criteria で引用される (`check-requirements-coverage.py` が id 出現を fail-closed 検査する)。id 照合は境界安全 (C1 が C01/C11 に誤マッチしない)。

## 成果物
goal-spec checklist C1-C13 の各項目 → 対応 component (C01-C07) への写像表 (下記完了チェックリスト)。C07 skill の `feedback_contract.criteria` が purpose-traceable な受入基準として確定済みであることの確認。

## スコープ外
criteria の実走 (pytest 実行等) は L4 build (run-skill-create/harness) へ委譲する。本フェーズは受入基準の写像確定に留まる。

## 完了チェックリスト
> 受入写像の正本は index.md 受入確認テーブル。本節はその一致要約で、齟齬時は index.md を正とする。番号衝突注意: 下記 C1-C14 は goal-spec checklist の番号であり、improvement-handoff の要因 C1-C6・inventory の component C01-C07 とは別系統 (§ドメイン知識)。
- [ ] goal-spec C1 (収集 billing-status 拡張=paws) → C01 が対応する
- [ ] goal-spec C2 (R1-collect 決定論 producer 化=構造的主因・発行済み社の当月行脱落 curr=None 根治) → C05 が対応する
- [ ] goal-spec C3 (carrier が C05→C03 seam を欠落なく貫通し『今月金額=null かつ忠実発行済み』偽発行漏れ0件=2nd Community/HOSONO 今月金額表示) → C05/C03/C06 が対応する
- [ ] goal-spec C4 (STATE_NEW×MATCH_ANNUAL 正常化+lookback配線) → C04 (+C07 orchestration) が対応する
- [ ] goal-spec C5 (prev取消の継続性=2nd Community 継続として今月金額表示) → C04 が対応する
- [ ] goal-spec C6 (代理店 compare 粒度+collapse 発行済み実額保全=HOSONO の複数発行が隠れない) → C04/C03 が対応する
- [ ] goal-spec C7 (MF顧客ID backfill=名前ドリフト耐性の恒久解) → C02 が対応する
- [ ] goal-spec C8 (GET専用維持)/C9 (evidence据え置き)/C10 (MF実績第一級非退行)/C11 (fetch fidelity非退行)/C12 (ゴールデンfixture凍結) が C07 の feedback_contract.criteria (OUT1/OUT2) または各 component の quality_gates へ反映されている
- [ ] goal-spec C13 (計画成果物限定) が P13 release の soft note と整合する
- [ ] goal-spec C14 (対症療法禁止=個社会社名リテラル0件・`_COMPANY_ALIAS_GROUPS` を C02 一般解へ吸収撤去・非ハードコード name-drift 社で偽発行漏れ0件回帰) → C02/C12/C06 が対応する

## 参照情報
goal-spec.json checklist / component-inventory.json / `check-requirements-coverage.py` / phase-lifecycle.md §8 P07 セル
