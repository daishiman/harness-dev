# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`harness-creator` plugin (旧名 `skill-creator`) の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased]

### Changed (2026-10-09 rubric 1.5.0 と、cooldown・承認の照合の修正, ubm-goal-setting の elegant-review 継続 run)

下の 1.4.0 の後に、30思考法のレビューで出た24件を直した。対応表は `eval-log/ubm-goal-setting/_plugin/elegant-review/20261010-context-resolution/proposal-resolution.json`。

- **rubric 1.5.0（PROP-2026-10-09-ELEGANT-PD002、minor、incident_fix）**: PD-002 が冒頭30行の禁則として `## 守ること` の行全体の一致も認める。本文の単語「守ること」だけでは通さず、冒頭30行と禁則の両方の条件は変えていない。あわせて、BD-001 と PD-002 を「包含関係（BD-001 ⊂ PD-002）」と書いていた誤った説明を、「直交する2つの検査」に直した。既存の127件で would_regress 0。L2 の pin と hash、2つの governance-log を同期した。
- **検査とガードの修理（ELEGANT-2026-10-09-CHECKER-GUARD-REPAIR、P2）**: `render-findings-score.py` が knowledge カードの分母から派生物（graph・index）を外す。`guard-change-category.py`（repo と skill-governance-automation の2つ）は、P0 を無条件に分類していた誤りを直し、承認は `target_sha256` が現物と一致するものだけを有効にした。`target_path` は文字列でも配列でも同じ規則で照合し、以前の変更の cooldown は残す（例外は承認済みで `incident_fix=true` の記録だけ）。CI の `--bypass-cooldown` は外した。
- **生成側の日本語と2つの型**: `build-subagent.py` が `--language auto|ja|en` と `--role auto|advisor|writer` を取り、助言役と書き込み役の2つの型で7層のエージェントを生成する。`render-combinators.py`・静的テンプレート・Codex の locale 指定も同じ選択に従う。英語の既存の出力は変えていない。言語の選び方と訳さないもの（schema のキー・Layer・responsibility ID・frontmatter のキー）の正本は `skills/run-build-skill/references/ja-contract-policy.md`。
- **入口の配線の検査**: skill-governance-lint の `lint-skill-dep-step7.py` が、command から `Skill` で呼ぶ先がモデルから起動できること（`disable-model-invocation: false`）と、危険な run-* に外部変更ガードの受領書と正規の workflow があることを検査する。
- **parity 監査**: `audit-capability-parity.py` が、英語と日本語の本文それぞれで実行時のルートの必須トークンと、日本語の正本への参照を検査する。

### Added (2026-10-09 日本語の正規形を2つ目の正規形として足す, ubm-goal-setting の日本語化)

照合される見出しと定型ブロックは、これまで英語の1組しかなかった。そのため、SKILL.md やエージェントを日本語で書くと、中身が同じでも lint・採点・生成で落ちていた。英語の正規形は1文字も変えずに、日本語の正規形を2つ目として足した。日本語の文字列は scratchpad の仕様ではなく、照合する各モジュールに置いてある。

- **rubric 1.4.0（PROP-2026-10-09-001）**: BD-001・BD-002・PD-002 が、`## 目的と出力契約`・`## つまずきやすい点` を英語の見出しの別名として認める。日本語の見出しは行全体の一致だけを通し、英語の判定は部分一致のまま変えていない。緩和の superset なので minor・猶予0日（`diff-rubric-impact.py` で would_flip 0）。採点は `render-findings-score.py` の `*_HEADING_JA`、説明は `rubric-rationale.md` と `ref-skill-design-rubric` の評価軸の要約に反映した。L2 の `rubric_hash` は `check-rubric-sync.py` で同期した。
- **外部変更ガードと実行時のルート（repo の `scripts/build-artifact-delivery.py`）**: 日本語のガードブロック `<!-- external-mutation-guard-cli-ja:v1 -->` と、節 `## 実行時のルートの決め方` を足した。どちらの言語を使うかは、SKILL.md の Post-choice の見出しで決まる（`_skill_language`）。日本語のブロックは散文だけを訳し、コマンド行は英語版とバイト単位で同じにしたので、必須コマンドの検査は両方の言語に効く。`--migrate-external-guard` は両方の言語のブロックを取り除き、ファイルの言語の正規形だけを入れ直す。
- **入口の lint（`scripts/lint-entrypoint-artifact-first.py`）**: `## 選ぶ前の実成果物の作成` → `## 選んだ深さでの改善の実行` の組を受け入れる。組の中で言語を混ぜると落とす。
- **parity 監査（`audit-capability-parity.py`）**: 実行時のルートの契約を、日本語のトークンの組（`RUNTIME_ROOT_CONTRACT_TOKENS_JA`）でも照合する。どちらかの組が全部揃えば合格。
- **エージェントの見出し（skill-governance-lint の `lint-agent-prompt-section.py`）**: `## プロンプトの型`・`## 自己採点` を受け入れる。`## 自己採点` は rubric PR-002 がすでに認めていた別名に合わせた。
- **食い違いの防止**: 日本語の正規形は5つのスクリプトと rubric に分かれて置かれている。値がずれると、あるゲートは通るのに別のゲートで落ちる。そのため `tests/scripts-root/test_root__ja_contract_parity.py` で、等しいことと含まれていることを固定した（見出しの一致、節がトークンをすべて含むこと、ガードブロックが ssot lint の生成ブロックとして除外されること、PR-002・BD-001・BD-002・PD-002 の check が採点の定数を含むこと）。
- 日本語の正規形へ移したのは ubm-goal-setting だけ。他の13プラグインは英語のままで、移すかどうかは別に扱う。

