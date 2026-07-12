---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C08, C09, C10, C11, C12]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
C01のcriteria IN1/IN2/OUT1/OUT2とC08-C12のnegative testsを実装前にRedで固定する。

## 背景
TDD 原則により実装 (P05) に先立って受入判定基準を固定する。criteria 対象は C01 のみである: C02 (`assign-system-dev-plan-evaluator`) は `skill_kind=assign` であり `FEEDBACK_LOOP_SKILL_KINDS` (run/wrap/delegate) に含まれないため `feedback_contract` を構造上省略する (P02 で確定済みの設計判断)。

## 前提条件
- P03 の design-gate が承認済み。
- C01 の `feedback_contract.criteria` (IN1/IN2/OUT1/OUT2) が `component-inventory.json` に定義されている。

## ドメイン知識
- IN1 (inner loop, `verify_by: script`): `check-implementation-readiness.py` が system-spec-harness 確定成果物の必須章欠落を送信前検証し欠落 0 件。
- OUT1 (outer loop, `verify_by: test`): implementation_readiness=complete の入力から生成した task-spec と task-graph が dev-graph の tasks/ グラフノード登録形式で全件検証可能なことを受入テストが確認する。
- IN2: host project-root不一致、repository_id不一致、absolute/traversal/root外symlink/別repo/broken content linkを拒否し、broken harness linkはhost launcher fixtureが起動前検出する。
- OUT2: repo-A/repo-B並行fixtureでcontent/state/cache/lockが交差せず、init再実行が既存docsを上書きしない。
- promotion test: digest mismatch/readiness incomplete/evaluator FAILでcurrent pointer不変、全PASS時だけatomic receiptを出す。
- registration test: promoted task node fixtureが現行dev-graph schemaの全必須fieldを満たし、publication intent、空linkage/execution arrays、linked-PR completion=in_progress、`status=active`、object型source_lineage、`tasks/` pathを検証する。旧payload、空object issue_linkage、生成時done、feature branch先行完了を拒否する。
- criteria の purpose-traceability (`specfm.criteria_purpose_traceability_errors`): criteria の text が goal/checklist の語彙と重複せず汎用フォールバックへ退化していないことを機械検査する。

## 成果物
- C01 の criteria Red 確定記録。

## スコープ外
- C01 以外の component の実装 (P05)。
- criteria を Green にする作業 (P05 の責務)。

## 完了チェックリスト
- [ ] IN1/IN2/OUT1/OUT2とpromotion negative casesがRedである。
- [ ] criteria の purpose-traceability エラーが 0 件 (goal/checklist 語彙との重複が確認できる)。
- [ ] C02 が `feedback_contract` を省略する設計根拠 (skill_kind=assign) が記録されている。

## 参照情報
- `io-contract.md` (条件付き規律表・feedback_contract.criteria)。
- P02 の `component-inventory.json` (C01 の feedback_contract)。
- 後続 P05 (implementation)。
