# 24. メタSkillテンプレート

メタSkill の SKILL.md 雛形と補助ファイル構成の設計意図をまとめる。メタSkill は `run-build-skill`（生成）・`assign-skill-design-evaluator`（採点）・`ref-skill-design-rubric`（評価基準の正本）の 3 Skill で、いずれも `plugins/harness-creator/skills/` に実在する。rubric（評価基準）の正本は `ref-skill-design-rubric/references/rubric.json`（L0）で、evaluator 配下の `references/rubric.json` はその上に重ねる L2 の上書きである（29章）。

> **正本の位置づけ**: 本章は設計の説明と雛形の要点（抜粋）であり、実装の正本ではない。実装の正本は実物の `plugins/harness-creator/skills/run-build-skill/SKILL.md` と、生成に使う雛形 `run-build-skill/templates/`（`_base.md`・`run.md`・`ref.md` ほか と `combinators/*.patch`）である。本章の抜粋と実物が食い違ったら実物を正とし、本章を直す。`11-templates.md` にある同名の雛形は cross-platform `run-*` の例示で、`run-build-skill-example` にリネーム済み。

> **配布対象の確認**: 配布対象の一覧は `installers/manifest.json`（`skills` / `scripts` / `agents` ほか）を正本とする。`run-skill-create`、`run-skill-elicit`、`run-build-skill`、`assign-skill-design-evaluator`、`run-elegant-review`、`run-skill-rubric-governance`、`ref-output-routing` などの収録有無はここで確かめ、本章へ重複して書かない。

