---
name: io-contract
description: 生成スキルの入出力契約と、生成プラグインが満たすべき検証接続/Markdown evidence 定義を読む。R3 出力形式と R4 検証の正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 入出力契約と検証 (§9 入出力契約 / §10 検証・evidence)

> パスはすべて repo root 相対。

## §9 生成スキルの入出力契約

- **入力**: プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望)。`--mode create|update`。任意で **skill-intake の intake.json** (schema_version 2.0.0) を構造化 `plugin_concept` 入力として受理する: `sections.0_executive_summary` (true_purpose_oneliner / pattern) / `sections.3_purpose_excavator` (true_purpose / underlying_motivation / output_priority) / next-action.json の `split_candidates[]` を goal-spec (purpose/background/goal/checklist) 写像の材料とする (供給側契約は `plugins/skill-intake/references/handoff-contract.md` の「plugin-dev-planner 分岐 (mode P)」節)。
- **処理**: R1(要件定義)→R2(分解)→R3(生成)→R4(検証) の責務を goal-seek ループで実行し、13 フェーズ (`phase-lifecycle.md` §8 の P01..P13) を成果物へ写像する。各責務の詳細プロンプトは `prompts/R1-R4`。
- **出力** (2 軸直交・単一 SSOT + 複数 projection。詳細は `component-domain.md`):
  1. **13 phase ファイル (Markdown)** — `phase-01-requirements.md` … `phase-13-release.md`。各々が §2 の phase frontmatter (`PHASE_REQUIRED`) を携帯し、本文は上から順に読める宣言型タスク仕様 (8 節・§5 表参照・ライフサイクル軸=人間向け primary deliverable)。命名は `phase-NN-<kebab>.md` (NN=ゼロ埋め 2 桁・kebab は `specfm.PHASE_NAMES`)。
  2. **index.md(main)** = P01..P13 を **phase_number 昇順**で列挙した目次 + 全体完了条件 + 受入確認 (build 後の見方) + plugin 階層規律 (`plugin_meta`)。§3 参照。
  3. **component-inventory.json** = buildable 実体軸 (機械) の**唯一の SSOT**。5 種を検討した証跡 (`considered_component_kinds`) と、実際に生成する buildable components (build routing・1 実体=1 `build_target`・依存 DAG・品質機構=旧 C*.md frontmatter の載せ替え先)、plugin-level surfaces の採否・不要理由。省略理由の正本キーは `plugin_level_surfaces.<surface>.omitted_reason` 一本のみ (評価器が読むのもこのキーのみ)。

phase ファイルは build_target/depends_on を**再記述しない** (正規化)。component は `entities_covered: [C01, ...]` の id 参照だけで phase に紐づく。**本数は 13 固定** (フェーズ数) であり、旧 per-component 分解の本数論争 gate 強制は廃止した (本数は input でなく output)。buildable な実体数 N は inventory の `components[]` 件数として現れる (13 とは独立)。ユーザーの本数要求は goal-spec に任意記録可 (gate 強制しない)。

### 出力先 (決定論的に解決・再現性の SSOT)

タスク仕様書の出力先は曖昧にせず**決定論的に解決する** (同一構想 → 常に同一ディレクトリ)。

| 項目 | 規約 |
|---|---|
| **既定パス** | repo-root (`$CLAUDE_PROJECT_DIR`/cwd) 相対の **`plugin-plans/<plugin-slug>/`** (可視・永続の tracked deliverable・捨て置き scratch でない) |
| **`<plugin-slug>`** | 対象プラグインの **ASCII kebab フォルダ名** (例 `notion-task-sync`)。**R1 が `goal-spec.json` の `target_plugin_slug` に固定し全 goal-seek 周回で不変** (中間成果物アンカーと同じ不変アンカー原則=ループが何周しても出力先がブレない)。R1 は構想自由文でなく確定済みの target plugin kebab 名を渡す (日本語主体の自由文は ASCII 以外が脱落し別構想と slug 衝突しうるため) |
| **slug 導出** | 決定論: 小文字化 → 英数とハイフン以外を `-` → 連続ハイフン圧縮 → 前後 `-` 除去 (`specfm.plan_slug` が正本実装) |
| **上書き** | `--out-dir <path>` 明示指定で既定を上書き (相対は repo-root 基準)。指定値も `goal-spec` に固定 |
| **内容** | `goal-spec.json` + `run-plugin-dev-plan-progress.json` + `run-plugin-dev-plan-intermediate.jsonl` + `index.md`(main) + `component-inventory.json` + `phase-01-requirements.md` … `phase-13-release.md` (**13 本・フェーズ 1 段階=1 ファイル**) + `task-graph.json` (**デフォルト成果物**・13 phase §5 + inventory `depends_on` を `derive-task-graph.py` が単一 writer 射影・build を task-graph mode で駆動) + `handoff-run-plugin-dev-plan.json` (`task_graph_ref` 常時付与) + `plan-findings.json`。`examples/sample-plan/` と同形の plan 成果物を plugin 別ディレクトリに同居 |
| **phase ファイル命名** | `phase-<NN>-<kebab>.md` (NN=ゼロ埋め 2 桁 phase_number・kebab は `specfm.PHASE_NAMES` の 13 enum。例 `phase-03-design-review.md`)。id は frontmatter が正本 (`verify-index-topsort.py`/`detect-unassigned.py` は frontmatter `id` (P01..P13) で突合する)。`index.md`(main) の名は据え置き。buildable 実体は phase ファイルでなく `component-inventory.json` の `components[]` (id `C<NN>`) が持つ |
| **PLAN_DIR** | 検証 core 5 scripts / 6 invocations、build handoff gate、R4 evaluator はこの出力先を `PLAN_DIR` 引数に取る。plugin-dev-planner 自身の dogfood は別途 `check-plugin-surface-audit.py --plugins-dir plugins --strict-manifest --expect-plan-ready plugin-dev-planner` で現物 surface を横断棚卸しする。`specfm.plan_output_dir(name, out_dir)` が解決の正本 (第 1 引数は生 plugin 名でも `plan_slug` 済 slug でも可=冪等。戻り値は repo-root 相対で、絶対化は呼び出し側が repo-root 基準で行う) |
| **component kind 検討証跡** | `considered_component_kinds` は 5 種 (`skill`/`sub-agent`/`slash-command`/`hook`/`script`) を全列挙する。これは「全種を検討した」証跡であり、「全種を必ず生成する」要求ではない。生成対象は `components[]` に必要最小で列挙する。`check-surface-inventory.py` がこの分離を機械検査する |
| **L3→L4 追跡 (`build_target`)** | 各コンポーネント (inventory / index) は run-skill-create が実体を置く L4 パスを `build_target` に記録する (例 skill→`plugins/<plugin-slug>/skills/<skill>/`、sub-agent→`plugins/<plugin-slug>/agents/<name>.md`、hook→`plugins/<plugin-slug>/hooks/<name>.py`、slash-command→`plugins/<plugin-slug>/commands/<name>.md`、script→親 skill の `scripts/<name>.py`)。計画(L3)は専用 dir に分離しつつ「どの仕様書がどこで実体化するか」を追跡可能にする (co-location せずトレーサビリティ確保)。**`detect-unassigned.py` が object 形式 `component-inventory.json` の各 component に `build_target` 非空を機械検査**し、doc-only に留まらせない (欠落で exit1)。hook→`plugins/<slug>/hooks/<name>.py` は**量産先の既定配置**で、harness-creator 自身のように hook を所有 skill の `scripts/` へ co-locate する hand-built plugin は本 taxonomy の対象外 (`placement_scope` を持たない意図的例外・生成される plan の component ではない) |
| **非生成 / 追跡** | 実プラグインディレクトリ (`plugins/<plugin-slug>/`) は本スキルでは作らない (計画のみ・L4 は run-skill-create が生成)。`plugin-plans/<plugin-slug>/` の deliverable (index/13 phase files/inventory/handoff/goal-spec/plan-findings/envelope-draft) は tracked (可視・永続)。goal-seek の transient 作業ログ (progress/intermediate/`.goal-seek/`) のみ gitignore 対象 |

