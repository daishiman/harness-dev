# harness-creator 完全解剖 — 何をどう構築し、何が出来上がるのか

> 対象: `plugins/harness-creator/`（version 1.4.27 / skills 32 + agents 8 + commands 6）
> 目的: (A) ハーネスをどう構築しているか (B) 出来上がったハーネスがどんな要素で構成されるか — を漏れなく抽出する
> 位置づけ: 本書は**解説文書**であり正本ではない。正本は各章末の「正本」欄に示すファイル。
> 配置理由: plugin 配下は `lint-ssot-duplication.py` が正本の再掲を violation 判定するため、解説は `doc/` 配下に置く。

---

## 第0部 用語 — 「ハーネス」とは何か

このリポジトリで **ハーネス (harness)** とは、次の 2 つを束ねた構築物の総体を指す。

1. **Capability**（能力の実体）… Skill / Agent / Hook / Command / Plugin-Composition / Prompt / Workflow の 7 種
2. **評価・統治機構**（能力を腐らせない仕組み）… rubric / verdict / lint / feedback loop / knowledge loop / governance

つまり「動くもの」だけでは harness ではない。**動くもの + それが正しいことを機械が証明し続ける仕組み** が harness。

harness-creator はその harness を作る **メタハーネス**であり、自分自身も上記の規約に従っている（dogfooding）。
2026-07-02 に `skill-creator` → `harness-creator` へ改名されたのは、「スキルを作る道具」から「ハーネスを作る道具」へ対象が拡大したため。

---

# 第1部 入口 — 何を作りたいときにどれを叩くか

| 作りたいもの | 入口 | 主な産物 |
|---|---|---|
| 構想から plugin 全体の計画 | `/plugin-dev-plan <構想>` | `index.md` + 13 phase ファイル + `component-inventory.json` + handoff |
| 単体スキルを端から端まで | `/run-skill-create` | `skills/<name>/` 一式 |
| skill 以外の単一 Capability | `/capability-build <kind> <name> --plugin=<plugin>` | Capability 1 個 |
| ハーネス総体を束ねる | `/plugin-compose <plugin-name>` | `plugin-composition.yaml` |
| 出荷前検査 | `/run-plugin-package-check <plugin> --phase all` | PKG-001〜015 verdict |
| レビュー | `/capability-review <target-path>` | 4 条件 verdict |
| 改善 | `/skill-improve <capability-path>` | 最小パッチ + 再レビュー |

**標準フロー（全ステップ必須。飛ばすと下流が false green になる）**

```text
0. 前提: cwd=repo root / make native-surfaces PASS / harness-creator + plugin-dev-planner が有効化・信頼済
1. /plugin-dev-plan <構想>
      → index.md + 13 phase + component-inventory.json + handoff(routes[] + task_graph_ref)
2. /capability-build --handoff <handoff>
      → 既定は task-graph route モード（並列 dispatch + 2 重ループ）
2.5 envelope 適用 ← 手動ステップ。省略すると Step4 の PKG-001 が FAIL する
3. /plugin-compose <plugin-name>
      → validate-plan-coverage.py が「計画の漏れなさ」を測る唯一の gate
4. /run-plugin-package-check <plugin-name> --phase all
      → --phase 省略(=0)は PKG-010〜015 が黙って未検査になる false green
5. /capability-review plugins/<plugin-name> plugin
6. /skill-improve <capability-path>
```

正本: `plugins/harness-creator/README.md`

---

# 第2部 どうやって構築しているか（構築メカニズム）

## 2.1 全体像 — 4 層構造

```
[計画層]  plugin-dev-planner  … 構想 → 13 phase + routes[] + task-graph
    │  E1 境界
[実行層]  capability-build    … task-graph を並列 dispatch する dispatcher
    │  E2 境界
[生成層]  run-build-skill     … 1 Capability の実体を生成する唯一のエンジン
    │
[検証層]  lint群 / assign-* evaluator / elegant-review / PKG gate / governance
```

## 2.2 パイプライン境界 E1〜E4

| 境界 | producer → consumer | 渡すもの | gate |
|---|---|---|---|
| **E1** | intake → plan | goal-spec | plan-evaluator |
| **E2** | plan → build | handoff（routes[] + task_graph_ref） | 構造検証 |
| **E3** | 改善 → plan | improvement-handoff | improvement-reviewer |
| **E4** | build 中の発見 → planner | discovered-task inbox | accept-discovered-task.py |

**識別子 namespace**（裸の `Cxx` は禁止）

| prefix | 意味 | 例 |
|---|---|---|
| `PB-Cxx` | パイプライン契約 | PB-C01〜C11 |
| `TG-Cxx` | task-graph 実行 | TG-C01〜C09 |
| `ENG-Cxx` | 生成 harness へ同梱される engine | ENG-C01/C02/C06/C07/C08 |
| `route Cxx` | plan ローカル | route 内でのみ有効 |

正本: `plugins/harness-creator/references/pipeline-boundary-contract.md`

