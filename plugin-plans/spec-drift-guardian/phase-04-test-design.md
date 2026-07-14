---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計 / tdd-red)

## 目的
loop 系 skill (C01 run-spec-drift-triage / C02 run-rubric-sync) の `feedback_contract.criteria` (inner/outer) と、それぞれの独立検証 sub-agent (C03 spec-impact-verifier / C04 rubric-sync-auditor) が再検査する受入観点を、実装に先立って red 状態 (未実装のため必ず失敗する) のテストとして確定する。

## 背景
影響判定・更新は完全diffに対する4軸+semantics期待値と、未承認時変更0件/承認時allowlist限定適用/post-image検証を先に固定しないと基準が後付けで緩む。tdd-redでIssue #17の実commit pairをpinする。

## 前提条件
- P03 design-gate が合格している。
- C01/C02 の `feedback_contract.criteria` (各 inner 1 件以上・outer 1 件以上) が component-inventory.json に定義されている。
- Issue #17の完全commit pair (base `da6d4e7…`, head `6ddd645…`) をfixture化できる。

## ドメイン知識
- criteria の `verify_by`: script (決定論変換の必須キー欠落検査) / test (既知正解セットに対する精度検証)。
- purpose-traceability: criteria のテキストは各 component 自身の goal/checklist 語彙から導出する (グローバル goal-spec ではなくコンポーネント単位)。
- C03/C04 の独立検証は、C01/C02 の出力に対する「独立 context での再検査」であり、C01/C02 自身のテストとは別軸の監査観点として設計する。

## 成果物
- C01 の criteria IN1 (script: hunk 構造化+影響フィールドマッピングの必須キー欠落 0 件) / OUT1 (test: 既知正解セットに対する誤検出/見逃し無し)。
- C02 criteriaは提案必須キーに加え、未承認/監査FAIL/hash drift/allowlist逸脱は変更0件、承認済みcaseは適用後hash/validator一致を固定する。
- C03/C04は独立verdict artifactをemitし、C10が不一致を拒否する観点を固定する。
- 共有 script (C08 parse-spec-diff.py / C09 map-field-impact.py / C10 check-triage-complete.py / C11 aggregate-issue-diffs.py) の決定論 unit test を tests_min≥80 で設計する: 必須キー欠落・exit_code 契約 (0/1/2)・空入力/積層 diff の境界を赤テストで固定する。これで P07 受入 (C1→C08 の hunk 構造化、C4→C07+C10 の close ゲート) の裏付けが entities_covered から連続する。
- C5 fixture matrixはIssue #17完全diffから settings追加、`/doctor`、plugin MCP matcher、hook transcript、sub-agent挙動を別case化し、name/type/required/enum/semanticsとno-impactを含める。truncated preview、missing commit、digest mismatchもfail-closed caseにする。

## スコープ外
- criteria を満たす実装そのもの (P05 の責務)。
- criteria の実行結果判定 (P06 test-run の責務)。

## 完了チェックリスト
- [ ] C01/C02 それぞれに inner 1 件以上・outer 1 件以上の criteria が定義され `validate_criteria` の必須キー (id/loop_scope/text/verify_by) を満たす。
- [ ] criteria のテキストが各 component 自身の goal/checklist 語彙と重なり (purpose-traceability)、汎用ゲート文言の言い換えになっていない。
- [ ] C03/C04 の監査観点 (見逃し/誤検出、反映漏れ/過剰変更) が component の description に明記されている。
- [ ] C08/C09/C10/C11のunit testとIssue #17完全fixture matrixが設計され、proposal-only close拒否・承認済みapply・独立no-changeのcaseを含む。

## 参照情報
- `component-inventory.json` (C01-C04 の feedback_contract/description、C08/C09/C10/C11 の script 契約 tests_min)。
- `EVALS.json` (C5 の既知正解セット定義、P05/P06 で使用)。
- 後続 P05 (この赤テストを green にする実装)。
