---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C06]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component (C01: run-plugin-dev-plan 更新 / C06: run-skill-create 更新) の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば断線が解消したと言えるか」を purpose 由来で先に固定できる。汎用ゲートの言い換え (lint exit0 / 4 条件 PASS) に退化した criteria は E1/E2 の実際の消費経路を一度も受入検証しないため、goal/checklist 語彙由来であることを設計時に担保する (`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C06 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点 (frontmatter/lint exit0)、outer=build 後の受入観点 (適用例/非適用例の両方が受入テストで確認できること)。
- Red = 実装前に criteria が未達であること (実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が goal/checklist の語彙を参照していること (汎用ゲートの言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C01/C06 の `feedback_contract.criteria` (inner+outer 各 1 件以上) が inventory に確定した状態。
- C8/C9 golden example fixture 一式 (`fixtures/c8-new-flow/`・`fixtures/c9-update-flow/`。P07 の golden example が参照する plan_dir 配下 fixture) が作成された状態。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの設計・実行 (P06・kind 別観点はそちらで扱う)。
- 非 skill component (C02-C05,C07-C11) の受入 (output_contract/purpose ベースで P07 が判定)。

## 完了チェックリスト
- [ ] C01/C06 の criteria が purpose 由来で inner/outer を各 1 件以上持つ (汎用ゲート言い換えに退化していない)。
- [ ] C01 は「intake_json 提供時に purpose/background/goal へ反映され goal-spec.source_intake が記録される」「--mode update + improvement-handoff.json 提供時に source_improvement が記録される」を outer criterion に持つ。
- [ ] C06 は「brief_path 提供時に再ヒアリングなしで build が開始する適用例と、未提供時に既存 dialog へ fallback する非適用例の両方」を outer criterion に持つ。
- [ ] 実装前は criteria が未達 (Red) であることが確認できる。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01 (run-plugin-dev-plan 更新) / C06 (run-skill-create 更新)。
- 後続 P05 (implementation)。