## 2.3 task-graph route モード — 2 重ループ

`/capability-build --handoff <handoff>` の既定モード。**node は 13 phase の §5 チェックリスト項目の決定論射影**であり、routes[] と同粒度ではない。`entity_ref == route.component_id` で node → route を決定論 join する。

### 内ループ（build-execution）

| 手順 | 実体 | 契約 |
|---|---|---|
| 0 | `manage-build-lease.py --lock-action acquire` | TG-C07。lock TTL 7200s |
| 0 | `derive-route-build-obligations.py` → `plan-verification-obligations.py` | 証明義務の導出 |
| 1 | `dispatch-ready-set.py` | TG-C01。`ready_batch` / `conflicts` / `blocked` / `graph_hash_pin` |
| 2 | `--max-workers`（既定2）以内で dispatch | `file_ownership` を worker に渡す |
| 3 | `sync-task-state.py` | TG-C02。**dispatcher 自身のみ**が直列呼出（単一 writer）。heartbeat は lock TTL の 1/3 以下 |
| 4 | ローリング発火 | **barrier 禁止**。done の write-back そのものが次 dispatch の発火条件 |
| 5 | `summarize-task-progress.py` (TG-C05) → `completion-evidence.json` → `build-summary.json` → **TG-C09 `project-task-status.py`** → lock release | TG-C09 は非スキップ必須 |

**TG-C09 が必須な理由**: `task-execution-report.html` は build 完了の必須成果物。これを生成せずに completed を宣言してはならない。レポートは「why & value（なぜ作ったか・何の価値か）」セクションの携帯が必須。

### 外ループ（spec-improvement）

結合点は 2 つだけ。

- **結合点1 = 完了ゲート TG-C08**: `record-task-graph-knowledge.py`。`completion_gate: blocked` なら `handback_command` と `next_steps[]` を提示して止まる。
- **結合点2 = graph_hash の provenance-gated repin**: 承認済み discovered-task に由来する hash 以外での re-pin は拒否される（`--repin-graph-hash` は `--authorized-hash` 併用が必須）。

### actor 責務の分離（設計の中核）

> **活性（前に進める）は AI orchestrator、安全と決定性は決定論 script、不可逆な仕様変更の承認は人間。**

この 3 分割が harness-creator 全体の背骨。AI に判断させる箇所は極小化されており、たとえば stall→emit で **AI 判断が必要な引数は `--node-title` と `--reason` の 2 つだけ**、残りは TG-C05 の構造化フィールドから機械導出される。

### 片方向 writer の逆説

harness 側が task-graph を直接書かないのは 4 つの理由による: ①canonical serializer の二重化 ②structural な二段受理のバイパス ③provenance の断裂 ④同時書込 race。

正本: `plugins/harness-creator/commands/capability-build.md`

## 2.4 生成エンジン — run-build-skill の Step 0〜12

「どうやって作るか」の実体。全 7 kind の生成本体がここにある。

| Step | 内容 | 使う script |
|---|---|---|
| **0** | kind 分岐ナビゲーション（kind 確認 → skeleton 選択 → Manifest 検証 → lint hook 連動） | — |
| **1** | 要求ヒアリング。`$PLUGIN_ROOT`/`$SKILL_DIR`/`$OUT_BASE` 確定、Loop B 蓄積知見の参照、**build-plan の決定論導出** | `resolve-skill-dirs.py` / `search_knowledge.py` / `validate-build-plan.py` |
| **2** | テンプレ展開。combinator を **kind → flag の順**で適用 | templates/ |
| **3** | 補助 references 生成 | — |
| **3.5** | 再現性トレース生成 + RTM(`requirement_coverage[]`) + `prompt_provenance` | → `eval-log/skill-build-trace.json` |
| **4** | 命名・構造 Lint（14 コマンドの bash ブロック） | 下表参照 |
| **5** | フォーク評価 | `Skill(assign-skill-design-evaluator)` |
| **6** | ゲート判定 | score ≥ 80 かつ high=0、最大 3 周 |
| **7** | subagent 派生（9 セクション固定構造） | — |
| **7.5** | prompt-creator ループ（R-id 単位） | — |
| **8** | evaluator ペア生成 | — |
| **9** | Hook 配線生成（**自動 merge 禁止**） | — |
| **10** | ナレッジループ注入 | knowledge/ 雛形 + 4 script + `## ナレッジループ` 節 |
| **10.6** | task-graph engine 同梱（byte 一致で冪等コピー） | ENG-C01/C02/C06/C07 |
| **11** | Notion スキル一覧 DB へ upsert | token は Keychain 経由。CI では `INTAKE_ALLOW_ENV_TOKEN=1` 明示時のみ `$NOTION_TOKEN` 可 |
| **11.5** | feedback-loop 同梱と配備（default-ON） | `run-skill-feedback` を実体コピー。**symlink 禁止** |
| **12** | 証拠 DAG 解決（verification obligations） | `plan-verification-obligations.py` |

