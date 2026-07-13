---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
依存DAG top-sort順 (C01/C08/C11→C06→C02/C05→C03/C04/C07→C09→C10) で全11 componentを実体化し、全acceptance contractをGreenにする。

## 背景
build順序は依存top-sortに従う。C03だけをC02配下へ置き、C05/C06/C07はplugin-rootへhoistする。既存capability A/Bはowner matrix内のadditive wiringだけを許可する。

## 前提条件
- P04 で criteria が Red (未達) として確定している。
- `handoff-run-plugin-dev-plan.json` の routes が builder/build_kind/build_args/build_target を保持している。
- 後段 builder (`run-skill-create`/`run-build-skill`/`plugin-scaffold`/`parent-skill-build`) が利用可能。

## ドメイン知識
- top-sort: C01/C08/C11 → C06 → C02/C05 → C03/C04/C07 → C09 → C10。C09はC07/C11に依存し、C10 command が唯一の明示入口になる。
- parent-skill-build/plugin-scaffoldはcontract-only builder語彙。C03/C05/C06/C07の全script routeで`build-script-route.py` scaffold/verify後にdomain implementationとroute reportを必須化する。
- **change owner matrix**: C08/C06はknowledge-sync manifestへrelation→graph append、C07はgoal-setting manifest/info-collector/resource mapへconsult append。P02 owns manifest draft、P09 owns EVALS/tests/composition/package parity、P12 owns README/RUNBOOK/CHANGELOG。既存entry/phase/gateは変更しない。
- run-skill-feedbackはcomponent IDを持たず既配備symlinkの維持検証のみ。現C05はharness artifact indexerであり別物である。

## 成果物
- 全11 componentのbuild_target実体。
- P04 criteria の Green 化。

## スコープ外
- harness カバレッジの拡充・実測 (P06)。
- purpose 受入の最終判定 (P07)。
- SSOT 重複の解消 (P08・実装段階では許容し次段でリファクタリングする)。

## 完了チェックリスト
- [ ] 全11 componentがtop-sort順で実体化され、全script routeのexecutor dry-run・domain implementation・route reportがPASSする。
- [ ] C02/C09 の feedback_contract.criteria (P04 で Red だったもの) が実装後に Green になっている。
- [ ] change owner matrix内はadditive parity、matrix外はdiff空、既存契約は回帰PASS。
- [ ] (検証専用・非 buildable) run-skill-feedback の symlink 配備が本 phase で変更されていない (現状維持) ことを確認している。

### 受入例
依存route完了後に各script executor dry-run、domain implementation、route reportが順にPASSする。

### 事前解決済み判断
scaffold生成だけではroute doneにしない。surface変更はowner matrix内のadditive差分に限る。

## 参照情報
- `component-inventory.json` (依存 DAG・build_target・builder)。
- `handoff-run-plugin-dev-plan.json` (routes・build_args)。
- 対象 component C01-C11、後続 P06。
