# 30. パラダイム類推マップ

## 目的

Claude Code Skill は新しい概念のように見えるが、その構成要素の大半は既存ソフトウェア工学のパラダイム（ESLint plugin / pytest fixture / LSP / Terraform module / Unix philosophy / Hexagonal Architecture）に対応物を持つ。本章は、既知の道具立てから Skill の構成を素早く理解するための類推地図を提供する。

## 読者像

- Claude Code Skill を初めて触る他言語/他IaCバックグラウンドのエンジニア
- ESLint plugin / pytest plugin / LSP server / Terraform module / pre-commit hook のいずれかを設計した経験がある人
- Skill 概念を「何のアナロジーで理解すればよいか」探している人

## 関連章

- `00-overview.md` 全体像と中心命題
- `05-layering-skill-subagent-hook-mcp-cli.md` Skill / Subagent / Hook / MCP / CLI の責務分離
- `09-evaluation-orchestration.md` Generator（生成役）/Evaluator（評価役） 分離と rubric
- `23-meta-skill-architecture.md` メタSkill と 3 点セット構成

類推は理解の足場であって、最終的には公式仕様 (16/17) と本設計書群が正本である。類推が成立しない領域は本章末尾「概念のズレ」に列挙する。

## 主要パラダイム対応表

| Skill 概念 | ESLint | pytest | LSP | Terraform | Unix philosophy | Hexagonal Arch |
|---|---|---|---|---|---|---|
| Skill 本体 | plugin / rule pack | plugin / conftest | LSP server | module | small focused command | use case / application service |
| `description` (frontmatter) | rule docs / meta | docstring + marker | server capabilities | module README + variables | man page summary | port interface |
| 発動条件 | match pattern / file glob | autouse / marker selector | activationEvents | resource type match | argv / stdin shape | inbound port adapter |
| rubric / references | `.eslintrc` extends | `pytest.ini` / `pyproject` | settings.json schema | `variables.tf` + provider | config file | domain policy |
| evaluator | ESLint runner + reporter | test runner / assertion | diagnostics provider | `plan` (no apply) | exit code 0/!=0 | acceptance test |
| generator (`run-build-skill`) | yeoman / `--init` | cookiecutter / `pytest-stub` | yo code / vsce generator | `terraform init` + scaffold | scaffold script | factory |
| Hook (PreToolUse 等) | pre-commit hook | pytest hookspec (`pytest_*`) | onWillSave / onSave | Sentinel / OPA gate | inetd / cron trigger | adapter middleware |
| Progressive Disclosure（段階的開示） | lazy rule load | fixture lazy import | server-side on-demand load | module `count = 0` | manpage SEE ALSO | lazy port resolution |
| Subagent (context fork) | child process worker | xdist worker / sub-session | language server child | child workspace | subshell / fork | bounded context |
| `pair:` (generator/evaluator) | `extends` + `plugins` | pair of fixture + test | server + client capability | module + assertion test | producer / consumer pipe | command + query 分離 |
| `rubric_refs:` | `extends` chain | plugin discovery via entry_points | settings inheritance | module source / registry | env var / config search path | dependency injection |
| MCP server | linter as service | pytest as daemon | LSP itself (まさに対応物) | provider plugin | daemon listening on socket | outbound port adapter |
| メタSkill | `eslint --init` の plugin 版 | `pytest-cookiecutter` | yo code generator | Terraform Registry publishing | autoconf / make スクリプト | factory of factories |

## 概念別マッピング詳細

### Skill 自体 ≒ ESLint plugin / pytest plugin / LSP server

Skill は単独の関数ではなく「発動条件 + 適用範囲 + 副作用境界 + 出力契約」を持つ部品である点で、これらの plugin 系と同型である。ESLint plugin が「特定の AST ノードに反応してメッセージを出す」のと同様、Skill は「特定の文脈で発動し、特定の手順を提示する」契約物である。差分は、入力が AST/ソースではなく自然言語コンテキストである点。

### rubric ≒ `.eslintrc` rules / `pytest.ini` / lint config

