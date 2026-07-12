# 18. 完成ディレクトリ例

## このファイルの読み方（変数辞書 + 骨格テンプレ + 展開例の三段構成）

本章の完成例は **横展開可能** にするため、具体値を `{{variable}}` 形式で抽象化し、共通変数を辞書として先頭に集約する。新パターンを追加するときは、辞書を 1 つ追加するだけで全完成例に伝搬する設計とする。

### 共通変数辞書

| 変数 | 意味 | 列挙値 / 例 |
|---|---|---|
| `{{skill_name}}` | kebab-case のスキル名 | `ref-api-conventions`, `run-release-check` |
| `{{skill_dir}}` | Skill 配置ディレクトリ | `.claude/skills/{{skill_name}}` |
| `{{title}}` | SKILL.md 本文の H1 | `API conventions`, `Release check` |
| `{{target_domain}}` | 対象ドメイン | `api`, `release`, `pull-request` |
| `{{artifact_type}}` | 作成・検証する成果物種別 | `endpoint`, `release`, `pull request` |
| `{{prefix}}` | kind に対応する prefix | `ref`, `run`, `assign`, `wrap`, `delegate` |
| `{{kind}}` | スキル種別 | `ref` / `run` / `wrap` / `assign` / `delegate`（`atomic` は旧仕様、使用禁止） |
| `{{description}}` | description 文 | 「{何の Skill か}. Use when {発動条件}.」形式 |
| `{{owner}}` | 所有チーム | `team-api`, `team-platform`, `team-skills` |
| `{{hierarchy_level}}` | 階層 | `L0`（単独参照）/ `L1`（連携）/ `L2`（オーケストレーション） |
| `{{output_contract}}` | 出力契約 | スキルが返すべき項目の箇条書き |
| `{{output_item_1}}` / `{{output_item_2}}` / `{{output_item_3}}` | 出力契約の各項目 | `blocking issues`, `validation command result` |
| `{{core_rules}}` | コアルール | スキルが守るべき本文ルールの箇条書き |
| `{{core_rule_1}}` / `{{core_rule_2}}` / `{{core_rule_3}}` | コアルールの各項目 | `Use RESTful resource names.` |
| `{{gotchas}}` | 落とし穴 | 既知の罠（誤発動・誤実装パターン） |
| `{{gotcha_1}}` | 落とし穴の各項目 | `Do not invent a second error format.` |
| `{{trigger_phrase_1}}` / `{{trigger_phrase_2}}` | 発動フレーズ | description に埋める「Use when X」「or Y」 |
| `{{base_cli}}` | ラップ対象 CLI | `gh`, `git`, `codex` |
| `{{base_command}}` | base CLI の subcommand | `pr create`, `commit`, `exec` |
| `{{verify_command}}` | 作成後・実行後の確認 command | `pr view`, `status` |
| `{{script_name}}` | 内部 script のファイル名 | `validate-release.sh`, `run-codex.sh` |
| `{{template_file}}` | 埋め込み用 template file | `templates/pr-body.md`, `handoff-template.md` |
| `{{handoff_template}}` | 委譲 handoff の template file | `handoff-template.md` |
| `{{runtime_name}}` | 外部実行環境名 | `codex`, `another-agent-runtime` |
| `{{arg_name}}` / `{{arg1}}` / `{{arg2}}` | 引数名 | `version`, `base`, `title`, `spec` |
| `{{rubric_ref_skill}}` | 参照する rubric Skill 名（単数） | `ref-skill-design-rubric` |
| `{{rubric_refs}}` | 参照する rubric Skill 名（複数可） | `ref-skill-design-rubric` |
| `{{pair_skill}}` | 対の generator / evaluator | `assign-skill-review-generator` |
| `{{paired_skill_name}}` | settings で同時に許可する関連 Skill | `run-release-check` |
| `{{allowed_tool_globs}}` | Bash 等の allowlist パターン | `Bash(gh pr *)`, `Bash(git status *)` |
| `{{settings_skill_allowlist}}` | settings で許可する Skill 呼び出し | `Skill({{skill_name}} *)` |

> 骨格テンプレートでは `{{var}}` を正本とする。具体名は sample expansion として扱い、固定値を正本へ昇格させない。新カテゴリのスキルを追加するときは、まず辞書に行を追加し、骨格テンプレを引用してから展開する。

### kind × 拡張フラグの組合せ一覧（横展開対応表）

| kind | role_suffix | `--with-evaluator` | `--with-hooks` | `--with-subagent` | 完成例セクション |
|---|---|---:|---:|---:|---|
| `ref` | - | No | optional | No | `ref-*` 完成例 |
| `run` | - | optional | optional | optional | `run-*` 完成例 |
| `assign` | `evaluator` | (pair=generator必須) | optional | optional | `assign-*` evaluator 完成例 |
| `assign` | `generator` | (pair=evaluator必須) | optional | optional | （変数辞書 + assign evaluator 骨格を generator 用に置換） |
| `wrap` | - | No | optional | No | `wrap-*` 完成例 |
| `delegate` | - | No | optional | optional | `delegate-*` 完成例 |