- **後段接続**: 各 inventory component → `run-skill-create`(L1) / `run-build-skill` → L4 build。本スキルは投入も build もしない。

### phase ファイル frontmatter 契約 (§2・PHASE_REQUIRED projection・parity test 対象)

各 `phase-NN-<kebab>.md` は下表の frontmatter を必ず携帯する。**SSOT=`scripts/specfm.py` の `PHASE_REQUIRED` + `schemas/phase-spec.schema.json`** で、下表はその**人間可読 projection**。両者の一致は `tests/test_kind_key_doc_parity.py` (doc↔`PHASE_REQUIRED`) と `tests/test_schema_parity.py` (schema↔`PHASE_REQUIRED`) が機械強制する。build_target/quality_gates/harness_coverage/feedback_contract は phase frontmatter に**置かない** (それらは inventory の component エントリが持つ=正規化)。

| キー | 型 / enum (SSOT) | 意味 |
|---|---|---|
| `id` | `P01`..`P13` (`specfm.PHASE_ID_RE`) | 大文字ゼロ埋め 2 桁のフェーズ id |
| `phase_number` | int 1-13 | id と一致し全 13 でユニーク |
| `phase_name` | `specfm.PHASE_NAMES` の 13 enum (kebab) | フェーズ名 |
| `category` | 日本語ラベル (`specfm.PHASE_CATEGORY`) | フェーズ分類 (enum 緩め) |
| `prev_phase` | int (P01 は 0) | 前フェーズ phase_number |
| `next_phase` | int (P13 は 14) | 次フェーズ phase_number |
| `status` | `specfm.PHASE_STATUS` (未実施/進行中/完了) | 進捗 |
| `gate_type` | `specfm.GATE_TYPES` の 8 enum | ゲート種別 |
| `entities_covered` | array of string (`C<NN>` 参照) | このフェーズが扱う inventory component id (該当なければ []) |
| `applicability` | object `{applicable: bool, reason: string}` | 非該当フェーズの明示 N/A (applicable:false のとき reason 非空必須) |

### inventory component エントリの構造契約 (旧 C*.md frontmatter の載せ替え先・skill 偏重を解消)

**plugin = 5 種の buildable component_kind × N 実体 + plugin-level surfaces** (`component-domain.md`)。5 種は分類軸で、各 kind に複数実体があれば**各実体を独立 component にする**。inventory は対象 `plugins/<slug>/` の shadow tree であり、各 `build_target` が 1 component・index の参照 1 行に対応する (実体数 N は inventory の射影であって input でない)。各 component は単一形状でなく `component_kind` を宣言し、kind 別に異なる構造キーを携帯する。`component_kind` ∈ {skill, sub-agent, slash-command, hook, script} を必須宣言し、`id` / `depends_on` (index 参照 + inventory DAG + orphan 検出に使う) は全 kind 共通。任意キー `couples_with` (対称・接合が密な同一 phase 兄弟の直列化宣言。`depends_on` の成果物ハード依存とは別概念で derive が同一 phase 直列化 depends_on へ展開し validate (j) が実現を検査する) も全 kind 共通の optional。manifest / harness / eval / composition / MCP / app connector は `component_kind` ではなく `plugin_meta` と inventory の surface に記録する。

> **kind→必須キーの正本は1つ (SSOT=`scripts/specfm.py` の `STRUCTURAL_REQUIRED`)**。下表と `prompts/R3-emit-specs.md` §2.2 の kind 別キー列挙は、その実行可能正本の**人間可読 projection** であって第二の正本ではない。両者の一致は `tests/test_kind_key_doc_parity.py` が機械強制する (specfm にキーを足して散文を忘れると fail)。旧 per-component の C*.md frontmatter はこの inventory component エントリへ載せ替わり、`specfm.validate_inventory_component` が component 単位で下表 + core 規律 + criteria purpose-traceability を fail-closed 検査する。手書きの穴埋め skeleton ファイルは持たず、必要時は `scripts/render-spec-skeleton.py` が specfm 正本から生成する。

