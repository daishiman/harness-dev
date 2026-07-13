---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了/PR・リリース)

## 目的
C1/C2/C3 の実装差分・C6/C7/C10/C11 の新規 script 2 本・C8/C12 の assign-plugin-plan-evaluator 拡張・governance-check.yml への repo-level 編集を PR としてまとめ、C4/C5/C9 の green 維持を CI で最終確認したうえでリリースする。

## 背景
plugin-dev-planner は distributable:false かつ NEVER_DISTRIBUTE denylist 対象のため、marketplace/bundle 経由の配布フローは対象外。リリースは repo 内 PR マージのみで完結する。

## 前提条件
- P10 の最終承認が完了している。
- P12 のドキュメント反映範囲が確定している。

## ドメイン知識
- **PR スコープ**: (1) `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-runtime-portability.py` の Edit、(2) 同 `check-build-handoff.py` の Edit、(3) 新規 `check-harness-coverage-selfcheck.py`、(4) 新規 `check-generative-fidelity.py` (C6/C7)、(5) 新規 `check-downstream-harness.py` (C10/C11)、(6) `assign-plugin-plan-evaluator/prompts/R1-evaluate.md` の C8/C12 判定ステップ追加、(7) 同 `schemas/plan-rubric.json` の semantic_checks (S3/S4) 追加、(8) `.github/workflows/governance-check.yml` の 1 ステップ追記 (open_issues 由来の repo-level 変更)、(9) `SKILL.md`/`references/io-contract.md` のドキュメント追記、(10) 対応する新規/拡張 pytest。
- **blocking release issue**: `handoff-run-plugin-dev-plan.json.open_issues[].id == GAP-GOVERNANCE-CI-001` は release 前に解消必須の repo-level CI gap である。PR スコープ 8 の governance-check.yml 追記が入っていない場合、C3 の受入は未達のため P13 は完了できない。
- **リリース前チェック**: `run-ci-checks.sh` (pytest 非包含に注意) + pytest 直接実行の両方を push 前に実施する。
- **配布不要の確認**: distributable:false のため `validate-plugin-completeness.py` の MK-001..004/BD-001/002 は非該当 (NEVER_DISTRIBUTE denylist の既存整合を維持するのみ)。

## 成果物
- PR (C1/C2/C3/C6/C7/C10/C11 実装 + C8/C12 プロンプト/schema 拡張 + governance-check.yml 編集 + ドキュメント追記 + テスト)。
- CI green の最終確認記録。

## スコープ外
- marketplace/bundle 登録 (distributable:false のため対象外)。

## 完了チェックリスト
- [ ] PR スコープ 10 項目が全て反映されている。
- [ ] `GAP-GOVERNANCE-CI-001` が PR スコープ 8 として解消され、handoff の open issue が release blocking で残っていない。
- [ ] `run-ci-checks.sh` と pytest 直接実行の両方が green。
- [ ] goal-spec.checklist C1-C12 全項目が done:true でマージされている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: PR 説明にスコープ 10 項目の対応関係が明記され、goal-spec.checklist の C1-C12 各 id が該当差分へトレース可能な状態で CI green のままマージされる。
- 満たさない例: PR 説明が「機械検出機能を追加」とだけ記述され、どの checklist id がどの差分に対応するか判別できない。

### 事前解決済み判断
- 分岐点: C1-C5 分と C6-C12 分を別 PR に分割するか単一 PR にまとめるか → 判断: 単一 PR にまとめる (両者は同一 goal-spec 改訂・同一 plan の反映であり、分割すると C9 の退行防止確認が二重の CI 実行を要し運用が煩雑になるため)。

## 参照情報
- `phase-12-documentation.md`。
- `.github/workflows/governance-check.yml`。
- `handoff-run-plugin-dev-plan.json`。