**Key Rules（19 項目のうち構造を決める主要なもの）**

- 本文 300 行以下 / ディレクトリ名 == `name`
- **Python 標準ライブラリが正本**（`.sh` / `.js` の新規作成禁止）
- `--mode update` は Edit 差分のみ（全書き換え禁止）
- 具体値の直書き禁止 / marketplace install 後の配置に非依存であること
- **評価分離**: 生成本体は自分の成果物を採点しない
- `lint-matrix.json` が lint 集合の唯一の正本
- **ゴールシーク必須**（固定手順の羅列は禁止）

正本: `plugins/harness-creator/skills/run-build-skill/SKILL.md`

## 2.5 ゴールシーク・パラダイム（構築思想の中核）

harness-creator は生成物に **固定手順を書かせない**。代わりに 4 ブロック構造を強制する。

| ブロック | 内容 |
|---|---|
| **Goal** | 到達状態を状態記述で書く（動作の列挙ではない） |
| **Why** | なぜその状態が必要か |
| **Checklist** | 完了チェックリスト（CL-1〜CL-n） |
| **Loop** | ゴールシークループ 6 ステップ |

**ゴールシークループ 6 ステップ**
1. 現状評価 → 2. 手順生成 → 3. 実行 → 4. 検証 → 5. **中間成果物スナップショット（Anchor Step）** → 6. 反復/差し戻し（既定 5 周）

**適用マトリクス**

| sub-role | 適用 |
|---|---|
| `run-*` / `wrap-*` / `delegate-*` | 必須 + default-ON |
| orchestrator / agent / agent-team / hook-integrated | 必須相当 |
| `assign-*` | 構造のみ（loop は配線しない＝採点者は反復しない） |
| `ref-*` | 対象外（静的参照） |

**執行**: `with-goal-seek` combinator が default-ON、`lint-goal-seek.py` が固定 `### Step N:` の羅列を violation として検出する。

### ドリフト圧縮アンカー（Step 5 の実体）

各周回の末尾に `eval-log/<skill>-intermediate.jsonl` へ 5 要素を追記する。

| フィールド | 意味 |
|---|---|
| `original_goal` | 不変。SHA-256 で pin される |
| `current_goal_snapshot` | 今この周回で追っているゴール |
| `delta_from_original` | 原ゴールからのズレ |
| `merged_directive_for_next` | 次周回への統合指示 |
| `drift_signal` | 6 種の enum |

これは長い反復で起きる「集約化ドリフト（ゴールがじわじわ抽象化・矮小化する現象）」を可視化し、押し戻すための機構。

### 達成判定（GOAL VERIFICATION）

fresh agent 1 体が `original_goal` に対し **PASS | FAIL + blocker 列挙のみ**を返す。**点数の出力は禁止**（点数を出すと点数を最適化する Goodhart 化が起きるため）。

### コンテキスト分離（必須）

ループ本体を親セッションで回さない。SubAgent 既定 / Agent Team。理由は sycophancy（自分の生成物を自分で甘く評価する）の防止。

### goal_seek.engine 3 変種

| engine | 用途 |
|---|---|
| `inline` | 小規模 |
| `run-goal-seek` | 汎用 |
| `task-graph` | loop kind の既定。ready 集合は最小 id を拘束選択、self-reflect 追記、consumption verifier、`max_loops` は item 数 × 1.5 が目安 |

正本: `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`

## 2.6 sub-role prefix（di-quartet）— ディレクトリ名が設計規約になっている

| prefix | 責務 | 書込 |
|---|---|---|
| `run-*` | オーケストレーション | 可 |
| `assign-*` | 採点・検査 | **read-only** |
| `ref-*` | 静的参照（leaf） | 不可 |
| `delegate-*` | 外部委譲 | — |
| `wrap-*` | 安全ラッパ | — |
| `lookup-*` / `dispatch-*` | 将来予約 | — |

**依存方向は `run-* → assign-* → ref-*` の一方向のみ**。逆流は lint が検出する。32 個の skill 名を見るだけで責務が判別できるのはこの規約の効果。

正本: `plugins/harness-creator/references/di-quartet.md`

## 2.7 単体スキルの E2E フロー（run-skill-create）

```
[Step 1 elicit]  run-skill-elicit → skill-brief.json ──[Gate 1]──▶
[Step 2 build]   run-build-skill → skill-build-trace.json
[Step 3   ] manifest-register  [Gate 2.5]  [Step 3.5] bundle-register
[Step 3.55/3.56] codex-platform-sync / check
[Step 3.6 ] local-marketplace-register   [Step 3.7] plugin-release-record
[Step 4a  ] p0-lint  (fail→Step 2 へ戻す、最大 3 周) ──[Gate 2: diff]──▶
[Step 4a.5] pkg-check   [Step 4b] design-evaluate (context:fork)
[Step 5   ] elegant-review (新規 or 30 行超の変更時, context:fork) ──[Gate 3]──▶
[Step 6   ] governance ──[Gate 4]──▶ [Step 7] report
```

