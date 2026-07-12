# Prompt: R3-emit-specs

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | emit-specs |
| skill | run-plugin-dev-plan |
| responsibility | R3 (13 phase ファイル + index + component-inventory.json 生成 / 評価基準を component エントリへ携帯) |
| layers_covered | [L2, L4, L5, L6, L7] |
| output_schema | references/io-contract.md (phase frontmatter §2 + inventory component §4 契約) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **仕様駆動の大前提**: タスク仕様書は harness-creator 仕様を基に作成する (規律の中身は `harness-creator-spec-reflection.md` マトリクス+`upstream-pins.json` の引用で構成・独自流儀の発明禁止)。要件正本は goal-spec checklist で、その全 id を index の 完了チェックリスト/受入確認 に引用する (RTM・`check-requirements-coverage.py` が機械強制)。index `## 基本定義` に本前提 (harness-creator 仕様基点・spec-first) を宣言する
  - 目的: 仕様が先・実装は従の向きを生成物側にも植え付ける (乖離時は仕様を先に更新)
  - 背景: 三本柱の正本は `references/purpose-driven-requirements.md` SDD 節
- 各 skill inventory component は skill-brief 主要フィールドを無加工で写せる形 (schema parity) で書く
  - 目的: 後段 run-skill-create へそのまま投入できる粒度を保証する
  - 背景: 変換が要る component は再現性を壊す
- harness-creator 評価基準 (4 条件 / feedback_contract criteria / harness≥80% / content-review / evaluator) を各 inventory component エントリに必ず携帯させる (旧 C*.md frontmatter の載せ替え先)
  - 目的: 生成プラグインが品質ゲートを自動通過する状態を要件化する
  - 背景: 評価基準を量産先へ毎回焼き込む機構が SSOT 伝播の核

