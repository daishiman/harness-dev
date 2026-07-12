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
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。goal-spec checklist C1-C12 が組み上がった 2 plugin (plugin-dev-planner/harness-creator) で実際に満たされているかを確認する見方を固定し、特に C8 (新規作成フロー一巡) / C9 (改善フロー一巡) は下流実行者が追加質問なく再現できる具体例で判定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose (E1/E2/E3 断線解消) を実際に満たすことは別の保証である。本フェーズは「整備した機械契約が量産パイプラインの実運用で実際に断線を塞ぐか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract/purpose と goal-spec checklist C1-C12 が確定している。
- purpose (E1/E2/E3 断線解消・新規作成フロー/改善フロー双方の一巡) を受入観点の正本 (`goal-spec.purpose`/`goal-spec.checklist`) として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose (断線解消) を満たす」保証 (両方必要・相互代替不可)。
- checklist→component 対応: C1→C01/C02、C2→C04、C3→C06/C07、C4→C08、C5→C01、C6→C01/C09、C7→C05、C8/C9→複数 component を跨ぐ一巡実演 (下記)、C10/C11→build_target routing (全 component 横断)、C12→plan-scoped ゲート exit0。
- build DAG と runtime 受入フローは別物として扱う。C08 は C06/C07 が build を始める前の preflight gate、C11 は C01 の `--mode update` を呼ぶ前の PreToolUse fail-closed gate、C05/C10 は update 後の出力検証である。
- C8 の golden example: 題材 component は `demo-boundary-skill` (component_kind=skill) に固定する。入力 fixture は `plugin-plans/harness-creator/fixtures/c8-new-flow/intake.json` と `next-action.json`、期待生成物は `fixtures/c8-new-flow/expected-goal-spec.json`・`expected-handoff-run-plugin-dev-plan.json`・`expected-route-component-parity.txt`。実行順は `C01` が intake_json を消費して goal-spec.source_intake を記録 → `C02` が command 経由で起動できることを確認 → `C07` が routes[] を選択 → `C08` が routes↔inventory を preflight PASS → `C06` が brief_path を再ヒアリングなしで消費して build dispatch へ進む。未提供 fallback は同 fixture の `without-intake-command.txt` で source_intake=null を期待値にする。
- C9 の golden example: 題材 component は C8 と同じ `demo-boundary-skill` に固定する。入力 fixture は `plugin-plans/harness-creator/fixtures/c9-update-flow/improvement-handoff.json` と、C8 で得た `expected-goal-spec.json`。期待生成物は `expected-updated-goal-spec.json`・`expected-provenance-chain.txt`・`expected-improvement-review.txt`・`expected-hook-block.txt`。実行順は `C09` が improvement-handoff を emit → `C11` が `--mode update` 呼び出し前に C04/C05 の PASS marker を要求し、欠落ケースでは exit2 block → PASS marker ありのケースで `C01` が source_improvement を記録 → `C05` が provenance chain を検証 → `C10` が意味的忠実性を PASS → routes[] に戻して build 再実行へ進む。

## 成果物
- 全 11 component + checklist C1-C12 の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`/`goal-spec.checklist`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C1: intake.json 提供時に C01/C02 経由で purpose/background へ反映される適用例と、未提供時のフォールバックの両方が判定できる。
- [ ] C2: C04 が intake.json の未反映項目を検出する例 (あり/なし) の両方が判定できる。
- [ ] C3/C4: C06/C07/C08 が routes[] を直接消費し contract-only builder を明示区別しつつ、一致例と不一致検出例の両方が判定できる。
- [ ] C5/C6/C7: C01 の --mode update 受理・C09 emit・C05 provenance chain 検証が、新規作成フロー (source_improvement=null) と断裂検出の両方で判定できる。
- [ ] C8: 新規作成フロー一巡 (intake→C01→C02→C07→C08 preflight→C06 build dispatch) が下流実行者の追加質問なしに再現できると判定できる。
- [ ] C9: 改善フロー一巡 (C09→C11 preflight→C01 update→C05→C10→build 再実行) が下流実行者の追加質問なしに再現できると判定できる。
- [ ] C10/C11: 全 build_target が所有 plugin 側へ正しく routing され、plugin-plans/plugin-dev-planner・plugin-plans/skill-intake を一切変更対象に含まないと判定できる。
- [ ] C12: specfm.GATE_SCOPE の plan-scoped ゲートが全 exit0 で、input-gate/dogfood ゲートと混同されていない。

## 参照情報
- `goal-spec.purpose` / `goal-spec.checklist` (C1-C12) / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C11。
- 後続 P08 (refactoring)。
