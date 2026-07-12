---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
task-graph関連capability (C1-C19の決定論契約) と意味判定capability (C8/C14(b)/C17/C19) を既存2 componentへ写像する。component分割は変更せず、C01=producer contract、C02=独立meaning evaluatorの責務を差分強化する。

## 背景
task-graph の schema/導出器/validator/ready-set 計算器/discovered-task 受理/handoff-notes 契約はいずれも run-plugin-dev-plan skill 単独の消費者であり、他 skill との共有・独立検証実体・280 行超の新規肥大のいずれの no-split threshold も満たさない。C8 のみ既存の fork evaluator (assign-plugin-plan-evaluator) の意味評価軸拡張として独立 component (C02) に計上する。

## 前提条件
- P01 の goal-spec が確定している。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/component-domain.md` の no-split threshold (≥2-skill-shared / independent-verification / >280-lines) を判定基準として用いる。

## ドメイン知識
- **5 種検討の帰結**: sub-agent 不要 (task-graph の導出/検証/ready-set 計算はいずれも決定論スクリプトの責務であり、既存 2 agent (plugin-dev-plan-architect/evaluator) の独立文脈判断面を追加で要求する新規判断軸を持たない)。slash-command 不要 (task-graph は既存 `/plugin-dev-plan` の R2/R3 内部で自動生成される sidecar 成果物であり、独立起動導線を要求しない)。hook 不要 (task-graph.json への手書き編集禁止・単一 writer 強制は validate-task-graph.py の fail-closed 検証で足り、accept-discovered-task.py の CLI 経由経路が構造変更級のユーザー承認を既に強制するため、PostToolUse hook の検査範囲拡張は必須要件に含まれない)。script の独立 component 昇格は各新規スクリプト (derive-task-graph.py/validate-task-graph.py/compute-ready-set.py/accept-discovered-task.py/apply-handoff-notes.py) ごとに no-split threshold を判定し、いずれも同一 plugin 内の他 skill からの import 共有が無い (≥2-skill-shared 非該当) ため C01 の build へ畳み込む。**ただし『単独消費』ではない (是正)**: compute-ready-set.py・derive-task-graph.py の canonicalize()/graph_hash()・check-task-state-schema.py は harness-creator の L4 実行系 (runtime script = 第二消費者) が CLI subprocess 経由 (固定パス起動・import ではない) で消費する repo-bundled cross-plugin 消費を持つ。この消費は import 共有ではないため畳み込み判定を変えないが、外部消費される producer script は安定 CLI 契約 (固定パス + argv 形状 + stdout schema + exit codes) を references/pipeline-boundary-contract.md 追記対象として保持する (plan-time script=planner が repo-root cwd で走らせる / runtime script=consumer が build 時に走らせる、の起動主体・cwd 前提・入出力担体の構造差を明記する)。
- **placement_scope**: 新規スクリプトは全て `placement_scope: skill` (既定・parent-skill-build)。plugin-root への昇格 (plugin-scaffold) は assign-plugin-plan-evaluator が derive/validate/compute の各スクリプトを直接 import/呼出する設計を採らない (C02 は plan-findings.json 経由で C01 の検証結果を読むのみ) ため発生しない。
- **依存 DAG**: C02 (assign-plugin-plan-evaluator) は C01 (run-plugin-dev-plan) に `depends_on: ["C01"]` (fork evaluator は plan 生成後に評価する既存の依存方向を維持、非循環)。
- **C13 (plan 出力ディレクトリ規約) の畳み込み根拠**: cycle-id 付きディレクトリ規約・plan-ledger.json 台帳検査・既存 flat 配置からの移行はいずれも `specfm.py` の `plan_output_dir()` 拡張 (既存関数への引数追加) と新規スクリプト (`check-plan-ledger.py`/`migrate-plan-layout.py`) に閉じ、run-plugin-dev-plan skill 単独消費のため no-split threshold のいずれも満たさず C01 へ畳み込む。メタ循環の分離は C10 と同型 (本 plan 自身は現行 flat 配置のまま生成し、cycle-id 配置は将来の plan が使う機能要件)。
- **C14 (新旧shape非劣化ゲート) の分割配置**: 3 軸のうち (a)精度 (二値受入基準携帯率の機械計測) と (c)再現性 (byte一致+仕様書構成一致の機械計測) は決定論スクリプト `check-shape-non-regression.py` に閉じ、run-plugin-dev-plan skill 単独消費のため no-split threshold を満たさず C01 へ畳み込む。(b)品質 (新旧shape A/B比較の下流ハーネス実効性 genuine 判定) は C8 と同型の理由 (意味評価軸拡張は既存 fork evaluator の責務) で C02 へ計上する。**C10⇔C14 相互参照**: shape_marker が `task-graph-derived` を採用するのは C14 (a,c) の script ゲート PASS + C14(b) の C02 genuine 判定 PASS を前提条件とし、いずれか劣化検出時は shape 解放を block し `fixed-13-phase` へ fallback する (平均回帰禁止)。
- **C15 (graph 可視化 renderer) の畳み込み根拠**: mermaid 依存グラフ図の決定論導出は新規スクリプト `render-task-graph-mermaid.py` に閉じ、他 skill 非共有・独立検証実体を要求せず・280 行超が計画時点で確定していないため no-split threshold のいずれも満たさず C01 へ畳み込む。genuine 判断 (人間可読性の質) を要求しない全数機械判定 (byte一致・graph 外要素非描画) のため C02 (fork evaluator) への計上根拠を持たない。
- **C16 (実行時契約 schema SSOT) の畳み込み根拠 + 所有/書込分離**: `task-state.schema.json` (新規) と graph_hash pin 検査は決定論スクリプト `check-task-state-schema.py` に閉じ、run-plugin-dev-plan skill 単独消費のため C01 へ畳み込む。C12 (handoff-notes) と同型の所有/書込分離原則: schema 定義・pin 整合検査ロジックの所有は producer (C01) だが、実行時の task-state.json への書込 (state 遷移・lease 更新) は consumer (harness-creator 側 L4 実行系) が単独 writer として担う。**C11⇔C16 相互参照**: `graph_hash` は C11 の canonicalizer が生成する canonical bytes から導出するハッシュであり、C11 の単一 writer 原則を pin 検証 (build 開始時固定・実行中変更は hash 不一致で fail-closed) へ接続する。
- **C17 (TaskExecutionEnvelope)**: task spec生成・nodeへのexecution_kind/route_ref/task_spec_ref付与・envelope schema/renderer/parity検査はproducer C01へ畳み込む。`entity_ref`は分類専用とし、component-buildだけが`route_ref`を解決する。consumerは既存`inject-task-inputs.py`とdispatcherでenvelopeを消費し、title単独dispatchとentity_ref暗黙routeを禁止する。C17の「追加質問なしで着手可能か」はC02がgenuine判定する。
- **C18 (状態三層分離)**: graph/state/projectionのschema/parity規約はC01、task-state/task-events書込とprojection実行はconsumer harness-creator。新componentは増やさない。
- **C19 (cycle知識)**: ledger lineage/knowledge_ref契約と検査はC01、知識の関連性・stale判断はC02。過去nodeをactive DAGへ混ぜないためexecution dependencyとは別のlineage relationとして扱う。
- **plugin-level surface 採否**: manifest/composition/harness_eval/references_config_assets は現状維持 (entry_points/hooks の変更なし)。schemas は task-graph.schema.json/discovered-task.schema.json/handoff-notes.schema.json/plan-ledger.schema.json/task-state.schema.json の 5 件追加で拡張。vendor/mcp_app_connector/notion_config は不採用 (component-inventory.json の `plugin_level_surfaces` の omitted_reason 参照)。
- **producer/consumer 境界 (対 harness-creator)**: C01 の所有範囲は task-graph の schema/導出/検証/ready-set 計算器のみ。dispatch (SubAgent 並列投入)・state write-back・produces 成果物の consumes 注入・discovered-task の emit は consumer 側 (`plugin-plans/harness-creator/` plan が component 化する L4 実行系) の所有であり、本 plan の component として計上しない。task state ファイル (確定: `eval-log/<slug>/build/task-state.json`・harness P02 の resolve_build_dir で解消済み) の単一 writer は consumer 側、C01 は初期 state (全 pending) 生成までを担う。この境界語彙は harness-creator 側 goal-spec.json の constraints/checklist C7 と 1:1 で揃え、最終的な正本追記先は `references/pipeline-boundary-contract.md` (harness-creator plan C7) である。**cycle_id 携帯契約 (C13 接続の閉路解消)**: handoff トップレベルに `cycle_id: str | None` (additive) を持たせ、consumer は build 成果物 (task-state.json/route-<id>.json) のスコープ化に必要な cycle-id を `handoff.cycle_id` から読む (`plan_dir` パス末尾を独自解析する経路は禁止・レイアウト判断の consumer 側二重実装を防ぐ)。check-build-handoff.py 拡張は `handoff.cycle_id` と goal-spec 側で R1 が固定した cycle-id との整合 (goal-spec↔handoff parity) も検査する。

## 成果物
- `component-inventory.json` (C01/C02の2 component、feedback_contract.criteria IN1-IN16/OUT1-OUT3)。
- envelope 設計の owner 判断: manifest は `plugin-scaffold` (既存 manifest は entry_points/hooks 変更なしで現状維持するため、envelope-draft/plugin.json は現行 plugin.json の複製 + description 追記に留める)。

## スコープ外
- 13 phase ファイル本文・index.md・handoff-run-plugin-dev-plan.json の具体的記述 (P04/P05/P12 相当の後続 phase で行う)。
- 実 `plugins/plugin-dev-planner/` への実コード反映 (L4 build・本 plan の対象外)。

## 完了チェックリスト
- [ ] considered_component_kinds が 5 種全て記載され、各不採用種に具体的な不採用根拠がある。
- [ ] C01/C02 の kind/build_target/builder/build_kind が確定している。
- [ ] 依存 DAG (C02 depends_on C01) が非循環である。
- [ ] plugin_level_surfaces の採否 (8 種) が全て明示され、不採用種に omitted_reason がある。
- [ ] producer/consumer 境界 (対 harness-creator) が dispatch/state write-back/成果物注入/discovered-task emit の所有区分込みで明示され、harness-creator 側 goal-spec.json の語彙と一致している。cycle_id 携帯契約 (consumer は `handoff.cycle_id` から読み `plan_dir` パス解析を禁止) が明記されている。
- [ ] 外部消費される producer script (compute-ready-set.py / derive-task-graph.py の canonicalize()・graph_hash() / check-task-state-schema.py) が harness-creator L4 runtime script の第二消費者を持つことが明示され、安定 CLI 契約 (固定パス + argv 形状 + stdout schema + exit codes) が references/pipeline-boundary-contract.md 追記対象として明記されている (plan-time / runtime script の起動主体・cwd 前提の構造差込み)。
- [ ] C13 (plan 出力ディレクトリ規約) の畳み込み根拠 (specfm.py 拡張 + check-plan-ledger.py + migrate-plan-layout.py の run-plugin-dev-plan skill 単独消費) が個別に判定され、C01 の build へ収束している。
- [ ] C14 (新旧shape非劣化ゲート) の分割配置 ((a)(c)=check-shape-non-regression.py で C01・(b)=A/B比較 genuine 判定で C02) が個別に判定され、C10⇔C14 相互参照 (shape 採用の前提条件) が明記されている。
- [ ] C15 (graph 可視化 renderer) が render-task-graph-mermaid.py として C01 へ畳み込まれる根拠が個別判定されている。
- [ ] C16 (実行時契約 schema SSOT) の所有 (C01=producer) と書込 (consumer=harness-creator) の分離が明記され、C11⇔C16 相互参照 (graph_hash の生成元) が個別判定されている。
- [ ] C17-C19がC01/C02へ責務分解され、component追加なしの根拠が明記されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 新規スクリプト 7 本それぞれについて no-split threshold の 3 条件 (共有/独立検証/280行超) を個別に否定し C01 へ畳み込む根拠が具体的に記される。
- 満たさない例: 「script は分割しない」とだけ記され、7 本それぞれの個別判定根拠が欠落する。

### 事前解決済み判断
- 分岐点: task-graph 関連の新規スクリプト群を独立 component (C03, C04, ...) として計上するか、既存 C01 の build へ畳み込むか → 判断: 畳み込む (全スクリプトが run-plugin-dev-plan skill 単独消費であり no-split threshold のいずれも満たさないため。component-domain.md の判定基準に従う)。

## 参照情報
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/component-domain.md`。
- `plugin-plans/finish/plugin-dev-planner/component-inventory.json` (同一プラグイン向け直前サイクルの帰結パターン)。
- 後続 P03 (design-review)。
