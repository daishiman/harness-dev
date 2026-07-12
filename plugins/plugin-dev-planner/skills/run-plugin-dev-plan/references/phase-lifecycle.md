---
name: phase-lifecycle
description: 機能開発13フェーズ→プラグイン開発の読み替え表と、成果物へ写像する13フェーズ (P01..P13) 定義を読む。R2/R3 のフェーズ設計の正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# プラグイン開発ライフサイクル (§7 読替表 / §8 13 フェーズ)

> パスはすべて repo root 相対。borrow 元 (UBM-Hyogo `task-specification-creator`) は read-only 抽出のみで fork/複製しない。

## §7 ドメイン読み替え表 (機能開発13フェーズ → プラグイン開発)

keep=精神維持 / transform=対象ドメインへ写像 / drop=廃止 / replace=別機構へ置換。**TDD/カバレッジ は drop ではなく transform** (vitest/Cloudflare/IPC という実装基盤の固有性のみ捨て、TDD/品質保証の精神は写像する)。

| 旧 Phase | 判定 | 置換先 |
|---|---|---|
| P1 要件定義 | transform | 目的ドリブン要件定義 (`run-goal-elicit`→goal-spec)。taskType/visual 分類 DROP、kind/prefix/placement 分類へ |
| P2 設計 (validation matrix/type 互換) | transform | コンポーネント設計 (5 種写像 + kind/hierarchy/pattern)。type 互換 → schema 契約 |
| P3 設計レビューゲート | keep | P03 design-review = `run-elegant-review` C1-C4 (design) ゲートへ写像・proposer≠approver |
| P4 テスト設計 (TDD Red) | transform | criteria を test-first 導出 (feedback_contract inner=lint exit0 / outer=verdict PASS)。Red=未達 criteria |
| P5 実装 (TDD Green) | transform | Green=criteria を goal-seek ループで充足。実 build は L4 へ委譲、本スキルは「Green の達成条件」を要件化 |
| P6 テスト実行 (vitest 80%) | transform | vitest/pnpm を DROP、pytest harness-coverage ≥80% (6 種別×二軸・kind 別パス) へ |
| P7 AC matrix 判定 | keep | 二値 AC を各 component の受入 checklist へ (§8 権威表・doc §4 と一致) |
| P8 リファクタリング (TDD Refactor) | transform | 重複排除 → `lint-ssot-duplication.py` (上書き一本化) へ写像 |
| P9 品質保証 | replace | P0 lint 8 本 + `validate-build-trace.py` + schema parity + content-review |
| P10 最終レビューゲート | keep | P10 final-review = elegant-review C1-C4 (final) + governance + unassigned 0 (P03 とは別の最終ゲート) |
| P11 evidence (スクショ) | replace | スクショ DROP。Markdown evidence = lint exit0 ログ / schema parity / build-trace coverage / content-review verdict / `eval-log/coverage/*.json` |
| P12 ドキュメント 6 タスク (aiworkflow 同期) | keep+replace | 6 タスク雛形流用。aiworkflow 連携 DROP、反映先を `feedback_contract_ssot.py`/`lessons-learned`/`bundles.json` へ |
| P13 PR 作成 (PR/IPC/Cloudflare) | transform | IPC・Cloudflare 全 DROP。PR は harness `feature→main + make validate + pytest` 完了条件として最終仕様書が言及 (本スキル責務外) |

### DROP (UBM 機能開発固有のみ)
Electron IPC・safeInvoke / Cloudflare・D1・Workers / Phase 11 スクリーンショット / aiworkflow-requirements SSOT 連携 / GitHub PR・deploy。**REPLACE**: スクショ → Markdown evidence (lint exit0 / schema parity / build-trace coverage / content-review verdict / coverage JSON)。この **5 要素集合** は P11 セル(上表)・`io-contract.md` §10 と一致させる (evidence 定義の単一 SSOT)。coverage JSON の表記は glob `eval-log/coverage/*.json` と具体パス `eval-log/coverage/skills/<plugin>__<skill>.json` の表層差を許容する (指す実体は同一)。

## §8 13 フェーズ写像 (従来 Phase 1-13 → プラグイン開発・成果物軸の SSOT)

