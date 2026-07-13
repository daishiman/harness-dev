# Phase 07 — 受け入れ基準レポート

feedback_contract の criteria を両 SKILL.md へ配線し、機械被覆を確立した。

## run-intake-interview (C01) criteria

| id | loop | verify_by | 対象 |
|----|------|-----------|------|
| IN3 | inner | script | procedure 完全性 (validate-procedure-completeness) |
| IN4 | inner | script | contamination 非混入 (C7) |
| OUT2 | outer | elegant-review | 相手固有の具体性記録 (C8) |
| OUT3 | outer | test | フォールバック発火時の継続 (C2) |

(既存 IN1/IN2/OUT1 は保持)

## run-intake-finalize (C03) criteria

| id | loop | verify_by | 対象 |
|----|------|-----------|------|
| IN3 | inner | script | dual-gate (validate-procedure-completeness + quality_gate --require-procedure) |
| OUT2 | outer | test | purpose/procedure 欠落時にハンドオフ遮断 (C3) |

(既存 IN1/IN2/OUT1 は保持)

## 被覆スナップショット同期

criteria 追加に伴い 2 つの派生スナップショットを再生成:
1. `tests/criteria/criteria_roster.py` ← `build_criteria_roster.py --write`
2. `eval-log/llm-coverage.json` ← `validate-llm-coverage.py --all` (**roster 再生成後**に実行=依存順序)

`test_roster_matches_discovery` / `test_llm_coverage_json_up_to_date` が fail-closed で drift を検出する設計のため、テストを緩めず生成物を正として追従させた。結果: 42 skill 平均 100.0% ≥ 80% 閾値。

## EVALS.json

run-intake-interview / run-intake-finalize の baseline entry (2026-07-05) を追加し、procedure 配線内容を note に記録。skill_intake_version 0.1.1→0.1.3。