Key Rules: ゲート前で必ず止まる / 子スキルへ委譲 / **context:fork 必須** / handoff 保存 / **lint の自動修正禁止** / 日本語成果物ゲート。

`build-plugin-release.py` は append-only ではないため、Gate 2.5 承認後かつ `--only <plugin>` 必須。

正本: `plugins/harness-creator/skills/run-skill-create/SKILL.md`

## 2.8 profile × stage の直交 2 軸

| 軸 | 値 | 意味 |
|---|---|---|
| **profile** | `incremental` / `build-only` / `exhaustive` | **証明の深さ** |
| **stage** | `draft` / `release` | **どこまで作るか** |

この 2 軸は直交しており、「draft だから検証を省く」も「exhaustive だから release」も成立しない。

## 2.9 verification obligation DAG

claim を `deterministic` / `semantic` / `observational` / `audit` の 4 種に compile し、fingerprint に束縛された PASS receipt で再利用する。

旧来の「routes × agents × methods × iterations」型のコストモデル（検証コストが組合せ爆発する）は明示的に否定されている。同じ fingerprint なら証明を使い回す設計。

## 2.10 ナレッジループ Loop A / Loop B

| ループ | 対象 | consult タイミング |
|---|---|---|
| **Loop A** | 生成された harness 側 | runtime consult |
| **Loop B** | harness-creator 自身 | build-time consult（Step 1 で `search_knowledge.py`） |

Loop B が dogfooding の実体。過去 build で得た知見が次の build の入力になる。

---

# 第3部 出来上がったハーネスは何で構成されるか（産物の要素）

## 3.1 Capability 7 kind

| kind | 実体 | 必須追加フィールド |
|---|---|---|
| **skill** | `skills/<name>/SKILL.md` + 付帯資産 | （commonCore のみ） |
| **agent** | `agents/<name>.md` | `tools`, `isolation`（fork / worktree / inherit。`assign-*` は必ず fork） |
| **hook** | `hooks/hooks.json` の共有定義 + script（Claude=標準自動検出 / Codex=manifest 明示参照） | `event`（8 種）, `command`（+ `exit_code_policy`, `side_effect_scope`） |
| **command** | `commands/<name>.md` | `argument-hint`, `allowed-tools`（entrypoint は薄いラッパであること） |
| **plugin-composition** | `plugin-composition.yaml` | `capabilities` |
| **prompt** | `prompts/R<n>-<role>.md` | `layers`（minItems=maxItems=7 の 7 層構造） |
| **workflow** | `workflow-manifest.json` | `phases` |

## 3.2 CapabilityManifest（統一宣言スキーマ）

`allOf: [commonCore, oneOf[kindSkill | kindAgent | kindHook | kindCommand | kindPluginComposition | kindPrompt | kindWorkflow]]`

**commonCore.required** = `name` / `description` / `kind` / `version` / `owner`

**commonCore.optional** =
`tags` / `since` / `last-audited` / `audit-trigger` / `contract{intent, interface, invariant}` / `rubric_refs` / `responsibility_refs` / `knowledge_loop` / `feedback_contract`

正本: `plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json`

## 3.3 skill の frontmatter に実際に並ぶもの

実例（`run-plugin-package-check`）で見ると、生成された skill は以下を持つ。

```yaml
name / description / disable-model-invocation / user-invocable
argument-hint / arguments / allowed-tools / model
kind / prefix / effect / owner / since / version
source / source-tier / last-audited / audit-trigger
pair:                # 対になる assign-* evaluator
manifest:            # workflow-manifest.json
responsibility_refs: # prompts/R1-*.md, R2-*.md …
rubric_refs:         # 採点軸の参照
schema_refs:         # 入出力スキーマ
script_refs:         # 同梱 script 一覧
feedback_contract:   # ↓ 次節
```

## 3.4 feedback_contract（自己評価契約）

各 skill が「自分が正しく動いた」と主張する条件を機械可読で宣言する。

```yaml
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1              # pattern ^(IN|OUT|C)[0-9]+$
      loop_scope: inner    # inner = lint/script、outer = evaluator/elegant-review
      text: <達成条件を1文で>
      verify_by: script    # lint | test | script | evaluator | elegant-review | live-trial | human
      derived_from: [CL-1] # 完了チェックリストのどの項目由来か
```

- **inner ループ** = lint / script で機械判定できるもの
- **outer ループ** = evaluator / elegant-review が意味判定するもの
- `derived_from` により「チェックリスト項目 → 評価基準」の追跡が切れないことが保証される

正本（判定ロジック）: repo-root `scripts/feedback_contract_ssot.py`

## 3.5 SKILL.md 本文の固定構造