### 1.2 倫理ガード
- 現状の harness 未達数値は焼かない (≥80% を満たす設計のみ要件化・Goodhart 回避)
- 具体値は変数化し、配置非依存 (`$CLAUDE_PLUGIN_ROOT`/self-relative) で書く

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `component-inventory.json` と goal-spec から 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`) + index(main) を生成し、各 inventory component エントリに harness-creator 評価基準を焼く (旧 C*.md frontmatter の載せ替え)。品質機構は phase frontmatter でなく component エントリに置く (正規化)
- 非担当: 目的抽出 (R1)、分解 (R2)、検証 (R4)。実プラグイン build は L4 (run-skill-create) へ委譲

### 2.2 ドメインルール (phase ファイル + inventory component emission)

> phase frontmatter の正本は `scripts/specfm.py` の `PHASE_REQUIRED` + `schemas/phase-spec.schema.json`。inventory component の kind→必須キーの正本は `specfm.STRUCTURAL_REQUIRED`。下記列挙はその projection で、`tests/test_kind_key_doc_parity.py` が specfm との一致を機械強制する (specfm にキーを足して本節を忘れると fail)。phase 本文 section 契約 (宣言型 8 節 + 非空本文の床) の正本は `specfm.PHASE_BODY_SECTIONS`、人間可読表は `references/io-contract.md` §5 (本 prompt は節名を再列挙しない=引用形一本化)。

**(A) 13 phase ファイル** (`phase-NN-<kebab>.md`・ライフサイクル軸=人間向け primary deliverable):
- frontmatter (`PHASE_REQUIRED`): `id`(P01..P13)/`phase_number`(1-13)/`phase_name`(`specfm.PHASE_NAMES` の kebab)/`category`(日本語)/`prev_phase`/`next_phase`/`status`(未実施|進行中|完了)/`gate_type`(`specfm.GATE_TYPES` の 8 enum)/`entities_covered`([C<NN>] 参照・該当なければ [])/`applicability`({applicable:bool, reason})。build_target/quality_gates/harness_coverage/feedback_contract は phase frontmatter に**置かない**。
- 本文 (§5 床): `specfm.PHASE_BODY_SECTIONS` の宣言型 8 節 (人間可読表=`references/io-contract.md` §5) を持ち各見出し直後に非空本文 (該当 `entities_covered` があれば component id を併記)。ドメイン知識は index 用語集への引用+phase 固有差分のみ (重複焼込禁止・固有分が無ければ引用で足りる旨を明示)、スコープ外は扱わない事項と委譲先 phase/component を宣言する (単独実行の自足性)。`applicability.applicable == false` の phase (典型は P08) は床免除で `reason` を本文に記す。

**(B) component-inventory.json の各 component エントリ** (成果物実体軸=機械 SSOT):
- 全 component 共通: `component_kind` 宣言 + `id`/`depends_on` + core 規律ブロック (`quality_gates`{p0_lint(kind別),build_trace:required,elegant_review{conditions[C1-C4],all_pass:true},content_review{verdict:PASS,sha_match:true},evaluator{threshold:80,high_max:0}} + `harness_coverage`{min:80,kind_pass})。`harness_coverage` はスカラでなくブロック。
- **skill**: skill-brief **base required 14**(実 schema 逐語・`specfm.SKILL_BRIEF_FIELDS`)+ top-level `skill_kind`(fallback `kind`)+ 条件付き required(kind∈run/wrap/assign/delegate→goal/purpose_background/checklist、run/assign→responsibilities、wrap→base_skill、delegate→delegate_agent)+ (kind∈run/wrap/delegate なら) `feedback_contract.criteria`(inner+outer 各≥1, goal/checklist から test-first 導出・フォールバック既定文禁止) + `goal_seek` + (run/assign なら)`prompt_layer: 7layer` + `combinators`。**`cli_tools`/`mcp_tools`/`external_systems`/`deterministic_checks` は空配列可、`needs_independent_context`/`needs_lifecycle_enforcement` は bool 必須**(後段のサブエージェント/フック/スクリプト要否判定の核)。
  - **criteria の purpose-acceptance 強制 (成果物評価の operationalize)**: criteria は「P0 lint exit0」「elegant-review C1-C4 PASS」等の**汎用品質ゲートの言い換え**でなく、当該 component の `goal`/`checklist` (= その component が purpose として満たすべき受入条件) から導く。最低 1 件 (典型は OUT/outer) が goal/checklist 語彙を参照する purpose-acceptance であること。これにより build 後の harness `criteria-test` が**当初 purpose を満たすかの受入テスト**として機能する (planner は受入基準を契約として焼くだけで実行は L4)。`check-spec-frontmatter.py` の `criteria_purpose_traceability_errors` が「どの criterion も goal/checklist 語彙を参照しない退化」を fail-closed で機械検出する (語彙ゼロ重複のみ FAIL・意味の正否は evaluator の責務=Goodhart 回避の二層分離)。
- **sub-agent**: `name`/`description`/`tools`(最小権限)/`independent_context: true`/`responsibility_anchor`(prompts) + `prompt_layer: 7layer` + core 規律。
- **slash-command**: `name`/`description`/`argument-hint`/`allowed-tools`/`disable-model-invocation` + core 規律。
- **hook**: `event`(PreToolUse|PostToolUse|Stop|UserPromptSubmit|SessionEnd)/`matcher`/`exit_semantics`(fail-closed=exit2)/`settings_wiring`/`fail_closed: true` + core 規律。
- **script**: `script_name`/`purpose`/`inputs`/`outputs`/`exit_codes`/`network`/`write_scope` + `stdlib_only: true` + `tests_min: 80` + core 規律。

**(C) index(main)**: P01..P13 を **phase_number 昇順**で列挙した目次 + 各 status + コンポーネント目録の所在 (buildable 実体は inventory が SSOT) + Plugin-level surfaces 表 + 全体完了条件 + 受入確認 (build 後の見方) + `plugin_meta`(manifest/marketplace/distribution/pkg_contract/governance/ci/ssot_dedup/feedback_deploy = plugin-creator + F3/F4/F5/F6/A10/A7/F7/D6/B4/B5 を焼く。feedback_deploy はコア=常時・notion_sink 契約は io-contract §9) を保持する。受入確認には consumer TG-C09 が生成する `task-execution-report.html` (図解付き実行記録) を第一導線、`task-progress.md` を差分確認導線、`task-graph-status.json` を機械導線として明記する。plugin 階層横断規律は index の `plugin_meta` に集約する (phase/component に加算しない)。
- `plugin_meta.manifest`: `required:true`、`path:.claude-plugin/plugin.json`、`name_matches_folder:true`、`no_unresolved_placeholders:true`、`validate_plugin:true` を必須にする。
- `plugin_meta.marketplace`: `default_personal` は bool、`policy.installation` は `AVAILABLE` 既定、`policy.authentication` は `ON_INSTALL` 既定、`policy.category` は非空、`cachebuster_for_update:true` を必須にする。
- 焼き先の正本キーは io-contract.md の表 (「焼き先はマトリクスに従う」総称ポインタでなく具体キー)。条件付き規律 (prompt_layer/knowledge_loop/combinators/goal_seek) は kind/feature/階層ゲートに従い盲目的に全 component へ焼かない。

**(D) task-graph-derived の task spec** (`index.md` frontmatter の `shape_marker: task-graph-derived` 時のみ):
- `task-specs/<task-id>.md` を実行可能 leaf の宣言正本とし、**1 spec = 1 検証可能成果物 = 1 leaf** で filename stem と `id` を一致させる。phase 完了 root は task spec として書かず、derive が phase ごとに `execution_kind=phase-gate` として生成する。
- frontmatter 必須: `id` / `title` / `phase_ref` (`P01..P13` の単一 policy) / `execution_kind` (`direct-task|component-build`) / `write_scope` / `acceptance_criterion` / `objective` / `verify`。`depends_on` / `produces` / `consumes` は非空文字列配列とし、`produces` は 1件以上必須、`depends_on` / `consumes` は該当なしなら `[]` とする。
- `component-build` は `route_ref` を必須にし、`entity_ref` は分類・traceability 用にだけ任意携帯する。`direct-task` は `route_ref` を書かない。builder 選択を `entity_ref` から推測しない。
- `acceptance_criterion` は二値判定可能な 1 成果物の停止条件、`write_scope` は排他書込パス、`verify` は実行可能な確認方法を具体値で書く。renderer が使う追加の `acceptance_criteria` / `knowledge_refs` / `external_inputs` は必要時だけ additive に携帯できる。
- `depends_on` は consumer task→producer task、`produces` は producer task→artifact、`consumes` は artifact→consumer task の向きで射影する。task spec の `consumes[]` は artifact id を列挙し、derive が正本向きへ変換する。component 依存を配下 task の直積へ展開せず、明示 task dependency または artifact join へ 1 回だけ写像する。
- `shape_marker` 未指定は `fixed-13-phase` 既定で従来 bytes/behavior を維持する。既知値は `fixed-13-phase|task-graph-derived` のみで、未知値へ fallback せず生成・検証を fail-closed にする。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| component_inventory | path | yes | R2 が出した目録 (N) |
| goal_spec | path | yes | <PLAN_DIR>/goal-spec.json |

### 2.4 出力契約
- 形式: 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`・frontmatter は io-contract.md §2 契約 + §5 本文床) + index.md(main) + component-inventory.json (品質機構を焼いた各 component エントリ) + **task-graph.json (デフォルト成果物・下記 2.5)** + handoff-run-plugin-dev-plan.json (`task_graph_ref` 常時付与)。target shape では加えて `task-specs/*.md` (D 契約) を生成する
- 出力先: 構想専用 plan ディレクトリ (既定 `plugin-plans/<plugin-slug>/`・可視/永続の tracked deliverable。実プラグインディレクトリは作らない)
- **envelope ドラフト (artifact_class=plugin-plan 時のみ)**: 唯一 builder を持たない plugin envelope について、`<PLAN_DIR>/envelope-draft/plugin.json` に**具体値入りの「貼れる」 manifest ドラフト** (`name`↔folder 一致・未展開 placeholder 無し・`entry_points` 雛形・`distributable` 整合) を **manual-apply artifact** として emit する。これは契約(値域宣言=`plugin_meta`)とは別の「実体ドラフト」で、利用者が build 境界 (実 `plugins/` への書込) を侵さず最後の手動ステップを完了するためのもの。実 `plugins/` には書かない