### Fixed (2026-10-05 install 先での兄弟 plugin の解決, PR #83)

install 先は `<cache>/<marketplace>/<plugin>/<version>/` なので、`<plugin root>/..` や `Path(__file__).parents[N] / "<sibling>"` では隣の plugin に届かない。repo の `plugins/` でだけ動いていた参照を、install 配置に依存しない形へ直した。

- **実行する参照**: `run-skill-create` の p0-lint と manifest 登録、`run-build-skill` の `GOV_LINT_DIR`、`run-plugin-package-check` の PKG-009/015 は、同梱の `scripts/extract-plugin-root.py` で兄弟の root を解決する。Python 側 (`run-pkg-015.py`、`sandbox-plugin-lifecycle.py`、`lint-knowledge-loop.py`、`build-external-intelligence*.py` の forwarder、`sync-task-state.py`、`inject-task-inputs.py`) も同じ resolver を importlib で読む。見つからないときは、推測したパスへ落ちずに止まるか、既存の未導入時の扱いに任せる。
- **メタデータと引用**: `resource-map.yaml` の兄弟 bundle を `plugin:<name>/<path>` 記法にし、agents と `SKILL.md` の契約正本への言及を出典表記にした。
- **同梱**: `assign-skill-design-evaluator` が起動する rubric 合成器 `compose-rubrics.py` を `scripts/` へ同梱した (正本は skill-governance-automation。`lint-vendored-ssot.py` が byte 一致を検査する)。cwd 起点の repo パスへの fallback は削除した。
- **再発防止**: repo に `scripts/lint-sibling-plugin-paths.py` を足し、CI (`harness-creator-kit-ci.yml`) と `make lint` で、plugin 内の親ディレクトリ起点の兄弟参照を検出する。

### Fixed (2026-10-04 配布経路の完了境界と導入入口の一本化, harness-f11)

- `install-local-plugins.py` の digest から `.DS_Store`・`.claude/handoff/`・通常 directory を除外した。release 側が内容として扱わない差分だけで `stale_runtime` になり、版上げしても解消しない状態から抜け出せなくなっていたため。本体ファイルの差は今までどおり検出する。
- Codex への install も、変更する前に既存の marketplace source を `--check` と同じ手順で確かめるようにした。別の source を指す同名の登録は上書きしない。
- `/marketplace-register` を、両製品へ全 plugin を入れる共通入口 `install-local-plugins.py --all --platform both` に一本化した。旧 `make sync` の案内と、重複して書かれていた配布件数を削除した。

### Fixed (2026-10-04 install receipt の stale runtime 検出)

- `install-local-plugins.py` が copy install の `source_digest` と `runtime_digest` を記録するだけで比べておらず、同じ版番号のまま中身の古いキャッシュが残っていても `verified=true` を返していた。両者が食い違うときは `verification_status=stale_runtime`・`activation.runtime=stale` とし、receipt 全体の `status` と `next_action` で該当 plugin の版上げ (`scripts/build-plugin-release.py`) を指示する。CLI は版が動かない限りキャッシュを取り直さないため、修復手段は版上げだけである。
- digest は Claude CLI がキャッシュ直下に置く `.in_use` / `.orphaned_at` を除外し、ツリー内を指す symlink は字面ではなく着地点で記録する。CLI はコピー時に `Versions/Current/X` のような連鎖を `Versions/<n>/X` へ書き換えるため、字面で比べると忠実なコピーまで stale と誤判定する。

### Changed (2026-08-20 usable-first build)

- 既存の `draft / release` stage を再利用し、`/capability-build` と `run-build-skill` の既定を `draft` に変更。新たなMVP modeは増やさず、まず試せる実体+決定論ゲートで `usable-draft` として引き渡す。
- draft の自動修復を1周に制限。usable draft後だけ単一read-only評価Agentの起動をartifact+contractあたり最大1回認可し、完了時は別runでreceiptを再利用する。評価は30思考法を各1回適用し、所見提示後にユーザーが改善深度を選ぶ。完全監査の3独立Agent、実走、出荷仕上げはrelease/exhaustiveの明示選択後だけ起動する。

### Added (2026-08-20 user-bounded improvement)

- `build-improvement-gate.py` と初回診断/ユーザー選択receipt schemaを追加。usable draft fingerprint・単一context・read-only・canonical 30 method IDの全件をfail-closedで検査する。
- 改善深度を `現状維持 / 軽微 / 標準 / 詳細 / release` に分け、対象findingと反復上限を決定論化。回答前の改善、release自動昇格、exhaustiveの単一確認起動を禁止した。
- 初回診断をskill subtype限定から全7 Capability共通へ移し、複数component harnessも評価context総数1に固定。`build-review-launch.py` がdurable claimを同一lock下でatomic consumeし、Claude Code/Codex共通のread-only fresh-context requestをat-most-once認可する。再生・unsupported runtimeをfail-closedに拒否する。
- `elegant-bounded-improvement-executor` とpost-improvement validatorをdecision後のDAGへ接続。`accept-draft`はexecutor 0、他levelはselected findingとround上限だけを処理し、C1〜C4再検証なしに完了・release/exhaustive昇格しない。

### Added (2026-08-20 external intelligence loop)

