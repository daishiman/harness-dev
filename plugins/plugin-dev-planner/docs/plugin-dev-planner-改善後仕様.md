# plugin-dev-planner 改善後 仕様サマリ (per-phase 転換)

> 作成日: 2026-07-01 / 対象: `plugins/plugin-dev-planner/`
> 本書は「per-component 分解 (C01-C11)」から「**per-phase 分解 (index.md + phase-01〜phase-13.md)**」への全面転換後の**確定仕様**をまとめたもの。
> **タスク仕様書 = 各フェーズごとに 1 ファイル生成** (`phase-01-requirements.md` … `phase-13-release.md` の 13 本)。buildable な実体 (skill/sub-agent/…) は `component-inventory.json` の 1 目録に集約する。
> 検証状態: plan 決定論ゲート exit0 / 両 skill (run-plugin-dev-plan・assign-plugin-plan-evaluator) の pytest 緑。
> 未完了の人手・LLM評価系は §11「コミット前の残手順」に分離する。

---

## 1. このプラグインは何をするか

**プラグイン構想 1 件を、2 軸直交 (ライフサイクル軸=13 フェーズ / 成果物実体軸=N 個の buildable component) に分解する「前段の計画」プラグイン。**

- 実プラグイン/実コードは**作らない**(build は harness-creator の `run-skill-create` / `run-build-skill` へ委譲)。
- 出力は「計画」のみ = **index(main) + 13 フェーズファイル + `component-inventory.json`**。各 component は harness-creator の評価基準を目録エントリで携帯し、後段 build へそのまま投入できる粒度。
- 起動: `/plugin-dev-plan <構想> [--mode create|update] [--out-dir <path>]`

---

## 2. 出力先

| 項目 | 仕様 |
|---|---|
| **既定出力先** | **`plugin-plans/<plugin-slug>/`**(repo-root 相対・**可視・永続の tracked deliverable**) |
| 上書き | `--out-dir <path>` で明示指定可 |
| SSOT | `scripts/specfm.py` の `PLAN_OUTPUT_BASE = "plugin-plans"` / `plan_output_dir()` |
| slug 導出 | 決定論(小文字化→英数とハイフン以外を `-`→連続圧縮→trim)。同一構想は常に同一出力先(再現性) |
| tracked(git 追跡) | `index.md` / `phase-01..13.md` / `component-inventory.json` / `handoff-*.json` / `goal-spec.json` / `plan-findings.json`(評価 skill 実行時に生成) / `envelope-draft/plugin.json` |
| gitignore(除外) | goal-seek の transient のみ = `run-plugin-dev-plan-progress.json` / `run-plugin-dev-plan-intermediate.jsonl` / `.goal-seek/` |

### 出力ディレクトリの中身(例: 構想 `notion-task-sync`)
```
plugin-plans/notion-task-sync/
├── index.md                         # main 目次(P01..P13 phase_number 昇順 + 受入確認 + plugin_meta)
├── phase-01-requirements.md         # ← 各フェーズ 1 ファイル(ライフサイクル軸・上から順に読める)
├── phase-02-design.md
├── …(phase-03 〜 phase-12)…
├── phase-13-release.md
├── component-inventory.json         # buildable 実体の唯一の SSOT(build routing + 依存 DAG + 品質機構)
├── handoff-run-plugin-dev-plan.json # L3 計画→L4 build のルーティング(routes は inventory 由来)
├── goal-spec.json                   # 目的ドリブン要件(purpose/goal/checklist)
├── plan-findings.json               # 4条件評価結果(評価 skill 実行時に生成・architect のゴールデン例 examples/sample-plan には非同梱)
└── envelope-draft/plugin.json       # 貼れる manifest ドラフト(手動適用用・Phase02 が owner)
```

---

## 3. 中心原則 = 2 軸直交 + 単一 SSOT + 複数 projection

plan は**直交する 2 軸**を、二重に持たず (正規化) 保持する:

| 軸 | 意味 | 本数 | SSOT |
|---|---|---|---|
| **ライフサイクル軸(人間)** | 13 フェーズ。各フェーズ = 1 Markdown `phase-NN-<kebab>.md`。上から順に読める宣言型タスク仕様(8 節)=**primary deliverable** | **13 固定**(フェーズ数) | `index.md` + phase ファイル |
| **成果物実体軸(機械)** | N 個の buildable component (skill/sub-agent/slash-command/hook/script)。build routing・1 実体=1 `build_target`・依存 DAG・品質機構を保持 | **N**(実体数の射影・input でなく output) | `component-inventory.json` |

- **正規化**: build_target / depends_on は inventory のみが持ち、phase ファイルは再記述しない。component は `entities_covered: [C01, ...]` の **id 参照だけ**でフェーズに紐づく。
- **「5」と「13」と「N」は別軸**: 5=component_kind の分類軸 / 13=フェーズ数(固定) / N=buildable 実体数(可変)。互いに独立。
- **旧 C*.md frontmatter (機械契約) は `component-inventory.json` の `components[]` エントリへ載せ替え**、C*.md 本文の物語は phase ファイルへ再編成した(**情報ロスなし**)。
- **廃止**: 本数論争機構(旧「実体の数だけ本を作る」導出・件数固定フラグ)。13 はフェーズ数として固定するため自然消滅。ユーザーの本数要求は `goal-spec.requested_count` に任意記録できるが gate 強制しない。

**改善点**: 旧仕様は buildable 実体 1 個につき 1 ファイル (`C01-…md`) で、本数が構想ごとに変動し「何本作るか」の論争が構造化されていた。→ 人間が読むファイル軸を **13 フェーズ固定**にし、機械が使う実体軸を **1 目録 (inventory)** に集約する 2 軸直交へ reframe した。

---

## 4. 13 フェーズ定義(ライフサイクル軸・機能開発 Phase 1-13 の写像)

従来の機能開発 Phase 1-13 をプラグイン開発ドメインへ 1:1 写像(UBM 固有物は DROP/REPLACE)。id/kebab/category/gate_type の実行可能正本 = `scripts/specfm.py` の `PHASE_*` dict + `schemas/phase-spec.schema.json`。

| # | id | phase_name | 日本語 | category | gate_type | 主な役割 |
|---|---|---|---|---|---|---|
| 1 | P01 | requirements | 要件定義 | 要件 | none | 目的ドリブン要件定義(run-goal-elicit→goal-spec)・target_plugin_slug 確定 |
| 2 | P02 | design | 設計 | 設計 | none | 5 種写像で N 実体を inventory へ分解・依存 DAG・**envelope(plugin.json)設計 owner** |
| 3 | P03 | design-review | 設計レビューゲート | レビュー | design-gate | elegant-review C1-C4(design)・proposer≠approver |
| 4 | P04 | test-design | テスト設計 | テスト | tdd-red | criteria を test-first 導出(feedback_contract inner/outer)・未達=Red |
| 5 | P05 | implementation | 実装 | 実装 | tdd-green | per-entity build を委譲・build routing runnable checklist(inventory top-sort 順) |
| 6 | P06 | test-run | テスト実行 | テスト | none | harness coverage 拡充(≥80% kind 別)・現状値焼かない |
| 7 | P07 | acceptance-criteria | 受入基準判定 | 判定 | none | 二値 AC を各 component の受入へ・受入確認(build 後の見方) |
| 8 | P08 | refactoring | リファクタリング | 改善 | tdd-refactor | SSOT 重複排除。該当なければ `{applicable:false, reason}` 可 |
| 9 | P09 | quality-assurance | 品質保証 | 品質 | qa | P0 lint + build-trace + schema parity + content-review |
| 10 | P10 | final-review | 最終レビューゲート | レビュー | final-gate | elegant-review C1-C4(final)+ governance + unassigned 0 |
| 11 | P11 | evidence | 手動テスト検証 | 検証 | evidence | スクショ DROP→Markdown evidence 5 要素 |
| 12 | P12 | documentation | ドキュメント | 文書 | none | 6 タスク雛形・反映先=feedback_contract_ssot/lessons-learned/bundles.json・distribution/install 手順 |
| 13 | P13 | release | 完了(PR/リリース) | 完了 | none | PR は責務外 soft note のみ(評価ゲート化しない) |

