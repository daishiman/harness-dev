---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
goal-spec checklist C1-C8 のそれぞれについて、担当 component・検証方法・P06 のテスト結果を対応付けた Requirements Traceability Matrix (RTM) を確定し、全項目が過不足なく満たされているかを判定する。

## 背景
P01 で C1-C8 を phase へ対応付け、P02-P06 で設計・レビュー・テスト設計・実装仕様・実行手順を積み上げてきた。本 phase はその総仕上げとして、checklist 単位で「どの component のどの criterion で確認されるか」を一意に確定し、漏れ (orphan checklist item) が無いことを判定する。

## 前提条件
- P06 のテスト実行手順が確定している。
- `component-inventory.json` の全 component (C01-C04) が `feedback_contract.criteria` または `checklist` を持つ。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **RTM (Requirements Traceability Matrix)**: 要件 id (goal-spec checklist) → 担当 component → 検証方法 → 検証結果、の一意対応表。

## 成果物

| checklist id | verify_by | 担当 component | 検証方法 |
|---|---|---|---|
| C1 | test | C01 (skill), C02 (script) | `interview.json.procedure` (mode=detailed) が拡張スキーマの validate PASS。C01 の IN1 criterion |
| C2 | test | C01 (skill) | 抽象回答/未回答連続入力で `overview_fallback` へ切替、ヒアリングが停止しない。C01 の R2-procedure-fallback 責務と OUT3 criterion (verify_by=test, P11 trial シナリオ 2/3 が証跡収集) |
| C3 | test | C03 (skill), C04 (script) | purpose/procedure 片方欠落時に `intake.json` が生成されず下流ハンドオフへ進めない。C03 の OUT1 criterion |
| C4 | reasoning | (plan phase 自体) | P01 のギャップ一覧 (G1-G7) と改善要否記載 |
| C5 | reasoning | `plugin_level_surfaces.references_config_assets` | root `references/handoff-contract.md` への `sections.6_five_axes_summary.procedure` 参照契約追加 |
| C6 | test | C01 (skill) | 同一回答パターンを複数回入力し常に同じ経路が選ばれる。C01 の OUT1 criterion |
| C7 | test | C01 (skill), C02 (script), C03 (skill), C04 (script) | handoff 対象 as-is フィールド (`procedure.*` と `five_axes.rows[name="真の課題"].content`) への to-be 語彙混入を C02 拡張の contamination check が検出し非 0 exit、Phase9 (C03)/Phase9 拡張ゲート (C04) が FAIL する。C01 の IN2 criterion |
| C8 | reasoning | C01 (skill) | 質問設計・記録指示が相手固有の具体性 (固有名詞/実例/頻度/関与者) を伴う回答を促す設計になっているかを独立レビューが確認する。C01 の OUT2 criterion (verify_by=elegant-review) |

- 上表が本 plan の RTM であり、goal-spec checklist の全 8 項目 (C1-C8) が component または plan phase 成果物のいずれかに一意対応し orphan が無いことを確認した状態。

## スコープ外
- RTM に基づく実際のテスト実行・合否判定そのもの (build 後に build 側が実施。本 phase は対応表の確定のみ)。

## 完了チェックリスト
- [ ] goal-spec checklist C1-C8 の全項目が RTM 上でいずれかの component/phase 成果物に対応付けられている (orphan 0 件)。
- [ ] test 系 (C1/C2/C3/C6/C7) が component の `feedback_contract.criteria` id (IN1/OUT1/IN2/OUT2 等) と紐づいている。
- [ ] reasoning 系 (C4/C5/C8) が該当 phase (P01/P02) の本文セクションまたは C01 の OUT2 criterion を参照している。

## 参照情報
- `plugin-plans/skill-intake/goal-spec.json` (checklist C1-C8 の正本)。
- P01 (C4 ギャップ一覧の所在) / P02 (C5 surface 判定・C7/C8 設計の所在)。
- 後続 P08 (RTM 確定後、実装仕様の改善余地をリファクタリング観点で見直す)。
