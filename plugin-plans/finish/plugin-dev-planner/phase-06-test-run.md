---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
P05 の実装 (build 後) に対して P04 で設計したテストケースおよび既存テストスイート全件を実行し、C1-C12 の checklist が全て `done: true` へ遷移する観測可能な証跡を得る (C8/C12 は verify_by=reasoning のため fork evaluator 実行による plan-findings.json 出現をもって証跡とする)。

## 背景
本 phase は build 後に後段プロセスが実施する検証手順の仕様であり、本 plan (L3) 自体はテストを実行しない。build 実行者 (run-skill-create の Edit build・assign-plugin-plan-evaluator の R1-evaluate.md 実行) がこの仕様に従って検証する。

## 前提条件
- P05 の実装設計に基づき、実 `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/` と `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/` へ Edit 差分が反映されている (build 後)。
- P04 のベースライン (既存テスト件数) が記録されている。

## ドメイン知識
- **実行対象**: `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/` および `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/tests/` の pytest 全件、`check-spec-matrix-coverage.py --self-test`、新規/拡張した各 script の `--self-test` (存在する場合)、新規 `check-generative-fidelity.py`/`check-downstream-harness.py` の embedded fixture テスト。
- **合否判定**: C1/C2 は新規 fixture を含む対象テストファイルの exit0、C3 は `check-harness-coverage-selfcheck.py` の embedded fixture テストと `test_ci_integration.py` の新規テスト関数の exit0、C4 は pytest 全件が P04 ベースラインの件数以上で exit0、C5 は `check-spec-matrix-coverage.py --self-test` の exit0。
- **C6/C7 の合否判定**: `check-generative-fidelity.py <PLAN_DIR>` を実行し、denylist 10 語の非検出 (WARN 0 件) と `_PHASE_SECTION_HINT` 完全一致の非検出 (FAIL 0 件) を確認する (本 plan 自身の phase 本文が対象・自己適用)。
- **C10/C11 の合否判定**: `check-downstream-harness.py <PLAN_DIR>` を実行し、13 phase 全てで `### 受入例`/`### 事前解決済み判断` サブ節が要件区分 (フル/縮小) に応じて存在することを exit0 で確認する。
- **C8/C12 の合否判定**: `assign-plugin-plan-evaluator` の R1-evaluate.md を fork context で実行し、`plan-findings.json` の `findings[]` に `bucket: "layer-a-generative-fidelity"` (C8) と `bucket: "layer-b-downstream-harness"` (C12) の記録が genuine 判定として出現することを確認する (pytest ではなく実行証跡で確認する verify_by=reasoning 項目)。
- **CI 実行文脈の非包含に注意**: `run-ci-checks.sh` は pytest を含まないため、本 phase の pytest 実行は push 前に開発者が直接実行する手順として明示する (既知の運用制約)。

## 成果物
- 各対象テストの実行結果 (exit code とテスト件数の記録)。
- `check-generative-fidelity.py`/`check-downstream-harness.py` の自己適用実行結果。
- `plan-findings.json` の C8/C12 bucket 出現記録。

## スコープ外
- テストの新規追加 (P04/P05 で確定済み・本 phase は実行のみ)。
- 失敗時の原因調査・修正 (見つかった場合は P05 へ差し戻す)。

## 完了チェックリスト
- [ ] C1/C2 対象テストファイルが exit0 で green。
- [ ] C3 の self-check fixture テストと governance-check.yml ステップ存在テストが exit0 で green。
- [ ] pytest 全件が P04 ベースライン件数から退行なく exit0 で green (C4)。
- [ ] `check-spec-matrix-coverage.py --self-test` が exit0 (C5)。
- [ ] `check-generative-fidelity.py` が本 plan 自身に対して WARN/FAIL 0 件 (C6/C7)。
- [ ] `check-downstream-harness.py` が本 plan 自身に対して exit0 (C10/C11)。
- [ ] fork evaluator 実行の `plan-findings.json` に layer-a-generative-fidelity/layer-b-downstream-harness bucket が出現している (C8/C12)。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: P04 で RED (未実装で失敗) と確認済みだった C6/C7/C10/C11 の新規テストが、P05 実装後の再実行で GREEN へ遷移したことが実行ログ (実行前 exit1・実行後 exit0 の対比) として記録され、かつ既存 388+ 件の pytest が P04 ベースライン件数を下回らず exit0 で通過する。
- 満たさない例: 新規テストを「実装したので通るはず」として実行ログを取らずに green 扱いにする、または既存 388+ 件のうち一部が red のまま件数を据え置いて「実行済み」と記録する (RED→GREEN の遷移証跡が無い状態を green と誤認する)。

### 事前解決済み判断
- 分岐点: C8/C12 (verify_by=reasoning) の証跡を、pytest の green 件数集計に混ぜて 1 つの合否数値にするか → 判断: 混ぜない。pytest 件数カウンタは C1-C7/C9-C11 の機械検証専用とし、C8/C12 は `plan-findings.json` の bucket 出現有無という別カウンタで扱う (二層分離を合否表現の数値レベルでも維持し、reasoning 系の合否を機械カウンタへ混入させて実質を薄めることを避ける)。

## 参照情報
- `phase-04-test-design.md` / `phase-05-implementation.md`。
- `feedback_prompt: run_ci_checks_excludes_pytest` (push 前 pytest 直接実行の運用制約)。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/prompts/R1-evaluate.md`。
- 後続 P07 (acceptance-criteria)。