> **skill component の kind 表現**: 下表 skill 行の `kind` (skill-brief base required) は、component エントリでは `component_kind` との衝突回避のため top-level `skill_kind` (fallback `kind`) として携帯する (`specfm._skill_kind_of` が両受容)。下表は STRUCTURAL_REQUIRED の projection のため parity 用に `kind` を列挙する。

| component_kind | 構造的必須キー (kind 固有) | 後段ルーティング |
|---|---|---|
| **skill** | skill-brief **base required 14**(実 schema 逐語): `skill_name`/`prefix`/`kind`(=run/ref/wrap/assign/delegate)/`hierarchy_level`/`trigger_conditions`/`output_contract`/`boundary`/`placement_candidates`/`cli_tools`/`deterministic_checks`/`external_systems`/`mcp_tools`/`needs_independent_context`/`needs_lifecycle_enforcement`。**条件付き**(allOf): kind∈{run,wrap,assign,delegate}→`goal`/`purpose_background`/`checklist`、kind∈{run,assign}→`responsibilities`、wrap→`base_skill`、delegate→`delegate_agent`。`output_language`/`mass_production_profile` は任意 property | `run-skill-create`(L1) へ 1 本ずつ投入 |
| **sub-agent** | `name`/`description`/`tools`(最小権限)/`independent_context: true`/`responsibility_anchor`(prompts 参照)/(任意)`evaluator_pair` | 親 skill build 内 `run-build-skill --with-subagent` |
| **slash-command** | `name`/`description`/`argument-hint`/`allowed-tools`/`disable-model-invocation` | 親 skill build 内 run-build-skill kind=command dispatch |
| **hook** | `event`(PreToolUse\|PostToolUse\|Stop\|UserPromptSubmit\|SessionEnd)/`matcher`/`exit_semantics`(fail-closed は exit2)/`settings_wiring`/`fail_closed: true` | 親 skill build 内 `run-build-skill --with-hooks` |
| **script** | `/// script` 相当 (`script_name`/`purpose`/`inputs`/`outputs`/`exit_codes`/`network`/`write_scope`) + `stdlib_only: true` + `tests_min: 80` | 親 skill build の scripts/ + tests/ |

`run-skill-create` は **skill 専用**。非 skill 4 種は単独投入せず、親 skill の build フロー (run-build-skill の kind dispatch / `--with-*`) で生成される。

### phase ファイル本文 section 契約 (§5・宣言型 8 節・正本=`specfm.PHASE_BODY_SECTIONS`)

frontmatter は specfm が厳格に operationalize する一方、本文 (prose) は LLM の判断を要するため形状を凍結しない。ただし**空セクションを許すと品質精度の床が抜ける**ため、本文にも最小の機械的な床を敷く。**節集合の正本は `specfm.PHASE_BODY_SECTIONS` (宣言型 8 節) で、下表はその人間可読 projection** — `scripts/detect-unassigned.py` は同定数を `REQUIRED_SECTIONS` として import し床 (`empty_body_sections`) を fail-closed 強制する。**宣言型** = 手続き的な「実行タスク」節を置かず、前提/目的/背景と到達状態 (成果物) + 二値条件 (完了チェックリスト) で書く (HOW=具体手順は後段 build/実行者に委ねる)。8 節は**単独実行の自足性** (実行者が当該 phase ファイルだけで着手→完了判定→次 phase へ移行できる) を狙う — ドメイン知識が phase 固有の前提知識を、スコープ外が「どこで止めて誰に渡すか」の境界を宣言する。各 `phase-NN-<kebab>.md` に適用:

| section | 必須 | 中身の床 (機械強制) | 中身の指針 (非強制・ゴールデン例が手本) |
|---|---|---|---|
| `## 目的` | yes | 見出し存在 + 直後に非空本文 | このフェーズが達成する到達状態の意図を 1-3 文 |
| `## 背景` | yes | 見出し存在 + 直後に非空本文 | 文脈・前段の状況・関連制約 |
| `## 前提条件` | yes | 見出し存在 + 直後に非空本文 | 開始前に満たすべき状態・受け取る入力 (先行成果物/参照/component id) |
| `## ドメイン知識` | yes | 見出し存在 + 直後に非空本文 | 実行者が repo/前段成果物から導出できない phase 固有の用語・不変条件・外部制約。plan 全体の用語集は index `## ドメイン知識` を引用し**差分のみ**記載 (重複焼込禁止)。phase 固有分が無ければ「index の用語集で足りる」旨を明示 (情報の膨張でなく漏れの封鎖が目的) |
| `## 成果物` | yes | 見出し存在 + 直後に非空本文 | 確定/生成する到達成果物 (build 実体は inventory が SSOT) |
| `## スコープ外` | yes | 見出し存在 + 直後に非空本文 | このフェーズで**扱わない**事項と委譲先 phase/component (境界宣言)。次タスクへの移行点を確定し、実行者のスコープ逸脱 (先回り実装・手続き化) を防ぐ |
| `## 完了チェックリスト` | yes | 見出し存在 + 直後に非空本文 | 完了=達成を宣言的に判定する観測可能な二値項目 (gate フェーズは gate_type の合否) |
| `## 参照情報` | yes | 見出し存在 + 直後に非空本文 | 参照すべき正本・資料・関連 component/phase |

`applicability.applicable == false` の phase は section 床を免除し、`reason` を本文に記す (非該当フェーズの N/A 明示)。機械の床は「見出し存在 + 非空本文」までに留める (意味検査はしない=Goodhart 回避)。床を超える本文の精度は**下流トラスト** (後述 §10) と evaluator の意味判定に委ねる。skeleton 穴埋めファイルは置かない (形状の正本は frontmatter=specfm、本文は床付きの自由記述・`scripts/render-spec-skeleton.py --phase N` が specfm から生成する)。