機能開発の従来 Phase 1-13 をプラグイン開発ドメインへ 1:1 写像した 13 フェーズ。**各フェーズ = 1 Markdown ファイル `phase-NN-<kebab>.md`** で、上から順に読める宣言型タスク仕様 (8 節・本文床の正本=`specfm.PHASE_BODY_SECTIONS`・人間向け primary deliverable)。id/kebab/category/gate_type は `scripts/specfm.py` の `PHASE_*` dict が正本 (`schemas/phase-spec.schema.json` と parity)。UBM 機能開発固有 (Electron IPC / Cloudflare・D1・Workers / スクショ / aiworkflow SSOT 連携 / GitHub PR・deploy) は §7 のとおり DROP/REPLACE 済み。

| # | id | phase_name (kebab) | 日本語 | category | gate_type | 目的 | 成果物 | 完了条件 |
|---|---|---|---|---|---|---|---|---|
| 1 | P01 | requirements | 要件定義 | 要件 | none | 目的ドリブン要件定義 (`run-goal-elicit`→goal-spec)・`target_plugin_slug` 確定・MCP 中核なら制約開示 | `goal-spec.json` | purpose/background/goal/checklist 充足・target_plugin_slug 固定・checklist 各 verify_by 付き |
| 2 | P02 | design | 設計 | 設計 | none | 5 種写像で N 実体を `component-inventory.json` へ分解・依存 DAG・**envelope(plugin.json) 設計 owner**・plugin-level surface 採否 (`notion_config` 含む) + `feedback_deploy` 確定 | N 実体の分解・依存 DAG・envelope 設計・surface 採否が確定した状態 (plan 時 artifact=`component-inventory.json` + `envelope-draft/plugin.json`) | 各実体の kind/`build_target` 確定・DAG 非循環・considered 5 種 |
| 3 | P03 | design-review | 設計レビューゲート | レビュー | design-gate | elegant-review C1-C4 (design)・proposer≠approver | design レビュー verdict | C1-C4 全 PASS |
| 4 | P04 | test-design | テスト設計 | テスト | tdd-red | criteria を test-first 導出 (feedback_contract inner/outer)・未達=Red | 各 skill loop component の `feedback_contract.criteria` | criteria が SSOT 形式・inner/outer 各≥1・purpose 由来 (未達=Red) |
| 5 | P05 | implementation | 実装 | 実装 | tdd-green | per-entity build を委譲 (`run-skill-create`/`run-build-skill`)・**build routing runnable checklist (inventory top-sort 順)**・phase 順≠build 順 | 全 buildable component の build 委譲経路が確定した状態=宣言型の到達状態 (plan 時 artifact=`handoff-run-plugin-dev-plan.json` の routes) | 全 buildable component が route 化・builder/build_kind 整合・top-sort 可能 |
| 6 | P06 | test-run | テスト実行 | テスト | none | harness coverage 拡充 (≥80% kind 別・6 種別×二軸)・現状値焼かない | 各 component の `harness_coverage` ブロック | min≥80 設計・kind_pass が kind 整合 |
| 7 | P07 | acceptance-criteria | 受入基準判定 | 判定 | none | 二値 AC を各 component の受入へ・受入確認 (build 後の見方) | index「受入確認」章 + component checklist | purpose 由来の受入観点が二値で列挙 |
| 8 | P08 | refactoring | リファクタリング | 改善 | tdd-refactor | SSOT 重複排除 (`lint-ssot-duplication`・上書き一本化)。該当なければ `{applicable:false, reason}` 可 | `plugin_meta.ssot_dedup` 記録 | 重複 0 or N/A 明示 |
| 9 | P09 | quality-assurance | 品質保証 | 品質 | qa | P0 lint + build-trace + schema parity + content-review | 各 component の `quality_gates` ブロック | p0_lint 網羅・build_trace required・content_review PASS・schema parity |
| 10 | P10 | final-review | 最終レビューゲート | レビュー | final-gate | elegant-review C1-C4 (final) + governance + unassigned 0 | final レビュー verdict | C1-C4 全 PASS・unassigned 0・governance PASS |
| 11 | P11 | evidence | 手動テスト検証 | 検証 | evidence | スクショ DROP→Markdown evidence 5 要素 | evidence 5 要素 | lint exit0 / schema parity / build-trace coverage / content-review verdict / coverage JSON が観測可能 |
| 12 | P12 | documentation | ドキュメント | 文書 | none | 6 タスク雛形 (中学生説明 Part1 概念+Part2 技術)・反映先=`feedback_contract_ssot`/`lessons-learned`/`bundles.json`・**distribution/install 手順** | doc + install 手順 (+ feedback 受け皿の `.notion-config.json` セットアップの宣言的注記=plan は DB キーのみ宣言し DB ID は設置先供給) | 6 タスク充足・反映先明示 |
| 13 | P13 | release | 完了(PR/リリース) | 完了 | none | IPC/Cloudflare 全 DROP・PR は責務外 soft note のみ (評価ゲート化しない) | feature→main soft note | (評価ゲートなし)・PR 言及は note 留め |

