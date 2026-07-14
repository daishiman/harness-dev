# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`harness-creator` plugin (旧名 `skill-creator`) の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased]

初稿 2026-05-22。以下の内容は**実装済み・版番号確定待ち** (Keep a Changelog の順序に従い最上部に置く。実体は 1.2.0 改名以前に本文へ取り込み済み)。次回リリース時に版番号を確定して正式リリース節へ昇格する。

### Added

- **incremental verification planner**: `run-skill-live-trial/scripts/plan-live-trials.py` を追加。挙動閉包 SHA と schema-valid PASS/transcript SHA を照合して現行証跡を再利用し、既定の新規 live trial を最大2本・同時2本へ制限。`build-only` は実セッション0、`exhaustive` は明示時のみ全件再実走する。
- **Capability 統一抽象**: `Capability` / `CapabilityManifest` / `CapabilityBundle` の三層モデルを導入し、skill/agent/hook/command/prompt/workflow/plugin-composition を単一語彙で表現可能にした。
- **plugin-composition.yaml**: plugin 間の依存・公開 capability・consume 関係を宣言する composition manifest を新設。
- **target_type 7 種対応 rubric**: `skill` / `agent` / `hook` / `command` / `plugin-composition` / `prompt` / `workflow` の 7 種に対し、共通核 + kind 固有 addendum の rubric を提供。
- **governance/feedback hook 配線**: 7 種すべてに対し governance gate と feedback ループの hook を配線。
- **lessons-learned 自動記録**: review/executor 実行ログから lessons を抽出し自動追記する経路を実装。
- **EVALS → rubric 自動 PR 経路**: EVALS 結果から rubric の改訂 PR を自動生成するパイプラインを追加。
- **依存グラフ生成**: capability 間の依存を DAG として出力する仕組みを追加。
- **dogfooding メトリクス**: 自己適用率・rubric 充足率・lessons 反映率を計測する初期メトリクスを導入。
- **ナレッジループ機構 (knowledge-loop)**: 生成スキルに「知見を蓄積・検索・§12改善し使うほど良くなる」ループを注入する横断 capability を追加。
  - **Loop A (生成物側)**: `run-build-skill --with-knowledge index-search|router-registry` で `knowledge/` 雛形 + 3 段階検索 (Stage1/2=決定論 script、Stage3=AI) + §12 フィードバックループを注入。正本 `ref-knowledge-loop`、雛形 `templates/knowledge-skeleton/`、横断 combinator `with-knowledge.patch`(新 kind を増やさず和空間で全 kind に伝搬)。
  - **Loop B (メタ側)**: `plugins/harness-creator/knowledge/`(build-patterns + lessons-index)を新設し、`run-skill-elicit` が build-time に蓄積知見を検索して設計判断へ反映 (dogfooding)。
  - **SSOT**: Loop A/B は同一スクリプトを共有。検索/記録/index 各スクリプトに `--dir <store>` を追加し複製を排除。`lint-knowledge-loop.py` に `--store-only` モードを追加し共有スクリプト構成 (Loop B) を正当化。
  - **検証**: KL-001..006 (`lint-knowledge-loop.py`)、`knowledge-loop.schema.json`、`skill-brief.schema.json` の `knowledge_loop` / `consult_build_knowledge`、rubric `KL-*` ルール。
  - **日々のブラッシュアップ機構 (elegant-review 反映)**: 生成スキル側でも知見を日々更新・追加できるよう片開きループを両開き化。`add_entry.py`(必須6フィールド検証つき追加=JSON手編集を排除)を雛形に追加し KL-006(warn)で推奨。`record_usage.py --analyze --emit-queue`(要改善エントリの brushup キュー出力)+ `--mark-needs-update`(status 付与) を追加。検出は決定論・内容改善は AI の二層分離を維持。
  - **配置の抽象階層を明示**: Loop A(生成物側=自己完結ユニットゆえ scripts/ を同梱)と Loop B(メタ側=正本を `--dir` 共有・複製しない)は排他でなく抽象階層が異なる旨を `knowledge-construction.md` §0a と `with-knowledge.patch` 脚注で明文化。全集約による死蔵を回避。
  - **再現性の機構化**: `governance-check.yml` に lint-knowledge-loop `--self-test` / 雛形4スクリプト `--self-test` / Loop B `--store-only --strict` を配線。lint↔schema の必須6フィールド二重定義を `--self-test` 内 drift 検出で SSOT 化、lint↔CI 配線忘れも `--self-test` のメタ検査で再発防止。汎用雛形からペルソナ固有語彙(`sakamoto_*`)を除去し汎用フィールド名(`expressions`/`voice`)へ。
  - **量産時の注入を決定論化 (毎回の再現性)**: `render-combinators.py` に `with-knowledge.patch` の semantic handler と `--with-knowledge` フラグを追加。これまで他9 combinator が `apply_semantic_patch` の決定論ハンドラを持つ一方、knowledge-loop 注入だけハンドラ不在で AI 解釈依存(`ComposeError: unknown combinator` 経路)だった穴を塞いだ。注入内容(frontmatter `knowledge_loop` ブロック + `## ナレッジループ` 節)は同梱4スクリプト(`search_knowledge`/`build_index`/`record_usage`/`add_entry`)のみを参照し、harness-creator (旧 skill-creator) 内部(`ref-knowledge-loop`/`templates/`/Loop B/`--dir`)へ一切依存しない=配布スキル自己完結。冪等(再適用しても二重注入なし)。`run-build-skill` Step 10 のコピー対象を3→4スクリプトへ修正し注入本文と一致させ、KL 表記を `KL-001..007` へ揃えた。