- gate_type enum: `none | design-gate | final-gate | tdd-red | tdd-green | tdd-refactor | qa | evidence`。
- `applicability.applicable == false` のフェーズ(典型は P08)は `{applicable: false, reason: <非空>}` で明示 N/A にでき、本文 section 床を免除される。
- **DROP/REPLACE**(UBM 機能開発固有): Electron IPC / Cloudflare・D1・Workers / スクショ(→Markdown evidence)/ aiworkflow SSOT 連携 / GitHub PR・deploy。正本 = `references/phase-lifecycle.md` §7 読替表。

### phase ファイル frontmatter(§2・`specfm.PHASE_REQUIRED`)
```yaml
---
id: P03                        # ^P(0[1-9]|1[0-3])$
phase_number: 3                # int 1-13(id と一致・全 13 ユニーク)
phase_name: design-review      # specfm.PHASE_NAMES の kebab
category: レビュー             # 日本語ラベル
prev_phase: 2                  # int(P01 は 0)
next_phase: 4                  # int(P13 は 14)
status: 未実施                 # 未実施 | 進行中 | 完了
gate_type: design-gate         # 8 enum
entities_covered: [C01, C02]   # inventory component id 参照(該当なければ [])
applicability:
  applicable: true
  reason: ""                   # applicable:false のとき非空必須
---
```
build_target / quality_gates / harness_coverage / feedback_contract は phase frontmatter に**置かない**(inventory の component エントリが持つ=正規化)。

### phase ファイル本文 section(§5・宣言型 8 節)
節集合の正本は `specfm.PHASE_BODY_SECTIONS`(宣言型 8 節)、人間可読表は `references/io-contract.md` §5(本書は節名を再列挙しない=引用形一本化)。`detect-unassigned.py` が同定数を import し、各見出し直後の非空本文を床として機械強制する(床のみ機械強制・意味は下流トラスト。該当 `entities_covered` があれば component id を併記)。

---

## 5. component-inventory.json(成果物実体軸・機械 SSOT・品質機構の住処)

```jsonc
{
  "considered_component_kinds": ["skill","sub-agent","slash-command","hook","script"],  // 5 種全列挙(検討証跡)
  "components": [
    {
      "id": "C01",                         // ^C[0-9]{2,}$
      "component_kind": "skill",           // 5 種 enum
      "name": "run-notion-task-sync",
      "skill_kind": "run",                 // component_kind==skill のとき(fallback kind)
      "depends_on": ["C09","C10"],         // component 間依存(循環なし)
      "build_target": "plugins/notion-task-sync/skills/run-notion-task-sync/",  // 非空必須
      "builder": "run-skill-create",       // handoff と一致
      "build_kind": "skill",
      "quality_gates": { /* §6 */ },       // 旧 C*.md frontmatter から載せ替え
      "harness_coverage": { "min": 80, "kind_pass": "..." },
      "feedback_contract": { "criteria": [ /* skill loop のみ */ ] }
    }
    // ... N 実体
  ],
  "plugin_level_surfaces": {               // manifest/composition/harness_eval/references_config_assets/schemas/vendor/mcp_app_connector/notion_config
    "manifest": {"required": true},
    "mcp_app_connector": {"required": false, "omitted_reason": "..."},
    "notion_config": {"required": true, "resolution": "notion_config", "databases": [{"key": "...", "used_by": "C01", "direction": "write"}], "token": "keychain"}
  }
}
```

- **各 component が ≥1 phase の `entities_covered` に出現**すること(orphan 防止・`detect-unassigned.py` が強制)。典型は Phase02(全 component)/ Phase05(全 buildable)/ Phase04(skill loop 系)。
- **script の畳み込み(P02)**: 独立 builder を持つ kind(skill/sub-agent/slash-command/hook)は各実体を必ず独立 component にする。builder を持たない script は複数 skill 共有 / 独立検証 / 280 行超のいずれか(no-split threshold)を満たす時のみ独立 component に昇格し、単一 skill 専用 script は親 skill の build へ畳む(水増し回避)。
- **水増し(padding)の定義** = 「本数が多い」ことではなく「`build_target` を持たない / 重複する / 到達不能な component の存在」。各 component が唯一の実 build_target に写像する限り、実体数が多いのは正しい帰結。

---

## 6. 各 component_kind の構造契約(要約)

