# Codex 配置・反映ルール

このファイルを AIDD エージェントキットにおける Codex 配置の正本とします。

## 利用者が覚える2行

| 種類 | リポジトリ内 | ユーザー共通 | ファイル形式 |
|---|---|---|---|
| Skill | `$REPO_ROOT/.agents/skills/<skill>/` | `$HOME/.agents/skills/<skill>/` | `SKILL.md` |
| Custom agent | `$REPO_ROOT/.codex/agents/` | `$CODEX_HOME/agents/`（通常は `~/.codex/agents/`） | 1 agentにつき1つの `.toml` |

`$REPO_ROOT/.codex/skills` は公式のrepository Skill authoring先ではなく、AIDDも使用しません。一方、`$CODEX_HOME/skills`（通常は `~/.codex/skills`）はCodex組込のskill-installer・skill-creator・plugin等がpersonal installed Skillを管理する領域として実行環境に現れることがあります。AIDDはそこへ書き込まず、project `.codex/skills` の誤配置と混同しません。Skill と custom agent は次のように組み合わせます。

```text
.agents/skills/app-orchestrator/SKILL.md   再利用する作業手順
                  ↓ 明示的に使用
.codex/agents/app-orchestrator.toml        委譲先の役割・境界・実行設定
```

## Codex公式の探索範囲

これはCodexが**読みに行く候補**です。AIDDが毎回すべてへ書く、という意味ではありません。

| 種類 | project scope | user scope | 補足 |
|---|---|---|---|
| Skill | CWDからリポジトリルートまでの各 `.agents/skills/` | `$HOME/.agents/skills/` | 同じ `name` は統合されず、両方が候補になり得る |
| Custom agent | `$REPO_ROOT/.codex/agents/*.toml` | `$CODEX_HOME/agents/*.toml` | project側はtrusted projectで利用する |
| Codex設定 | ルートからCWDまでの各 `.codex/config.toml` | `$CODEX_HOME/config.toml` | project側は近い階層を優先 |
| Hooks | `$REPO_ROOT/.codex/hooks.json` またはprojectの `.codex/config.toml` | `$CODEX_HOME/hooks.json` またはuserの `config.toml` | 複数scopeの一致するhookはすべて実行候補になる |
| 常設指示 | ルートからCWDまでの `AGENTS.md` / `AGENTS.override.md` | `$CODEX_HOME/AGENTS.md` / `AGENTS.override.md` | Skillやcustom agentの代替ではない |

公開公式docsが示すSkill authoring/discovery先は上表の`.agents/skills`です。これとは別に、このCodex runtimeは`$CODEX_HOME/skills`もpersonal installed Skill rootとしてcatalogへ載せます。後者はCodex組込installer/plugin等の所有領域で、AIDDの配布先ではありません。

## AIDDが書くscope

AIDDは1回の処理で、明示したscopeだけへ書きます。**このAIDDキット開発リポジトリではproject scopeを正**とし、生成済みの `.agents`・`.codex`・`.claude` はproject runtimeです。編集正本は後述する `aidd-agent-kit/` 内にあります。

| 利用場面 | 明示scope | AIDDの書込先 |
|---|---|---|
| 配布キットを全プロジェクトで使う | user | `$HOME/.agents/skills`、`$CODEX_HOME/agents`、Claude Codeのuser領域 |
| このリポジトリでキットを開発・検証する | project | `$REPO_ROOT/.agents/skills`、`$REPO_ROOT/.codex/agents`、project内のClaude Code領域 |

userとprojectに同名のAIDD Skill/custom agentを置く運用は推奨しません。Codexは同名Skillを自動統合しないため、表示の重複や参照元の誤認につながります。`./aidd-agent-kit/doctor-codex-layout.sh` は両scopeと誤配置を**読み取り専用で診断**します。AIDD管理のuser/project間は同内容の重複が警告、内容差またはproject `.codex/skills` がNGです。`$CODEX_HOME/skills` との同名はAIDD管理外の衝突候補として警告しますが、存在だけで誤配置とは判定しません。CIでは `--strict` を付けるとこれらの重複警告もNGになります。doctorはファイルを移動・削除しません。

## AIDD キット内の編集原本

実際の配置先を直接編集すると次回更新で差分が分散するため、編集元を次に固定します。

| 編集する内容 | 唯一の編集原本 | scopeに応じた反映先 |
|---|---|---|
| Claude/Codex共通Skill | `skills/<skill>/` | `.claude/skills/<skill>/` と `.agents/skills/<skill>/` |
| Codex用コマンドワークフロー | `codex/workflow-skills/<skill>/` | `.agents/skills/<skill>/` |
| app-orchestratorの手順 | `agents/app-orchestrator.md` | `.claude/agents/app-orchestrator.md` と `.agents/skills/app-orchestrator/SKILL.md` |
| Codex custom agent | `codex/agents/<agent>.toml` | `.codex/agents/<agent>.toml` |
| SkillのCodex UIメタデータ | 各Skillの `agents/openai.yaml` または `codex/app-orchestrator-openai.yaml` | 対応する `.agents/skills/<skill>/agents/openai.yaml` |

`codex/workflow-skills` という名前は「Codexだけで使うSkillの配布元」を表します。`.codex` の下へコピーする、という意味ではありません。