### Added (2026-07-07 engine:task-graph 変種 = with-task-graph-goalseek build)

- **run-build-skill 0.3.0 — with-goal-seek の engine:task-graph 変種**: `brief.goal_seek.engine=task-graph` 指定時、checklist の `depends_on` 依存充足順消費 + self-reflect 追記 (発見タスクを単一 truth の checklist へ) の engine 変種を生成物へ焼込む。テンプレ 4 script (ENG-C01 `ready-set-from-checklist.py` / ENG-C02 `self-reflect-append.py` / ENG-C06 `extract-capability-dependency-graph.py` / ENG-C07 `record-capability-graph-knowledge.py`) を `templates/task-graph-engine/scripts/` に新設し Step 10.6 (prose Step・CLI flag 非新設=A2 制約) で生成先へ同梱。`render-combinators.py` へ変種 3 サブセクション (配線/機械検査 consumption verifier/dependency graph knowledge consult) を注入、`lint-goal-seek.py` へ変種 self-test 3 検査 (engine enum / depends_on schema / verifier トークン)、ENG-C08 `lint-capability-graph-knowledge.py` (同梱+consult+source_ref の横断ゲート) を新設。schemas (`build-flags` engine enum / `goal-seek-loop` の `depends_on`・`engine`) を additive 拡張。

### Changed (2026-07-07 30思考法 elegant-review 反映)

- **max_loops×checklist 規模の bound 連動規則**: 1 周回 1 item 消費×消費完全性の拘束下では done 化 item 数 ≤ max_loops のため、engine:task-graph では `max_loops` を checklist item 数×1.5 目安へ設定する規則を配線 prose / `goal-seek-loop.schema.json` / `goal-seek-paradigm.md` へ明文化し、consumption verifier へ bound 不足の早期診断 (WARN) を追加 (checklist>max_loops で completed 構造的不能になる合成欠陥の封鎖)。
- **done 記述=発火条件の明文化**: item 完了の `status: done` 記述そのものが次周回 ready 再計算の入力=次 item の発火条件である連鎖 (完了記述→ready 再計算→次 item 発火) を配線 prose と `goal-seek-paradigm.md` engine 変種節へ明文化。
- **ENG-C08 同梱検査を byte-parity 化**: 存在のみ検査→テンプレ原本との byte 一致検査へ強化 (手改変 script の緑通過を封鎖)。`--self-test` (BUNDLED_SCRIPTS↔SKILL.md Step10.6 列挙 parity + `lint-goal-seek.py` との `_CONCRETE_TASK_GRAPH_ENGINE_RE` 定義 drift 検査) を新設。
- **task-graph トークン検査の scope 限定**: `lint-goal-seek.py` の変種トークン検査を全文 substring から配線セクション scope 限定へ (LS-01b と同型・本文引用による偽陰性経路を封鎖)。
- **内ループ手順 4 をローリング発火 (イベント駆動) へ**: `commands/capability-build.md` の task-graph route モード内ループを「batch 全完了待ちの周回再呼出し」から「done write-back (TG-C02) 完了そのものを発火条件に、in-flight 残を待たず TG-C01 再計算→新規 ready を即時 dispatch」へ明文化 (完了記述→ready 再計算→次 task 発火の連鎖。conflicts/file_ownership 衝突候補の delay 直列化は維持)。
- **route report 層の cycle-dir 対応 (証跡名前空間衝突の恒久解)**: 同一 plugin への複数 plan 並走で `eval-log/<slug>/build/` flat 共有が route report/task-state を相互上書きする衝突に対し、handoff `cycle_id` (resolve_build_dir 既設計) を consumer 側まで貫通 — `build-script-route.py` の inputs_consumed と `validate-route-build-reports.py` の期待パスを flat 規約ハードコードから実 reports_dir 由来 (`report_rel`/`_report_rel_dyn`) へ変更 (flat 既定では従来と同一=後方互換・cycle build で flat 宣言する偽 provenance は fail-closed)。

