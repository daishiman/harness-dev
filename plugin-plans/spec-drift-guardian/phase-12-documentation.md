---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (文書化)

## 目的
`index.md` の受入確認章・完了チェックリストと、各 component の boundary/output_contract 記述を、build 後に実プラグインの利用者 (harness-creator 保守者・issue 対応者) が読んで挙動を理解できる水準まで文書として整える。

## 背景
本planはL3止まりだが、履歴previewと完全diffの違い、通常read-only/C02承認済みapply限定、proposal-onlyではclose不可、ローカルhookがWeb/API closeを保証しない境界を文書化しないとbuild時に誤解が生じる。

## 前提条件
- P11 のエビデンスが確定している。
- `index.md` の草稿がある (P02 以降の設計を反映済み)。

## ドメイン知識
- 文書化は完全diff provenance、4軸+semantics、独立verdict、承認済みapply、post-image close gateと、保証外のserver-side closeを中心に据える。
- checklist C1-C6 は index.md の完了チェックリスト/受入確認章で literal に参照されるべき語彙 (RTM 追跡性) である。

## 成果物
- `index.md` の受入確認章・完了チェックリスト (checklist C1-C6 を literal に含む)。
- 各 component の boundary/output_contract 記述の最終化。

## スコープ外
- リリース対応・PR 作成 (P13 の責務外・本 plan の責務外)。
- 実プラグインのユーザー向け README 生成 (build フェーズの責務)。

## 完了チェックリスト
- [ ] `index.md` の完了チェックリストと受入確認章の双方に checklist C1-C6 が literal に含まれている。
- [ ] C02以外は実適用しないこと、C02も監査PASS/明示承認/allowlist/hash guardなしでは適用しないこと、C07はローカルcloseのみを守ることが明示されている。
- [ ] `check-requirements-coverage.py` が exit0 (C1-C6 の RTM 追跡性確認)。

## 参照情報
- `index.md` / `component-inventory.json`。
- `goal-spec.json` (checklist C1-C6 の原文)。
- 後続 P13 (文書化完了を以て plan 完了とする)。
