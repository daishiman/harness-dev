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

# P05 — implementation (実装)

## 目的
全 11 component を後段 builder へ委譲して実体化し、P04 で固定した C01/C06 の criteria を満たす (Green) 状態にする。build routing は `handoff-run-plugin-dev-plan.json` の routes[] 配列順 (inventory 依存 DAG の top-sort) に実行する (順序の SSOT は routes[]・本文へ順序を重複列挙しない。phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく依存 top-sort 順に走る (共有 script/gate → 親 skill → command → 独立 agent/hook)。plugin-root 共有 script (C09/C08) は複数 consumer から参照されるため最初に実体化し、skill 付随 script (C03/C04/C05) は親 skill (C01) の scaffold 内へ畳み込む。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果 (到達状態) を宣言する。

## 前提条件
- P04 で C01/C06 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来の依存 top-sort 順で用意されている (順序の正本は routes[] 配列そのもの)。
- executor-backed builder (run-skill-create / run-build-skill) が利用可能。contract-only builder (parent-skill-build / plugin-scaffold) は run-build-skill の kind ではなく planner 上の routing 語彙として扱い、script route は `/capability-build --handoff ... --route-id ...` から `plugins/harness-creator/scripts/build-script-route.py` へ委譲する。
- `requires_parent_scaffold` は DAG 依存ではなく配置境界を示す二相 build 指示である。C03/C04/C05 の script route を処理する executor は、親 skill C01 のディレクトリが未生成なら空 scaffold を先に作り、script 配置後に C01 本体 build で同じディレクトリを上書き統合する。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順 (依存先が常に先。phase 番号順ではない)。具体的な線形順序は routes[] 配列を正本とし、本文は依存辺の説明に留める。
- builder 4 種の実行実体差: `builder_status` が executor-backed (run-skill-create/run-build-skill=実行 skill 実在) / contract-only (parent-skill-build/plugin-scaffold=planner routing 語彙・`gap_ref` が `open_issues` を参照) を区別する。contract-only script route は build 不能ではなく、`build-script-route.py` が実体確認または最小 scaffold 生成を行う。
- contract-only script route の実行境界: plugin-root script (C08/C09) は `build_target` へ直接生成、skill 配下 script (C03/C04/C05) は `requires_parent_scaffold` が指す C01 の配下へ生成する。生成結果は route-build-report の必須証跡に含める。
- Green 判定の主体は P04 で固定した criteria (実装が判定基準を都合よく再定義しない)。
- self-build 注意: C06 は builder==build_target の自己適用 build (run-skill-create が run-skill-create 自身を更新する)。build 中は旧仕様で走ることを前提に、開始前に現行版を git commit/stash で退避し、完了後に C8 golden example (P07) で再検証する。

## 成果物
- 全 11 component の実体 (skill 更新 2 件/command 更新 2 件/script 5 件/sub-agent 1 件/hook 1 件) が build_target に生成された状態。
- `envelope-draft/plugin.json` (harness-creator 側は無変更、plugin-dev-planner 側は C10/C11 の build スコープ内で entry_points.agents[]/hooks.PreToolUse[] へ登録) を基にした実 manifest。
- contract-only script route を `build-script-route.py` で実行した場合は、実体確認/生成結果を route-build-report に残した状態。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT 重複整理 (P08)。
- run-build-skill の kind 集合そのものへ `script` kind を追加する改修。

## 完了チェックリスト
- [ ] 依存 top-sort 順に全 11 component が build され、C01/C06 の criteria が Green (受入テスト PASS) になる。
- [ ] build 実体パスが inventory の build_target と一致する (cross-plugin routing: plugin-dev-planner 側 7 件・harness-creator 側 4 件)。
- [ ] contract-only builder の script route は `GAP-SCRIPT-BUILDER` を参照し、`build-script-route.py` の実行結果が route-build-report に記録されている。
- [ ] 共有 script C08/C09 が `plugins/harness-creator/scripts/` (plugin-root) へ実体化されている (単一 skill 配下に退化していない)。
- [ ] plugin-dev-planner 側 manifest へ C10 (entry_points.agents[]) / C11 (hooks.PreToolUse[]) の登録が反映されている。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing) / `component-inventory.json` (依存 DAG)。
- 対象 component C01-C11。
- 後続 P06 (test-run)。
