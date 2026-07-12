---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 24 buildable component (温存23 + 新設 C24) を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす(Green)状態にする。11 thin-adapter sub-agent の本文を役割・起動条件・I/O契約へ薄化し、抽出した procedural knowledge/rubric を plugin-root references/ (D2一本化・既存 references と同層) へ配置し、委譲先 skill(C01/C02/C03)は SKILL.md ポインタで参照する。新設 C24(lint-reference-attribution.py)を plugin-root scripts/ へ配置し、resource-map.yaml を機械検証可能にする。thin-adapter 化・references_new 配置・resource-map.yaml 置換は本フェーズで完了させ、P08 はその後の重複除去と green 維持確認に限定する。build routing は `component-inventory.json` の依存 top-sort 順に実行する(phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る(worker 群 + 共有 script → orchestrator skill → hook/command)。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果(到達状態)を宣言する。responsibility rebalance の実装は「既存機能を変えず本文の置き場所だけを是正する」性質のため、5 maintain agent(hearing-facilitator/structure-validator/slide-renderer/visual-strategist/report-composer)は本文無変更、11 thin-adapter agent は本文を役割・起動条件・I/O契約へ縮退し委譲先 references/ へ procedural knowledge/rubric を移設する。

## 前提条件
- P04 で C01/C02/C03 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている(worker sub-agent C04-C19 + 共有 script C23/C24 → skill C01/C02/C03 → hook C20 → command C21/C22 の依存順)。
- 後段 builder(run-skill-create / run-build-skill / plugin-scaffold)が利用可能。plugin-scaffold が contract-only の場合は、`handoff-run-plugin-dev-plan.json` の `build_readiness` に従い、C23/C24 bootstrap route を最初に実行して trace を取得するか、`WAIVED_NON_MECHANICAL` へ降格してから C23/C24 依存 route へ進む。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順(依存先が常に先。phase 番号順ではない)。
- build readiness の不変条件: C01-C03 の brief 生成、pre-route surface、C23/C24 bootstrap route の trace または `WAIVED_NON_MECHANICAL` 降格、build-start 再実測が揃うまで C23/C24 依存 route へ入らない。
- 薄化の実装規律: 11 thin-adapter agent の本文縮退は「procedural knowledge/rubric を削除する」のではなく「plugin-root references/ (D2一本化・既存 content 50件=直下45+feedback/5 と同じ references 配下。resource-map は content 外メタ) へ移設した上で本文から参照へ差し替える」(情報の消失を禁じる・移動のみ)。
- 実行時アクセス経路 (D2): 抽出した手続き知識は skill 私有 references/ でなく plugin-root references/ に置くため、薄化 fork agent は skill が load した文脈に依存せず、agent 自身の相対経路 `../references/<file>` (plugins/slide-report-generator-v2/agents/ から plugins/slide-report-generator-v2/references/ を指す既存慣用) で reference を実行時 read する。skill (C01/C02/C03) も SKILL.md から同一 plugin-root references を index/ポインタ経由で参照し、agent と skill が同一 SSOT へ到達する (二層化しない)。
- 共有 script hoist の拡張: 新設 C24(lint-reference-attribution.py)は builder=plugin-scaffold で plugins/slide-report-generator-v2/scripts/ 直下へ実体化する(既存 C23 と同一パターン・単一 skill 配下に退化させない)。
- vendor 携行の不変条件(v1 から継続): Node/CJS 製エンジンは byte 維持で温存し、本計画では一切変更しない(goal-spec C7)。

## 成果物
- 全 24 component の実体(skills/agents/commands/hooks/scripts)が build_target に生成された状態。
- 11 thin-adapter agent の本文が役割・起動条件・I/O契約へ薄化され、対応する references_new ファイル(structure-design-rules.md 等)が plugin-root references/ (D2一本化・既存 content 50件と同じ references 配下) に配置された状態。
- resource-map.yaml(旧 resource-map.md を置換)が全 references の owner_component/consumers を宣言した状態。

## スコープ外
- カバレッジ拡充・テスト網羅(P06)。
- purpose 受入判定(P07)・SSOT 重複整理(P08)。
- builder 自体の改修(harness-creator 側の責務・gap は `open_issues` へ起票)。
- vendor Node engine・schemas 共通コアの変更(goal-spec C7 により対象外)。

## 完了チェックリスト
- [ ] 依存 top-sort 順に全 24 component が build され、skill loop の criteria(OUT1既存機能維持+OUT2 rebalance達成)が Green(受入テスト PASS)になる。
- [ ] `handoff-run-plugin-dev-plan.json` の `build_readiness` を満たし、C23/C24 bootstrap route の trace または `WAIVED_NON_MECHANICAL` 降格、contract-only builder の fallback/waiver、surface 実行順が build trace に記録されている。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] 11 thin-adapter agent の本文が役割・起動条件・I/O契約のみへ薄化され、procedural knowledge/rubric が委譲先 references/ へ移設されている(情報消失なし)。
- [ ] 共有 script C23/C24 が plugin-root へ実体化されている(単一 skill 配下に退化していない)。
- [ ] resource-map.yaml が全 references の帰属を宣言し lint-reference-attribution.py が exit0 (C24 waiver 時は `WAIVED_NON_MECHANICAL` として PASS ではなく人手帰属確認ログへ降格し、index 受入表の降格記載に従う)。

## 参照情報
- `handoff-run-plugin-dev-plan.json`(build routing)/ `component-inventory.json`(依存 DAG・rebalance フィールド)。
- 対象 component C01-C24、vendor surface(変更対象外)。
- 後続 P06(test-run)。