- Codex / Claude Code 共通の `build-external-intelligence.py` を追加。runtime state を installed plugin 外の project/user state に保存し、thin index、on-demand detail、exact/near-duplicate 統合、hash-chain 検証を実装。
- observation → candidate → verified → promoted の証拠ゲートを追加。昇格には独立 evidence source 2件、別文脈の helpful reuse、owner 承認者+承認証跡、反証条件、rollback を必須化。曖昧な無人 hook 観測の隔離保存、superseded の終端化、派生 index/detail の利用時検証も追加。
- 両製品の PostToolUse payload を共通 engine へ渡す fail-soft adapter と native hook 配線を追加。

### Changed (2026-08-20 external intelligence loop)

- `knowledge/` / `lessons-learned/` を reviewed curated seed に限定し、旧 hook の package 内 Markdown/索引直接追記を削除。
- with-knowledge 生成契約を5スクリプトへ拡張し、runtime store を package 外へ固定。prompt cache/quota 削減は保証せず、重複統合・helpful reuse・再検索回避を直接 KPI とする。

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

- **run-build-skill 0.3.0 — with-goal-seek の engine:task-graph 変種**: `brief.goal_seek.engine=task-graph` 指定時、checklist の `depends_on` 依存充足順消費 + self-reflect 追記 (発見タスクを単一 truth の checklist へ) の engine 変種を生成物へ焼込む。テンプレ 4 script (ENG-C01 `extract-ready-set-from-checklist.py` / ENG-C02 `build-self-reflection-entry.py` / ENG-C06 `extract-capability-dependency-graph.py` / ENG-C07 `build-capability-graph-knowledge-entry.py`) を `templates/task-graph-engine/scripts/` に新設し Step 10.6 (prose Step・CLI flag 非新設=A2 制約) で生成先へ同梱。`render-combinators.py` へ変種 3 サブセクション (配線/機械検査 consumption verifier/dependency graph knowledge consult) を注入、`lint-goal-seek.py` へ変種 self-test 3 検査 (engine enum / depends_on schema / verifier トークン)、ENG-C08 `lint-capability-graph-knowledge.py` (同梱+consult+source_ref の横断ゲート) を新設。schemas (`build-flags` engine enum / `goal-seek-loop` の `depends_on`・`engine`) を additive 拡張。

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

## [1.4.49] - 2026-10-19

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## [1.4.48] - 2026-10-12

- 版番号だけを上げた。中身は 1.4.47 と同じ。利用者の手元の local marketplace には、1.4.47 の版番号のまま中身の違うもの（PR #85 の途中の作業ツリー）が入っていた。同じ版番号で中身が2通りあると、どちらが入っているかを版で見分けられないので、区別のために上げた。

## [1.4.47] - 2026-10-11

1.4.46 の後の変更をまとめる。git に版上げの記録が無いので、1.4.46 との境界は commit の日付で近似した（2026-10-11 の commit と、その後のまだ commit していない変更を本版に入れる）。下の 2026-10-12 の3節は `[Unreleased]` から移した（文面は変えていない）。

### Changed (2026-10-11 package 検査・検証の義務・生成器の入力検査, 独立レビュー i・j 回目の指摘)

