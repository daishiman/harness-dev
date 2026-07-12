---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C24, C25, C26, C27, C28]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各componentの二値ACを後段buildが判定できる契約として固定する。本L3 planでは実プラグインのPASSを宣言せず、purposeをbuild後にどう観測するかを確定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが管理ハーネスという purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06でharness test matrixとevidence契約が確定している。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose「タスクグラフでissue/task/specification/architecture/documentを一元管理しGitHubと同期しながら要件定義から実装handoffまでを担う」を受入観点の正本として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 双方向同期の観測方法: 同一状態で二回同期し、二回目の追加/更新件数 0 を観測する (C03 の outer criterion)。id+updated_at 同時競合を注入しタイブレーク規則どおりの解決を観測する (C03 の OUT2)。
- fail-closed: 判定不能・異常時に安全側 (拒否) へ倒す性質 (C10 hook の受入観点)。

## 成果物
- 全componentのAC matrix (後段buildが記録するPASS/FAIL欄と検証方法)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01/C02: 6正規rootが冪等で、混在入力が保存先質問なしにroutingされ、低信頼入力だけ確認されると判定できる。
- [ ] C02/C03/C11: 199/200/201件境界で必要時だけ段階分割し、migration/rollback後もgraph_node_idとlinkが維持されると判定できる。
- [ ] C03: 同一状態を二回同期して 2 回目の反映が 0 件、id+updated_at 同時競合がタイブレーク規則どおり解決されると判定できる。
- [ ] C04: 要件定義書が生成され capability-build/task-graph build へ handoff され、本ハーネス自身が実装コードを生成していないと判定できる。
- [ ] C05: 生成 HTML をブラウザで開いた際に追加ランタイム依存なく SVG 可視化が表示されると判定できる。
- [ ] C10: 破壊的操作が hook で fail-closed に阻まれると判定できる。
- [ ] C14: 自然文入力からの分解DAGが循環なし・粒度が閾値内で、同一入力の再実行でIssue起票が重複しないと判定できる。
- [ ] C15: 推薦タスクが全依存充足済み (ready) で、並列バッチ内で resource_scope が重複するノードペアが 0 件と判定できる (C17 の独立再検証と一致する)。
- [ ] C18: 検索/状態表示結果がグラフストアの実状態 (status/closed_at/依存関係) と一致し、実行後もグラフストア・GitHub Issue 側に変更が生じない (read-only) と判定できる (要件C11)。
- [ ] C03: GitHub Issue の close/delete 後、次回同期でローカルノードが物理削除されず tombstone/status 遷移として双方向伝播されると判定できる (要件C12)。
- [ ] C03/C14: `--dry-run` 指定時に GitHub 側への書込みが 0 件のまま反映/起票予定差分のみがプレビューされ、guard hook (C10) が gh write の暴発を阻むと判定できる (要件C13)。
- [ ] C01/C02/C11: kind/subtype/API条件templateが適用され、必須section欠落やplaceholderだけの成果物はreadiness incompleteになる (要件C18-C20)。
- [ ] C19: 仕様/architectureがsystem-spec-harness確定成果物とlineageを引用し、ロジック複製がない (要件C21)。
- [ ] external system-dev-planner引用: P01..P13 exact 13 executable task specs、13-entry inventory、13-node intra-feature DAG、handoff、4条件PASSを所有し、dev-graphはexpected/applied=13とphase/node exact-set後だけC02がatomic登録すると判定できる (要件C22-C23/C56)。
- [ ] C24/C01/C02/C19: 同一symlinkを異なるrepoから実行して各repo固有docs/config/stateだけを扱い、cross-read/write・root外path・絶対path保存が0件と判定できる (要件C24-C26)。
- [ ] C03/C26: linked PR closed未mergeではdoneにならず、default branchへmergedかつpolicy充足時だけIssue/Project/local completion evidenceが冪等収束する (要件C31-C34)。
- [ ] C01/C25: plugin hookとproject settings fallbackの二重登録0件、既存settings全書換0件で、対象Claude eventだけが発火しTaskCompletedはpending_reviewへparkするがGitHub doneにせず、identity/owner不整合以外をblockしない (要件C35-C38)。
- [ ] C24/C27/C15/C16/C26: 複数linked worktreeで同一task二重claimとtouches重複batchが0件、crash後TTL回復が可能で、feature branchの先行done書込み0件、clean default branchでのみdurable projectionが更新される (要件C39-C42)。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

### 受入例
- 満たす例: 同一状態を二回同期 (C03) して 2 回目の GitHub からの取込/ローカルからの反映が 0 件になる、かつ id+updated_at 同時競合を注入した際にタイブレーク規則どおり解決される。
- 満たす例: C18 を実行し、検索/状態表示結果が実際のグラフストア状態 (status/closed_at/依存関係) と一致し、実行後もグラフストア・GitHub Issue に変更が生じない。
- 満たさない例: `--dry-run` 指定時に GitHub 側へ 1 件でも書込みが発生する → C03/C14 の OUT3/OUT4 criterion 不達として FAIL 判定。

### 事前解決済み判断
- AC (受入基準) と品質ゲート (lint/coverage) は別種の保証であり、両方が揃って初めて PASS とする (相互代替不可)。
- 受入観点の正本は `goal-spec.purpose` に固定し、本フェーズで新規観点を発明しない。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C19・C24-C28 (計24)。
- 後続 P08 (refactoring)。