### build handoff 契約 (L3 計画 → L4 実 build の橋)

`handoff-run-plugin-dev-plan.json` は、plan が「後段で build できる粒度か」を機械検証するための routing artifact。routes[] は **`component-inventory.json` の `components[]` から導出**する (phase からではない=build は component 単位)。run-plugin-dev-plan 自身は L4 実 build を実行しないが、後段 `run-skill-create` / `run-build-skill` / 将来の scaffold executor が消費できるよう次を必須にする。**旧 top-level の本数論争フィールドは per-phase 転換で削除した** (13 固定はフェーズ数で、buildable 実体数は inventory 件数)。

| field | 要件 |
|---|---|
| `plan_dir` | 解決済み PLAN_DIR。repo-root 相対または絶対パス |
| `target_plugin_slug` | ASCII kebab plugin slug |
| `mode` | `create` / `update` |
| `task_graph_ref` | **必須** (task-graph はデフォルト成果物ゆえ常時付与)。`{path: "task-graph.json", schema_version: "1.0"}`。consumer=`/capability-build` はこれが在れば task-graph 2 ループ mode (依存グラフ駆動 dispatch + discovered-task 還流) で駆動する。`check-build-handoff.py` が実在を fail-closed 検査し、`validate-task-graph.py` が実体 10 検査を担う (責務分離) |
| `routes[]` | inventory DAG の top-sort 順。各 route は `id` / `component_kind` / `name` / `spec` / `depends_on` / `builder` / `build_kind` / `build_args` / `build_target` を持つ (inventory component 由来) |
| `routes[].status` | **plan-time 宣言のみ** (`planned` 等)。build 後も据置が正 — 実行状態の正本は consumer 側 `task-state.json` / route-build-report で、live 可視化は `task-graph-status.json` (TG-C09 投影)。consumer は handoff を書かない (単一 writer)。この値を実行状態として読まないこと (harness 側正本 = `references/pipeline-boundary-contract.md` 同旨) |
| `routes[].spec` | 参照する phase ファイル (任意)。**推奨: 当該 component が実装される Phase05 ファイル `phase-05-implementation.md`** (トレース用)。build は component 単位ゆえ phase 参照は必須でない |
| `routes[].builder` | skill→`run-skill-create`、sub-agent/slash-command/hook→`run-build-skill`、script→`parent-skill-build` (既定 `placement_scope=skill`)。**共有 script (`placement_scope=plugin-root`) は `plugin-scaffold`** で `plugins/<slug>/scripts/` へ hoist する。写像は `specfm.builder_for(component_kind, placement_scope)` が SSOT (route/inventory 両辺で `placement_scope` を一致させる) |
| `routes[].build_kind` | skill→`skill`、sub-agent→`agent`、slash-command→`command`、hook→`hook`、script→`script` (`specfm.BUILD_KIND_BY_KIND` が SSOT)。`run-build-skill` の Capability 7 kind へ渡す実行 kind を明示する |
| `routes[].placement_scope` | (script のみ・任意/既定 `skill`) `skill` = 親 skill 配下に畳む / `plugin-root` = `plugins/<slug>/scripts/` へ hoist した共有 script。inventory component の `placement_scope` と一致させる |
| `routes[].build_args` | 後段 builder へ渡す最小引数。`run-build-skill` route では `kind == build_kind` を必須にする。`plugin-scaffold` route (plugin-root script) は `script_path` 非空必須 (親 skill 不要) |
| `routes[].build_args.brief_path` | (skill route のみ) `scripts/render-skill-brief.py --inventory <PLAN_DIR>/component-inventory.json --component <id>` が inventory から決定論射影する skill-brief JSON の PLAN_DIR 相対出力先。brief 実体は plan に置かない (render で生成される宣言) |
| `routes[].builder_status` | `executor-backed` (実行 skill が実在) / `contract-only` (planner 上の routing 語彙で、run-build-skill の 7 kind ではない)。SSOT は `specfm.BUILDER_STATUS`。contract-only route は `gap_ref` 必須 (`check-build-handoff.py` が fail-closed 強制) |
| `routes[].gap_ref` | contract-only route が参照する `open_issues[].id` (routing 語彙の構造化参照)。L4 では `/capability-build` が script route を `build-script-route.py` に委譲する |
| `routes[].requires_parent_scaffold` | (placement=skill script のみ) `build_target` が親 skill の `build_target` ディレクトリ配下にある script は、二相 build (scaffold→fill) の順序逆転を後段 consumer が routes 配列順でなく守れるよう、自身を内包する親 skill の id を機械可読に宣言する。`check-build-handoff.py` が `build_target` 包含から親を特定し一致を fail-closed 検査する (散文 `build_sequencing_notes` 依存の機械可読化・M2)。plugin-root へ hoist した共有 script は親 skill 配下でないため不要 |
| `envelope` | manifest/marketplace 等 plugin-level surface の owner/status/build_target。`external_gap` / `manual-user-gated` は gap/approval reason 必須。**`envelope.manifest.draft_path` = `<PLAN_DIR>/envelope-draft/plugin.json`** (Phase02=設計 が owner) |
| `envelope.manifest.draft_path` | `<PLAN_DIR>` 相対の manifest draft。存在・JSON parse・`name == target_plugin_slug`・未解決 placeholder 不在を検査する |

**builder → 実行手段の解決表** (SSOT=`specfm.BUILDER_STATUS`・消費側が routes を dispatch する際の唯一の対応表):

| builder | builder_status | 実行手段 |
|---|---|---|
| `run-skill-create` | executor-backed | skill component を 1 本ずつ L4 build (`build_args.brief_path` の skill-brief を投入) |
| `run-build-skill` | executor-backed | sub-agent/slash-command/hook を Capability kind dispatch で build |
| `parent-skill-build` | contract-only | 親 skill 配下 script の routing 語彙。L4 では `/capability-build` が `build-script-route.py` に委譲し、親 skill ディレクトリ配下へ配置する (`gap_ref` 必須) |
| `plugin-scaffold` | contract-only | plugin-root 共有 script hoist / envelope scaffold の routing 語彙。script route は L4 で `build-script-route.py` が `plugins/<slug>/scripts/` へ配置する (`gap_ref` 必須) |