`app-orchestrator.toml` の中では `name = "app_orchestrator"` と定義しています。Codexがagentを識別する正本はファイル名ではなくTOMLの `name` フィールドです。そのため、Skillとして明示するときは `$app-orchestrator`、custom agentへ委譲するときは `app_orchestrator` になります。

## Custom agent TOML・権限・Hooksの責務

`codex/agents/app-orchestrator.toml` は、公式必須の `name`・`description`・`developer_instructions` を定義します。`model`・`model_reasoning_effort`・`sandbox_mode`・`mcp_servers`・`skills.config` などの公式追加キーも使用できますが、このキットは次の理由で固定していません。

| 設定 | AIDDの標準 | 理由 |
|---|---|---|
| `model` / `model_reasoning_effort` | 親・Codexの選択を継承 | 利用できるモデル、価格、タスク難度に追従するため |
| `sandbox_mode` / `approval_policy` | 親セッションの権限を継承 | custom agentだけが利用者の権限選択を広げないため |
| `mcp_servers` / `skills.config` | 親設定を継承 | `setup-env-*` とproject/user設定を重複させないため |

したがって、必須3キーだけのTOMLは設定漏れではありません。インストーラーと検証器は必須3キーの存在・型・非空を厳格に検査しつつ、公式の追加config key/tableは拒否しない設計です。AIDDの配布既定として `danger-full-access`、`approval_policy = "never"`、ネットワーク常時許可を強制しません。実装・公開で追加権限が必要なときは、Codexの現在のpermission modeと通常の承認フローを使います。

CodexにはClaude Codeと同様に公式Hooksがあります。`PreToolUse`・`PermissionRequest`・`PostToolUse`・`SessionStart`・`Stop`・subagentイベントなどをproject/userの `hooks.json` または `config.toml` に定義できます。ただし、複数scopeの一致するhookは置換ではなくすべて実行され、command hookは定義内容のレビューとtrustが必要です。そのためAIDDインストーラーは、利用者所有の `$CODEX_HOME/config.toml` と `$CODEX_HOME/hooks.json` を生成・上書きしません。既存hookの消失や、意図しない自動承認・外部送信を避けるためです。

hookを導入するときは、対象リポジトリの `.codex/hooks.json` をproject固有ポリシーとして管理し、Codexの `/hooks` で内容を確認してからtrustしてください。自動承認を行う `PermissionRequest` hookは標準化せず、具体的な許可条件をレビューできる場合だけ追加します。Hooksは有用なガードレールですが、公式仕様上も完全な強制境界ではないため、sandboxとapproval policyの代替にはしません。

## 反映手順

用語と順序を **編集原本 → 明示scope → manifest → verify** に統一します。

利用者の全プロジェクトへ入れる通常インストールはuser scopeです。Macでは `install-mac.command`、Windowsでは `install-windows.bat` を実行します。

このリポジトリ自体へ反映するときはproject scopeです。リポジトリルートから次を実行します。どちらも反映したファイルをmanifestへ記録し、コピー元との一致を検証します。

```bash
bash aidd-agent-kit/sync-project-mac.command
```

```bat
call aidd-agent-kit\sync-project-windows.bat
```

反映後はdoctorとverifyを実行します。

```bash
./aidd-agent-kit/doctor-codex-layout.sh
bash aidd-agent-kit/verify-codex-layout.sh
```

CIでuser/projectの同名重複も失敗にする場合は `./aidd-agent-kit/doctor-codex-layout.sh --strict` を使います。次も確認します。

1. `.agents/skills/build-app/SKILL.md` が存在する。
2. `.codex/agents/app-orchestrator.toml` が存在し、`codex/agents/app-orchestrator.toml` と一致する。
3. project `.codex/skills` を新規作成していない。
4. Codexを再起動し、`/skills` に `build-app` が表示される。
5. custom agent一覧に `app_orchestrator` が表示される。

## 誤配置・二重導入を見つけたとき

project `.codex/skills` やuser/projectの同名AIDD項目は利用者所有かもしれないため、installer・sync・doctorは自動移動・自動削除しません。まずdoctorの診断結果と各scopeのmanifestを確認し、どちらを残すか利用者が決めます。内容差がある場合はバックアップを取ったうえで、編集原本へ必要な変更を統合し、選んだscopeへ反映してください。`$CODEX_HOME/skills` のpersonal installed Skillは別所有なので、この整理対象へ含めません。

## 仕様根拠

- [OpenAI Docs: Build skills](https://developers.openai.com/codex/skills) — リポジトリSkillは `.agents/skills`、ユーザーSkillは `~/.agents/skills`
- [OpenAI Docs: Subagents](https://developers.openai.com/codex/subagents) — custom agentはプロジェクトの `.codex/agents`、またはユーザーの `~/.codex/agents`
- [OpenAI Docs: Configuration Reference](https://developers.openai.com/codex/config-reference) — `approval_policy`、`sandbox_mode`、multi-agent、Hooksの設定キー
- [OpenAI Docs: Hooks](https://developers.openai.com/codex/hooks) — hookの探索場所、イベント、trust、入出力仕様
- [OpenAI Docs: Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security) — sandboxとapprovalの役割分担
- [OpenAI Docs: AGENTS.md](https://developers.openai.com/codex/guides/agents-md) — `AGENTS.md` は階層的に読み込む常設指示

最終確認日: 2026-08-13
