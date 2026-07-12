---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P07 — acceptance-criteria (判定)

## 目的
goal-spec.json checklist C1-C12 全項目の done 判定基準を実測結果と突合し、本 plan の受入可否を判定する。

## 背景
checklist は本 plan の要件正本であり、各項目に `verify_by`(script/reasoning/test)が付与されている。verify_by=script の項目は決定論ゲートの exit0、reasoning の項目は phase 記述の存在確認、test の項目は matrix-coverage の実行結果で判定する。

## 前提条件
Phase06 テスト実行完了。

## ドメイン知識
(引用)index.md ## ドメイン知識。差分なし。

## 成果物
C1-C12 各項目の合否記録(11 ゲート実行結果を含む)。

## スコープ外
checklist 項目自体の追加・変更(goal-spec.json は本 plan の入力として固定し、追加要件は次サイクルへ回す)。

## 完了チェックリスト
- [ ] C1(component-inventory 分解 + plugin-level surfaces 採否)が check-surface-inventory.py exit0 で裏付けられている
- [ ] C2(quality_gates + harness_coverage 携帯)が check-spec-gates.py exit0 で裏付けられている
- [ ] C3(handoff routes 1:1)が check-build-handoff.py exit0 で裏付けられている
- [ ] C4(index.md P01-P13 + plugin_meta + 受入確認 + role 表)が verify-index-topsort.py exit0 で裏付けられている
- [ ] C5(DAG 非循環・unassigned 0 件・矢印方向統一)が detect-unassigned.py / validate-task-graph.py exit0 で裏付けられている
- [ ] C6(単一truth設計・自己反映が完了gate)が phase-02-design.md H3 節の記述で裏付けられている
- [ ] C7(write_scope 並列衝突機構不要 + 既存 fail-closed の正しい再framing)が phase-02-design.md H1/H2 節の記述で裏付けられている
- [ ] C8(consumption verifier の機械検査埋め込み + cross-surface dependency graph knowledge consult)が phase-02-design.md H4/H6 節 + C04/C08 実装で裏付けられている
- [ ] C9(既存 build-pipeline task-graph 非改変境界)が index.md 受入確認の記述で裏付けられている
- [ ] C10(default/opt-in 軸=engine 選択の一貫性)が phase-02-design.md H5 節の記述で裏付けられている
- [ ] C11(11 ゲート全 exit0 + core/拡張ラベル内訳の単一表)が本 plan 最終実行ログと index.md ## ゲート一覧 で裏付けられている
- [ ] C12(46 行 matrix 焼き先反映 + elegant-review C1-C4 PASS 設計意図の分離)が check-spec-matrix-coverage.py exit0 と phase-03-design-review.md LR1-LR4 の分離記述で裏付けられている

### 受入例
- 満たす例: C1-C12 各項目が対応ゲートの実行ログ(コマンド+exit code)、または verify_by=reasoning 項目は対応 phase の節見出し(ファイル名+H見出し)への参照によって 1 対 1 で裏付けられる。
- 満たさない例: 「概ね満たしている」という曖昧判定のみで、個別ゲート結果や参照節への言及がない。

### 事前解決済み判断
- 分岐点: verify_by=reasoning の項目(C6-C10)を機械ゲートなしにどう判定するか → 判断: 対応する `phase-02-design.md` の該当 H 節見出し(H1-H6)の存在 + 非空本文の目視確認をもって裏付けとし、機械ゲートに依らない項目でも参照箇所を phase-02-design.md の節番号で固定する(check-downstream-harness.py の非空本文検査と同型の規律)。

## 参照情報
- `goal-spec.json` checklist C1-C12
- 本 index.md ## 受入確認