`scripts/check-build-handoff.py` が spec (phase ファイル・任意) 実在、top-sort、builder/build_kind/build_args 整合、builder_status/gap_ref (contract-only の gap 起票)、二相 build 順序 (`requires_parent_scaffold`・placement=skill script の scaffold→fill)、routes↔inventory 件数/`build_target` 一致、manifest draft、envelope gap reason を検査する。これにより「inventory をもとにプラグインを構築できるか」の最低条件を、実 build 実行前に fail-closed で確認する。

**route 実行レポート (L4 復路・受け渡し契約)**: 本 handoff は往路 (計画→build) の routing のみで実行結果を運ばない。後段 builder は route 1 本の build 完了ごとに実行レポートを `eval-log/<target_plugin_slug>/build/route-<id>.json` へ書き、後続 route は自身の依存 route のレポート (`handover`/`deviations`) を読取宣言 (`inputs_consumed`) 付きで消費してから着手する (依存レポート欠落/failure は着手不可の fail-closed)。契約・schema・検証器の正本は consumer 側 = `plugins/harness-creator/skills/run-build-skill/` の `references/route-build-report.md` / `schemas/route-build-report.schema.json` / `scripts/validate-route-build-reports.py` (route 毎 `--route <id>` / 終端 `--complete`) であり、planner はレポートを生成しない (書き手=build 実行主体)。eval-log 配下は transient で、恒久 trace は built plugin 実体 + `validate-plan-coverage.py` が担う。

### core 規律 (全 buildable component が必ず携帯。inventory component エントリへ焼く)

harness-creator ネイティブ規律を参照でなく **inventory component エントリのキーへ焼いて検証**する (operationalize)。`specfm.validate_inventory_component` が component 単位で下記を fail-closed 検査し、`check-spec-frontmatter.py` (構造 + criteria) と `check-spec-gates.py` (quality_gates/harness 値域 + index.plugin_meta) が inventory を走査して機械強制する。

```yaml
quality_gates:
  p0_lint: [<component_kind 別の必須 lint 名を網羅>]   # skill は P0 lint 8 本
  build_trace: required                                # F2
  elegant_review: {conditions: [C1, C2, C3, C4], all_pass: true}  # A1
  content_review: {verdict: PASS, sha_match: true}     # A8
  evaluator: {threshold: 80, high_max: 0}              # A5
harness_coverage:
  min: 80                                              # C1/C2 (スカラでなくブロック)
  kind_pass: <ref→source-traceability+ref-review / assign→evaluator verdict / loop→criteria検証test+content-review verdict>
```

`quality_gates.p0_lint` が網羅すべき必須 lint 集合は component_kind 別 (`specfm.P0_LINT_BY_KIND`): skill=8 本 / sub-agent=[validate-frontmatter,lint-skill-description,lint-agent-prompt-section] / slash-command=[validate-frontmatter] (command 専用 lint は未提供) / hook=[validate-frontmatter,lint-script-frontmatter] / script=[lint-script-frontmatter]。

### 条件付き規律 (kind/feature/階層でゲート。盲目的に全 component へ焼かない=bloat/Goodhart 回避)

| 規律 (キー) | 適用条件 | 焼き先 |
|---|---|---|
| `feedback_contract.criteria` (B1) | skill かつ skill_kind∈{run,wrap,delegate} (ref/assign は `skip_reason` 可)。criteria は当該 component の goal/checklist 由来 (**purpose-acceptance**)・汎用ゲート言い換え禁止 (`validate_inventory_component` が機械検証) | inventory component |
| `goal_seek` (D1/D2/D5) | skill かつ skill_kind∈{run,wrap,delegate} | inventory component |
| `prompt_layer: 7layer` (A11/E5/E6) | prompts を持つ component (skill run/assign, sub-agent) のみ | inventory component |
| `knowledge_loop` (G1) | opt-in (`features: [knowledge_loop]`) 時のみ | inventory component |
| `combinators` (D5/G2) | 全 skill (build flag 非該当時は空配列 `combinators: []` で no-flag を明示)。`check-spec-matrix-coverage.py` の述語 `_is_skill` が全 skill component に焼き先キー存在を要求する | inventory component |
| manifest/marketplace/cachebuster/配布判定/bundles/PKG/governance/CI/SSOT重複/feedback+Notion 受け皿 (plugin-creator + F3/F4/F5/F6/A10/A7/F7/D6/B4/B5) | **plugin 階層** (per-component でなく) | index(main) の `plugin_meta` (+ inventory `plugin_level_surfaces.notion_config`) |

`skill-brief.schema.json` 主要フィールドへ無加工で写せること (schema parity) は skill component で要件化する。

### index(main) の plugin_meta (plugin 階層の規律を焼く)

index frontmatter に `plugin_meta` を持たせ、plugin 階層の規律を集約する:

```yaml
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution: {distributable: <bool>, bundles: [...], marketplace: <bool>}  # F3/F4
  pkg_contract: {...}        # A7/F5 (plugin-package-evaluator / PKG 契約)・条件付き(下記)
  governance: {...}          # A10 (rubric governance runbook)・条件付き(下記)
  ci: {...}                  # F6 (governance-check.yml 配線)・コア(常に必須)
  ssot_dedup: {...}          # F7 (lint-ssot-duplication)・条件付き(下記)
  feedback_deploy:           # D6+B4/B5 (量産先への run-skill-feedback 配備 + Notion 受け皿)・コア(常に必須)
    deploy: run-skill-feedback
    enabled: true            # 配備しない構想は {enabled: false, reason: <非空>} の明示 opt-out のみ許す
    notion_sink:
      config_key: <DB キー名>   # plan が宣言するのはキーのみ (DB ID は書かない・設置先 .notion-config.json が供給)
      schema_ref: doc/notion-schema/improvement-request.schema.json  # B5 受け皿 schema (パス参照・複製しない)
      resolution: notion_config  # B4 解決器の名前参照 (実体 plugins/harness-creator/scripts/notion_config.py)
    portability: repo-bundled  # repo-bundled | vendored。distributable:true → vendored 強制
  # 条件付き 3 キー (pkg_contract/governance/ssot_dedup) は該当しない構想では
  #   <key>: {applicable: false, reason: "<N/A の根拠>"}
  # と明示宣言できる (例 skill のみ・非配布構想で PKG packaging が不要 → A7「skill-only は PKG 一部 N/A」と整合)。
  # 空 dict / 欠落は不可 (省略は必ず根拠付き明示=plugin_level_surfaces.<surface>.omitted_reason 原則と同型)。
```