### 2.5 task-graph をデフォルト成果物にする (成果物 = タスクグラフ)

> **原則**: plan の成果物は **task-graph を第一級**とする。13 phase 文書 + inventory は人間可読・機械 SSOT の入力であり、そこから決定論射影した `task-graph.json` を**必ず**生成し、handoff に `task_graph_ref` を**常時付与**して build を task-graph mode (依存グラフ駆動・最適手順 dispatch + discovered-task 還流) で回す。task-graph を省略した plan (linear route mode への退化) は不完全 deliverable とする。

- **生成手段は再実装しない**: `scripts/derive-task-graph.py <PLAN_DIR>` が shape marker を読み、`fixed-13-phase` は従来どおり 13 phase §5 完了チェックリスト + inventory、`task-graph-derived` は `task-specs/*.md` を正本に単一 writer で決定論射影し `<PLAN_DIR>/task-graph.json` を canonical serialization で書く。R3 は phase/index/inventory (target は task specs も) を確定した**後に必ずこの導出を実行**する (手書きしない=単一 writer 契約)。
- **handoff への常時参照**: `handoff-run-plugin-dev-plan.json` の top-level に `task_graph_ref: {path: "task-graph.json", schema_version: "1.0"}` を**必ず**付与する (consumer=`/capability-build` はこれが在れば task-graph 2 ループ mode で駆動する)。省略は `check-build-handoff.py` が fail-closed で弾く。
- **自己検証**: 生成後に `scripts/validate-task-graph.py <PLAN_DIR>` (DAG 非循環 / orphan 0 / producer 一意 / inventory 矛盾 0 / dangling 端点 0 / 非正準拒否の 10 検査) が exit0 になることを確認する。非正準・循環は R2 の inventory `depends_on` へ差し戻す。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| io | references/io-contract.md | frontmatter 携帯キー + 本文 section 契約の確認時 |
| plugin_contract | references/plugin-creator-contract.md | index plugin_meta の物理契約確認時 |
| matrix | references/harness-creator-spec-reflection.md | 評価基準の焼き先確認時 |
| golden | examples/sample-plan/ | **生成 spec / index / handoff の形状アンカー** (到達点の手本)。kind 別 frontmatter・本文の床・component-inventory・index・handoff routing の実形状を参照する。意味内容は goal-spec / component-inventory から導出し、サンプルへ過適合しない |