> 唯一の実行可能正本 = `scripts/specfm.py` の `STRUCTURAL_REQUIRED`。下表はその projection。

| component_kind | 主な必須キー | 後段 builder |
|---|---|---|
| **skill** | skill-brief 14 base + `skill_kind` + 条件付き(goal/purpose_background/checklist/responsibilities 等)+(run/wrap/delegate なら)feedback_contract.criteria(inner+outer)+ goal_seek + prompt_layer + combinators | `run-skill-create` |
| **sub-agent** | name / description / tools(最小権限)/ independent_context:true / responsibility_anchor / prompt_layer | 親 skill build 内 `run-build-skill --with-subagent` |
| **slash-command** | name / description / argument-hint / allowed-tools / disable-model-invocation | 親 skill build 内 `run-build-skill kind=command` |
| **hook** | event / matcher / exit_semantics / settings_wiring / fail_closed:true | 親 skill build 内 `run-build-skill --with-hooks` |
| **script** | script_name / purpose / inputs / outputs / exit_codes / network / write_scope / stdlib_only:true / tests_min:80 | 親 skill build の scripts/ + tests/ |

全 buildable component 共通で **core 規律**を目録エントリに携帯:
```yaml
quality_gates:
  p0_lint: [<kind別の必須lint>]
  build_trace: required
  elegant_review: {conditions: [C1,C2,C3,C4], all_pass: true}
  content_review: {verdict: PASS, sha_match: true}
  evaluator: {threshold: 80, high_max: 0}
harness_coverage: {min: 80, kind_pass: <kind別>}
```

index(main) は `plugin_meta`(manifest / marketplace / cachebuster / validate_plugin + distribution/pkg_contract/governance/ci/ssot_dedup/feedback_deploy)を携帯。feedback_deploy はコア(常時・opt-out は `{enabled:false, reason}`)で、Notion 受け皿は `notion_sink{config_key, schema_ref, resolution}` を宣言し DB ID は設置先 `.notion-config.json` が供給する(契約は `references/io-contract.md` §9)。

---

## 7. 品質ゲート(生成 plan が全 exit0 で通る決定論検査)

| スクリプト | 検査 |
|---|---|
| `check-plugin-goal-spec.py` | goal-spec + plugin 固有アンカー(target_plugin_slug/plan_dir。requested_count は任意) |
| `check-requirements-coverage.py` | (SDD・RTM) goal-spec checklist の各要件 id が index の `## 完了チェックリスト` / `## 受入確認` へ被覆されることを fail-closed 検査(要件 orphan=silent drop 防止・detect-unassigned の component orphan と鏡像) |
| `verify-index-topsort.py` | (二層) index が P01..P13 を phase_number 昇順で全列挙 + inventory component DAG 非循環 |
| `detect-unassigned.py` | 13 phase ファイル全存在 + §5 section 床 + 各 component が ≥1 phase の entities_covered に出現(orphan 防止)+ build_target 非空 |
| `check-spec-frontmatter.py` | phase frontmatter(PHASE_REQUIRED)+ inventory component_kind 別構造 + criteria の purpose-traceability |
| `check-spec-gates.py` | inventory component の quality_gates / harness_coverage 値域 + index.plugin_meta 値域 |
| `check-spec-matrix-coverage.py` | 46 行マトリクスの焼き先反映(--self-test で drift 検出)+ phase/inventory scope |
| `check-surface-inventory.py` | 5 種検討証跡 + plugin-level surface 採否 |
| `check-build-handoff.py` | L3→L4 routing(inventory 由来)/ builder / build_kind / manifest draft / `task_graph_ref` 必須 |
| `validate-task-graph.py` | デフォルト成果物 `task-graph.json` の 10 検査(DAG 非循環/orphan 0/producer 一意/inventory 矛盾 0/非正準拒否) |
| `check-runtime-portability.py` | install 携帯性: 共有 script の plugin-root hoist(P)+ build_target の plugin 内自己完結(Q) |
| `check-plugin-surface-audit.py` | plugins/ 配下の現物 surface 横断棚卸し(dogfood) |

