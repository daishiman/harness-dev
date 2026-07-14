---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
全 14 component の `harness_coverage` (min≥80) と `kind_pass` 整合を実測する。

## 背景
quality_gates/harness_coverage は「≥80% を満たす設計」を要件化した契約であり、本フェーズはその実測値を確認する (契約は P02 で焼き、実測は本フェーズ。現状値は component エントリへ焼かない=Goodhart 回避)。

## 前提条件
- P05 で全 14 component が実体化されている。

## ドメイン知識
- `kind_pass` の kind 別値: skill loop (C01) = `loop=criteria-test+content-review-verdict`、skill assign (C02) = `content-review-verdict+coverage`、sub-agent (C03-C05) = `content-review-verdict+verdict`、slash-command (C06) = `content-review-verdict+test`、hook (C07) = `content-review-verdict+test`、script (C08/C09/C10/C11/C12/C13/C14) = `content-review-verdict+coverage`。
- harness_coverage は component ごとの evidence (P11) で裏付けられる実測値であり、契約 (P02) と実測 (本フェーズ) の 2 段階に分離する。C09 (root resolver)・C10 (idempotent init)・C11 (atomic promotion) は multi-repo isolation fixture (受入確認表) で、C12 (staging validator) は staging fixture validation test で実測される。

## 成果物
- 全 14 component の harness coverage 実測レポート。

## スコープ外
- 受入判定 (P07)。

## 完了チェックリスト
- [ ] 全 14 component が `harness_coverage.min >= 80` を実測する。
- [ ] `kind_pass` 文字列と実測項目 (criteria-test/content-review-verdict/coverage/test/verdict) が整合する。
- [ ] two-repo parallel、host project-root/repository_id不一致、absolute/traversal/symlink escape、broken/moved content link、host broken-harness-link preflight、init twice、digest mismatch、atomic successを検証する。

## 参照情報
- `io-contract.md` (harness_coverage 契約表)。
- 対象 component C01-C14。
- 後続 P07 (acceptance-criteria)。