`check-spec-gates.py` が plugin_meta を**値域検証**する (存在チェックでない): `manifest.path` は `.claude-plugin/plugin.json`、`manifest.validate_plugin` は true。`marketplace.policy.installation` は `NOT_AVAILABLE` / `AVAILABLE` / `INSTALLED_BY_DEFAULT`、`marketplace.policy.authentication` は `ON_INSTALL` / `ON_USE`、`category` は非空。`distributable` は bool 必須。`distributable:false` なら `bundles` は空 (=非登録を明示) かつ `marketplace` は false/不在 (非配布整合)。`distributable:true` なら `bundles` に最低 1 件。**コア** `manifest`/`marketplace`/`ci`/`feedback_deploy` は常に非空 dict (正本 `specfm.PLUGIN_META_CORE_DICTS`)。`feedback_deploy` は enabled:true なら `notion_sink` 値域 (config_key 非空 / schema_ref パス / resolution==`notion_config`) + `portability`∈{repo-bundled, vendored} を検証し、**`distributable:true` → `portability==vendored` を強制**、opt-out は `{enabled: false, reason: <非空>}` のみ許す。**条件付き** `pkg_contract`/`governance`/`ssot_dedup` は非空 dict だが、該当しない構想では `{applicable: false, reason: <非空>}` で明示 N/A 可 (reason 空はエラー)。matrix-coverage は焼き先スロットの addressed (空コンテナ・`{applicable:false}` 含む)、gates は値域、と責務分離する。

### plugin-level surface: notion_config (per-project Notion DB の解決宣言・B4/B5)

inventory の `plugin_level_surfaces.notion_config` は、生成 harness が読み書きする **project 可変な Notion DB 全般** (domain DB と `feedback_deploy.notion_sink` の feedback 受け皿の両方) を per-project に解決するための宣言スロット。`databases[]` には harness の component が使う domain DB キーを宣言し、feedback 受け皿キーは `feedback_deploy.notion_sink.config_key` 側が宣言する (二重に載せない)。**解決ロジックは複製せず名前参照のみ** (実体 `plugins/harness-creator/scripts/notion_config.py`・fail 方針は同スクリプトの require_or_skip fail-closed を継承):

```yaml
notion_config:
  required: <bool>
  resolution: notion_config   # 解決器の名前参照 (再実装禁止)
  databases: [{key: <DB キー名>, used_by: <component id>, direction: read|write|readwrite}]
  token: keychain             # トークン供給元の宣言のみ (値は書かない)
  omitted_reason: <required:false のとき非空>
```

`specfm.validate_surface_inventory` が required:true → `databases` 非空 + 各 `used_by` が実在 component id / required:false → `omitted_reason` 必須を fail-closed 検査する。**二層分離**: DB キー (論理名) は plan が宣言し、DB ID (具体値) は設置先 repo-root の `.notion-config.json` (gitignore) が供給する — plan 成果物に DB ID・トークンを一切書かない。

## §10 検証・完了条件 (harness 接続 / Markdown evidence)

対象スキル(L2)が `run-skill-create` 完了時に満たす条件 (詳細強制内容は harness-creator-spec-reflection.md):

| 接続先 | 検証 |
|---|---|
| **P0 lint 8 本** | `plugins/skill-governance-lint/scripts/` の 8 本 全 exit0 |
| **build-trace** | `validate-build-trace.py` exit0・章 coverage 全 PASS/N-A/skip |
| **content-review** | `scripts/lint-content-review.py` verdict=PASS (独立 SubAgent で genuine 生成・sha 一致) |
| **harness-coverage** | `validate-harness-coverage.py` / `make coverage-gate`。run=loop パス: criteria 検証テスト(inner/outer) + content-review verdict + 同梱 scripts 機能テスト ≥80% |
| **schema parity** | 各 skill component が `skill-brief.schema.json` 主要フィールドへ無加工で写せる |
| **evaluator** | `assign-skill-design-evaluator`(fork) score≥80 / high=0 |
| **elegant-review** | 新規/30 行超で C1-C4 全 PASS (`phase-output.schema.json` convergence_status enum 準拠) |
| **feedback_contract** | criteria を `feedback_contract_ssot.py`(SSOT) 制約に適合・content-review の criteria_evaluated と突合 |

**Markdown 主体プラグインの evidence 定義 (スクショ代替)**: lint exit0 ログ + schema parity + build-trace coverage 全 PASS + content-review verdict(PASS) + `eval-log/coverage/skills/<plugin>__<skill>.json`(mechanical/llm_eval)。**ランタイムスクショは取得しない** (取得不要を確定明記。対象=Claude Code の skill/plugin/hook/script=GUI ランタイム非保有の Markdown/CLI 主体ゆえ、視覚受入証跡でなく lint/test/coverage 等のテキスト受入証跡で完了を証明する)。

