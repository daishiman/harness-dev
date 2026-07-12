---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
C01/C03 の `feedback_contract.criteria` (IN1/OUT1/IN2/OUT2) を具体的な受入テストケースへ落とし込み、goal-spec C1/C2/C6/C7 (いずれも `verify_by: test`) の受入テスト仕様を、実装前に red (失敗する期待値を明示した状態) として設計する。

## 背景
本 plan は実装を含まないため、本 phase の成果物は「後段 build 時に実装者が満たすべきテストケース仕様」である。TDD の red フェーズに相当し、後続 P05 (実装仕様) はこのテストケースを満たすことを目標に記述される。

## 前提条件
- P03 の design-gate が PASS している (component-inventory.json が確定)。
- C01/C03 の `feedback_contract.criteria` (IN1/OUT1/IN2/OUT2) が component-inventory.json に定義済みである。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **tdd-red**: 実装前にテストケースを仕様化し「まだ実装がないため失敗する」ことを前提に設計するフェーズ (本 plan では実装しないため、テストケースの仕様化のみを成果物とする)。

## 成果物
- **C1 詳細抽出テストケース**: ユーザーが具体的な手順を発話する入力に対し、`interview.json.procedure.mode=detailed` かつ `steps[]` 各要素が `action/input/output/tool/frequency` 非空で構造化され、拡張版 `output.schema.json` の validate が PASS するケース。
- **C2 フォールバックテストケース**: procedure 軸で 2 連続抽象判定/未回答となる入力に対し、`procedure.mode=overview_fallback` かつ `difficulty_flag=true` かつ `overview` (`step_count_estimate`/`participants`/`frequency`) が非空となり、ヒアリングが停止しないケース。
- **C6 決定論境界値テストケース**: 「抽象回答 1 回→具体的回答」(フォールバックへ切り替わらない) と「抽象回答 2 回連続」(フォールバックへ切り替わる) の境界を明示し、同一パターンの再入力で常に同じ経路が選ばれることを確認するケース。
- **C3 ハンドオフゲートテストケース**: procedure または purpose (true_purpose) のいずれかを意図的に欠落させた `interview.json`/`intake.json` 入力に対し、`validate-procedure-completeness.py` (C02) または `quality_gate.py` 拡張 (C04) が非 0 exit となり Phase9/10/11 へ進めないケース。
- **C7 混入検出テストケース**: handoff 対象の as-is フィールド (`interview.json.procedure.steps[]/overview` と `interview.json.five_axes.rows[name="真の課題"].content`) へ to-be 語彙 (例: 「本来はこうすべき」「もっと効率的な方法は」等) を意図的に含む `interview.json` 入力に対し、`validate-procedure-completeness.py` (C02) 拡張の contamination check が `contamination.detected=true` を返し非 0 exit となり Phase9 (C03) が FAIL するケース。raw 会話ログ中の to-be 発話は検査対象ではなく、C01 が as-is handoff フィールドへ保存しないことで混入なし PASS とする。対照として handoff 対象 as-is フィールドに to-be 語彙を含まない入力では `contamination.detected=false` かつ exit0 となるケース。

## スコープ外
- テストの実装 (pytest 等の実コード化) は本 phase では行わない。実装は後段 build (`run-skill-create`) へ委譲する。
- C4 (ギャップ洗い出し, verify_by=reasoning) / C5 (handoff-contract.md 追加, verify_by=reasoning) / C8 (相手固有の具体性記録, verify_by=reasoning) はテストケースでなく reasoning/elegant-review 検証であるため本 phase の対象外 (P01/P02/P07 で扱う)。

## 完了チェックリスト
- [ ] C1/C2/C6 (verify_by=test) の受入テストケースが入力/期待出力を伴って明記されている。
- [ ] C3 のハンドオフゲートテストケース (purpose/procedure 片方欠落時に非 0 exit) が明記されている。
- [ ] C7 の混入検出テストケース (to-be 語彙混入時に非 0 exit、非混入時に exit0) が明記されている。
- [ ] 各テストケースが C01/C03 の `feedback_contract.criteria` (IN1/OUT1/IN2/OUT2) のいずれかに紐づいている。

## 参照情報
- `plugin-plans/skill-intake/goal-spec.json` (C1/C2/C3/C6/C7 の checklist 定義元)。
- `plugin-plans/skill-intake/component-inventory.json` (C01/C03 の feedback_contract.criteria)。
- 後続 P05 (このテストケースを満たす実装仕様を記述する)。