- **digest から生成物を外す**: `scripts/feedback_contract_ssot.py` と PKG-003 は、`__pycache__`・`*.pyc`・`*.pyo`・`.DS_Store` を digest に含めない。正本と写しで別々に生成されると、中身が同じでも fingerprint がずれ、PKG-003 の偽陽性になっていた。
- **`validate-plugin-package.py`**: PKG-005 は、agent の frontmatter の name がファイル名と一致すること、SKILL.md の `subagent_refs` が指す agent が実在することを検査する。PKG-006 は `hooks/hooks.json` を読み、hook の実体と照合する。`package_mode` が範囲外なら bundle として全 check を流し、PKG-002 で fail にする。
- **package 検査の集約と表示**: `aggregate-pkg-findings.py` は `--run` と `--phase` を必須にし、ログの無い必須 ID を fail にする。`lint-pkg-009.py` は常に result JSON を出す。`sandbox-plugin-lifecycle.py` は名前空間のディレクトリも消し、終了コードを 0 / 1 / 2 にした。`render-pkg-findings.py`（0.2.0）に終了コード 2 を足した。
- **package 検査の SKILL.md・R1・評価者の契約**: 条件の表を、script が判定するものと評価者が判定するものに分けた。`fail_fast` をやめ、location を絶対パスにした。`pkg-batch/` を足し、`rubric_refs` を `reference_refs` に移した。
- **`audit-capability-parity.py`**: 型の崩れた manifest を ERROR にする。終了コードは 0 / 1 / 2。
- **`sync-plugin-platforms.py`**: write-scope を宣言し、lock を取る。不正な repo-root は終了コード 3。
- **検証の義務と証跡**: `derive-verification-contract.py` は checker のパスを実物から解決する。`plan-verification-obligations.py` に終了コード 2 を足した。`derive-route-build-obligations.py` は repo の外のパスを拒み、id の衝突を終了コード 2 にする。`record-verification-evidence.py` は fingerprint の形を確かめ、evidence-dir の外へ書かず、NaN と inf を拒む。
- **生成器**: `build-subagent.py` は `--skill-name` を検証し、frontmatter の値の引用符を `_unquote_scalar` で外す。助言役（advisor）が書き込みの tool を持つと終了コード 2 で止める。`render-combinators.py` は `--language auto` に `--target-skill` を求め、日本語の Key Rules の anchor を `## 守ること` にした。節の置き換え（`_replace_section`）はコードフェンスの中を見出しとみなさない。`templates/` の見出し `## 注意点` を `## つまずきやすい点`（BD-002 の日本語の正規形）にし、`ja-contract-policy.md` に gotchas の行を足した。
- **`render-findings-score.py`**: header と終了コードを足した。日本語の Key Rules の見出し（`KEY_RULES_HEADING_JA`）を照合し、コードフェンスの中の見出しは数えない。
- **lint**: `lint-goal-seek.py` は終了コード 2 を足し、AST で検査し、root の外を指す symlink を拒む。`lint-knowledge-loop.py` と `sync-task-state.py` に終了コード 2 を足した。`sync-task-state.py` は `plugin_resources.py` が無い配置でも import で落ちない。`lint-capability-manifest.py` に header を足した。`lint-skill-runtime-profiles.py` は終了コード 2 を足し、写しの陳腐化を検査する。
- **`run-build-skill/scripts` の8本**: PEP 723 の header を足した。
- **`plugin_resources.py`**: resolver を、読み込んだ file の path ごとに持つ。共有の名前で `sys.modules` に登録すると、別の plugin root から読んだ resolver どうしが上書きし合い、呼び手の root を取り違えていた。
- **`scripts/extract-plugin-root.py`（0.2.0）**: 他プロジェクト専用の登録しか無い `<plugin>@<marketplace>` は、cache の `<marketplace>/<plugin>/` の下を version を問わず除く。同じ marketplace に有効な登録があれば、除くのはその installPath だけにする。同じ X.Y.Z なら正式版を prerelease より先に選ぶ。
- **写しの追従**: `validate-inline-goal-seek-anchor.py`（`run-skill-feedback` の正本と `templates/goal-seek-runtime/` の写し）と `vendor/prompt-creator/verify-completeness.py` を更新した。
- **rubric の文書**: `ref-skill-design-rubric` の SKILL.md（0.2.0）・R1・`rubric-rationale.md` を直し、`references/CHANGELOG.md` に 1.2.0〜1.5.0 の節を足した。`run-skill-rubric-governance` の SKILL.md と `governance-board.md` に、発効の順序と巻き戻しの節を足した。`lint-matrix.json` の文言を直した。
- **外部変更ガード**: repo 側の guard runtime が、正規のコマンドかどうかを語の形と実パスで判定するように作り直されたので、`artifact-delivery.json` の guard runtime 固定値（`runner_sha256`）を合わせた。

### Changed (2026-10-11〜12 rubric 1.6.0 と、rubric の再評価・lint の ratchet)

- **rubric 1.6.0（PROP-2026-10-11-HK001-POSTTOOLUSEFAILURE、minor、`sunset_days` 0）**: HK-001 が認める hook の event に `PostToolUseFailure` を足した（10値）。hooks.json が配線しているのに high で落ちる誤検出を直した。check だけが書き換わって `RUBRIC_DRIFT` になっていた状態を、rubric の変更の手順に乗せ直した。L2 の pin を 1.6.0 にし、hash を合わせた。提案は `status: pending`（承認待ち）。`capability-manifest.schema.json` の `kindHook` の enum に `SessionStart` を足し、`tests/test_hook_event_vocabulary_parity.py` で hook の event の語彙の一致を固定した。
- **`diff-rubric-impact.py` の読み方と向き**: score ログ（`*-score.jsonl`）だけを再帰で読み、score の無いレコードは数えない（`skipped_no_score`・`skipped_invalid`・`unreadable_logs` で報告する）。数えられるレコードが0件なら終了コード 2。変更の向きは、add を厳格化、remove を緩和とし、modify は `change.direction` で決める（無ければ厳格化とみなし、`direction_source: assumed` を付ける）。`impact_model` は厳格化で `worst_case_tightening`、緩和で `relaxation_no_new_failures`。flip_rate が 0.30 を超えると `exceeds_flip_rate_limit` を立てる（猶予と board の招集の根拠で、bump は決めない）。緩和の bump の下限は下の 2026-10-12 の節、severity が不明なときの重みと、bump を2か所に書いたときの扱いは下の第三者レビューの節（0.5.1）。
- **`lint-rubric-violation.py`（0.2.0）**: score ログだけを読み、rule ごとに数える。終了コードは 0 / 2。
- **`lint-goal-seek.py`**: 配線の warning を ratchet にした（2026-10-10 の実測の37件で固定）。`--baseline` は (path, 規則) の組で、載せられる規則は6種だけ。`fixtures/` は走査しない。`--no-goal-seek` が外すのは render 時の配線だけで、lint の合否は変えない。repo 外の生成物では warning のままだが、repo 内に入った配線の無い loop 系スキルは、plugin を問わずこの ratchet が exit 1 で落とす。harness-creator のスキルは `GRANDFATHERED_WARNINGS` に根拠付きで登録するか配線を戻し、ほかの plugin のスキルは baseline に追記できないので配線を戻す。このことを、SKILL.md・`goal-seek-paradigm.md`・`build-flags.schema.json`・`doc/harness-creator-完全解剖.md` にそろえて書いた。
- **`render-findings-score.py`**: 壊れた rubric の扱いは下の第三者レビューの節。検索の段の script を、名前に search を含むものに加えて、frontmatter の `script_refs` で宣言し重みの表（`*WEIGHTS = {...}`）を持つものも認める。動詞の命名規約に合わせて改名した script が、中身を変えずに FAIL に落ちていた。
- **`lint-matrix.json`**: 各 lint に `owner_plugin` と `script_path` を足した。`tests/test_lint_matrix_script_locations.py` が、`script_path` の実在、basename と `script` の一致、`owner_plugin` と配置の整合を照合する。
- **`lint-skill-runtime-profiles.py`**: `FORK_TOOLS_BASELINE` を両方向の ratchet にした（テストを足した）。
- **`plugin_resources.py`**: `forward_external_intelligence(namespace, *, provider=...)` の provider を呼ぶ側が渡す。`build-external-intelligence*.py` の2本は `provider="skill-governance-adapters"` を渡す。
- **文書**: `pipeline-boundary-contract.md` の PB-C を、実在の10件（01・02・04〜11）の列挙にした。03 は欠番で、採番し直さない。`build-steps.md` の script の type に、状態を書き換える動詞の sync・install・record・manage・migrate を足した（28章 §4.1 の13の動詞に追従）。grace_period は major は14日以上、minor は7日以上、patch は0日にした（would_flip が0の緩和の minor は、理由を記録すれば0日でよい）。`wrap-git-commit-safe` の `resource-map.yaml` を第13条の形にした。
- **script の header**: 設計書28章の実行コンテキスト（§2・§3）に合わせて、`# contexts:` を直した。`install-local-plugins.py`・`manage-build-lease.py` は hook から呼ばれないので、`[C, E]` から `[A, E]` にした。`sync-native-surfaces.py` は SessionStart の hook から1セッションに1回だけ回るので C を残し、`[A, C, E]` にした。
- **自動ドラフトの追跡**: plugin のツリーに commit されていた rubric 提案の自動ドラフト24件（2026-07-11〜2026-10-10）を追跡から外した（書き先は下の 2026-10-12 の節）。
- **外部変更ガード**: `artifact-delivery.json` の `runner_sha256` を、いまの guard runtime に合わせた。