- gate_type enum: `none | design-gate | final-gate | tdd-red | tdd-green | tdd-refactor | qa | evidence` (`specfm.GATE_TYPES`)。
- category は日本語ラベル (enum 緩め・上表の値・`specfm.PHASE_CATEGORY`)。
- `applicability` 既定は `{applicable: true}`。該当しないフェーズ (典型は P08) は `{applicable: false, reason: <非空>}` で明示 N/A にでき、section 床を免除される。

**横断パラダイム (goal-seek)**: P01-P13 全体を `goal-seek-paradigm.md` の 6 ステップで回し、各周回末に中間成果物アンカー (jsonl) を追記する。固定手順でなくゴール駆動。

**成果物モデル (13 phase files + index + inventory sidecar)**: 出力は 2 軸直交 (詳細は `component-domain.md`):
- **ファイル軸 (人間)** = 13 phase files (`phase-01-requirements.md` … `phase-13-release.md`)。上から順に読める宣言型タスク仕様 (8 節)=primary deliverable。
- **build 軸 (機械)** = `component-inventory.json` (機械 SSOT・sidecar)。buildable 実体 (skill/sub-agent/slash-command/hook/script) の build routing・依存 DAG・品質機構 (旧 C*.md frontmatter の載せ替え先) を保持する。
- **index.md(main)** = P01..P13 を **phase_number 昇順**で列挙した目次 + 全体完了条件 + 受入確認 + plugin 階層規律 (`plugin_meta`)。

旧「独立した横断仕様書を作らない/13→8 畳み込み」は廃止し、フェーズは 13 固定で 1 段階=1 ファイルとする (本数は 13 固定=フェーズ数で、buildable 実体数 N とは独立)。phase ファイルは build_target/depends_on を再記述せず、component は `entities_covered` の id 参照だけで phase に紐づく (正規化)。

**出力先 (再現性)**: plan は repo-root 相対の **可視・永続の tracked ディレクトリ `plugin-plans/<plugin-slug>/`** に plugin ごとに隔離して作成する (捨て置き scratch でなくレビュー可能な deliverable)。`<plugin-slug>` は R1 が `goal-spec.json` の `target_plugin_slug` に固定し、P01-P13 と全 goal-seek 周回で不変にする。`--out-dir` 明示時のみ上書きでき、その場合も `goal-spec` に固定する。goal-seek の transient 作業ログ (progress/intermediate) のみ gitignore 対象。実プラグインディレクトリ (`plugins/<plugin-slug>/`) は本スキルでは作らず、L4 build 先は inventory の `build_target` で追跡する。

**buildable 実体数 N**: `component-inventory.json` に列挙された buildable 実体 (同一 kind 複数実体を含む) の数であり、kind 数 (5) でもフェーズ数 (13) でもない。対象プラグインの実体数の射影 (input でなく output)。ユーザーが具体的な本数を求めた場合も 13 固定はフェーズ数として保ち、要求本数は goal-spec に任意記録するに留め gate 強制しない (旧 Phase 1-13 の読み物ビューが要る構想では phase ファイルがそのビューを兼ねる)。