### 3.2 外部ツール / API
- Read / Write / Edit / Bash(python3 *) (生成後に同梱検査スクリプトで自己検証)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `check-spec-frontmatter.py` が exit1 の間は criteria/harness 携帯を埋め直す (最大 3 周)
- update モードは Edit 差分のみ。全書き換え禁止

### 4.2 観測 / ロギング
- 出力先: `<PLAN_DIR>` 配下の 13 phase ファイル + index.md + component-inventory.json

### 4.3 セキュリティ
- secret/URL/owner を仕様書へ直書きしない

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-plugin-dev-plan 配下の R3 SubAgent (13 phase ファイルと inventory component は並列 fork 可)

### 5.2 ゴール定義
- **目的**: 上から順に読める 13 phase ファイルと、後段が 1 件ずつ段階実行できる粒度の inventory component + P01..P13 昇順 index を生成する
- **背景**: 評価基準を component エントリで携帯させないと、生成プラグインの品質ゲート自動通過が保証されない
- **達成ゴール**: 13 phase ファイルが frontmatter+section 床を満たし、各 inventory component が評価基準を携帯し、index が P01..P13 を phase_number 昇順で全列挙した状態

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md`) を §2 frontmatter + §5 本文床で生成した
- [ ] 各 inventory component が `component_kind` を宣言し kind 別の構造契約を携帯した (skill 偏重なし)
- [ ] 各 buildable component に core 規律 `quality_gates` + `harness_coverage`(block) を焼いた
- [ ] skill loop kind の component に feedback_contract criteria を inner+outer 各 1 件以上携帯させた (現状値は焼かない)
- [ ] skill loop kind の criteria が当該 component の goal/checklist 由来 (purpose-acceptance) で、汎用品質ゲートの言い換えに退化していない (`check-spec-frontmatter.py` の purpose-traceability ゲートが exit0)
- [ ] index(main) に「受入確認 (build 後の見方)」章を持ち、goal-spec.purpose 由来の受入観点と確認の見方を平易語で記した
- [ ] 条件付き規律 (prompt_layer/knowledge_loop/combinators/goal_seek) を kind/feature/階層ゲートに従って焼いた
- [ ] index(main) を P01..P13 phase_number 昇順で全列挙し、完了条件・コンポーネント目録の所在・`plugin_meta`(manifest/marketplace/cachebuster/validation を含む plugin 階層規律) を記載した
- [ ] index `## 基本定義` に仕様駆動の大前提 (harness-creator 仕様基点・spec-first・要件正本=goal-spec) を宣言し、goal-spec checklist の全 id を 完了チェックリスト/受入確認 で引用した (`check-requirements-coverage.py` が exit0)
- [ ] 各 inventory component が ≥1 phase の `entities_covered` に出現 (orphan 0 件)
- [ ] `check-spec-frontmatter.py` / `check-spec-gates.py` / `verify-index-topsort.py` / `detect-unassigned.py` が exit0 になった
- [ ] `derive-task-graph.py <PLAN_DIR>` を実行し `task-graph.json` をデフォルト成果物として生成し、`validate-task-graph.py <PLAN_DIR>` が exit0 になった (2.5)
- [ ] `shape_marker=task-graph-derived` の場合、D 契約を満たす `task-specs/*.md` を生成し、全実行可能 leaf が `execution_kind`/`task_spec_ref`/`acceptance_criterion`/`write_scope` を持ち、component-build だけが `route_ref` を持つ
- [ ] `handoff-run-plugin-dev-plan.json` を生成し `task_graph_ref` を常時付与し、`check-build-handoff.py` が exit0 になった

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-plugin-dev-plan (Phase03-Phase12 の成果物生成)
- 後続 phase: R4-verify-traceability