### Fixed (2026-10-12 緩和の required_bump を最低 minor にする, run-skill-rubric-governance のレビュー指摘)

`diff-rubric-impact.py` は、緩和の提案に提案の bump をそのまま `required_bump` として返していた。閾値や severity を下げる緩和を patch で出すと `required_bump` も patch になり、semver 規約の「内容を変えるなら最低 minor」と食い違っていた。bump の値も確かめていなかった。

- **緩和の下限**: `required_bump` は、厳格化なら major、緩和なら提案の bump と minor の大きい方にした（`diff-rubric-impact.py` 0.5.0）。提案の bump が届かないときは stderr に警告を出す。下回ってよいのは文言だけの patch と緊急パッチ（`emergency: true`）だけで、承認者が rubric.json の差分で確かめる。
- **bump の検証**: bump が無いときや major・minor・patch 以外のときは、`required_bump` と比べられないので exit 2 で止める。
- SKILL.md、`references/version-rules.md`・`governance-board.md`、`prompts/R1-govern.md`、`templates/proposal.json` の notes、27章 §6 を同じ規則にそろえた。

### Fixed (2026-10-12 rubric 提案の自動ドラフトを plugin の外へ書く, SessionEnd hook の書き先の根本策)

SessionEnd hook（`aggregate-evals.py`）は、セッションを終えるたびに `skills/run-skill-rubric-governance/proposals/<date>-rubric-update.md` を plugin の tracked ツリーへ書いていた。そのため、作業ツリーが常に dirty になり、install copy にも混ざっていた。

- **書き先**: `HARNESS_CREATOR_PROPOSALS_DIR` があればそこだけに書く。無ければ `$CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/` に書き、書けなければ `$XDG_STATE_HOME` か `~/.claude/state` の `harness-creator/proposals/` へ退避する。`$CLAUDE_PROJECT_DIR` が plugin 自身を指すとき（plugin を cwd にしたセッション）も、plugin の中の候補は外すので、plugin のツリーには書かない。
- **読む側**: `aggregate-evals.py --list-proposals` が、新しい置き場と従来の `$SKILL_DIR/proposals/` の両方を JSON で一覧し、`generated` で自動ドラフトかどうかを示す。SKILL.md の局面カタログ、`prompts/R1-govern.md`、`references/version-rules.md` に置き場を書いた。手書きの提案は従来どおり `$SKILL_DIR/proposals/` に置く。Bash から手で流すと `CLAUDE_PROJECT_DIR` が無く、hook が project の state に書いた自動ドラフトを見落としていた。そこで `CLAUDE_PROJECT_DIR` が無いときは、cwd と git の作業ツリーの root（`.git` のあるディレクトリ）を project とみなし、その state も読む（`aggregate-evals.py` 0.2.0）。推し量った置き場は読む側だけで使い、書き先には足さない。
- **追跡しないもの**: repo の `.gitignore` に `.claude/state/` と `plugins/harness-creator/skills/run-skill-rubric-governance/proposals/*-rubric-update.md` を足した。手書きの提案はこのパターンに一致しない。`build-plugin-release.py` の marker による除外は、手元に残った旧生成物への防御として残し、marker が生成器の文言と一致することをテストで照合する。
- `plugin-composition.yaml` の outputs の `proposals/*.md` を概念名 `rubric-update-proposals` にした（plugin の中のパスではないため）。

### Fixed (2026-10-12 run-skill-update-notifier の通知の表示経路と作者向けの文言, content-review iteration 2)