> 実証済みパスはこの表に対応する `eval-log/skill-build-trace.json` の `variant_support` フィールドで集計される（`scripts/build-tested-paths-ledger.py` 参照）。

## `ref-*` 骨格テンプレート

```text
{{skill_dir}}/
├── SKILL.md
└── examples.md
```

`SKILL.md`:

```markdown
---
name: {{skill_name}}            # 例: ref-api-conventions
description: {{description}}    # 例: API conventions. Use when designing or reviewing API endpoints.
kind: ref                       # 列挙値: ref|run|wrap|assign|delegate（atomic は旧仕様。使用禁止）
owner: {{owner}}                # 例: team-api
hierarchy_level: L0             # L0=単独参照 / L1=連携 / L2=オーケストレーション
---

# {{title}}

Use these rules when {{target_domain}} naming, error shape, or validation matters.

## Core rules

- {{core_rule_1}}
- {{core_rule_2}}
- {{core_rule_3}}

## Gotchas（落とし穴）

- {{gotcha_1}}

## Additional resources

- Examples: [examples.md](examples.md)
```

Sample expansion: `{{skill_name}}=ref-api-conventions`, `{{title}}=API conventions`, `{{target_domain}}=API endpoint`。

## `run-*` 骨格テンプレート

```text
{{skill_dir}}/
├── SKILL.md
└── scripts/
    └── {{script_name}}
```

`SKILL.md`:

````markdown
---
name: {{skill_name}}              # 例: run-release-check
description: {{description}}      # 例: Release check. Use when the user asks to verify a release, prepare a release, or run a pre-release gate.
kind: run
hierarchy_level: L1               # CLI/script 連携を伴うので L1
disable-model-invocation: true    # 危険操作を含むため Claude の自動 invocation を禁止
argument-hint: "[{{arg_name}}]"   # 例: "[version]"
arguments: [{{arg_name}}]         # 例: [version]
allowed-tools:
  - Bash(git status *)
  - Bash({{base_cli}} *)          # 例: Bash(gh *)
  - Bash(${CLAUDE_SKILL_DIR}/scripts/{{script_name}} *)  # 例: scripts/validate-release.sh
---

# {{title}}

Output contract（契約）:

- {{output_item_1}}
- {{output_item_2}}
- {{output_item_3}}
- next action

Run:

```bash
${CLAUDE_SKILL_DIR}/scripts/{{script_name}} "${{arg_name}}"
```
````

Sample expansion: `{{skill_name}}=run-release-check`, `{{script_name}}=validate-release.sh`, `{{arg_name}}=version`。

## `assign-*` evaluator 骨格テンプレート

```text
{{skill_dir}}/
├── SKILL.md
└── rubric.md
```

`SKILL.md`:

```markdown
---
name: {{skill_name}}              # 例: assign-skill-review-evaluator （prefix=assign, role_suffix=evaluator）
description: {{description}}      # 例: Skill review evaluator. Use internally from {{pair_skill}}, or when the user asks to score X against the rubric.
kind: assign                      # 列挙値: ref|run|wrap|assign|delegate
role_suffix: evaluator            # assign は必ず evaluator / generator のいずれかを取る
hierarchy_level: L1
user-invocable: false             # evaluator は内部呼び出し専用
context: fork                     # 同 context 評価 (sycophancy) を防ぐため必須
agent: general-purpose
allowed-tools:
  - Read
  - Grep
pair: {{pair_skill}}              # 例: assign-skill-review-generator
rubric_refs:
  - {{rubric_ref_skill}}          # 例: ref-skill-design-rubric
---

# {{title}}

Read the submitted artifact and [rubric.md](rubric.md). Do not edit files.

Return JSON:

{
  "score": 0,
  "passed": false,
  "findings": [],
  "required_fixes": []
}
```

Sample expansion: `{{skill_name}}=assign-skill-review-evaluator`, `{{pair_skill}}=assign-skill-review-generator`, `{{rubric_ref_skill}}=ref-skill-design-rubric`。

## `wrap-*` 骨格テンプレート

既存 CLI / Skill / コマンドを「定型 preset」として再利用するための薄いラッパー。`{{base_cli}} {{base_command}}` を対象にし、具体 CLI は sample expansion に閉じ込める。

```text
{{skill_dir}}/
├── SKILL.md
├── reference.md
└── templates/
    └── {{template_file}}
```

`SKILL.md`:

````markdown
---
name: {{skill_name}}              # 例: wrap-github-pr-create
description: {{description}}      # 例: GitHub PR を社内テンプレートで作成する。Use when the user asks to open or draft a pull request via gh CLI.
kind: wrap
hierarchy_level: L1
base: {{base_cli}}                # 例: gh （ラップ対象の CLI）
pair: {{pair_skill}}              # 例: ref-pr-conventions （規約参照 ref）
argument-hint: "[{{arg1}}] [{{arg2}}]"   # 例: "[base-branch] [title]"
arguments: [{{arg1}}, {{arg2}}]   # 例: [base, title]
allowed-tools:
  - Bash({{base_cli}} {{base_command}} *)   # 例: Bash(gh pr create *)
  - Bash({{base_cli}} {{verify_command}} *) # 例: Bash(gh pr view *)
  - Bash(git log *)
  - Bash(git diff *)
  - Read
---

# {{skill_name}}

Output contract（契約）:

- 作成された {{artifact_type}} の識別子または URL
- 適用した {{template_file}} の種別
- 自動付与した metadata
- 次に促す確認手順

## 手順

1. `git log ${{arg1}}..HEAD` と `git diff ${{arg1}}...HEAD` を読む。
2. [{{template_file}}]({{template_file}}) を埋める。
3. 次を実行する。

```bash
{{base_cli}} {{base_command}} \
  --base "${{arg1}}" \
  --title "${{arg2}}" \
  --body-file <(envsubst < {{template_file}})
```

4. 作成後に `{{base_cli}} {{verify_command}}` で結果を確認し、識別子または URL を返す。

## 禁止事項

- 対話専用 mode での作成。
- 本文テンプレートを無視した自由記述。

## Gotchas（落とし穴）

- `{{base_cli}}` 未認証時は認証状態を先に確認する。
- `{{arg1}}` が remote または upstream に存在しない場合は中断する。

## Additional resources

- 詳細仕様: [reference.md](reference.md)
````

Sample expansion: `{{skill_name}}=wrap-github-pr-create`, `{{base_cli}}=gh`, `{{base_command}}=pr create`, `{{verify_command}}=pr view`, `{{template_file}}=templates/pr-body.md`。

## `delegate-*` 骨格テンプレート

外部実行環境 (別 CLI / 別 LLM / 別 agent runtime) に作業を委譲し、結果だけを取り込むパターン。`{{runtime_name}}` 固有の名前は sample expansion に閉じ込める。

```text
{{skill_dir}}/
├── SKILL.md
├── {{handoff_template}}
└── scripts/
    └── {{script_name}}
```

`SKILL.md`:

````markdown
---
name: {{skill_name}}              # 例: delegate-codex-implementation
description: {{description}}      # 例: Runtime delegation. Use when the user asks to offload an implementation task to {{base_cli}}, request a second-model implementation, or import a {{base_cli}}-generated artifact.
kind: delegate
hierarchy_level: L2               # 外部実行委譲は L2 扱い（複数 step を束ねるオーケストレーション相当）
base: {{base_cli}}                # 例: codex （委譲先の外部実行環境）
disable-model-invocation: true
user-invocable: true
argument-hint: "[{{arg_name}}]"   # 例: "[task-spec-path]"
arguments: [{{arg_name}}]         # 例: [spec]
allowed-tools:
  - Read
  - Bash(${CLAUDE_SKILL_DIR}/scripts/{{script_name}} *)   # 例: scripts/run-codex.sh
  - Bash(git diff *)
  - Bash(git status *)
---

# {{skill_name}}

Output contract（契約）:

- 委譲した task の要約
- {{runtime_name}} 実行 log の要点
- 生成 / 変更 file の一覧
- 受け入れ判定 (accept / revise / reject)
- 次の人間レビュー観点

## 手順

1. `${{arg_name}}` を読み、[{{handoff_template}}]({{handoff_template}}) に沿って handoff を生成する。
2. 次を実行する。

```bash
${CLAUDE_SKILL_DIR}/scripts/{{script_name}} "${{arg_name}}"
```

3. `git status` / `git diff` で生成物を確認する。
4. output contract（契約） を満たす要約を返す。

## 禁止事項

- 委譲先の出力をそのまま commit する。必ず diff を人間に提示する。
- secret を含む env を委譲先に渡す。

## Gotchas（落とし穴）

- {{runtime_name}} 側 context は forked。当 session の memory は引き継がれない前提で spec を自己完結させる。
- 長時間 job は background 実行し、終了通知を待つ。

## Additional resources

- handoff フォーマット: [{{handoff_template}}]({{handoff_template}})
- 実行 script: `scripts/{{script_name}}`
````

Sample expansion: `{{skill_name}}=delegate-codex-implementation`, `{{runtime_name}}=Codex`, `{{script_name}}=run-codex.sh`, `{{arg_name}}=spec`。

## settings 連携例

```json
{
  "permissions": {
    "deny": [
      "Bash(rm *)",
      "Bash(curl *)"
    ],
    "allow": [
      "{{settings_skill_allowlist}}",
      "Skill({{paired_skill_name}} *)"
    ]
  },
  "skillOverrides": {
    "legacy-context": "name-only"
  }
}
```