### Removed (2026-07-07)

- **ENG-C06 の `--strict` 予約 no-op flag**: 既定が最厳格 fail-closed で緩和も強化もしない死表面のため削除 (YAGNI)。

### Fixed (2026-07-07 plan 台帳 write-back)

- **with-task-graph-goalseek plan 台帳の実装追随**: 「単一truち」誤字全域 (plan 9 ファイル+coverage record)・envelope-draft version drift (1.1.0→1.2.0)・C07 write_scope の機構契約→挙動契約化 (add_entry.py 非依存の stdlib 内蔵を正)・C08 同梱検査 2 本→4 本 parity と 3 段 consult 設計の明文化 (goal-spec/inventory/spec)・C06 plugin-composition 走査宣言の実装整合・C01 exit code 記載 (読込不能=2)・coverage record の TESTS 主張をテスト実体 (ファイル名/ケース数) と一致へ修正。
- **with-task-graph-goalseek build 証跡の名前空間分離再建**: 別 plan (plugin-plans/harness-creator) との flat dir 衝突で汚染された本 plan の route report/task-state を、handoff へ `cycle_id: "with-task-graph-goalseek"` を付与して `eval-log/harness-creator/build/with-task-graph-goalseek/` へ再建 (route report 8 本 covered_task_ids 焼込・plan-node-verification 13 本実測生成・346 node を sync-task-state transition (未知 id fail-closed+require-covered) で replay・TG-C01 ready 0/TG-C08 completion_gate ok/validate-route-build-reports --complete valid)。

### Added (2026-07-06 elegant-review 整合改善)

- **run-build-skill/scripts の機能テスト 4 本**: `validate-naming.py` / `set-frontmatter-field.py` / `render-hook-skeleton.py` / `render-settings-proposal.py` へ `tests/scripts-plugins/` に計 48 テストを新設 (各 script 行カバレッジ 95% 以上・CL-8 自己適用)。

### Changed (2026-07-06 elegant-review 整合改善)

- **Cxx 識別子の namespace 凡例を新設**: `references/pipeline-boundary-contract.md` に PB-Cxx (契約系) / TG-Cxx (task-graph 実行系) / ENG-Cxx (生成 harness 同梱 engine 系) / route・component Cxx (plan-local・文脈語必須) の凡例表と「裸 Cxx 禁止」規約を追加し、plugin 内全 doc・script docstring・テスト docstring の裸 Cxx を修飾 (同一 token 異義の解消)。
- **task-graph route モード既定の doc 統一**: README 標準フロー Step2 / `pipeline-command-reference.md` / `pipeline-boundary-contract.md` E2 記述に残っていた旧既定「route 1 件ずつ `--route-id` 反復」を「`--handoff` 1 回でグラフ全体 (既定) / `--route-id` は段階 build 用 escape hatch」へ統一。2 ループ機構の narrative 重複は制御フロー正本 (`commands/capability-build.md`) への参照+契約不変条件のみへ縮約。
- **lint-matrix.json 拡充**: CI 実行中だが未登録だった `lint-agent-prompt-content.py` / `lint-prompt-placement.py` を ci context で登録し、hook 配線 lint (`lint-capability-manifest.py`) のスコープ外理由を $comment に明記。

### Fixed (2026-07-06 elegant-review 整合改善)

- **doc↔実装の記載不一致**: TG-C01 (`dispatch-ready-set.py`) の受理引数記載を argparse 実装 (`--task-graph`/`--task-state`/`--planner-root` のみ) に一致させ、`file_ownership` の機械導出規則 (= node の `write_scope` + route 消費 node は `build_target`) を明文化。
- **dangling lint 起動指示の除去**: 実体のない `lint-command-md.py` / `lint-prompt-md.py` / `lint-workflow-md.py` を「未実装のため起動しない」へ (SKILL.md / build-steps.md 両面)。
- **plugin.json**: description の欠字 (「単一truち」) と version drift (1.1.0 → 1.2.0 追随) を修正。
- **frontmatter argument-hint**: `/capability-build` の `--route-id` が optional (escape hatch) であることを明示。
- **CHANGELOG 順序回復**: 本 [Unreleased] 節を Keep a Changelog 準拠の最上部へ移動し、旧パス表記 (`plugins/skill-creator/knowledge/`) を現名へ修正。
- **render-hook-skeleton.py**: 生成 skeleton の TODO(human) 文言を `# IMPLEMENT:` へ変更 (repo 方針準拠)。