content-review の iteration 2 で出た3件（medium 2件・low 1件）を直した。指摘の全文は `eval-log/harness-creator/run-skill-update-notifier/content-review/rubric-verdict.json` の `feedback_loop.negative_feedback`。

- **通知が利用者に届くようにした**: PostToolUse の hook の素の stdout は debug log に行くだけで、利用者にも Claude にも見えていなかった。`hook-notify-skill-end.py` は通知を `{"systemMessage": "<plugin>: <1行>"}` の JSON 1個として stdout に出す。Claude への文脈（`additionalContext`）は付けない。通知が無いときは何も出さない。文書の「表示先は hook の扱いに従う」は、実際の表示経路（`references/output-format.md`「表示経路」が正本）に書き換えた。hook のテストは stdout を JSON として読み、`systemMessage` を照合する。
- **文言を作者向けにした**: 比べているのは同じツリーの plugin.json の version と CHANGELOG 先頭の版なので、食い違いは作者の書き忘れになる。通知は向きごとに「plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性」「CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性」と出し、ラベルも `plugin.json:` / `CHANGELOG:` にした。semver として読めない値は「版を比べられない」とだけ出し、値は書かれたまま表示する。利用者に更新を促す `/skill-update` の案内は消した。status は `update-available` を `manifest-behind`、`up-to-date` を `in-sync` に改め、`changelog-behind`・`not-comparable` を足した。ネットワークに出ないので到達しない `offline` は外した。Stage 2 の記載は SKILL.md の範囲の1か所だけにし、Purpose に通知の相手（作者）を1文足した。`output-format.md` の例の表は、テストが読んで実装の出力と照合する。
- **書き込み検査の抜け道を塞いだ（IN3）**: AST 検査が、書き込みの flag を付けた `os.open`、`os`・`shutil` からの from-import と別名 import、keyword で渡した書き込み先、`subprocess`・`os.system`・`os.exec*` などの別プロセスの起動、`from os import *`・`getattr(os, ...)`・`__import__`・importlib を拾う。hook の2本は、`subprocess.run` の argv が `python3` と `str(NOTIFIER)` で始まり、NOTIFIER が同じディレクトリの `notifier-check.py` を指すことを確かめる。書き込みと起動の呼び出しの件数は、scripts の3本すべてで固定した。

### Fixed (2026-10-11〜12 run-skill-update-notifier の snapshot の key と、session ごとの重複抑止)

`notifier-check.py` の refresh と notify を直した。この PR の前の回で直したが、CHANGELOG に書き漏れていた。

- **snapshot の key**: snapshot の key を、ディレクトリ名から plugin.json の `name` にした（読めなければディレクトリ名）。hook は skill 名の `<name>:` から plugin を引く。key がディレクトリ名だと、install 先（`~/.claude/plugins/cache/<marketplace>/<name>/<version>/`）の親を走査したときに key が版名になり、notify が常に何も出していなかった。
- **同じ name が複数あるとき**: install 先には版ディレクトリが並ぶので、同じ name のディレクトリが複数出る。`_candidate_rank` が次の順で比べて1つに決める。
  1. `--plugin-root` で直接渡したもの（hook が渡す、いま動いている plugin）
  2. plugin.json の version が semver として読めるもの
  3. その version が semver で大きいもの（文字列の順だと 1.4.9 が 1.4.43 より後になる）
  4. パスが辞書順で後ろのもの
- **session ごとの重複抑止**: 以前の文書は1セッション内で通知が重複しないと書いていたが、script には重複抑止が無かった。hook が payload の `session_id` を `--session-id=<id>` で渡し、notify は同じ session で同じ plugin を2度通知しない。記録は cache の `notified.<plugin>` に `session_id` と `last_notified_at` を残す。記録するのは表示の後である。`session_id` の無い payload では抑止しない。
- **refresh で記録を消さない**: refresh は cache を書き直すときに `notified` を引き継ぐ。消すと、session の途中で 24h の TTL を跨いだときに同じ通知がもう一度出る。

### Fixed (2026-10-12 run-skill-update-notifier の SKILL.md を、実際の分岐と配線に合わせる)

SKILL.md の記述のうち、`notifier-check.py` の実際の分岐や hook の配線と食い違っていたところを直した。

- **Runtime root contract**: frontmatter に `runtime_root_policy: host-skill-path` を足し、本文に `## Runtime root contract` 節（`<!-- runtime-root-contract:v1 -->`）を足した。Claude Code では `CLAUDE_PLUGIN_ROOT` を plugin root として使う。Codex では、SKILL.md の absolute path から plugin manifest を持つ祖先を探して `PLUGIN_ROOT` を決める。cwd からは推測しない。`prompts/` もこの契約を継承する。局面カタログのコマンドは `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` から始まる絶対パスで書いた。Checklist の refresh には、cwd 基準の `plugins/` ではなく、plugins/ と自 plugin の root を絶対パスで渡すと書いた。
- **cache を読めないときと、読めるが書けないときを分けた**: 以前の Key Rules 2 と criteria の IN1 は、オフラインや権限不足を含むどの分岐でも no-op になると書いていた。実際の `notifier-check.py notify` の動きは次のとおり。
  - cache を読めなければ何もしない。
  - 読めるが書けなければ、通知を表示し、通知済みの記録だけを飛ばす。記録するのは表示の後なので、書けなくても通知は失わない。

  Key Rules 2・IN1・Checklist の最終項をこの分岐に合わせた。ネットワークに出ないので起きない「オフライン」は、Key Rules 2 と IN1 から外した。Key Rules 3 の stdlib の一覧は、scripts が実際に import するもの（argparse・datetime・json・os・pathlib・re・subprocess・sys）に合わせ、使っていない `urllib.request` を外した。
