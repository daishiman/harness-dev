---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 完了
gate_type: tdd-refactor
entities_covered: [C02]
applicability:
  applicable: true
  reason:
---

# P08 — refactoring (改善)

## 目的
C02 が導入する vendoring (prompt-creator の verify-completeness.py コアロジックの harness-creator 側 byte 一致コピー) による SSOT 重複を、既存の ssot_dedup 機構 (lint-ssot-duplication.py) の枠組みで整理する。

## 背景
skill-intake の vendor/ + scripts/_vendor.py + scripts/validate-plugin-vendor.py という先行事例に倣い、意図的な複製は単一正本 + parity 検証によって管理する方針を踏襲する。

## 前提条件
P05 で C02 の build_target と vendor ターゲットが確定していること。

## ドメイン知識
component-inventory.json の plugin_level_surfaces.vendor の必要性宣言と index.md の ssot_dedup ブロックが整合していなければならない。

## 成果物
C02 の --check-vendor-parity モード仕様 (vendor 元/vendor 先の対応関係の確定記述)。

## スコープ外
C02 以外の8 component は複製を持たないため refactoring 対象外。

## 完了チェックリスト
- [ ] vendor 元 (plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py) と vendor 先 (plugins/harness-creator/vendor/prompt-creator/verify-completeness.py) が1対1で明記されている
- [ ] parity 検証手段 (--check-vendor-parity) が component-inventory.json 上で宣言されている

## 参照情報
component-inventory.json (plugin_level_surfaces.vendor)、plugins/skill-intake/scripts/_vendor.py