### Removed (2026-07-06 elegant-review 整合改善)

- **superseded テスト残骸**: `tests/scripts-plugins/test_harness_creator__render_combinators_r1_superseded.py.bak` (被参照ゼロを grep 実証のうえ削除)。

### Fixed

- **`with-run.patch` の世代ずれ解消 (`run` kind 描画失敗)**: semantic handler が旧世代の固定手順(`### Step 1/2/3` を `## 手順` アンカーへ)を注入しようとし、goal-seek 化済みの現 `_base.md`(`## ゴールシーク実行` を全 kind が継承)とアンカー不整合で `run` kind が必ず `ComposeError` で落ちていた。固定手順注入は goal-seek 原則「固定手順は書かない」と矛盾するため廃止し、run handler は run 固有 frontmatter(`effect`/`role_suffix`)付与のみに責務を限定。手順は `_base.md` から継承するため情報欠落なし。レビュー用 `with-run.patch` diff も実 semantic 挙動へ一致(diff↔handler SSOT)。これにより全 18 kind×フラグ組合せ(run/ref/wrap/delegate/assign-gen/assign-eval × none/knowledge/all)が決定論合成 PASS。

### Changed

- **post-build 検証を profile 制御へ変更**: `/capability-build` と `run-build-skill` の既定を `incremental` にし、変更時の内容評価を独立 evaluator 1 context (4条件+rubric、既存2 verdictへ分離) に集約。思考リセット+30思考法3並列+rubric evaluator+最大3周は `exhaustive` 明示時だけにした。
- **live-trial 依存を Skill 単位へ縮小**: package sidecar の任意 `skill_dependencies` で `depends_on` を対象 Skill ごとの部分集合へ射影し、boot と behavior closure が同じ依存だけを load/hash する。無指定 package は従来どおり全 direct dependency を使う。
- **harness-creator native manifest 正規化**: `distributable` / `entry_points` / `requirements` を `references/package-contract.json` へ分離し、Claude plugin validator が受理する native manifest にした。
- **rubric 構造再編**: 単一 rubric から「共通核 + kind 固有 addendum」構造へ再編し、target_type ごとに必要項目を最小化。
- **validate-build-trace.py 汎化**: skill 専用検証から kind 対応の汎用検証へリファクタし、7 種すべての build trace を検証可能にした。

### Status

実装済み・版確定待ち。次回リリース時に版番号を確定して本セクションを正式リリースへ昇格する。

## [1.2.0] - 2026-07-02

### Changed

- **plugin 改名: `skill-creator` → `harness-creator`** (機械可読対応: `{"old": "skill-creator", "new": "harness-creator", "old_underscore": "skill_creator", "new_underscore": "harness_creator", "old_ja": "スキルクリエイター", "new_ja": "ハーネスクリエイター", "kit_old": "skill-creator-kit", "kit_new": "harness-creator-kit", "enabled_plugins_key_old": "skill-creator@harness", "enabled_plugins_key_new": "harness-creator@harness"}`)。
  理由: 本 plugin が構築するのは単体スキルではなく、skill/agent/hook/command/評価/統治を束ねたハーネス全体であるため。
  意味論境界 (単体スキル生成=skill 表現維持 / 総体構築=harness 表現) は CONVENTIONS.md「用語規約」と `ref-skill-glossary` の「ハーネス」エントリが正本。内部 skill 名 `run-skill-*` は単体スキル概念のため意図的に維持。
- 機械層追従: `NEVER_DISTRIBUTE` / `SELF_DOGFOODING_PLUGIN` (正本+vendored byte 一致) / `VENDORED_PAIRS` / CI 固定パス (4 workflow) / Makefile / `.claude/settings.json` enabledPlugins キー / upstream-pins (path+sha256) / criteria_roster / テストファイル名 `test_skill_creator__*` → `test_harness_creator__*`。
- 移行手順: 既存ローカル環境は enabledPlugins の旧キー削除+新キー追加が必要 (README「改名の移行手順」参照)。旧キーのままでは plugin が未ロードになり hooks が発火しない。

### Added

- `scripts/lint-legacy-plugin-name.py` (repo root): 旧固有名 3 変形の能動層再流入を fail-closed 遮断 (governance-check.yml / make lint / run-ci-checks.sh に配線)。
- dir↔SSOT 定数 parity test / NEVER_DISTRIBUTE 実在 test / `_JUDGMENT_LITERAL_RES` の SSOT 導出化 (`tests/test_dogfooding_boundary.py`) — 将来の plugin 改名でも fail-closed。
- 過去の評価履歴は `eval-log/skill-creator/` に凍結 (tombstone README で双方向参照)。新規 run は `eval-log/harness-creator/` に記録。
