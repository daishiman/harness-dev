---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。改善計画の全要件 (REQ1a/1b/1c/REQ2/REQ3/REQ4) が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが REQ1a/1b/1c/REQ2/REQ3/REQ4 を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- goal-spec.checklist C1-C11 を受入観点の正本として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose (REQ1a-REQ4) を満たす」保証 (両方必要・相互代替不可)。
- 全量性: required-primaryのdiscovered_totalを固定し、content coverage 100%、temporary_failure=0、unapproved unavailable=0。accountability coverage 100%だけではFULL PASSにしない。
- 非後退の観測方法 (二層): 契約非後退 (既存 phase id/gate/出力契約・21項目・6カテゴリ・knowledge schema 既存フィールド) を回帰テストで確認し、allowlist 外ファイルは build 前後 diff 空・allowlist 内 (workflow-manifest への phase5-graph-sync append / phase1-2-collect への consult 追記) は additive (既存 entry 無変更) であることを確認する (C11 の受入観点)。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.checklist`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C02/C03: URL単発保存とrequired-primary content coverage 100%を判定できる。
- [ ] C02: scheduler fixtureで新着が無操作で一度だけ反映され、retry回復できる。
- [ ] REQ2 (検証専用・非 buildable): 既配備 run-skill-feedback の symlink が build 前後で維持され、`scripts/lint-feedback-protocol.py --strict` が R1-R7 PASS することで判定できる。
- [ ] C08/C06/C07: raw knowledge fixtureから根拠付きnon-zero edge→DAG→known consult hitが得られる。
- [ ] C05/C07: task-state/route report/build traceの実在成果物を1件以上dereferenceし、stale/redacted状態を判定できる。
- [ ] C09/C11: 単一解の押し付けなし、協働モード選択、role=user provenance、action/reflection分岐、安全分岐、保存同意を判定できる。
- [ ] C10: command→skill 透過と package surface 一意登録を判定できる。
- [ ] 全11 componentのacceptance contractがPASS/FAIL二値で被覆される。

### 受入例
primary content coverage 100%、無人sync一度だけ反映、non-zero edge、real artifact hitが同時PASSする。

### 事前解決済み判断
accountability coverageだけをFULL_BACKFILL_PASSと呼ばず、waiverはユーザー承認参照を必須にする。

## 参照情報
- `goal-spec.json` checklist C1-C11 / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C11。
- 後続 P08 (refactoring)。