rubric（評価基準）は「何を合格とみなすか」の規約ファイルであり、`.eslintrc` の `rules: { ... }` や `pytest.ini` の marker 定義に対応する。重要なのは Goodhart（評価基準を都合よく歪める罠） 対策として **rubric を read-only に置く** こと（09 章）。これは `.eslintrc` を CI で固定して開発者が勝手に緩めない運用に相当する。

### evaluator ≒ ESLint runner / pytest test runner / LSP diagnostics

evaluator は rubric を読み込み、artifact に対して採点する。ESLint の `eslint --format json` 出力、pytest の `--junitxml`、LSP の `textDocument/publishDiagnostics` がそれぞれ機械可読 findings を返す点で完全に対応する。LLM 評価が non-deterministic である点だけが異なる（後述「概念のズレ」）。

### generator (`run-build-skill`) ≒ scaffold tool / cookiecutter / yeoman

`run-build-skill` は新しい Skill を雛形展開するメタ部品で、yeoman generator、cookiecutter template、`npm init`、`cargo new`、`terraform init` の役割に対応する。違いは「雛形展開後に evaluator が自動採点して reject/retry する自己進化ループ」を組み込んでいる点（23 章）。

### Hook ≒ git hook / pre-commit framework

PreToolUse / PostToolUse / SubagentStop などの lifecycle hook は、git の `pre-commit` / `post-merge` や pre-commit framework の stage に対応する。共通点は「LLM 判断に任せず決定論で gate する」こと。05 章の「高級リンターにしない」原則は、git hook で十分なものを ESLint plugin にしないのと同じ判断である。

### Progressive Disclosure（段階的開示） ≒ lazy import / on-demand load

`SKILL.md` 本体は薄く保ち、`references/`, `templates/`, `scripts/` は必要時のみ参照する設計（07 章）は、Python の lazy import、ESLint plugin の rule lazy load、LSP の `onRequest` 遅延ロード、Terraform の `count = 0` による条件展開に対応する。狙いは context window / token cost の節約という点で、メモリ/起動時間節約と同じ動機。

### Subagent (context fork) ≒ subprocess / sandbox / pytest fixture scope

Subagent は親文脈から切り離された別 context を持つ実行単位で、subprocess、Docker container、pytest の `scope="function"` fixture（テストごとに新規生成）、git worktree に対応する。09 章の「generator と evaluator を分ける」原則は、テストコードがプロダクションコードの内部状態を直接 mock せず black-box にすべき原則と同じ理由（sycophancy 回避 = test smell 回避）。

### rubric_refs (依存注入) ≒ ESLint extends / pytest plugin discovery / Terraform module source

`rubric_refs:` で評価基準を外部参照する仕組みは、`.eslintrc` の `extends: ["@company/eslint-config"]`、pytest の `entry_points` plugin discovery、Terraform の `source = "registry.terraform.io/..."` に対応する。一方向依存（artifact/generator → evaluator → rubric）は Hexagonal Architecture の依存方向ルールそのもの。

## 役割対応図

```text
Claude Code Skill ≒ Language Server + Linter + Scaffolder の合成

  ┌─────────────────────────────────────────────────────────┐
  │                  Claude Code Skill                      │
  │                                                         │
  │   ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │
  │   │ Generator（生成役）    │  │ Evaluator（評価役）    │  │ Reference（参照）   │   │
  │   │ (scaffolder) │→ │ (linter/test)│← │ (rubric)    │   │
  │   │  ≒ yeoman    │  │  ≒ ESLint    │  │  ≒ .eslintrc│   │
  │   │    cookiecutr│  │    pytest    │  │    pytest.ini│  │
  │   └──────┬───────┘  └──────┬───────┘  └─────────────┘   │
  │          │                  │                            │
  │          ▼                  ▼                            │
  │      Artifact（成果物）          findings JSON                     │
  │      ≒ generated      ≒ diagnostics                      │
  │        project          (LSP)                            │
  │                                                          │
  │   ┌──────────────────────────────────────────────────┐   │
  │   │ Hook (PreToolUse / PostToolUse)                  │   │
  │   │   ≒ git pre-commit / pre-commit framework        │   │
  │   └──────────────────────────────────────────────────┘   │
  │                                                          │
  │   ┌──────────────────────────────────────────────────┐   │
  │   │ Subagent (context fork)                          │   │
  │   │   ≒ subprocess / pytest fixture scope            │   │
  │   └──────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────┘
```

