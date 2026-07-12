---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 完了
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09]
applicability:
  applicable: true
  reason:
---

# P07 — acceptance-criteria (判定)

## 目的
goal-spec.json の C1-C8 各項目が本 plan 成果物のどの部分で充足されるかを1対1で確定し、index.md の受入確認セクションへ反映する。

## 背景
check-requirements-coverage.py は index.md の完了チェックリスト/受入確認セクション内で C1..C8 の id 出現を境界安全 (C1 が C11/C01 に誤マッチしない) に走査する。

## 前提条件
P05/P06 が完了していること。

## ドメイン知識
境界安全な id マッチング正規表現の挙動 (前後に数字が連続しないことを要求)。

## 成果物
index.md 内での C1-C8 対応表 (受入確認セクション)。

## スコープ外
component レベルの acceptance (quality_gates.evaluator 等の値域判定) は P09/P10 の責務。

## 完了チェックリスト
- [ ] C1-C8 全てが index.md の完了チェックリストまたは受入確認セクション本文に出現する

## 参照情報
goal-spec.json、index.md、scripts/check-requirements-coverage.py