```markdown
# <name>
## Purpose & Output Contract     ← BD-001（high）で必須
   入力 / 出力 / 完了条件
## Key Rules                      ← 禁止事項と不変条件
## ゴールシーク実行                 ← lint-goal-seek.py の検査対象
   ### ゴール (Goal)
   ### 目的・背景 (Why)
   ### 完了チェックリスト (Checklist)
   ### ゴールシークループ
## 局面カタログ（順序は都度判断）    ← 「Step N を順に実行」ではない
## Gotchas                        ← BD-002（medium）
## ナレッジループ                   ← knowledge 組込時のみ
```

**本文は 300 行以下**（BD-003, high）。超える内容は `references/` へ逃がす。

## 3.6 skill ディレクトリの構成資産

```
skills/<name>/
├── SKILL.md                  # 本体（300行以下）
├── prompts/                  # R1-*.md, R2-*.md … 責務プロンプト（7層構造）
├── references/               # 静的参照。本文から溢れた仕様
├── schemas/                  # 入出力 JSON Schema
├── scripts/                  # Python 標準ライブラリのみ（.sh/.js 新規禁止）
├── templates/                # 生成物の雛形
├── knowledge/                # ナレッジループ（Step 10 で注入）
│   ├── index-search/
│   ├── router-registry/
│   └── scripts/              # search_knowledge.py / record_usage.py 等 4 本
└── workflow-manifest.json    # phase 定義（workflow kind のとき）
```

## 3.7 生成時に自動同梱される 4 機構

| 機構 | 注入 Step | 実体 |
|---|---|---|
| **goal-seek 配線** | Step 2 | `with-goal-seek.patch` combinator（default-ON） |
| **knowledge ループ** | Step 10 | `knowledge/` 雛形 + 4 script + `## ナレッジループ` 節 + `consult_at: ["runtime"]` |
| **feedback ループ** | Step 11.5 | `run-skill-feedback` を**実体コピー**で冪等配備（symlink 禁止） |
| **task-graph engine** | Step 10.6 | ENG-C01/C02/C06/C07 を byte 一致でコピー。`engine_profile: checklist-graph` / `full_task_spec_graph: false` |

つまり生成された harness は、**放っておいても自分で反復し・知見を貯め・自己採点し・並列実行できる**状態で出荷される。

## 3.8 テンプレート体系（templates/）

**skeleton（kind ごとの骨格）**
`_base.md` / `run.md` / `ref.md` / `delegate.md` / `wrap.md` / `orchestrator.md` /
`agent-skeleton.md` / `agent-team.md` / `hook-skeleton.md` / `hook-integrated.md` /
`command-skeleton.md` / `prompt-skeleton.md` / `workflow-skeleton.md` /
`plugin-composition-skeleton.yaml` / `assign-evaluator.md` / `assign-generator.md`

**combinator（12 個の差分パッチ。kind → flag の順で適用）**

| combinator | 付与するもの |
|---|---|
| `with-goal-seek.patch` | ゴールシーク 4 ブロック（default-ON） |
| `with-feedback-contract.patch` | feedback_contract |
| `with-knowledge.patch` | ナレッジループ |
| `with-run.patch` / `with-ref.patch` / `with-wrap.patch` / `with-delegate.patch` | sub-role 固有構造 |
| `with-assign-evaluator.patch` / `with-assign-generator.patch` / `with-evaluator.patch` | 採点系の配線 |
| `with-subagent.patch` | subagent 派生 |
| `with-hooks.patch` | hook 配線 |

**同梱ディレクトリ**: `knowledge-skeleton/`（index-search / router-registry / scripts）、`task-graph-engine/scripts/`

この「skeleton × combinator」の組合せ設計により、7 kind × 各種フラグの直積を、テンプレート数を線形に保ったまま表現できている。

## 3.9 plugin-composition.yaml（ハーネス総体の宣言）

```yaml
name / description / kind: plugin-composition / version / owner
distribution: codex-marketplace

contract:
  intent:      <このハーネスは何のために存在するか>
  interface:   { inputs: [...], outputs: [...] }
  invariant:   # 12 個。各々に enforcement 注記が付く
    - text: ...
      enforcement: <機械執行する script 名> または manual + 意図的残置理由

capabilities:   # {kind, ref, tier} の列挙
  # harness-creator 実測: skill 32 / agent 6 / command 6 / script 6 / hook 1
  # tier: core | ref | extension

dependencies:   # {from, to, type} の DAG
  # type: calls / reads / extends / evaluates / emits / writes / delegates / deploys
  # lint が循環を検出する

eval_sinks:     # 評価結果の出力先
governance:
  rubric_refs / changelog / roadmap
  merge_strategy: deep-merge
  conflict_policy: most-specific-wins
observability:
  hooks / metrics / lessons_path
```

**`invariant[]` の各項目に `enforcement:` が必須**なのが特徴。「守るべきこと」を書いたら「誰が守らせるか」を同時に書かせる。manual の場合は意図的に人間に残した理由の明記が要る。

正本: `plugins/harness-creator/plugin-composition.yaml`（リファレンス実装）

## 3.10 hook 配線（共有 hooks/hooks.json）

