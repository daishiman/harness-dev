---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
P10 の最終承認後、機械ゲートでは捕捉しづらい実運用シナリオ (別 plugin slug が混在する実際の handoff での挙動、governance-check.yml 実行時のステップ出力、生成された phase 本文が実際に下流 builder AI の着手を助けるか) を手動で検証し、証跡を残す。

## 背景
C1/C2 は fixture ベースの pytest で検証済みだが、実際の複数 plugin plan (例: `plugin-plans/ubm-goal-setting/` 等) を対象にした手動疎通も、機械検証の盲点を補う証跡として有用である。C6/C7/C10/C11 (機械層) は fixture で検証可能だが、C8/C12 (意味層) の genuine 判定は実際の fork evaluator 実行と実際の下流 builder AI 着手シナリオでの手動確認が最も説得力のある証跡となる。

## 前提条件
- P10 の最終承認が完了している。

## ドメイン知識
- **手動検証シナリオ 1 (C1)**: 既存の他 plan (target_plugin_slug が異なる plan_dir) に対し `check-runtime-portability.py <plan_dir>` を実行し、target_plugin_slug 不一致が無いことを確認する (誤検出が無いことの実データ実証)。
- **手動検証シナリオ 2 (C3)**: `check-harness-coverage-selfcheck.py` を実際に実行し、出力が EVALS.json の記述と整合することを目視確認する。
- **手動検証シナリオ 3 (C6/C7/C10/C11)**: `check-generative-fidelity.py`/`check-downstream-harness.py` を本 plan (plugin-plans/plugin-dev-planner) 自身の phase 本文に対して実行し、自己適用結果 (WARN/FAIL 0 件・全 phase での受入例/事前解決済み判断存在) を目視確認する (自己言及的検証・dogfooding)。
- **手動検証シナリオ 4 (C8/C12)**: 実際の下流 builder AI (別 context) に生成済み phase ファイル 1 本を渡し、追加質問なしで実装着手できたかを観察する。着手に追加質問が必要だった場合は C8/C12 の genuine 判定が捕捉すべき曖昧箇所として plan-findings.json への記録漏れを疑う。
- **証跡の形式**: 実行コマンドと出力の記録 (本 plan は L3 のため実行ログの物理配置は build 後の運用手順に委ねる)。

## 成果物
- 手動検証シナリオ 1-4 の実行証跡。

## スコープ外
- 新規 fixture の追加 (機械テストは P04/P05 で確定済み)。

## 完了チェックリスト
- [ ] シナリオ 1 (他 plan に対する C1 誤検出無し確認) が実施された。
- [ ] シナリオ 2 (C3 self-check の実データ実行) が実施された。
- [ ] シナリオ 3 (C6/C7/C10/C11 の本 plan 自身への自己適用実行) が実施された。
- [ ] シナリオ 4 (C8/C12 の下流 builder AI 実着手観察) が実施された。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: シナリオ 1-4 それぞれについて実行コマンド・出力・観察結果 (追加質問の有無を含む) が記録される。
- 満たさない例: シナリオ 4 (C8/C12) を「機械テストで代替可能」として省略する (verify_by=reasoning 項目は機械テストで代替できないため)。

### 事前解決済み判断
- 分岐点: シナリオ 4 で下流 builder AI が追加質問をした場合の扱い → 判断: 失敗ではなく発見事項として記録し、該当箇所を P05/P08 への差し戻し候補として open_issues に起票する (evidence phase は是正ではなく証跡収集が目的のため)。

## 参照情報
- `phase-10-final-review.md`。
- `plugin-plans/ubm-goal-setting/` (他 plan の実例)。
- 後続 P12 (documentation)。
