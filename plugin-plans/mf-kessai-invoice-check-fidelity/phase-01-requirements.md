---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
既存プラグイン `mf-kessai-invoice-check` の改善増分「MF実績起点の発行漏れ確認」を目的ドリブンに要件化し、`goal-spec.json`(checklist C1-C13)を不変のアンカーとして確定する。artifact_class=`existing-plugin-update`・target_plugin_slug=`mf-kessai-invoice-check`・plan_dir=`plugin-plans/mf-kessai-invoice-check-fidelity` を固定する。

## 背景
既存 run-mf-invoice-report の前月↔今月比較レポートは、突合が契約(請求確認シート)起点・期待額駆動という単一の設計偏りを持つ。`lib/mfk_reconcile.py` の `find_mf_match(mode="monthly")` は金額不一致/名寄せ供給ゼロで evidence=None を返し、下流 `scripts/mfk_period_report.py` の金額列・issued 判定がこれに引きずられて症状①〜⑦(今月金額空白/MF無し情報のDB残存/金額一致なのに未☑等)を生む。この根本原因はユーザーとのブリーフィングで file:line 単位に確定済みであり、本フェーズはそれを `goal-spec.json` へ固定する。

## 前提条件
- 改善構想ブリーフ(症状①〜⑦・根本原因・D1/D2/D3 のユーザー確定事項)が入力として与えられている。
- `goal-spec.json` が既に生成済みで purpose/background/goal/checklist(C1-C13)/constraints(7 件)を保持している。
- 本フェーズは特定 component へ紐づかない(責務は goal-spec 確定・既存プラグイン境界の固定)。

## ドメイン知識
- 本改善は既存プラグインへの「増分」であり、ゼロから作り直す change ではない(既存 SSOT `lib/mfk_reconcile.py` の normalize/extract_names/has_end_basis/_classify_stopped/build_mf_index を再利用)。
- D1(新規は12ヶ月ルックバック裏取りでgate)/D2(今月MF供給なしは正常事情判定で残す)/D3(金額列はMF実績常時表示+差分フラグ)がユーザー確定済みの判定変更の全て。
- goal-spec は全 goal-seek 周回で不変のアンカー(target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。

## 成果物
- `goal-spec.json`(purpose/background/goal/checklist C1-C13/constraints/handoff_targets/max_loops=5)。
- target_plugin_slug=`mf-kessai-invoice-check` と plan_dir の確定値。

## スコープ外
- component 分解(P02 へ委譲)。
- 実コード変更(既存 `run-mf-invoice-reconcile`・年間前払い抑制・契約終了最終請求判定ロジックは温存し触れない)。
- 実装・build(P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、checklist C1-C13 が全て verify_by 付きで記載されている。
- [ ] target_plugin_slug=`mf-kessai-invoice-check` が確定し以降のフェーズがそれを参照できる。
- [ ] artifact_class=`existing-plugin-update` が明示され、既存プラグインの温存範囲(reconcile/年間前払い抑制/契約終了判定)が constraints に記録されている。

## 参照情報
- `goal-spec.json`(checklist C1-C13・constraints 7 件)。
- 改善構想ブリーフ(症状①〜⑦・根本原因 file:line・D1/D2/D3)。
- 後続 P02(この goal-spec を component 分解の入力とする)。