harness-creator の現行の plugin hook は **7 イベント / 13 コマンド**（SessionStart / PostToolUse /
UserPromptSubmit / PreToolUse / PostToolUseFailure / Stop / SessionEnd）。共有正本
`hooks/hooks.json` が唯一の配線元で、各コマンドは公開面 `hooks/<capability>.py` を起動し、
実体は対応する `skills/*/scripts/` の実装へ委譲する（`plugin-composition.yaml` の
`hook:` capability と 1 対 1）。コマンドは dual-root 形
`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` で、どちらの product でも install 先に依存しない。

- Claude は標準自動検出で `hooks/hooks.json` を読むため、`.claude-plugin/plugin.json` に
  `hooks` pointer を重ねない（二重発火防止）。
- Codex manifest は `./hooks/hooks.json` を明示参照し、同じ正本を読む。
- project 設定へ plugin hook を再投影しない。配信カーディナリティは plugin ごとに 1 とする。

## 3.11 eval-log 証跡群（作られたものの「証明書」）

| ファイル | 内容 |
|---|---|
| `skill-build-trace.json` | 再現性トレース + RTM(`requirement_coverage[]`) + `prompt_provenance` |
| `<skill>-build-plan.json` | Step 1 で決定論導出された build 計画 |
| `<skill>-intermediate.jsonl` | ドリフト圧縮アンカー（周回ごと append） |
| `<plugin>/pkg-<id>/<date>-<run>.json` | 各 PKG gate の個別ログ |
| `<plugin>/pkg-summary/<date>-<run>.json` | PKG 集約（run-report.schema.json 準拠） |
| `**/content-review/*-verdict.json` | elegance / rubric verdict |
| `**/*-score.jsonl` | 採点レコード（**実評価の正本**） |
| `route-*.json` / `plan-P*.json` | route / plan 単位の成果 |
| `completion-evidence.json` | 完了証拠。evidence[] は**裸の実在パスのみ**（注釈を付けると invalid） |
| `build-summary.json` | build 集約 |
| `task-execution-report.html` | TG-C09 の必須成果物。why & value セクション携帯必須 |

> `EVALS.json` の `evaluations[]` は **DEPRECATED**。実評価レコードの正本は `eval-log/**/*-score.jsonl` と `eval-log/**/content-review/*-verdict.json`。

## 3.12 配布まわり

| 項目 | Claude | Codex |
|---|---|---|
| manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| marketplace | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| `distributable` | **false**（公開 marketplace 非配布） | **true**（単独 install 可） |
| root 変数 | `${CLAUDE_PLUGIN_ROOT}` | `${PLUGIN_ROOT}` — dual-root 形で両対応 |

`native-surfaces.toml` は `[activation]` / `[codex]` / `[discovery]` / `[[hooks]]` を持ち、
`activation_requires = ["user-install", "user-enable", "user-hook-trust"]` を宣言する。

**native surface projection (C01)**: `sync-native-surfaces.py` が唯一の desired-set owner。install / trust は `pending_user_gate` として分離される（＝ツールが勝手にユーザー環境へ有効化しない）。

`package-contract.json`: `package_mode: bundle` / `entry_points` / `requirements.external_clis` に tmux（live-trial の輸送層。不在時は verdict=BLOCKED として明示失敗）。

---

# 第4部 品質を保証する機構

## 4.1 lint 群（lint-matrix.json が唯一の正本）

`lint-matrix.json` は 3 つの消費面を持ち、`lint-matrix-sync.py` が消費面との突合を機械検査する。

| consumer | 実体 |
|---|---|
| `build-preflight` | `run-build-skill/SKILL.md` Step 4 の bash ブロック |
| `p0-gate` | `run-skill-create/workflow-manifest.json` の `phases[id=p0-lint].commands` |
| `ci` | `.github/workflows/governance-check.yml`, `harness-creator-kit-ci.yml` |

| lint id | script | 検出するもの |
|---|---|---|
| skill-name | `lint-skill-name.py` | 命名規約 第1〜5,7 条 |
| skill-description | `lint-skill-description.py` | trigger phrase 数・内部詳細の漏れ |
| skill-tree | `lint-skill-tree.py` | ディレクトリ構造 第8〜13 条 |
| frontmatter | `validate-frontmatter.py` | CapabilityManifest 適合 |
| script-frontmatter | `lint-script-frontmatter.py` | script の frontmatter |
| skill-completeness | `lint-skill-completeness.py` | 必須節の欠落 |
| **goal-seek** | `lint-goal-seek.py` | **固定 `### Step N:` 羅列**（ゴールシーク違反） |
| feedback-contract | `lint-feedback-contract.py` | criteria の id / verify_by / derived_from |
| **ssot-duplication** | `lint-ssot-duplication.py` | DUP-SCHEMA-ID / REDIRECT-FAT-BODY / DUP-REQUIRED-SET / DUP-PASSAGE |
| knowledge-loop | `lint-knowledge-loop.py` | knowledge/ の 6 必須フィールド等 |
| build-trace | `validate-build-trace.py` | トレースの完全性 |
| readme-portability | `lint-readme-plugin-root-portability.py` | install 配置依存の混入 |
| （hook 層・matrix 外） | `lint-capability-manifest.py` | PostToolUse:Edit\|Write で常時発火 |

