# 24. メタSkillテンプレート

メタSkill の SKILL.md 雛形と補助ファイル構成。MVP は `run-build-skill` / `assign-skill-design-evaluator` の 2 Skill とし、rubric（評価基準）は evaluator 配下の `references/rubric.json` に置く。`ref-skill-design-rubric` は共有が必要になった段階で独立 Skill に昇格する。

> **正本宣言**: `run-build-skill` の正本仕様はこのファイル (24) である。`11-templates.md` にある同名の雛形は cross-platform `run-*` の例示として位置付け直し、`run-build-skill-example` にリネーム済み。本物のメタSkillとして利用する場合は本ファイルの定義を採用すること。

> **creator-kit 対応**: 現行の配布対象は `creator-kit/manifest.json` を正本とする。テンプレ本文をここへ重複展開せず、`run-skill-create`、`run-skill-elicit`、`run-build-skill`、`assign-skill-design-evaluator`、`run-elegant-review`、`run-skill-rubric-governance`、`ref-output-routing` などの収録有無は manifest で確認する。

> **plugin 移行後の配置（2026-05-18 暫定）**: **現在（Phase 0 未完了）**: `.claude/skills/<skill-name>/SKILL.md`（`creator-kit/skills/` 正本）。**Phase 0 完了後**: `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` 形式へ移行。`.claude/skills/<skill-name>/` は `plugins/*/skills/` への symlink 経由の派生となる（34章 § plugin 物理レイアウト）。本章の `.claude/skills/...` 記法は派生側の参照表現として読み、正本書き換えは plugin 配下に対して行う。`name:` フィールドは kebab-case の Skill 名のみで、plugin 名は配置パスで表現する（06章第17条）。
>
> **正本パスのレイヤー優先順位（package_mode 別）**: `package_mode != skill-only` の plugin package mode では `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` が一次（正本）、`.claude/skills/<skill-name>/SKILL.md` は symlink 経由の派生表現にすぎない（[36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`package_mode`）。`package_mode: skill-only`（legacy / dev-only / migration exception、36章）の場合に限り `.claude/skills/<skill-name>/SKILL.md` を一次表記として読む。本章テンプレ本文の `.claude/skills/...` 表記は、互換のための派生側参照として維持しているのみで、新規生成・更新の書き換え先は plugin root を優先する。

## リンクパスの記法ルール

このドキュメント内のリンクは 2 種類を意図的に使い分ける:

- **コードブロック内** (実Skill配置位置 `.claude/skills/<name>/SKILL.md` から相対参照することを想定): `../../../doc/スキルの設計書/<file>.md`
- **地の文** (設計書フォルダ内基準): `./<file>.md`

両者は同じファイルを指すが、想定する参照起点が異なるため記法を切り替えている。

## `.claude/skills/run-build-skill/SKILL.md`

> 表記注: 以下のパスは `package_mode: skill-only`（互換・移行例外）時の一次表記。`package_mode != skill-only` の plugin package mode では正本は `plugins/<plugin-name>/skills/run-build-skill/SKILL.md`、`.claude/skills/run-build-skill/SKILL.md` はその派生 symlink（36章）。

```markdown
---
name: run-build-skill
description: 新規Skillを作成するとき、既存Skillを更新するときに使う。
disable-model-invocation: false
argument-hint: "[skill-name] [kind?]"
arguments: [skill_name, kind]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Bash(powershell *)
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: workflow
owner: team-skills
---

# Build a Skill

Output contract（契約）:

- 新規 `.claude/skills/<name>/SKILL.md`
- 必要なら `templates/`, `examples/`, `scripts/`, `references/`
- evaluator JSON (score / passed / findings)

Steps:

1. 要件確認: name / kind (`run-` / `assign-` / `ref-` / `wrap-` / `delegate-`) / 想定 invoker / 出力契約。
2. 分類判定: 設計書 06 と 09 を Read し kind と evaluator 必要性を決定。
3. 雛形展開: `templates/<kind>.md` を Read → 置換 → Write。
4. Progressive Disclosure（段階的開示）: 本文 100 行超なら `examples/` / `references/` に分割 (07 参照)。
5. scripts/ 同梱が必要なら **Python 3 標準ライブラリのみ** で実装し、Windows 用に PowerShell ラッパーを併設 (詳細: [22-cross-platform-runtime.md](../../../doc/スキルの設計書/22-cross-platform-runtime.md))。
6. self-check (13 のチェックリスト) を本文末尾に挿入。
7. `Skill(assign-skill-design-evaluator)` を context: fork で起動し artifact path を渡す。
8. score < threshold なら findings を反映して 3〜6 を retry (最大 3 回)。
9. pass したら installed path をユーザーに返す。

## Gotchas（落とし穴）

- generator の会話文脈で self-check しない (09 sycophancy)。
- rubric を編集してはならない (Goodhart（評価基準を都合よく歪める罠）)。
- scripts/ で `requests` 等の外部依存禁止 (22)。
```

補助ファイル:

```
run-build-skill/
├── SKILL.md
├── templates/
│   ├── run.md         # run-* 雛形 (11 から複製)
│   ├── ref.md         # ref-* 雛形
│   ├── assign-generator.md
│   ├── assign-evaluator.md
│   ├── wrap.md
│   └── delegate.md
├── examples/
│   ├── minimal-ref.md
│   └── workflow-with-evaluator.md
├── scripts/
│   ├── render-frontmatter.py   # Python3 stdlib only
│   ├── validate-naming.py
│   └── render-frontmatter.ps1  # PowerShell wrapper (22 準拠)
└── references/
    └── design-docs-index.md    # 01-21 への索引 (Progressive Disclosure（段階的開示）)
```

## `.claude/skills/assign-skill-design-evaluator/SKILL.md`

> 表記注: 同上。`package_mode != skill-only` では正本は `plugins/<plugin-name>/skills/assign-skill-design-evaluator/SKILL.md`（36章）。

```markdown
---
name: assign-skill-design-evaluator
description: 生成済みSKILL.mdを評価したいとき、rubric準拠を確認したいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Grep
pair: run-build-skill
kind: evaluator
owner: team-skills
rubric_refs:
  - references/rubric.json
reference_refs:
  - references/evaluator-contract（契約）.md
script_refs:
  - scripts/render-findings-score.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
---

# Evaluator（評価役） contract（契約）

Inputs:

- artifact_path: 生成された SKILL.md (および補助ファイル) のディレクトリ
- rubric: `rubric_refs` で指定された read-only rubric を取得。MVP では `references/rubric.json`、昇格版では `ref-skill-design-rubric` を含めてよい。

Do NOT:

- artifact を編集する
- rubric を編集する
- `rubric_refs` を実行中に書き換える
- generator の会話履歴を参照する (forked のため不可能であることを保証)

Return JSON only:

{
  "score": 0,
  "passed": false,
  "threshold": 80,
  "findings": [
    { "severity": "high|medium|low", "area": "frontmatter|body|naming|disclosure|gotchas", "message": "..." }
  ],
  "required_fixes": ["..."]
}

Severity weights:

- high: -20, medium: -10, low: -3
- 初期値 100、減点後の値を score とする
```

補助ファイル:

```
assign-skill-design-evaluator/
├── SKILL.md
├── references/
│   ├── rubric.json
│   └── evaluator-contract（契約）.md
└── scripts/
    ├── render-findings-score.py        # findings → score 計算 (stdlib)
    └── render-findings-score.ps1
```

複数プロジェクトで使う場合は、Skill 本体を増やさず `rubric_refs` に project / domain（ドメイン） rubric（評価基準） を追加する。

```yaml
rubric_refs:
  - ref-skill-design-rubric
  - ref-clean-architecture-rules
  - references/project-x-rubric.json
reference_refs:
  - references/projects/project-x/api-contract（契約）.yaml
  - references/projects/project-x/domain-dictionary.yaml
script_refs:
  - scripts/validate-rubric-composition.py
  - scripts/lint-dependency-direction.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
```

## 昇格版: `.claude/skills/ref-skill-design-rubric/SKILL.md`

> 表記注: 同上。`package_mode != skill-only` では正本は `plugins/<plugin-name>/skills/ref-skill-design-rubric/SKILL.md`（36章）。

複数 evaluator が同じ rubric を共有する場合だけ、次の `ref-*` Skill に昇格する。MVP では作らない。

```markdown
---
name: ref-skill-design-rubric
description: Skill設計時に評価基準を確認したいとき、SKILL.md採点の正本rubricを参照したいときに使う。
disable-model-invocation: true
user-invocable: false
kind: reference
owner: team-skills
---

# Skill design rubric

## Frontmatter（先頭メタ情報） (must)

- `name`: kebab-case, kind プレフィックス必須 (06)
- `description`: trigger + invocation 条件を含む (03)
- `allowed-tools`: 最小権限 (04)
- evaluator なら `context: fork` + `user-invocable: false` (09)

## Body (must)

- Output contract（契約） が冒頭にある (11)
- Steps は番号付き、Why（理由） を含む (08)
- Gotchas（落とし穴） セクションが存在する (08)
- 本文 100 行以下、超過分は `examples/` `references/` (07)

## Naming (must)

- `run-*` / `assign-*-generator` / `assign-*-evaluator` / `ref-*` / `wrap-*` / `delegate-*` (06)

## Disclosure (should)

- Additional resources 経由で詳細を分離

## Gotchas（落とし穴） (should)

- 既知 failure mode を 1 件以上記述

## 4条件PASS (01)

- 矛盾なし / 漏れなし / 整合性あり / 依存関係整合
- 本文品質の補助観点として DRY / Less is More / Why（理由）-driven / Self-contained も確認する
```

補助ファイル:

```
ref-skill-design-rubric/
├── SKILL.md
└── rubric.json          # 機械可読版
```

`rubric.json` 例:

```yaml
version: 1
threshold: 80

# 追加要件 Phase3-H 由来の hard limits
max_skill_md_lines: 300            # SKILL.md 本文の最大行数 (HumanLayer 由来、08 参照)
trigger_count_min: 2               # description の発動条件 最小数
trigger_count_max: 3               # description の発動条件 最大数
description_no_action_detail: true # description に動作詳細（採点する/JSON で返す/段数 等）を書かない

rules:
  - id: FM-001
    area: frontmatter
    severity: high
    check: "name field exists and matches ^(run|assign|ref|wrap|delegate)-[a-z0-9-]+$"
  - id: FM-002
    area: frontmatter
    severity: high
    check: "description contains trigger phrase 'Use when'"
  - id: FM-003
    area: frontmatter
    severity: high
    check: "description trigger condition count is between trigger_count_min and trigger_count_max (2-3)"
  - id: FM-004
    area: frontmatter
    severity: high
    check: "description does NOT contain action-detail tokens (採点する/JSON で返す/段数/段階で実行 等) — description_no_action_detail"
  - id: FM-005
    area: frontmatter
    severity: medium
    check: "description trigger is verb / procedure based, not noun enumeration"
  - id: BD-001
    area: body
    severity: medium
    check: "body contains 'Output contract（契約）'"
  - id: BD-002
    area: body
    severity: medium
    check: "body contains 'Gotchas（落とし穴）'"
  - id: BD-003
    area: body
    severity: high
    check: "SKILL.md body line count <= max_skill_md_lines (300)"
  - id: RG-001
    area: rubric
    severity: high
    check: "evaluator output includes rubric_hash so rubric changes are auditable"
  - id: PD-001
    area: disclosure
    severity: low
    check: "body line count <= 100 OR references/ directory exists"
  - id: NM-001
    area: naming
    severity: high
    check: "directory name == frontmatter.name"
```

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

- **Python 3 標準ライブラリのみ** (pip install 禁止)
- 同等機能を持つ PowerShell 5.1+ ラッパー (`*.ps1`) を併設 (Windows 10 以降に標準同梱)
- 詳細・サンプル・OS 判定ロジックは [22-cross-platform-runtime.md](./22-cross-platform-runtime.md) を参照

これにより Mac/Windows 両環境でメタSkillが動作する。
