---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的

P04 matrix を実行し、機能・negative・concurrency・trust・freshness の fresh evidence を得る。

## 背景

plan shape の PASS と runtime contract の PASS は別物である。特に target event preserve と trust 未承認 non-run は実測 fixture が必要。

## 前提条件

- P05 実装完了。
- test command/runner/version が記録済み。

## ドメイン知識

- test layer: root reflector / C02 / C01 / C03 / C05 / C04 / integration。
- failure は first failing layer へ帰属させ、下流を偽陰性として数えない。
- runtime install/trust test は P11 user gate まで pending 可だが PASS 扱いしない。

## 成果物

- focused/full test log、coverage JSON、concurrency log、negative fixture diff。
- pending runtime evidence ledger。

## スコープ外

- user approval のない install/trust mutation。
- failing test の仕様変更による回避。

## 完了チェックリスト

- [ ] C1-C10 test matrix の local 実行対象が全 PASS。
- [ ] target unknown event が保持され、managed source unknown event が block される。
- [ ] 同時2 session/二重実行/timeout/lock recovery が PASS。
- [ ] unsupported/global/beads/trust-store negative test が PASS。
- [ ] pending runtime evidence が present と混同されない。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: command、exit code、case count、artifact path、timestamp が揃う。
- 満たさない例: 「テスト済み」だけで raw log がない。

### 事前解決済み判断

- runtime trust 未実行は `pending_user_gate` と記録し local PASS に含めない。

## 参照情報

- P04 test matrix
- `eval-log/` planned evidence paths
