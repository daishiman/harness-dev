---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 完了
gate_type: none
entities_covered: [C01, C09]
applicability:
  applicable: true
  reason:
---

# P12 — documentation (文書)

## 目的
C01 の新規 reference 文書 (subagent-hybrid-format.md) と C09 のフロー配線内容が、後続の実 build 時に迷わず参照できる形で index.md/component-inventory.json に文書化されていることを確認する。

## 背景
本 skill の成果物はタスク仕様書であり実装そのものではないため、文書としての自己完結性 (self-containment、build_target が "plugins/" で始まる等) が P13 リリース判定の前提となる。

## 前提条件
P07 (acceptance-criteria) が確定していること。

## ドメイン知識
check-runtime-portability.py の自己完結制約 (build_target は "plugins/" で開始し ".." セグメントを含まない)。

## 成果物
index.md 最終版 (7必須セクション + plugin_meta + フェーズ一覧 + 完了チェックリスト + 受入確認)。

## スコープ外
subagent-hybrid-format.md 本文そのものの執筆は後続 build (C01 の build_target 側) の作業であり、本 plan の成果物ではない。

## 完了チェックリスト
- [ ] index.md が7必須セクションを全て備えている
- [ ] フェーズ一覧が P01..P13 昇順で重複/欠落なく列挙されている

## 参照情報
index.md、references/io-contract.md (INDEX_REQUIRED_SECTIONS)
