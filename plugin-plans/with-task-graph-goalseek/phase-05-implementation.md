---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P05 — implementation (実装)

## 目的
C01-C08 を実装し、Phase04 で設計したテストに対する tdd-green(実装によるテスト通過)を到達する。C05 における C01/C02/C06/C07 テンプレートスクリプトの生成先コピー手順を「新規 CLI flag を追加しない prose Step」として実装する事前解決済み判断を含め実装方針を確定する。

## 背景
`render-combinators.py`(C03)は既存の決定論 frontmatter/section 注入器であり、engine:task-graph 変種はこのファイルへの Edit として実装する。ゼロから新規 combinator を起こすのではなく、with-goal-seek が既に default-ON である既存機構への静的テキスト追加パターンに従う。

## 前提条件
Phase04 テスト設計確定。

## ドメイン知識
(引用+差分)BUILDER_STATUS=contract-only(parent-skill-build)。C01-C04/C06-C08 は builder=parent-skill-build(contract-only)につき handoff routes で gap_ref 必須(GAP-SCRIPT-BUILDER)。

## 成果物
- **C01 ready-set-from-checklist.py**: checklist(progress.json)を読み、depends_on 全充足かつ status==pending の item を id 昇順で ready 配列として stdout へ出力する。write_scope フィールド・tie-break ロジックを一切持たない(H1 解消の実装)。
- **C02 self-reflect-append.py**: 新規 item(id/text/depends_on/verify_by)を checklist 末尾へ追記する。追記前に id 重複・存在しない depends_on 参照・追記後サイクルを検査し、いずれかに該当すれば exit1 で fail-closed する。既存 item のフィールドは一切書き換えない(単一truth原則・H3 解消の実装)。
- **C06 extract-capability-dependency-graph.py**: 生成 harness の skill/slash-command/sub-agent/hook/script surface と frontmatter refs・明示参照を実ディレクトリ走査で収集し、surface 間 dependency graph JSON を決定論出力する(plugin-composition.yaml は登録簿であり依存辺の源でないため走査対象にしない)。未知参照・循環・空 graph は fail-closed とする(H6 実装)。
- **C07 record-capability-graph-knowledge.py**: C06 graph と self-reflect discovered task を Loop A/Loop B knowledge entry へ `source_ref` 付きで記録する。既存 knowledge entry は上書きせず append/merge のみを行う(H6 実装)。
- **C03 render-combinators.py 拡張**: `GOAL_SEEK_WIRING_SECTION`(L203-263)へ『### ゴールシーク配線(task-graph 変種)』『### ゴールシーク検証(task-graph 変種・機械検査)』『### dependency graph knowledge consult』の 3 サブセクションを追加する静的テキスト拡張。`schemas/build-flags.schema.json` の `with_goal_seek.engine` enum(L166)へ 'task-graph' を additive 追加。`schemas/goal-seek-loop.schema.json` の checklist item properties へ `depends_on`(additive・array<string>・pattern `^C[0-9]+$`・default `[]`)を追加。C01/C02/C06/C07 の同梱手順を生成 SKILL.md に挿入し、CLI flag は新設しない(H5/H6 解消の実装)。
- **C04 lint-goal-seek.py 拡張**: `check_default_drift()` へ (a) engine enum と配線コメントの整合検査、(b) depends_on additive フィールドの schema 存在検査、(c) 生成 SKILL.md 内 consumption verifier トークンの存在検査、の 3 検査を追加する(H4 解消の実装)。
- **C08 lint-capability-graph-knowledge.py**: 生成 harness の skill/slash-command/sub-agent/script 各 surface が dependency graph knowledge consult token を持つこと(skill=hard gate / command・agent=warning / script=同梱実在で代替の3段設計)、C01/C02/C06/C07 の 4 script が scripts/ に同梱されること(参照集合=検査集合 parity: Step10.6 で複写する全 script を検査対象とする)、Loop A/B knowledge entry が `source_ref` を持つことを検査する(H6 実装)。
- **C05 run-build-skill**: SKILL.md へ「brief.goal_seek.engine=task-graph 指定時のみ C01/C02/C06/C07 テンプレートスクリプトを生成先 scripts/ へ条件付きコピーし、C08 lint を後段検査に追加する」prose Step を追記する。

### 事前解決済み判断: schemas/template-selection.schema.json は編集しない
with-goal-seek は with-knowledge/with-evaluator と同型の「flag/engine 駆動 combinator」である。`template-selection.schema.json` の `selection_rules` は kind 別(run/ref/assign/delegate/wrap)+ role_suffix + composite によるテンプレ選択のみを扱い、flag/engine 駆動 combinator の適用可否には一切関与しない。よって `engine:task-graph` は `build-flags.schema.json` の `with_goal_seek.engine` enum 拡張と、C03 による C01/C02/C06/C07 同梱・knowledge consult 手順追加で足り、`template-selection.schema.json` の改修は不要と判断する(C03 derivation 参照)。

### 事前解決済み判断: C05 のテンプレートコピーは新規 CLI flag でなく prose Step
`render-combinators.py` の `selected_patches()`(L310-328)確認の結果、with-goal-seek は loop kind(run/wrap/delegate)へ CLI flag なしで無条件適用される。よって `engine` は brief 由来のテンプレート変数であり、C01/C02/C06/C07 の生成先コピーも `apply_feedback_loop()`(L584-603、`--deploy-feedback-loop` flag 駆動の `shutil.copytree`)と同型の新規自動化関数を追加するのではなく、SKILL.md 内の AI 実行 prose Step(brief 値による条件分岐)として実装する。これにより「独立 combinator flag を新設しない」A2 制約を最も直接に満たす(C05 derivation 参照)。

## スコープ外
既存 build-pipeline task-graph 側実装(`plugin-plans/harness-creator/` の producer/consumer)の変更 → 対象外。

## 完了チェックリスト
- [ ] C01-C04/C06-C08 が tests_min>=80 を満たすテストとともに実装される
- [ ] C03 が template-selection.schema.json を改修せず build-flags.schema.json + goal-seek-loop.schema.json のみ additive 拡張する
- [ ] C05 の SKILL.md へ C01/C02/C06/C07 同梱 + C08 lint の新設 prose Step(CLI flag 非新設)が追記される

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C01/C02/C06/C07/C08 が tests_min>=80 のテストとともに実装され、C03 が `template-selection.schema.json` を一切改修せず `build-flags.schema.json`/`goal-seek-loop.schema.json` のみを additive 拡張する差分になっている。
- 満たさない例: C05 の SKILL.md へ新規 CLI flag(例: `--engine=task-graph`)を追加してしまい、A2 制約(独立 combinator flag の新設禁止・goal-spec constraints #3)に反する。

### 事前解決済み判断
- 分岐点: C04(lint-goal-seek.py)拡張時に既存 `check_default_drift()` の他検査を壊さないか → 判断: 新規 3 検査((a)engine enum 整合 (b)depends_on schema 存在 (c)consumption verifier トークン存在)は既存検査関数への追加(append)のみとし、既存検査ロジックの変更・削除を一切行わない回帰防止方針を採る(Phase06 のテスト実行でこの回帰非発生を実測確認する)。

## 参照情報
- `plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py`
- `plugins/harness-creator/skills/run-build-skill/schemas/build-flags.schema.json`
- `plugins/harness-creator/skills/run-build-skill/schemas/goal-seek-loop.schema.json`
