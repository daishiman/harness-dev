---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装 / tdd-green)

## 目的
`component-inventory.json` に定義された全 11 component を、対応する builder (run-skill-create / run-build-skill / plugin-scaffold) 経由で実体化し、P04 で赤くした criteria を green にする。

## 背景
本planはL3止まりだが、下流buildがC11→C08→C09→C01→C03/C02→C04→C10→C06/C07のDAGで、完全diff・独立verdict・承認済み限定apply・post-image close gateを実装できる契約を明示する。

## 前提条件
- P04 の criteria (赤テスト) が確定している。
- builder 別の実行系統 (`run-skill-create`/`run-build-skill`) が利用可能、または `plugin-scaffold` による script 実装手順が利用可能である (script builder の自動化 gap は handoff の open_issues に記録する)。

## ドメイン知識
- 依存順序は `component-inventory.json` の `depends_on` を SSOT とし本文で再記述しない (散文への二重焼込は drift 源)。おおまかな段は aggregate(C11)→parse(C08)/map(C09) の共有 script root → loop skill (C01→C02) → sub-agent/command/hook (C03/C04/C05/C06/C07) で、正確な有向辺は inventory を参照する。
- C06はC01/C03一致→C02 propose→C04 audit→ユーザー明示承認→C02 apply→C10 post-image検証を直列実行する。C07はissue番号から4 artifactを解決しC10へ渡す。C10は`applied_verified`または`independently_verified_no_change`以外をINCOMPLETEとしてcloseを遮断する。
- C11はhistory見出しとcache commit subjectを照合し親子commitから完全diffを復元する。missing/shallow/ambiguous/digest mismatch時はfetchせずexit2と回復手順を返す。
- 各 component の quality_gates (p0_lint/build_trace/elegant_review C1-C4/content_review/evaluator threshold=80,high_max=0) と harness_coverage (min=80) は builder が実装完了の合否判定に用いる契約値であり、本 phase では「満たすべき設計値」として焼き込むのみで実測結果は書かない。

## 成果物
- 実装対象一覧 (component id/builder/build_target の対応表、component-inventory.json をそのまま参照)。
- P04 criteria の green 化を確認するための実装差分 (下流 build フェーズの成果物)。

## スコープ外
- 実プラグイン/実コードの生成そのもの (本 L3 plan の責務外、下流 build フェーズへ委譲)。
- 品質ゲートの実測・判定 (P06/P09 の責務)。

## 完了チェックリスト
- [ ] 全 11 component の build_target が `plugins/spec-drift-guardian/` 配下の一意なパスに確定している。
- [ ] 実装順序が `component-inventory.json` の depends_on を top-sort した順で矛盾なく解決される (依存の有向辺は inventory を SSOT とし本文で列挙しない)。
- [ ] harness-creatorへの書き込みはC02 apply modeだけで、C04 PASS・明示承認・allowlist・pre-image hash一致を満たさない場合は変更0件でfail-closedになる。

## 参照情報
- `component-inventory.json` (全 11 component の builder/build_target/depends_on)。
- `handoff-run-plugin-dev-plan.json` (builder への実際のルーティング)。
- 後続 P06 (この実装を test-run で実行する)。