- **Gotchas**: 実際の動きから出る制限を足した。
  - cache に書けないと、通知済みの記録（`notified.<plugin>`）が残らない。そのため重複抑止が働かず、同じ session でも Skill を使うたびに同じ通知がもう一度出る。
  - 重複抑止の記録は、plugin ごとに最新の session の1件だけである。2つの session が同じ plugin を交互に使うと、通知がもう一度出る。
  - install 先では、snapshot に入るのは自 plugin（harness-creator）だけで、他の plugin の Skill には通知が出ない。
  - **Codex では通知が自動で出ない**。Codex に配線されるのは UserPromptSubmit の cache-refresh だけで、PostToolUse（matcher=`Skill`）の notify-skill-end は Claude Code 専用である（`.codex/hooks/registry.json` の products が `claude` だけ）。Codex で通知を見るには、`notifier-check.py notify` を明示して起動する。

### Fixed (2026-10-12 第三者レビューの指摘を直す)

- **`aggregate-evals.py`（0.2.1）**: 引数があるときは `--list-proposals` だけを受ける。`--help` は usage を出して exit 0、知らない引数や綴りの誤りは exit 2 で、何も書かない。以前は知らない引数でも hook の経路に進み、提案を書いていた。hook は引数を渡さないので、hook の挙動は変わらない。
- **`diff-rubric-impact.py`（0.5.1）**:
  - 最上位と `change.bump` の両方に bump があり、どちらかが不正か値が違うときは exit 2 で止める。以前は `change.bump` だけを使っていた。
  - 厳格化で `change.severity` が無いか、high・medium・low 以外のときは、一番重い重み（high の -20）で見積もり、stderr に warning を出す。以前は黙って medium で見積もっていた。
  - 厳格化の見積もりに使った severity の重みを、出力の `severity_weight` に出す。その出どころを `severity_source` に出す。`severity_source` は、`change.severity` どおりなら `declared`、分からず一番重い重みにしたなら `assumed` で、`direction_source` と同じ流儀にした。緩和は重みを使わないので、どちらも null。以前は、推し量った重みが stderr にしか残らなかった。`prompts/R1-govern.md` は、`severity_source: assumed` のときも `uncertain` を付け、`change.severity` を書いて流し直す。
- **`lint-skill-runtime-profiles.py`**: workflow manifest の top-level が object でないとき（配列など）も、traceback で落ちない。`manifest の top-level が object でない (<型>)` という finding を出して、exit 1 で止める。
- **`build-subagent.py`**: allowed-tools の項目に付いた引用符（`- "Write"`・`["Write"]`・`Read "Write"`）を外してから、書き込みの道具かどうかを判定する。以前は引用符が付いたままの名前で比べていたので、advisor に書き込みの道具が付いていても検出をすり抜けていた。
- **`notifier-check.py` の cache の保存**:
  - 固定名の `version-snapshot.tmp` をやめ、呼び出しごとの名前で排他的に作った一時ファイルを、replace で置き換える。固定名だと、同時に動いた2つが同じ一時ファイルを書き合い、片方の replace が一時ファイルを持ち去ったあとで、もう片方の replace が失敗して保存が飛んでいた。失敗したら自分の一時ファイルだけを消し、通知は出したまま exit 0 で終わる。
  - 防ぐのは、この保存の失敗だけである。cache を読んでから保存するまでに lock が無いので、並行に呼んだときの lost update は残る。後から保存したプロセスが先の記録を上書きするので、重複抑止の記録が消え、同じ通知がもう一度出る。lock は入れていない。
  - docstring にこの限界を書いた。引数の誤り（mode が無い・知らない mode・notify の `--plugin` が無い）は argparse が usage を出して exit 2 にする（`--help` は exit 0）ことも書いた。
- **`render-findings-score.py`**: 壊れた rubric（JSON でない、必須キーが無い、型が違う）を、合成の前の各ファイルと合成の後の rubric の両方で検証する。理由を stderr に出して exit 2 で止まる。以前は、合成の途中で Traceback を出して落ちることがあった。
- **`manage-build-lease.py`**:
  - owner-token 形式の lock は、pid の生死を見ず、TTL を過ぎたときだけ回収する。lock の pid は、呼ぶたびにすぐ終わる CLI のものなので、生きた build でも死んでいる。以前は、同じ host の2回目の acquire が、生きた build の lock を奪っていた。legacy lock（owner_token の無い形式）は今までどおり、TTL を過ぎたときか、同じ host で pid が死んでいるときに回収し、owner-token 形式へ移す。owner-token 形式の lock に止められたときの remediation（release か TTL の失効を待つ）を足した。
  - `--lease-seconds`・`--lock-ttl-seconds` が 0 以下のときは exit 2 で止める。0 以下だと、経過0秒の生きた lock まで孤児とみなして奪えてしまう。
  - 配列や非 UTF-8 の discovered-task form は、traceback で落ちずに、認可に数えない。stderr に warning を出し、graph_hash の mismatch の出力では `invalid_forms` に名前を出す。
  - renew の docstring を、owner_token の一致だけで判定する実装に合わせた。
  - `references/pipeline-boundary-contract.md` の表の2か所（`.build.lock` の行と、build 開始ゲートの行）を、「pid 生存判定は legacy lock だけ」に直した。