呼称は 2 層(core 5 scripts / 6 invocations + 拡張ゲート 7 本)。一覧と総数(検証 12 本)の単一正本 = `references/io-contract.md` §11 表 + `specfm.GATE_SCRIPTS`(本表はその要約 projection)。task-graph はデフォルト成果物(§9)ゆえ handoff に `task_graph_ref` を常時付与し build を task-graph mode で駆動する。

per-phase の恒久ロック(pytest): `test_examples_golden`(13 phase + index = 14 Markdown / 全 P01-P13 存在)+ inventory の 5-kind 網羅(≥1 kind が ≥2 実体)+ `test_detect_unassigned`(phase 完全性 + component orphan)。

---

## 8. ゴールデン例(到達点の生きた手本)

`examples/sample-plan/` = 構想「notion-task-sync」を index.md + **13 phase ファイル**(`phase-01-requirements.md` … `phase-13-release.md`)+ **`component-inventory.json`(11 の buildable component)** で表現した実例(全ゲート exit0):

| id | kind | 実体 | 依存 |
|---|---|---|---|
| C09 | script | validate-sync-payload.py(3 skill 共有) | — |
| C10 | script | notion-idempotency-key.py(2 skill 共有) | — |
| C11 | hook | guard-destructive-sync | — |
| C01 | skill/run | run-notion-task-sync | C09,C10 |
| C03 | skill/run | run-notion-task-backfill | C09,C10 |
| C02 | skill/run | run-notion-task-reconcile | C09,C01 |
| C04 | sub-agent | notion-sync-verifier | C01 |
| C05 | sub-agent | notion-reconcile-auditor | C02 |
| C06 | sub-agent | notion-backfill-auditor | C03 |
| C07 | slash-command | sync-tasks | C01 |
| C08 | slash-command | reconcile-tasks | C02 |

skill×3 / sub-agent×3 / slash-command×2 / hook×1 / 共有 script×2 = **同一 kind 複数実体を inventory で実演**し「kind ごと 1 本」への退化を防ぐ。各 component が実 build_target を持ち padding ゼロ。フェーズ軸ではこれらが `entities_covered` の id 参照として各 phase ファイルに現れる(Phase02 が全 component、Phase05 が全 buildable、Phase04 が skill loop 系)。

---

## 9. 境界(変わらない原則)

- 実プラグイン `plugins/<slug>/` は**作らない**(計画のみ)。実 build は run-skill-create/run-build-skill へ委譲。
- `distributable:false`(marketplace/bundles 非登録・計画専用プラグイン)。
- `--mode update` は Edit 差分のみ(全書き換え禁止)。
- スクショは取得しない(Markdown/CLI 主体ゆえ lint/test/coverage のテキスト受入証跡で完了を証明)。

---

## 10. 今回の改善差分(Before → After)

| 項目 | Before(per-component) | After(per-phase) |
|---|---|---|
| ファイル軸 | buildable 実体 1 個 = 1 ファイル(`C01-…md`・本数可変) | **13 フェーズ = 13 ファイル(`phase-01..13.md`・本数固定)** |
| 本数の扱い | 実体数だけ本を作る導出 + 件数固定フラグ + 並記論争 | **13 固定(フェーズ数)。実体数 N は inventory 件数の射影・要求本数は任意記録** |
| 機械契約の住処 | 各 C*.md の frontmatter | **`component-inventory.json` の `components[]` エントリ(旧 frontmatter を載せ替え)** |
| 実体と phase の関係 | 実体 = ファイル(1:1) | **正規化: phase は `entities_covered` の id 参照だけで component に紐づく** |
| index | 依存 top-sort 順 + 本数根拠 | **P01..P13 phase_number 昇順 + コンポーネント目録の所在 + 受入確認** |
| ゴールデン例 | 11 の C*.md | **13 phase ファイル + inventory(11 component)** |
| 検証 | build_target 非空 + 実体単位の回帰ロック | **phase 完全性 + component orphan 検出 + inventory DAG(二層)** |

---

## 11. コミット前の残手順(未実施)

1. content-review verdict の再生成(SKILL/refs/prompts 変更のため・`run-elegant-review` + `assign-skill-design-evaluator` で genuine 生成・SHA 手書換禁止)
2. `make sync`(`.claude/` の symlink 展開)
3. `git archive HEAD` でクリーンチェックアウト検証(新 phase ファイルが tracked かの再発防止)
