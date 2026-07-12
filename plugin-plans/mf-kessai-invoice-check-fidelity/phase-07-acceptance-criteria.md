---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準(AC)を build 後の受け入れとして判定する。purpose「MF実績を第一級の真実として発行漏れ確認レポートを正しく駆動する」が組み上がったプラグインで実際に満たされているかを goal-spec checklist C1-C13 の観点で確認する。

## 背景
品質ゲート(lint/coverage)を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは index の「受入確認」章と対応し、C1(amount-gate根治)/C3-C6(flowchart+D1/D2/D3)/C7(症状再現)/C8(偽陽性偽陰性検出)/C9(冪等sink)/C10(fetch fidelity診断)/C11-C12(既存ガード維持)を build 後の受入観点として二値判定する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と C01 の criteria が確定している。
- purpose「MF実績起点の発行漏れ確認」を受入観点の正本(`goal-spec.purpose`)として参照できる。

## ドメイン知識
- AC と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証(両方必要・相互代替不可)。
- fail-closed: fetch fidelity 監査(C06/C2)が NG のとき安全側(処理停止)へ倒す性質。
- 偽陽性/偽陰性: C02(C8)が「両月発行済なのに漏れ扱い」「今月未発行なのに正常☑」を独立検出できることが受入観点。

## 成果物
- 全 component の AC 判定結果(PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装(P05 へ差し戻し)。
- 機械品質ゲートの実行(P09)・全域最終審査(P10)。
- 受入観点の新規発明(正本は `goal-spec.checklist` C1-C13・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C05: `scripts/mfk_actuals.py` 由来の実額抽出が `lib/mfk_reconcile.py` の find_mf_match/classify を経由し、全 status(match/typo/mismatch/no_supply/inactive)で `actual_amount`/issued evidence が添付され金額列が空白にならないと判定できる(C1)。
- [ ] C06: `lib/mfk_api.py`/R1 collect が生成した `fetch_trace` を入力に fetch fidelity監査が実行され、NGのとき漏れ確認処理がfail-closedで停止すると判定できる(C2)。
- [ ] C03: D1(12ヶ月ルックバック裏取り)/D2(正常事情判定で行残置)/D3(実額+差分フラグ)が全て反映されていると判定できる(C4/C5/C6)。
- [ ] C02: MF実績ベースの偽陽性/偽陰性検出が独立contextで機能すると判定できる(C8)。
- [ ] C04: Notion冪等sinkが重複行を生まず stale行を理由付きで整理し、既存8列の金額欄に MF実額を入れ、金額差フラグを比較/コメント欄へ出すと判定できる(C9)。
- [ ] C07: fetch fidelity診断が単独実行可能であると判定できる(C10)。
- [ ] C01/C05/C06: MF API(`lib/mfk_api.py`)がGET専用のまま維持され(hooks/guard-mfk-readonly.py)、guard-mfk-no-reinvent.pyのSANCTIONED allowlistへC05(mfk_actuals.py)とC06(mfk_fetch_audit.py)の新規関数シグネチャが登録されていると判定できる(C11/C12)。

## 参照情報
- `goal-spec.checklist`(C1-C13) / index「受入確認(build 後の見方)」章。
- 対象 component C01-C07。
- 後続 P08(refactoring)。
