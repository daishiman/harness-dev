---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 で確定した C1/C2/C3 の設計 (関数シグネチャ拡張方針・C3 配線先確定) に加え、C6/C7/C10/C11 の機械層設計 (denylist 語彙集合・一致判定厳密度・埋め込み形式・適用強度分類) と C8/C12 の意味層設計 (findings 新規 bucket・conditions/schema 構造不変) が、既存契約 (46 行マトリクス・既存テスト・F8 install-portability・plan-findings.schema.json の conditions 固定) を破壊しないことを、設計提案者とは別 context の approver が承認する。

## 背景
本計画の環境ポリシーは proposer≠approver を要求する (design-gate/final-gate)。P02 の設計判断は goal-spec の C1-C12 解消という狭いスコープだが、既存の決定論ゲート (check-runtime-portability.py / check-build-handoff.py) や既存の評価器契約 (plan-findings.schema.json の conditions 固定・test_gate_parity.py の 9 parity テスト) への変更は誤ると既存 388+ 件のテストや 46 行マトリクス整合を破壊しうるため、実装着手前にゲートを設ける。

## 前提条件
- P02 の設計判断 (C1: `_target_plugin_slug`/`check_inventory` 拡張、C2: `_load_inventory_components`/`_check_manifest_entry_points_coverage`、C3: governance-check.yml block 追加 + 新規 self-check script、C6/C7: check-generative-fidelity.py の denylist 10 語+部分一致/完全一致、C10/C11: check-downstream-harness.py の完了チェックリスト拡張形式、C8/C12: R1-evaluate.md 拡張+findings 新規 bucket) が記録済みである。
- レビュー対象は設計のプローズ (関数シグネチャ・影響範囲) であり実コードではない。

## ドメイン知識
- **design-gate の判定基準**: (1) 既存関数への破壊的変更 (シグネチャの必須引数化・戻り値型変更) が無いこと、(2) 新規チェックが opt-in (target_plugin_slug=None 等の後方互換パス) を持つこと、(3) C3 の component 化しない判断 (governance-check.yml は plugins/ 外) が F8 制約と整合すること、(4) 既存 8 本の script_refs との no-split threshold 判定が妥当であること、(5) C8/C12 が plan-findings.schema.json の conditions (additionalProperties:false + required:["C1","C2","C3","C4"]) を変更せず findings[] の新規 bucket として表現されていること、(6) C6/C7/C10/C11 の機械検出が意味の正否判定 (Goodhart 化) を兼ねていないこと。
- **差し戻し条件**: 上記いずれかを満たさない設計は P02 へ差し戻し、再設計後に再度本ゲートを通す。

## 成果物
- 設計承認記録 (本ファイルの完了チェックリストに承認結果を反映)。

## スコープ外
- 実装そのもの (P05 へ委譲)。
- テストケースの具体的な列挙 (P04 へ委譲)。

## 完了チェックリスト
- [ ] C1/C2/C3 の設計が既存関数への後方互換拡張であり破壊的変更を含まないことを確認した。
- [ ] C3 の component 非化 (governance-check.yml 編集を open_issues 起票) が F8 (plugin 内自己完結) 制約と矛盾しないことを確認した。
- [ ] C6/C7/C10/C11 (機械層) が意味の正否判定を兼ねず、C8/C12 (意味層) が plan-findings.schema.json の conditions を変更せず findings[] 新規 bucket に留まることを確認した。
- [ ] 設計提案者 (P02) と別 context の approver によるレビューが完了し承認された。

### 受入例 (満たす例 / 満たさない例・判定行為ゲート簡略形)
- 満たす例: 上記 4 判定基準を全て確認したうえで承認 (または具体的な差し戻し理由付きで否認) の記録が本ファイルに残る。
- 満たさない例: 判定基準の一部 (特に C8/C12 の conditions 不変性) を確認せず承認したまま次フェーズへ進む。

### 事前解決済み判断
- 分岐点: C6/C7/C10/C11 のいずれかが意味判定寄りの記述になっていた場合の扱い → 判断: P02 へ差し戻し、機械層 (存在/語彙/文言一致) のみに縮小させたうえで再度本ゲートを通す (二層分離の維持を最優先する)。

## 参照情報
- `phase-02-design.md`。
- `references/plugin-creator-contract.md` (F8 install-portability)。
- `assign-plugin-plan-evaluator/schemas/plan-findings.schema.json` / `tests/test_evaluate_plan.py`。
- 後続 P04 (test-design)。
