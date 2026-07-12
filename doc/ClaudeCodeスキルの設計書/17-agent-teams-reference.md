# 17. Agent Teams 公式仕様と Skill 設計への接続

取得日: 2026-05-17  
参照元: https://code.claude.com/docs/en/agent-teams

## このファイルの位置づけ（正本宣言）

このファイルは Claude Code Agent Teams および Subagent との対比・連携の **公式仕様の唯一の正本** である。`10-subagents-hooks-integration.md` は本ファイルにリンクし、Skill 設計から見た Hook 適用パターン・設計判断のみを保持する。

**更新責務マトリクス（このファイル）**: Agent Teams 公式仕様（teammate 数、display modes、shutdown、permission 継承、`teammateMode` settings、`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` 等）と Subagent frontmatter 一覧が変わったら本ファイルのみを更新する。

**リンク元**:
- 10-subagents-hooks-integration.md → Subagent frontmatter / Skill との 2 方向接続

このファイルは、ユーザー指定の「SubAgent に切り分けて並列実行」「Agent Team 機能」を Skill 設計へ接続するため、Claude Code Agent Teams の該当仕様を整理する。

## 1. 位置づけ

Agent Teams は、複数の Claude Code instance を team として協調させる実験的機能である。shared tasks、inter-agent messaging、centralized management を持つ。

有効化:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

または environment variable で `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。

要件:

- Claude Code v2.1.32 以降
- 既定では disabled
- session resumption、task coordination、shutdown behavior に既知の制約がある

## 2. いつ使うか

Agent Teams が向く:

- research and review
- independent modules / features
- debugging with competing hypotheses
- frontend / backend / tests など cross-layer coordination
- 複数視点が本当に価値を増やす作業

向かない:

- sequential tasks
- same-file edits
- dependencies が多い作業
- coordination overhead が価値を上回る作業
- routine tasks

## 2.1 Subagent frontmatter 全項目（公式）

Subagent は `.claude/agents/` または `~/.claude/agents/` に Markdown file として置く。YAML frontmatter と body system prompt で構成される。

| field | 必須 | 用途 |
|---|---:|---|
| `name` | Yes | unique identifier。hooks の `agent_type` にもなる |
| `description` | Yes | Claude がいつ delegate するか |
| `tools` | No | subagent が使える tool allowlist |
| `disallowedTools` | No | inherited / specified tool から deny |
| `model` | No | `sonnet`, `opus`, `haiku`, full model ID, `inherit` |
| `permissionMode` | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | No | max agentic turns |
| `skills` | No | startup 時に full Skill content を preload |
| `mcpServers` | No | subagent scoped MCP servers |
| `hooks` | No | subagent lifecycle hooks |
| `memory` | No | `user`, `project`, `local` persistent memory |
| `background` | No | background task |
| `effort` | No | effort override |
| `isolation` | No | `worktree` で isolated git worktree |
| `color` | No | UI display color |
| `initialPrompt` | No | main session agent として起動時の initial prompt |

### Skill と Subagent の 2 方向

| Approach | System prompt | Task | Also loads |
|---|---|---|---|
| Skill with `context: fork` | `agent` type | SKILL.md content | CLAUDE.md |
| Subagent with `skills` field | subagent body | delegation message | preloaded skills + CLAUDE.md |

### `skills:` preload の注意

- description だけではなく full content が startup 時に注入される。
- `disable-model-invocation: true` の Skill は preload できない。
- `skills` は access 制御ではない。未列挙 Skill も Skill tool で呼べる。
- Skill tool 自体を防ぎたい場合は `tools` から omit するか `disallowedTools` に入れる。

### 公式 Hook event 一覧

| Event | 発火タイミング |
|---|---|
| `SessionStart` | session begins / resumes |
| `UserPromptSubmit` | prompt submit 前 |
| `UserPromptExpansion` | slash command expansion 前 |
| `PreToolUse` | tool call 前 |
| `PermissionRequest` | permission dialog |
| `PostToolUse` | tool success 後 |
| `PostToolUseFailure` | tool failure 後 |
| `PostToolBatch` | parallel tool batch 後 |
| `SubagentStart` | subagent spawned |
| `SubagentStop` | subagent finished |
| `TaskCreated` | task created |
| `TaskCompleted` | task completed |
| `TeammateIdle` | teammate idle 直前 |
| `Stop` | main agent finished |
| `PreCompact` | compaction 前 |
| `PostCompact` | compaction 後 |
| `FileChanged` | watched file changed |

### Hook decision schema（公式）

PreToolUse の structured decision は `hookSpecificOutput.permissionDecision` を使う。top-level `decision` / `reason` は PreToolUse では deprecated。

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Database writes are not allowed"
  }
}
```

