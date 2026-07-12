---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
C02/C09のfeedback_contractと、C01/C03/C04/C05/C06/C07/C08/C10/C11のbinary acceptance_contractをtest-firstでRedに固定する。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え (lint exit0 / 4 条件 PASS) に退化した criteria は purpose を一度も受入検証しないため、goal/checklist 語彙由来であることを設計時に担保する (`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C02/C09 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点、outer=build 後の受入観点 (各 1 件以上が契約)。
- Red = 実装前に criteria が未達であること (実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が goal/checklist の語彙を参照していること (汎用ゲートの言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C02のfeedback criteriaと全non-skill componentのpositive/negative/failure/retry/zero-hit acceptance fixtures。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの設計・実行 (P06・kind 別観点はそちらで扱う)。
- なし。全componentを本phaseでRed設計する。

## 完了チェックリスト
- [ ] C02/C09 の criteria が purpose 由来で inner/outer を各 1 件以上持つ (汎用ゲート言い換えに退化していない)。
- [ ] C02はcontent coverage 100%をinner、無人syncの一度だけ反映+retry回復をouterに持つ。
- [ ] C09/C11は協働モード適合と単一解非強制をinner、分岐・保存同意・role=user provenance・action/reflection closure・ownershipをouterに持つ。
- [ ] C01/C08はprovenance/edge evidence、C03は分母維持、C04はdry-run、C05はreal artifact+redaction、C06はcycle/dangling、C07はknown-hit/zero-hitをRed fixtureに持つ。
- [ ] 実装前は criteria が未達 (Red) であることが確認できる。
- [ ] (検証専用・非 buildable) 既配備 run-skill-feedback の維持確認は本 phase の criteria 対象外とし、P09 (quality-assurance) の完了チェックリストで扱う。

### 受入例
一時取得失敗、cycle、evidence欠落、stale artifact、正しいzero-hitを実装前Redにする。

### 事前解決済み判断
non-skillもP04対象でありP07へテスト設計を先送りしない。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01-C11。
- 後続 P05 (implementation)。