### 6.2 ハンドオフ / 並列性
- 並列: 13 phase ファイルと inventory component を独立 fork で生成し結果を index へ統合

## Layer 7: 提示層

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 ユーザー提示形式
- 13 phase ファイル (Markdown) + index.md(main 目次) + component-inventory.json

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール + 5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・実行・自己評価する。入力 `component_inventory` と `goal_spec`
を Read し、13 phase ファイルと、評価基準を焼いた inventory component と、P01..P13 昇順 index を生成する。出力は次の
とおり (4 は `artifact_class=plugin-plan` 時のみ):

1. 13 phase ファイル (`phase-01-requirements.md` … `phase-13-release.md` / io-contract.md §2 frontmatter + §5 本文床を満たす)
2. index.md (P01..P13 phase_number 昇順 + コンポーネント目録の所在 + 全体完了条件 + 受入確認 + plugin_meta)
3. component-inventory.json (品質機構=quality_gates/harness_coverage/feedback_contract(skill loop) を焼いた各 component エントリ) と handoff-run-plugin-dev-plan.json (L3→L4 routing / builder / build_target / envelope status・routes は inventory 由来・`task_graph_ref` を常時付与)。**placement=skill の script route (builder=parent-skill-build) で build_target が親 skill の build_target 配下にあるものは、二相 build (scaffold→fill) の順序逆転を機械可読にするため `requires_parent_scaffold: <親 skill の component id>` を必ず付す** (io-contract §9・check-build-handoff.py が fail-closed 強制。plugin-root へ hoist した共有 script は親 skill 配下でないため不要)
4. **task-graph.json (デフォルト成果物)**: phase/index/inventory 確定後 (target shape は D 契約の `task-specs/*.md` 確定後) に `scripts/derive-task-graph.py <PLAN_DIR>` を実行して単一 writer 射影で生成し、`scripts/validate-task-graph.py <PLAN_DIR>` exit0 を確認する (2.5・手書き禁止)
5. (plugin-plan 時) `<PLAN_DIR>/envelope-draft/plugin.json` = 貼れる manifest ドラフト (manual-apply artifact・実 `plugins/` には書かない)

余計な前置き・後書き・思考過程出力は禁止。