Top-level decision を使う events: `UserPromptSubmit`, `UserPromptExpansion`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop`, `SubagentStop`, `ConfigChange`, `PreCompact`。

Exit code 2 の挙動:

- JSON stdout は無視され、stderr が Claude への feedback になる。
- `PreToolUse` は tool call を block。
- `TaskCreated` は task creation を rollback。
- `TaskCompleted` は completed marking を block。
- `TeammateIdle` は teammate を idle にせず作業継続。
- `PreCompact` は compaction を block。

HTTP hooks: non-2xx は non-blocking error。block したい場合は 2xx + JSON body で decision fields を返す。

## 3. Subagents との違い

| 項目 | Subagents | Agent Teams |
|---|---|---|
| Context（文脈） | own context window | own context window, fully independent |
| Communication | main agent へ結果を返すだけ | teammates が直接 message できる |
| Coordination | main agent が管理 | shared task list と self-coordination |
| Best for | 結果だけ必要な focused task | 議論・相互挑戦・独立協調が必要な complex work |
| Token cost | lower | higher |

設計判断:

- quick focused worker なら Subagent。
- teammates が発見を共有し、互いに challenge する必要があるなら Agent Team。

## 4. Team architecture

| Component | Role（役割） |
|---|---|
| Team lead | main Claude Code session。team 作成、spawn、coordination |
| Teammates | separate Claude Code instances。assigned task を実行 |
| Task list | shared work item list。claim / complete される |
| Mailbox | inter-agent messaging system |

local storage:

- Team config: `~/.claude/teams/{team-name}/config.json`
- Task list: `~/.claude/tasks/{team-name}/`

注意:

- team config は runtime state を持つため手編集しない。
- project-level `.claude/teams/teams.json` のような config は認識されない。
- reusable teammate roles は subagent definitions で定義する。

## 5. Display modes

| Mode | 内容 |
|---|---|
| `in-process` | main terminal 内で全 teammate を実行。Shift+Down で cycle |
| `tmux` / split panes | 各 teammate を pane に表示。tmux または iTerm2 が必要 |
| `auto` | tmux session 内なら split panes、そうでなければ in-process |

settings:

```json
{
  "teammateMode": "in-process"
}
```

session flag:

```bash
claude --teammate-mode in-process
```

## 6. Teammates and models

Claude は task に応じて teammate 数を決められる。ユーザーが明示指定することもできる。

例:

```text
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

注意:

- teammates は lead の `/model` selection を default では継承しない。
- `/config` で Default teammate model を設定できる。
- Default を leader's model にすることもできる。

## 7. Plan approval

complex / risky task では、teammate を read-only plan mode にして lead approval 後に implementation へ進ませられる。

用途:

- database schema 変更
- authentication refactor
- large-scale file edits
- production-impacting changes

lead の approval criteria を prompt に含めると判断に影響できる。

## 8. Direct teammate interaction

各 teammate は full independent Claude Code session であり、直接 message できる。

In-process:

- Shift+Down: teammate cycle
- Enter: teammate session view
- Escape: interrupt current turn
- Ctrl+T: task list toggle

Split-pane:

- pane を click して直接操作

## 9. Tasks

shared task list は team coordination の中心。

task states:

- pending
- in progress
- completed

dependencies:

- pending task は unresolved dependencies があると claim できない。
- dependency が completed になると blocked task が自動 unblock される。

claim:

- lead assigns
- teammate self-claim

race condition:

- task claiming は file locking で保護される。

## 10. Shutdown and cleanup

teammate を終了するには lead に依頼する。

```text
Ask the researcher teammate to shut down
```

team cleanup:

```text
Clean up the team
```

注意:

- cleanup は lead 経由で行う。
- active teammates がいると cleanup は fail。
- teammates が cleanup を実行すると context 解決の問題で resource inconsistency が起き得る。

## 11. Quality gates with hooks

Agent Teams で使う hook:

| Hook | 用途 |
|---|---|
| `TeammateIdle` | teammate が idle になる前。exit code 2 で feedback して継続させる |
| `TaskCreated` | task 作成時。exit code 2 で作成阻止と feedback |
| `TaskCompleted` | task completed marking 時。exit code 2 で完了阻止と feedback |

Skill 設計への接続:

- evaluator JSON がない task completion を block。
- required files がない completion を block。
- 同じ file ownership に複数 teammate が触る task creation を block。

## 12. Subagent definitions as teammates

teammate spawn 時に project / user / plugin / CLI-defined の subagent type を参照できる。

spawn prompt template:

```text
Spawn a teammate using the {{teammate_role}} agent type to {{teammate_action}} the {{target_scope}}.
```

Sample expansion: `{{teammate_role}}=security-reviewer`, `{{teammate_action}}=audit`, `{{target_scope}}=auth module`。

適用されるもの:

- subagent definition の `tools` allowlist
- subagent definition の `model`
- definition body は teammate system prompt に追加 instruction として append

適用されないもの:

- subagent definition の `skills`
- subagent definition の `mcpServers`

team coordination tools:

- `SendMessage`
- task management tools

これらは `tools` restrict があっても teammate に利用可能。

## 13. Permissions

teammates は lead の permission settings で開始する。

注意:

- lead が `--dangerously-skip-permissions` なら teammates も同様。
- spawn 後に individual teammate mode を変えることはできる。
- spawn 時点で per-teammate mode は設定できない。