**lint の追加・削除は必ず `lint-matrix.json` を先に更新**し、消費面（SKILL.md / manifest / CI）を追従させる。`ci` を持たない lint は `ci_exclusion_reason` が必須。

## 4.2 設計 rubric（41 rule / threshold 80 / L0）

`rubric_id: skill-design`, `rubric_version: 1.3.0`, `threshold: 80`, `max_skill_md_lines: 300`, `trigger_count_min/max: 2/3`。

各 rule は `applies_to_kinds` でどの kind に適用するかを宣言する（`*` = 全 kind 共通核）。

| 群 | 適用 | rule |
|---|---|---|
| **FM**（frontmatter） | `*` | FM-001 name 正規表現(high) / FM-002 trigger phrase 有(medium) / FM-003 trigger 2〜3個(medium) / FM-004 description に内部動作の動詞を書かない(medium) / FM-005 動詞始まり(low) |
| **BD**（body） | `*` | BD-001 `## Purpose & Output Contract` 必須(high) / BD-002 `## Gotchas`(medium) / BD-003 本文 ≤300 行(high) / BD-004 description の発動条件が本文に対応(medium) |
| **NM**（naming） | `*` | NM-001 ディレクトリ名==name(high) / NM-002 命名 lint 通過 / NM-003 tree lint 通過 |
| **PD** | `*` | PD-001 本文 ≤100 行 or references 有 / PD-002 冒頭 30 行に Purpose 見出し |
| **RG** | `*` | RG-001 出力 JSON に `rubric_hash`(rubric 自身の sha256) |
| **AG**（agent） | agent | AG-001 tools 明示 allowlist(high) / AG-002 `## Isolation` or `## Context Boundary`(high) / AG-003 phase 一意 id / AG-004 `## Handoff` or `## Output Contract` |
| **HK**（hook） | hook | HK-001 event が 8 種のいずれか(high) / HK-002 matcher が具体的（**ワイルドカード禁止**, high） / HK-003 timeout 有界（無限待ち禁止） / HK-004 副作用の文書化 |
| **CM**（command） | command | CM-001 argument-hint / CM-002 allowed-tools が最小 allowlist（ワイルドカード・欠落禁止, high） / CM-003 実在する entrypoint skill を参照(high) |
| **PC**（composition） | plugin-composition | PC-001 capabilities[] 列挙(high) / PC-002 **依存が DAG（循環禁止）**(high) / PC-003 rubric 参照が解決可能 / PC-004 hook が実在 event に配線 |
| **PR**（prompt） | prompt | PR-001 **ちょうど 7 層**(high) / PR-002 `## Self-Evaluation` / PR-003 `## Output Format` 明示(high) |
| **WF**（workflow） | workflow | WF-001 phase が順序付き(high) / WF-002 各遷移に PASS/FAIL gate 条件(high) / WF-003 `max_iterations` 等の安全弁 |
| **KL**（knowledge-loop） | `*`（ゲート付き） | KL-001〜005。knowledge/ 不在なら**無条件 PASS**（誤減点防止） |

`severity_weights` は high / medium / low の 3 段。`merge_strategy: deep-merge` / `conflict_policy: most-specific-wins`。

正本: `plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json`

## 4.3 PKG-001〜017（package 契約 gate）

phase で段階が分かれる。**`--phase all` を明示しないと 010〜015 が黙って未検査になる**。

| PKG | 内容 | 適用 mode | phase |
|---|---|---|---|
| 001 | `claude plugin validate --strict` 通過 | bundle | 0 |
| 002 | `plugin.json` frontmatter 完備 | bundle, skill-only | 0 |
| 003 | package 単位の名前空間衝突検査 | bundle | 0 |
| 004 | SKILL.md frontmatter 完備 | bundle, skill-only | 0 |
| 005 | Agent definition 整合 | bundle | 0 |
| 006 | Hook registration 整合 | bundle | 0 |
| 007 | script 存在 + 実行可能 | bundle | 0 |
| 008 | settings 断片 lint | bundle | 0 |
| 009 | **外部参照ゼロ** | bundle | 0 |
| 010 | install smoke | bundle | 1 |
| 011 | uninstall 完全性 | bundle | 2 |
| 012 | upgrade 冪等性 | bundle | 2 |
| 013a | tool permissions scope | bundle | 2 |
| 013b | filesystem permissions scope | bundle | 2 |
| 013c | network permissions scope | bundle | 2 |
| 013d | MCP/external permissions scope | bundle | 2 |
| 014 | runtime contract 検証 | bundle | 2 |
| 015 | rubric 違反率しきい値 | bundle | 2 |
| 016 / 017 | 予約（未確定。参照すると warn） | — | — |