主要な「合成」関係は次のとおり。

- LSP の「発動条件 + capability + diagnostics」 + ESLint の「rule + reporter」 + yeoman の「template + prompt」 が一つの Skill 部品に統合されている。

## もしあなたが○○の経験者なら… 推奨読み順

| 経験 | 推奨読み順 | 理由 |
|---|---|---|
| ESLint plugin 開発者 | 03 → 09 → 29 → 24 | frontmatter (= rule metadata)、evaluator (= reporter)、rubric (= rule config)、テンプレを優先 |
| pytest plugin 開発者 | 09 → 28 → 27 | fixture scope と evaluator の対応、forked 実行の意義 |
| Terraform / IaC 経験者 | 05 → 29 → 23 | 責務分離（module 境界）、依存方向、メタモジュール |
| LSP / IDE 拡張開発者 | 14 → 09 → 10 | 動的 context 注入、diagnostics 契約、lifecycle hook |
| SRE / Platform engineer | 27 → 28 → 04 | dogfooding、運用ループ、permission / settings |
| Unix shell / pipeline 派 | 05 → 07 → 11 | 小さく組む、必要時だけロード、テンプレ |
| Hexagonal Arch / Clean Arch 派 | 05 → 23 → 09 | 依存方向、メタアーキテクチャ、評価境界 |

（章番号は本リポジトリ `xl-skills/doc/スキルの設計書/` 配下。未存在番号は将来章を指す場合がある。）

## 概念のズレ（類推が成立しない部分）

類推は導入には有効だが、以下の領域では破綻する。設計判断では必ず公式仕様に戻ること。

| ズレ項目 | ESLint/pytest 等 | Skill |
|---|---|---|
| 評価の決定性 | AST/構文ベースで decidable | LLM 評価は non-deterministic、score 揺らぎあり |
| 発動 trigger | match pattern / glob で grep-based | `description` ベース、Claude が意味で選択 |
| 失敗時の振る舞い | exit code で再現可能 | retry / fallback / re-prompt の余地 |
| context の概念 | scope = AST node / fixture lifetime | LLM context window / token budget |
| rule の合成 | `extends` は決定論的 merge | rubric merge は LLM 解釈に依存 |
| 副作用境界 | 通常 read-only (linter) | Skill は file write / shell 実行を伴うことが多い |
| versioning | semver で機械的に判定 | `rubric_version` + hash + 影響評価 (23 章 governance) |
| sycophancy | 存在しない（テストはコードを忖度しない） | 同 context だと評価が甘くなる固有問題 (09 章) |

特に重要なのは **discovery の差**。ESLint / pytest は config と filename pattern で機械的に rule/test を選ぶが、Skill は `description` の自然言語意味を Claude が解釈して選ぶ。このため `description` を「機械可読 trigger」のつもりで書くと発動精度が落ちる（03 章「description は宣伝文 + trigger 列」原則）。

## 参考図書・公式ドキュメント

- Claude Code 公式: https://docs.claude.com/en/docs/claude-code
- Claude Code Skills: https://docs.claude.com/en/docs/claude-code/skills
- ESLint Plugin Developer Guide: https://eslint.org/docs/latest/extend/plugins
- pytest Writing plugins: https://docs.pytest.org/en/stable/how-to/writing_plugins.html
- Language Server Protocol Spec: https://microsoft.github.io/language-server-protocol/
- Terraform Module Development: https://developer.hashicorp.com/terraform/language/modules/develop
- pre-commit framework: https://pre-commit.com/
- Hexagonal Architecture (Alistair Cockburn): https://alistair.cockburn.us/hexagonal-architecture/
- The Art of Unix Programming (E. S. Raymond): http://www.catb.org/esr/writings/taoup/

---

類推は理解の足場であり、設計判断の根拠ではない。詳細な仕様判断は 03/05/09/23 章および 16/17（公式正本）に戻って確認すること。