**本文トラスト境界 (L3 が保証する範囲・skeleton 不要の根拠)**: 本スキル(L3 計画)が**機械的に保証するのは (i) inventory component の shape (specfm/lint) と (ii) 評価基準=criteria の携帯、(iii) 13 phase ファイルの frontmatter+section 床**であり、**phase 本文 prose の最終的な内容品質は下流 L1 `run-skill-create` の再ヒアリング (`run-skill-elicit`) と build 時 evaluator の意味判定で確定する**。L3 の責務は「shape + criteria を運べる粒度 + §5 phase 本文の床 (空セクションを弾く)」までで、完成された本文ではない。ゆえに本スキルが渡す価値 (criteria を携帯した component) は inventory エントリに宿り、phase 本文穴埋め skeleton を新設しても搬送価値は増えない (skeleton 不要の構造的根拠)。中心問い「ひな形を持つべきか」は、この境界の明示により「shape=specfm/lint/例で既にひな形相当・phase 本文=床付き自由記述で下流が仕上げる」へ解消される。

**成果物評価の境界 (purpose-acceptance は委譲しない)**: 本スキルが下流へ委譲するのは**phase 本文 prose の仕上げ**であって、**成果物が当初 purpose を満たすかの受入基準 (purpose-acceptance) の定義ではない**。「build しない」を「評価基準も焼かない」と過剰一般化しない。purpose-acceptance は (i) 各 skill loop component の `feedback_contract.criteria` を当該 component の goal/checklist から導いて焼く (汎用品質ゲートの言い換えに退化させない・`validate_inventory_component` が purpose-traceability を機械検証)、(ii) index(main) に「受入確認 (build 後の見方)」章を持たせ goal-spec.purpose 由来の受入観点と平易語の確認の見方を記す、(iii) `EVALS.json` の `llm_eval` で受入が評価系に配線されていることを宣言する、の 3 点で **plan が契約として焼く**。実行 (criteria-test の実走) は build フェーズ (L4 `run-skill-create` の harness) が担い、planner は build しない原則と両立する (契約として焼く ≠ 実行する)。これにより「各 component が品質ゲートを携帯する」だけでなく「組み上がった実プラグインが purpose を満たしたか」を build 後に確認できる trace が通る。意味の正否 (criterion が purpose を正しく受入検証するか) は evaluator の意味判定に残す (機械層は語彙ゼロ参照の退化のみ検出=二層分離)。

**PR / feature→main は本スキルの焼き先対象外 (soft note)**: `phase-lifecycle.md` §8 P13 (release) のとおり PR 作成・`make validate`・`pytest` 緑化は **build 完了後の repo git 操作**で、本スキル(L3 計画)/`run-skill-create`(L1 build)いずれの責務でもない。`quality_gates`/§10 検証表/検査スクリプトに PR キーは設けない (operationalize しない=ユーザー意図「PR/Cloudflare/IPC は今回スコープ外」と整合)。Phase13 が言及する場合も「下流で人手が feature→main する」旨の soft note に留め、評価ゲート化しない。

## 配布・.claude 反映・install 携帯性 (F8)

計画が焼く plugin-root 資産 (schema / references / scripts / vendor) を巡る 2 つの問いへの回答を成文化する。

**(1) plugin-root の schema/references/scripts/vendor を `.claude/` へ反映する必要は無い (正しい)。**
`.claude/` は discovery surface (agents/skills/commands の 3 kind) 専用で、`build-claude-symlinks.py` が唯一の SSOT (`VALID_KINDS` 3 種) として展開する。runtime asset (schema/references/scripts/vendor) は install 時に **plugin dir 全体がコピー**され、実行時は `$CLAUDE_PLUGIN_ROOT` / self-relative で plugin 内解決されるため、`.claude/` への別途反映は不要。全反映は二重管理 / drift / 絶対パス混入で有害 (反映すべきは discovery surface のみ)。

**(2) 「install→plugin-root 資産まで実行できる」担保は 3 点で行う。**
(a) inventory component の `placement_scope` (`skill` | `plugin-root`) で配置境界を宣言する、(b) `check-runtime-portability.py` が「>=2 skill consumer の共有 script は plugin-root 必須」「build_target は plugin 内自己完結 (`plugins/` 始まり・`..` 不在)」を fail-closed 検査する、(c) install-portability 規律 (`harness-creator-spec-reflection.md` の F8) が cross-plugin SSOT は vendoring (byte 一致) または self-derive fail-soft loader で携帯性を担保することを規定する (先行事例 skill-intake / harness-creator)。これにより plugin dir コピー後、第二 consumer 側からも共有 script が dangling せず解決できる。

**placement_scope → builder → build_target の写像**: plugin-root script は `builder=plugin-scaffold` / `build_args.script_path` / `build_target=plugins/<slug>/scripts/<name>.py` (親 skill 配下に置かない)。skill placement script は `builder=parent-skill-build` / `build_target=plugins/<slug>/skills/<skill>/scripts/<name>.py`。写像正本は `specfm.builder_for`、検査は `check-runtime-portability.py` (共有判定) + `specfm.validate_inventory_component` (build_target 形状)。

## §11 本スキル同梱の決定論検査スクリプト (R1 入力ゲート + R4 検証を自然言語突合から機械化)

呼称は 2 層: **core 5 scripts / 6 invocations** (`verify-index-topsort` / `detect-unassigned` / `check-spec-frontmatter` / `check-spec-gates` / `check-spec-matrix-coverage`=`--self-test`+PLAN の 2 invocation) + **拡張ゲート 7 本** (`check-plugin-goal-spec` / `check-requirements-coverage` / `check-surface-inventory` / `check-build-handoff` / `validate-task-graph` / `check-runtime-portability` / `check-plugin-surface-audit`)。名称+起動引数の実行可能正本は `specfm.GATE_SCRIPTS`、**総数 (検証 12 本) と一覧の単一正本は下表** — SKILL.md / golden index の記述はこの projection であり、本数を再定義しない。task-graph はデフォルト成果物 (§9) ゆえ `validate-task-graph` は全 plan で必ず走る。