**規約**
- **PKG-013 は単独存在しない**。必ず 013a/b/c/d の 4 sub-check に展開する
- `skill-only` mode では PKG-002/004 のみ適用、他は skip ではなく **`not_applicable`**
- PKG-002〜008 / 014 は `assign-plugin-package-evaluator` へ `context: fork` で委譲（判定者の分離）
- 1 件でも `fail` なら exit 1 で下流パイプラインを止める
- `verdict.fail > 0` のとき `pkg_check_failed` を `.claude/logs/` へ 1 run 1 行だけ emit

正本: `plugins/harness-creator/skills/ref-pkg-contract/SKILL.md`

## 4.4 elegant-review（30 思考法 × 4 条件）

**4 条件**: 矛盾なし / 漏れなし / 整合性あり / 依存関係整合

**3 フェーズ**
1. **Phase 1 (reset)** … `elegant-reset-observer` が先入観なしで read-only 俯瞰
2. **Phase 2 (3 並列分析)** … `elegant-logical-structural-analyst`（論理と構造）/ `elegant-system-strategic-analyst`（システム・戦略・価値・根本原因）/ `elegant-meta-divergent-analyst`（メタ・抽象・発想拡張）
3. **Phase 3 (改善)** … `elegant-improvement-executor` が範囲を絞って実装

**完了チェックリスト**
- `thought_method_coverage.used + skipped_with_reason == 30`（**スキップは理由付きでのみ許される**）
- `fail_counts.{contradiction, omission, inconsistency, dependency_break} == 0`

references: `30-paradigms-full.md` / `thought-methods.yaml` / `convergence-policy.json` / `amplified-patterns.json` ほか 8 種。

正本: `plugins/harness-creator/skills/run-elegant-review/SKILL.md`

## 4.5 二層分離 — 機械層と意味層

| 層 | 担当 | 判定形式 |
|---|---|---|
| **機械層** | PB-C04 / C05 / C08 / C11 | exit code |
| **意味層** | PB-C10 | fork した agent の verdict |

機械で決まることは機械で決め、意味の判断だけを AI に渡す。この分離が「AI が自分に甘い判定を出す」経路を構造的に潰している。

---

# 第5部 設計思想のまとめ（なぜこうなっているか）

1. **正本を 1 つに固定する（SSOT）** — `lint-matrix.json` が lint の、`rubric.json` が採点の、`capability-manifest.schema.json` が宣言形式の唯一の正本。再掲は lint 違反。
2. **評価者と生成者を分離する** — 生成本体は自分を採点しない。`assign-*` は read-only。評価は必ず `context: fork`。
3. **点数を最終判定に使わない** — GOAL VERIFICATION は PASS/FAIL + blocker のみ。点数を出すと点数が最適化される。
4. **手順ではなく状態を書かせる** — 固定 Step の羅列は `lint-goal-seek.py` が violation にする。ゴール + チェックリスト + ループ。
5. **ドリフトを可視化して押し戻す** — `original_goal` を SHA-256 で pin し、周回ごとに delta を記録する。
6. **活性は AI、安全と決定性は script、不可逆な承認は人間** — 3 者の責務分離。
7. **単一 writer** — task-state の書込は dispatcher のみ。race を設計で消す。
8. **barrier を置かない** — done の write-back が次 dispatch の発火条件（ローリング発火）。
9. **fail-closed** — evidence が実在しなければ blocked。tmux 不在なら BLOCKED。lint fail なら exit 1。
10. **自分自身に適用する（dogfooding）** — harness-creator の `plugin-composition.yaml` が生成物のリファレンス実装であり、Loop B で自分の build 知見を次の build に食わせる。

---

## 付録: 主要正本ファイル一覧

| 主題 | 正本 |
|---|---|
| 入口と標準フロー | `plugins/harness-creator/README.md` |
| 生成エンジン | `skills/run-build-skill/SKILL.md` |
| 単体 E2E | `skills/run-skill-create/SKILL.md` |
| task-graph dispatcher | `commands/capability-build.md` |
| パイプライン境界 | `references/pipeline-boundary-contract.md` |
| ゴールシーク | `skills/run-build-skill/references/goal-seek-paradigm.md` |
| 宣言スキーマ | `skills/run-build-skill/references/capability-manifest.schema.json` |
| sub-role 規約 | `references/di-quartet.md` |
| lint 集合 | `references/lint-matrix.json` |
| 設計 rubric | `skills/ref-skill-design-rubric/references/rubric.json` |
| PKG 契約 | `skills/ref-pkg-contract/SKILL.md` |
| レビュー | `skills/run-elegant-review/SKILL.md` |
| ハーネス総体宣言 | `plugins/harness-creator/plugin-composition.yaml` |
| feedback_contract 判定 | repo-root `scripts/feedback_contract_ssot.py` |
| package 契約 | `references/package-contract.json` / `native-surfaces.toml` |
