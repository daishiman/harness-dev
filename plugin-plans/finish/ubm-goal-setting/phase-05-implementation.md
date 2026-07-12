---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 完了
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C15, C16, C17, C18, C19]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 18 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria/テストを満たす (Green) 状態にする。特に 3 本の既存 shell script (validate-goal-output.sh/detect-knowledge-updates.sh/check-knowledge-split.sh) を Python 標準ライブラリのみへ書き換える実装タスクを含む。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。本 phase は再設計でなく faithful-transfer+adapt (既存資産の移植) の性格を持つ。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る (script → agent → skill → command)。二相 skill build: C01-C03 (script) は toposort 上 C16/C17 (親 skill) より先に build されるが、build_target は親 skill 配下パスである。この逆転は「(1) run-skill-create が C16/C17 の skill scaffold (空の scripts//references//assets/ を含む骨組み) を先行生成 → (2) parent-skill-build がその scripts/ を script 本体で充填 → (3) finalize」の二相 build で調停する。parent-skill-build は scaffold 済み skill dir へのみ書き込む契約とする (詳細は component-inventory.json の `build_sequencing_notes`)。

## 前提条件
- P04 で C01/C02/C03/C16/C17 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている。
- 後段 builder (run-skill-create / run-build-skill / parent-skill-build) が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順 (依存先が常に先。phase 番号順ではない)。
- builder の実行実体差: `builder_status` が executor-backed (実行 skill 実在) / contract-only (routing 語彙のみ・`gap_ref` 必須、C01-C03 の parent-skill-build が該当) を区別する。
- Green 判定の主体は P04 で固定した criteria (実装が判定基準を都合よく再定義しない)。
- 旧 .sh の削除は golden-master equivalence (同一コーパスで新旧出力が一致すること) を確認した後に行う不変条件。

## 成果物
build は component 単位で `handoff-run-plugin-dev-plan.json` の routes に従い、以下を inventory の top-sort 順で実行した到達状態:
1. C01 validate-goal-output.py — parent-skill-build (script。旧 validate-goal-output.sh 474 行を stdlib Python へ書き換え)。
2. C02 detect-knowledge-updates.py — parent-skill-build (script。旧 detect-knowledge-updates.sh 183 行を stdlib Python へ書き換え)。
3. C03 check-knowledge-split.py — parent-skill-build (script。旧 check-knowledge-split.sh 67 行を stdlib Python へ書き換え)。
4. C04 ubm-write-path-guard — run-build-skill (hook)。
5. C05 info-collector / C07 goal-reviewer — run-build-skill (agent)。
6. C08-C12 steps1-5 (現状振り返り/ギャップ分析/目標設定/アクションプラン/最終確認) — run-build-skill (agent×5)。
7. C06 output-formatter — run-build-skill (agent・C01 に依存)。
8. C15 knowledge-extractor — run-build-skill (agent・C03 に依存)。
9. C13 phase3-coordinator — run-build-skill (agent・C08-C12 に依存。旧 phase3-interviewer の責務を統合済み)。
10. C16 run-ubm-goal-setting — run-skill-create (skill・C05/C06/C07/C13/C01 に依存)。
11. C17 run-ubm-knowledge-sync — run-skill-create (skill・C15/C02 に依存)。
12. C18 ubm-goal-setting コマンド — run-build-skill (command・C16 に依存)。
13. C19 ubm-knowledge-sync コマンド — run-build-skill (command・C17 に依存)。
- 全 18 component の実体 (skills/agents/commands/hooks/scripts) が build_target に生成され、3 本の旧 shell script が Python 標準ライブラリのみの実装に置換された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest (後段 scaffold owner)。
- references 8 本 + assets 5 本が `component-inventory.json` の `plugin_level_surfaces.references_config_assets.files` に列挙された per-file build_target へ移送され、knowledge L1 curated (28 category JSON + router.json) が `plugins/ubm-goal-setting/knowledge/` へ vendor シードとして配置された状態。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT 重複整理 (P08)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存順に全 18 component が build され、2 skill loop の criteria が Green (受入テスト PASS) になる。
- [ ] build 実体パスが inventory の build_target と一致し、3 本の script が stdlib Python のみで動作する。
- [ ] 旧 .sh の削除は golden-master equivalence (同一コーパスで新旧出力が一致すること) を確認した後に行い、等価確認が済むまでは旧 .sh を fixture として保持する。
- [ ] 二相 build の順序逆転が実際に成立する: C16/C17 の scaffold 先行生成後に C01-C03 (handoff routes の `requires_parent_scaffold` が指す親 skill = C16/C17) を充填し、充填時点で各 script の build_target ディレクトリ (親 skill 配下 scripts/) が存在することを確認する (consumer は routes 配列順でなく `requires_parent_scaffold` 制約に従う)。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing) / `component-inventory.json` (依存 DAG・`build_sequencing_notes`)。
- 対象 component C01-C19 (全 18 component)。
- 後続 P06 (test-run)。