## 14. Context（文脈） and communication

各 teammate は own context window を持つ。spawn 時に regular session と同じ project context を load する。

load されるもの:

- `CLAUDE.md`
- MCP servers
- skills
- lead からの spawn prompt

load されないもの:

- lead conversation history

communication:

- teammate messages は自動 delivery。
- teammate idle / finish notifications は lead に届く。
- shared task list は全 agents が参照可能。
- name 指定で teammate に message できる。
- 全員に送るには recipient ごとに message を送る。

設計上の注意:

- 後続 prompt で参照できるよう teammate name を明示して spawn する。
- spawn prompt に task-specific context を十分に入れる。

## 15. Token usage

Agent Teams は single session より token usage が大きい。各 teammate が own context window を持ち、active teammate 数に比例して token 使用量が増える。

判断:

- research / review / new feature work では追加 token が価値を生みやすい。
- routine task は single session の方が cost-effective。

## 16. 公式 use case

### Parallel code review

レビュー観点を security / performance / test coverage のように分け、同時に調査させる。lead が最後に findings を synthesize する。

### Competing hypotheses debugging

原因が不明な障害で、teammates に異なる仮説を持たせ、互いに challenge させる。anchoring bias を減らす。

## 17. Best practices

### Give teammates enough context

teammates は lead history を継承しない。spawn prompt に対象 path、前提、評価観点、severity format などを明示する。

### Choose team size

hard limit は明示されていないが、実務上は token cost、coordination overhead、file conflicts を考慮する。

### Size tasks appropriately

task は独立して claim / complete できる粒度にする。

### Wait for teammates

lead が早く終了しないよう、全 teammate の completion を待つ。

### Start with research and review

最初から実装させるより、research / review で活用すると conflict が少ない。

### Avoid file conflicts

teammate ごとの file ownership を明示する。同じ file を複数 teammate に触らせない。

### Monitor and steer

直接 message と lead coordination で進行中に方向修正する。

## 18. Skill 設計への取り込み

Agent Team を Skill 設計へ組み込む場合の方針:

- Skill 自体に Agent Team を常用させない。coordination overhead が高い。
- Agent Team は「複数視点の並列検証」「独立 ownership の実装」「競合仮説検証」に限定する。
- team prompt は Skill から生成できるが、teammate は lead history を継承しないため必要 context を明示する。
- team task list の dependencies を明示する。
- `TaskCompleted` hook で evaluator gate を設ける。
- reusable teammate role は subagent definition として管理する。

### Agent Team prompt template

公式仕様の field / hook / environment variable は固定値として扱う。一方、Skill から生成する運用 prompt は次の変数で横展開する。

| 変数 | 意味 |
|---|---|
| `{{objective}}` | team 全体で達成する目的 |
| `{{teammate_roles}}` | teammate role の一覧 |
| `{{parallel_unit}}` | 並列化する単位（観点、module、仮説など） |
| `{{owned_paths}}` | teammate ごとの file ownership |
| `{{dependency_rule}}` | task dependencies の解決規則 |
| `{{approval_gate}}` | plan approval / evaluator gate の条件 |
| `{{completion_gate}}` | completed と見なす evidence |

```text
Create an Agent Team for {{objective}}.
Split work by {{parallel_unit}}.
Assign roles: {{teammate_roles}}.
Respect file ownership: {{owned_paths}}.
Do not claim a task until {{dependency_rule}} is satisfied.
Before implementation, pass {{approval_gate}}.
Mark tasks completed only when {{completion_gate}} is present.
```

## 19. Agent Team 利用チェックリスト

- [ ] 並列化に実質的な価値がある。
- [ ] teammates が独立して作業できる。
- [ ] `{{parallel_unit}}` が明示されている。
- [ ] `{{owned_paths}}` / file ownership が分かれている。
- [ ] lead history に依存しない spawn prompt を書ける。
- [ ] `{{dependency_rule}}` / task dependencies が定義されている。
- [ ] `{{approval_gate}}` が必要な risky task を識別した。
- [ ] `{{completion_gate}}` が evidence として確認できる。
- [ ] cleanup を lead 経由で行う。
- [ ] token cost と coordination overhead が許容できる。

## 20. 制約・トラブルシュート

公式上の現在の制約:

- in-process teammates は `/resume` / `/rewind` で復元されない。
- task status が遅延し、依存 task が block されることがある。
- shutdown は current request / tool call 完了まで遅くなることがある。
- lead は同時に 1 team だけ管理できる。
- nested teams は不可。teammate は team / teammate を spawn できない。
- lead は固定で、teammate を lead に昇格できない。
- teammates は spawn 時に lead の permission mode で始まる。per-teammate mode は spawn 時指定できない。
- split-pane mode には tmux または iTerm2 が必要。

運用対策:

- resume 後に古い teammate へ message しようとしたら、新しい teammate を spawn する。
- task が詰まったら lead が status を確認し、必要なら teammate を nudge する。
- cleanup は必ず lead 経由で実行する。
- permissions は team 作成前に pre-approve しておく。