> **配置（plugin 移行済み）**: 正本は `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`。`.claude/skills/<skill-name>` は `plugins/*/skills/` への symlink による派生である（例: `.claude/skills/run-build-skill` → `../../plugins/harness-creator/skills/run-build-skill`。34章 § plugin 物理レイアウト）。書き換えは plugin 配下に対して行う。`name:` フィールドは kebab-case の Skill 名だけで、plugin 名は配置パスで表す（06章第17条）。`package_mode: skill-only`（legacy / dev-only / migration exception、[36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`package_mode`）の場合に限り `.claude/skills/<skill-name>/SKILL.md` を一次表記として読む。

## リンクパスの記法ルール

このドキュメント内の参照は 2 種類を使い分ける:

- **コードブロック内**（SKILL.md の本文を想定）: 相対リンクを張らず「設計書 NN章」と章番号で書く。plugin は marketplace から配布され、配布先には `doc/` が無いため、`doc/ClaudeCodeスキルの設計書/` への相対リンクは配布後に切れる。
- **地の文**（設計書フォルダ内基準）: `./<file>.md`

## `plugins/harness-creator/skills/run-build-skill/SKILL.md`（抜粋）

実物は frontmatter に `triggers`・`arguments`・`goal_seek`・`responsibility_refs` などを持ち、本文はゴールシーク型（局面カタログ）で書かれている。以下は雛形の要点だけを抜き出したもので、`render-findings-score.py` と `ref-skill-design-rubric/references/rubric.json`（`--kind skill`）で採点して合格する形にしてある。

```markdown
---
name: run-build-skill
description: Capability 7 kind を新規作成・更新するとき、CapabilityManifest と plugin-composition.yaml を整備するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[skill-name] [kind?] [--mode create|update] [--stage draft|release]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Task
  - AskUserQuestion
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: run
owner: team-platform
version: 0.3.0
---

# run-build-skill

## 目的と出力契約

ユーザー要求から Skill を 1 本作る、または更新する。`build_stage` は `draft`（既定）と `release` の2段階だけを使う。

- 出力: `plugins/<plugin-name>/skills/<name>/SKILL.md`（本文 300 行以下）と、必要な `templates/`・`scripts/`・`references/`・`prompts/`
- 出力: `eval-log/skill-build-trace.json` と、検証契約・plan・evidence receipts
- draft の完了条件: 実際に試せる生成物があり、class 別の最小 guard が通り、`stage_gate.status=usable-draft` となること
- release の完了条件（明示したときだけ）: rubric の high severity 0 件、C1-C4 ゲート pass、`validate-build-trace.py` exit 0

## 守ること

- 生成本体は採点しない。machine proof の後に未解決の semantic obligation がある場合だけ、別 context の `assign-skill-design-evaluator` へ最小 slice を渡す（09章）。
- 現物を提示して利用者が選ぶ前に、semantic evaluator・task fork・subagent・multi-worker・revise loop を起動しない（`pre_choice_forbidden`）。
- rubric を編集しない。変更は rubric governance を通す（27章）。
- `scripts/` は Python 3 標準ライブラリだけで書く。`requests` などの外部依存は禁止（22章）。

## 手順（要点）

1. 要件を確かめる: name / kind（`run` `assign` `ref` `wrap` `delegate`）/ 想定する呼び出し元 / 出力契約。必須成果物は `validate-build-plan.py` で brief から決定論で導く。
2. 雛形を展開する: kind → template の選択は `schemas/template-selection.schema.json` に従い、atomic のときは combinator を kind → flag の順に適用する。
3. 本文が 100 行を超えたら `references/` へ分ける（07章）。
4. 命名・構造 Lint を流す。ゲート未達の再実行は draft で1周、release で最大3周。
5. draft: 現物に最小 guard（parse/open・secret・不可逆操作・破損）を掛け、path と試し方を先に提示する。その後に診断の深さ（accept-as-is / light / standard / detailed）を聞く。accept-as-is は evaluator 0 / improver 0 で完了。
6. light / standard / detailed を選んだときだけ `elegant-initial-draft-evaluator` を read-only で起動し、選ばれた finding だけを有界に改善する。release / exhaustive へ自動で昇格しない。
7. release（`--stage release` を明示したときだけ）: machine proof の後に semantic obligation が残った場合だけ `Skill(assign-skill-design-evaluator)` を1 context 起動し、score >= 80 かつ high=0 で完了。

## つまずきやすい点

- `.claude/skills/<name>` は symlink なので、そこを書き換えても正本は変わらない。書き換え先は plugin 配下。
- description に動作の詳細（採点する、JSON で返す など）を書くと FM-004 で減点される。
```

補助ファイル（主なもの。全量は実物を `ls` で確かめる）:

```
run-build-skill/
├── SKILL.md
├── workflow-manifest.json
├── templates/
│   ├── _base.md        # 全 kind 共通の骨格（Atomic Composer）
│   ├── run.md / ref.md / wrap.md / delegate.md
│   ├── assign-generator.md / assign-evaluator.md
│   ├── agent-team.md / orchestrator.md / hook-integrated.md
│   └── combinators/    # with-run.patch / with-subagent.patch / with-hooks.patch ほか
├── examples/
│   ├── minimal-ref.md
│   ├── workflow-with-evaluator.md
│   └── task-graph-engine-skill.md
├── prompts/            # R1-scaffold.md ほか（責務別プロンプト）
├── schemas/
├── scripts/
│   ├── render-frontmatter.py   # Python 3 標準ライブラリのみ
│   └── validate-naming.py
└── references/
    └── design-docs-index.md    # 設計書への索引（Progressive Disclosure）
```

## `plugins/harness-creator/skills/assign-skill-design-evaluator/SKILL.md`（抜粋）

```markdown
---
name: assign-skill-design-evaluator
description: 生成済みSKILL.mdを評価したいとき、rubric準拠を確認したいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: run-build-skill
kind: assign
owner: team-platform
version: 0.1.0
rubric_refs:
  - ref-skill-design-rubric      # L0: 共通
  - references/rubric.json       # L2: この evaluator 固有の上書き
reference_refs:
  - references/evaluator-contract.md
script_refs:
  - scripts/render-findings-score.py
---

# assign-skill-design-evaluator

## 目的と出力契約

生成済みの Skill を rubric で採点し、JSON を 1 つ返す。fork で動き、生成役と文脈を共有しない。

- 入力: `target` = SKILL.md のパス、またはスキルのディレクトリ
- 出力: `{rubric_hash, score, threshold, passed, findings[], required_fixes[], pending_human[]}`
- 減点: high -20 / medium -10 / low -3。初期値 100 から引いた値を score とする。

## 守ること

- artifact と rubric を編集しない（Write / Edit を持たない）。修正は `pair` の run-build-skill が担う。
- 実行中に `rubric_refs` を書き換えない。
- 生成役の会話履歴を参照しない（fork なので見えないことを前提にする）。

## つまずきやすい点

- `TODO(human)` が残る rule は採点せず `pending_human` に分ける。score には入れない。
```

`script_refs` の `render-findings-score.py` を実行するため、`allowed-tools` に `Bash(python3 *)` が要る。Write / Edit は持たせない。

補助ファイル:

```
assign-skill-design-evaluator/
├── SKILL.md
├── references/
│   ├── rubric.json              # L2 上書き（正本は ref-skill-design-rubric）
│   ├── evaluator-contract.md
│   └── resource-map.yaml
├── prompts/R1-evaluate.md
├── schemas/evaluator-output.schema.json
└── scripts/
    └── render-findings-score.py   # findings → score 計算（標準ライブラリのみ）
```

複数プロジェクトで使う場合は、Skill 本体を増やさず `rubric_refs` に project / domain（ドメイン）の rubric を追加する（29章）。次は書き方の例で、`ref-clean-architecture-rules` や `project-x` は説明用の架空の名前である。

```yaml
rubric_refs:
  - ref-skill-design-rubric
  - ref-clean-architecture-rules
  - references/project-x-rubric.json
reference_refs:
  - references/projects/project-x/api-contract.yaml
  - references/projects/project-x/domain-dictionary.yaml
script_refs:
  - scripts/validate-rubric-composition.py
  - scripts/lint-dependency-direction.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
```

## 昇格版: `plugins/harness-creator/skills/ref-skill-design-rubric/SKILL.md`（昇格済み）

複数の evaluator が同じ rubric を共有するため、rubric は `ref-*` Skill として昇格済みである。`assign-skill-design-evaluator` は `rubric_refs` の L0 にこれを置き、自分の `references/rubric.json` を L2 として deep-merge する。

実物の SKILL.md（`kind: ref`、`owner: team-platform`）は次を持つ:

- `## Purpose & Output Contract`: 評価基準の正本であること、出力は無いこと（reference）
- `## Key Rules`: 唯一の正本、threshold 80、rubric_version は semver、改正は governance runbook 経由
- `## 評価軸サマリ`: 41 rule を FM / BD / NM / PD / RG / AG / HK / CM / PC / PR / WF / KL に分ける。適用する kind は rule ごとの `applies_to_kinds` で決まり、RG と KL は全 kind 共通（`*`）、AG〜WF はそれぞれ1つの kind だけに掛かる
- `## Gotchas`: rubric.json を直接編集しない、trigger は 2 個ちょうどで書く

補助ファイル:

```
ref-skill-design-rubric/
├── SKILL.md
├── prompts/R1-search-summarize.md
└── references/
    ├── rubric.json          # 機械可読の正本（check 式・severity・閾値）
    ├── rubric-rationale.md  # 人が読むための理由
    ├── CHANGELOG.md
    └── resource-map.yaml
```

### rubric の hard limits（本章が由来）

rule の本数・check 式・severity の正本は `ref-skill-design-rubric/references/rubric.json` である（rubric 1.6.0 時点で 41 rule、threshold 80、severity_weights は high -20 / medium -10 / low -3）。本章が由来になっている上限値は次のとおりで、値は rubric.json の最上位キーに置かれている。

| キー | 値 | 対応する rule |
|---|---|---|
| `max_skill_md_lines` | 300 | BD-003（high）: 本文 300 行以下 |
| `trigger_count_min` / `trigger_count_max` | 2 / 3 | FM-003（medium）。ただし `validate-frontmatter.py` と `lint-skill-description.py` は 2 個ちょうどを強制する |
| `description_no_action_detail` | true | FM-004（medium）: description に動作の詳細を書かない |

rubric の例を本章に別形式（YAML など）で写すと、実物とずれたまま誤誘導になる。値や rule を変えるときは本章ではなく rubric.json を `run-skill-rubric-governance` の手順（27章）で改正し、本章の表はその結果に合わせる。

## runの複合kind: agent-team / orchestrator / hook-integrated

`run` kind は単体workflow以外に、複数の構成要素を内包する **複合kind** を持つ。
これらは独立した kind 値ではなく `kind: run` のまま、適用する combinator の組合せで識別する。

Plugin package として量産する場合、`run-build-skill` は `.claude/skills/<skill>/` ではなく `plugins/<plugin-name>/skills/<skill>/` を正本出力先にする。必要な Agent / Hook / script / settings / config の同梱判定と package completeness check は [36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) を正本とする。

| 複合kind | 旧テンプレ | atomic combinator 組合せ | 用途 |
|---|---|---|---|
| `agent-team` | `templates/agent-team.md` | `with-run.patch` + `with-subagent.patch` | 複数 SubAgent を並列起動するチーム編成workflow（例: `run-elegant-review`） |
| `orchestrator` | `templates/orchestrator.md` | `with-run.patch` + `with-subagent.patch`×N | フェーズゲート付きで複数 Skill を順次連鎖する E2E入口（例: `run-skill-create`） |
| `hook-integrated` | `templates/hook-integrated.md` | `with-run.patch` + `with-hooks.patch` | PreToolUse / PostToolUse hook と連動する workflow |

**判定基準**:
- workflow が **単一のロジック** で完結するなら通常の `run`（`with-run.patch` のみ）
- workflow が **SubAgent 委譲を含む** なら `agent-team`
- workflow が **3段以上のフェーズゲート** を持ち、各フェーズで別 Skill を呼ぶなら `orchestrator`
- workflow が **hook 配線必須** なら `hook-integrated`

これらの複合kindは frontmatter 上は `kind: run` のままだが、本文構造（SubAgent invocation セクション、フェーズゲート表、hook 配線記述）が異なる。Atomic Composer モード（combinators/）では適用する patch の組合せで自動的に骨格が生成される。

## scripts/ クロスプラットフォーム制約

`run-build-skill` および `assign-skill-design-evaluator` の `scripts/` は次に従う:

- **Python 3 標準ライブラリのみ**（pip install 禁止）
- Windows でも Python 実装に閉じ、PowerShell 固有の構文を本文に直書きしない（`ref-cross-platform-runtime`）。現状 harness-creator は `.ps1` ラッパーを同梱していない。
- Python が無い Windows でのフォールバック（PowerShell 経路、または利用者への確認）と OS 判定は [22-cross-platform-runtime.md](./22-cross-platform-runtime.md) を参照

これにより Mac/Windows 両環境でメタSkillが動作する。