- **`sync-native-surfaces.py`**:
  - codex_project_settings の child の `--json` report が object でない（stdout が空・JSON でない・配列など）ときは、理由付きの invalid（exit 3）を返す。以前は AttributeError の traceback で exit 1 になり、drift（exit 1）と区別できなかった。
  - 読めない check のあとに apply へ進まない。以前は、check の child が exit 1 で終わると、report が読めなくても drift とみなして apply に進み、synced を返していた。apply の child の report が object でないときも invalid にする。
  - `--lock-ttl` が正の有限値でないときは exit 2 にする。
- **`ref-cross-platform-runtime`**:
  - Runtime 判定の雛形を、`python_cmd` に名前（`python3` | `python` | `unknown`。path ではない）を返す形にした。探す順は、Windows が python → python3、ほかが python3 → python で、`references/os-matrix.md` と設計書22章に合わせた。雛形の見出しを「script に貼る雛形」にした。
  - `.sh` を配布しない範囲を、生成・検証・adapter・hook の処理（設計書28章 §3.2 の L2）に限った。install などの lifecycle の `.sh`（L1）は対象の外と、Key Rules・Gotchas・`os-matrix.md`・`forbidden-clis.md` に書いた。
  - OS の判定は、Skill 本文では `uname -s` の注入（設計書22章）、script の中では `platform` と `shutil.which` で行う、と Key Rules に書いた。
  - `forbidden-clis.md` が正本としていた、存在しない `plugin.json` の `requirements.external_clis` を、設計書22章の「許可 CLI ホワイトリスト」に直した。`lint-forbidden-deps.py` は、いまは読む先の `plugins/skill-governance-lint/manifest.json` が無いので、検査せずに SKIP で exit 0 を返すと書いた。
- **run-build-skill の Step 12 の番号と合流先**:
  - SKILL.md の本文に「### Step 12.7: ユーザー選択範囲だけの有界改善」を足し、`workflow-manifest.json` の `bounded-improvement` と対応させた。Step 12.6 の見出しから改善を外し、「選択時のsemantic診断」にした。
  - Step 12.45 の段を差し込んだときに残った、Step 番号のずれを直した。共通の合流先を「`usable-draft-proof` (Step 12.4) → `artifact-present-handoff` (Step 12.45) → `diagnostic-choice` (Step 12.5)」とし、`workflow-manifest.json` の Step 0 の note も同じ合流先にした。usable-draft proof を再検証する主体は、実装どおり `build-improvement-gate.py` とした。毎回の判定で、提示の receipt と診断の選択を検査するより前に、artifact の sha、validator の sha、validator の再実行を確かめる。proof を作れない kind は Step 12.45 へ進まない。
  - plugin の `references/capability-build-runtime-contract.md` で、承認 receipt の正本を Step 12.6 にし、usable-draft handoff の再検証の主体を `build-improvement-gate.py` にした。`doc/harness-creator-完全解剖.md` の Step の表は、12.6 を semantic 診断（`build-improvement-gate.py` → `build-review-launch.py` → `elegant-initial-draft-evaluator`）、12.7 を有界改善（phase は `bounded-improvement`）と書き分けた。
  - `lint-goal-seek.py` が `### ゴールシーク配線` の不在を warning で検査する、という記述に「repo 内では、未登録のものを ratchet が exit 1 にする」を補った。
- `--no-goal-seek` の文書と、`# contexts:` の直しは、上の 2026-10-11〜12 の節に書いた。

## [1.4.46] - 2026-10-10

1.4.44 からの変更をまとめる（1.4.45 は節を持たない）。git に版上げの記録が無いので、1.4.47 との境界は commit の日付で近似した（2026-10-10 の commit の分を本版に入れる）。

### Changed

- **`scripts/extract-plugin-root.py`**: 他プロジェクト専用（`scope` が `project` / `local`）の install 先を、sibling と cache fallback の候補からも除く。同じ path に有効な登録があれば、共有 install として許可する。
- **`scripts/plugin_resources.py` を新設**: 兄弟 plugin の root を `resolve_root` で解決し、同梱の resolver が無いときは `ResolverUnavailable` を投げる。`sync-task-state.py`・`build-external-intelligence*.py`・`lint-knowledge-loop.py`・`lint-pkg-009.py`・`run-pkg-015.py`・`sandbox-plugin-lifecycle.py` が個別に持っていた importlib の読み込みを、これに置き換えた。shebang と実行ビットを付けた（PKG-007）。
- **`run-skill-create` の workflow-manifest**: 兄弟の root を `SIBLING_PLUGIN_ROOT=… && python3 …` の形で渡し、lint の段の `fatal_exit_codes` を `[1, 2]` にした。
- **`run-plugin-package-check` の SKILL.md**: `script_refs` を足した。
- **`run-build-skill` の SKILL.md**: frontmatter から `../../scripts/plugin_resources.py` を外した。
- **`wrap-git-commit-safe`**: `references/resource-map.yaml` を新設した。
- **`lint-skill-runtime-profiles.py`**: anchor の写しとして skill に同梱した写しも認め、正本との byte 一致を求める。テストを足した。
- **rubric 提案の自動ドラフト**: SessionEnd hook が plugin のツリーに書いた 2026-10-06〜2026-10-10 の自動ドラフトが commit に入った（1.4.47 で追跡から外した）。

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