| スクリプト | 役割 (検査する完了チェックリスト項目) |
|---|---|
| `scripts/check-plugin-goal-spec.py` | R1 入力ゲート: `goal-spec.json` が汎用 goal-spec + plugin 固有アンカー (`target_plugin_slug`/`plan_dir`。`requested_count` は任意存置・本数固定フラグは廃止) を満たすか検証 (schema 契約は `schemas/plugin-goal-spec.schema.json`、両者の parity は `tests/test_check_plugin_goal_spec.py`) |
| `scripts/check-requirements-coverage.py` | (SDD・RTM) 要件→計画のトレーサビリティ: `goal-spec.json` checklist の各要件 id が index の `## 完了チェックリスト` / `## 受入確認` で引用されることを fail-closed 検査 (要件 orphan=silent drop 防止・detect-unassigned の component orphan 検査と鏡像)。id 照合は境界安全 (C1 が C01/C11 に誤マッチしない)。床は id トークン出現まで=充足の意味判定は evaluator (Goodhart 回避) (C2) |
| `scripts/verify-index-topsort.py` | (二層) index が P01..P13 を **phase_number 昇順**で全列挙 (phase 完全性) + `component-inventory.json` の component DAG 非循環 (top-sort 可能) を検査 (C1/C4) |
| `scripts/detect-unassigned.py` | (a) 13 phase ファイル全存在 + §5 section 床、(b) **各 inventory component が ≥1 phase の `entities_covered` に出現** (orphan 防止) + `build_target` 非空 (L3→L4 追跡) (C5) |
| `scripts/check-spec-frontmatter.py` | **phase ファイル frontmatter (`PHASE_REQUIRED`) を検証** + **inventory components を `specfm.validate_inventory_component` で検証** (component_kind 別構造 + skill loop の criteria purpose-traceability) (C2/C3) |
| `scripts/check-spec-gates.py` | **inventory components の `quality_gates`** (p0_lint 網羅/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) と `harness_coverage` (min≥80/kind_pass) + index.plugin_meta 値域を機械検証 (A1/A5/A8/C1-C2/F1/F2) |
| `scripts/check-spec-matrix-coverage.py` | `harness-creator-spec-reflection.md` の46行を component_kind/階層別適用述語で評価し、適用行の焼き先 (**inventory component** / index plugin_meta) の存在を検査。OP/conditional/N-A 内訳を出力。`--self-test` で46行 table drift 検出 |
| `scripts/check-surface-inventory.py` | `component-inventory.json` が 5 component_kind の検討証跡 (`considered_component_kinds`) と plugin-level surfaces (`manifest`/`composition`/`harness_eval`/`references_config_assets`/`schemas`/`vendor`/`mcp_app_connector`/`notion_config`) の required/omitted_reason を漏れなく持つことを検査 (`specfm.validate_surface_inventory` 追随) |
| `scripts/check-build-handoff.py` | `handoff-run-plugin-dev-plan.json` の L3→L4 routing を検証。routes は inventory 由来。builder 種別 (`placement_scope` を写す) / build_kind / build_args / build_target / spec (phase ファイル・任意) 実在 / top-sort / manifest draft / envelope gap reason。**`task_graph_ref` を必須検査**し、task-graph mode をデフォルト駆動にする (§9・未設定は fail-closed) |
| `scripts/validate-task-graph.py` | **デフォルト成果物 `task-graph.json` を検証** (§9)。DAG 非循環 / orphan 0 / producer 一意 / inventory 矛盾 0 / consumes producer 実在 / dangling edge 端点 0 / phase 非逆走 / **couples_with 直列化実現 (j)** / canonical node.state=pending seed 固定 / 非正準拒否 の 10 検査を fail-soft で実行。単一 writer=`derive-task-graph.py` の canonicalize を再適用し手書き編集を拒否する。(j) は inventory の couples_with (接合が密な兄弟ペア) が同一 phase 直列化 depends_on で実現され参照先が実在 component であることを検査 (未宣言候補の advisory 検出は `lint-sibling-coupling.py`=ハード 12 ゲート外の安全網) |
| `scripts/check-runtime-portability.py` | (C2/C4・F8) install 携帯性: (P) >=2 skill から共有される script は `placement_scope=plugin-root` で `plugins/<slug>/scripts/` へ hoist 済み、(Q) 全 component の `build_target` が plugin 内自己完結 (`plugins/` 始まり・`..` 不在)。`--self-test` で P/Q 検出を自己検査 |
| `scripts/check-plugin-surface-audit.py` | `plugins/` 配下の現物 plugin surface を横断棚卸し。skill/agent/command/hook/script/test/reference/config/assets/schemas/vendor/MCP-app/harness/composition/manifest と owned/symlink 内訳を数え、`--expect-plan-ready` 指定 plugin が必須 surface を dogfood していることを検査 |
| `scripts/render-spec-skeleton.py` | `specfm.py` から phase skeleton (`--phase N`) / component_kind 別の inventory component skeleton を生成。手書き skeleton ファイルを増やさず、ひな形の正本を実行可能契約へ一本化 |
| `scripts/render-skill-brief.py` | (射影器・ゲート外) inventory の skill component 1 件を skill-brief JSON へ決定論射影 (`--inventory`/`--component`/`--out`)。planner 固有キーを剥がし `specfm.SKILL_BRIEF_FIELDS` subset へ変換、実 schema 実在時は required 充足+余剰キー 0 を自己検証 |
| `scripts/check-upstream-pins.py` | (鮮度ゲート・plan 非対象) `references/upstream-pins.json` の引用先 sha256 を再計算し、上流 (harness-creator 等) の契約級ファイル変更を event-driven に検出。in-repo は不一致 exit1 (該当マトリクス行の再監査+pin bump を同一変更で要求)、standalone は verified_at を開示 |
| `scripts/specfm.py` | (import 専用) frontmatter 最小 YAML パーサ + phase (`PHASE_*`) / criteria / component_kind 契約 (`validate_inventory_component`) の SSOT |

`check-spec-matrix-coverage.py` の分類: OP=10 (全 buildable へ機械強制) / conditional=19 (kind/feature/階層でゲート) / N-A=17 (process・reference で per-spec 焼き先キーを持たない=計数のみ)。計 46 (内訳の機械正本は `--self-test` 出力)。
