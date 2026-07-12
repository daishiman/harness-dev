# 15. 公式参照元メモ

取得日: 2026-05-17  
目的: 元記事・画像に加えて補完した Claude Code の最新仕様について、参照した公式ドキュメントを追跡できるようにする。

このファイルは出典、取得日、更新手順の追跡メモである。公式仕様の正本は `16-official-skills-complete-reference.md`、Agent Teams / Subagent / Hooks の正本は `17-agent-teams-reference.md` とする。

## 参照元

| 領域 | 公式 URL | この設計書での反映先 |
|---|---|---|
| Claude Code Skills | https://code.claude.com/docs/en/skills | `02-claude-code-skill-spec.md`, `03-yaml-frontmatter-reference.md`, `04-invocation-permissions-settings.md`, `07-progressive-disclosure.md`, `14-dynamic-context-injection.md` |
| Subagents | https://code.claude.com/docs/en/sub-agents | `10-subagents-hooks-integration.md` |
| Hooks | https://code.claude.com/docs/en/hooks | `10-subagents-hooks-integration.md`, `04-invocation-permissions-settings.md` |
| Settings | https://code.claude.com/docs/en/settings | `04-invocation-permissions-settings.md` |
| Permissions | https://code.claude.com/docs/en/permissions | `04-invocation-permissions-settings.md`, `10-subagents-hooks-integration.md` |
| Agent Teams | https://code.claude.com/docs/en/agent-teams | `05-layering-skill-subagent-hook-mcp-cli.md`, `10-subagents-hooks-integration.md`, `17-agent-teams-reference.md` |
| Commands / Slash Commands | https://code.claude.com/docs/en/commands | 監視対象（生成する slash command 契約）。章反映は drift 検知後の人間レビュー |
| Plugins / Marketplace | https://code.claude.com/docs/en/plugins, https://code.claude.com/docs/en/plugins-reference | 監視対象（plugin.json / marketplace スキーマ）。本リポ自体がマーケットプレイス |
| Output Styles | https://code.claude.com/docs/en/output-styles | 監視対象（出力スタイル契約） |
| Tools | https://code.claude.com/docs/en/tools-reference | 監視対象（ツール名・権限の正本） |
| Claude Code CHANGELOG | https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md | 製品レベル変更の広域センサー（単一ファイルで「何かあったか」を検知） |
| Claude Code Docs index | https://code.claude.com/docs/llms.txt | 公式更新確認の起点 |

## 公式 Skills から抽出した主な仕様

- Skill は `SKILL.md` の YAML frontmatter と Markdown 本文で構成される。
- すべての frontmatter field は optional だが、`description` は推奨。
- `description` と `when_to_use` は skill listing で合算され、1,536 文字 cap の対象。
- Skill content は invocation 後に conversation へ入り、session 中に残る。
- auto-compaction 後は最近呼ばれた Skill から、各先頭 5,000 tokens、合計 25,000 tokens まで再付与される。
- `allowed-tools` は allow-list であり deny ではない。
- `disable-model-invocation: true` は Claude の自動 invocation を止め、description を context から外す。
- `user-invocable: false` は `/` menu から隠すだけで、Claude からの invocation は止めない。
- `skillOverrides` は settings 側で visibility を制御する。
- `context: fork` は Skill content を subagent prompt として実行する。
- `!` dynamic injection は Claude が見る前に shell command output を prompt へ挿入する。

## 公式 Subagents から抽出した主な仕様

- Subagent frontmatter では `name` と `description` が必須。
- `skills` field は startup 時に Skill 本文全文を preload する。
- `skills` は access control ではなく preload control。
- `disable-model-invocation: true` の Skill は preload できない。
- Subagent は `tools` / `disallowedTools` / `permissionMode` / `mcpServers` / `memory` / `isolation` などで実行境界を制御できる。
- plugin subagent では `hooks`, `mcpServers`, `permissionMode` が無視される。

## 公式 Hooks から抽出した主な仕様

- Hooks は lifecycle event に応じて shell command / HTTP endpoint / LLM prompt を実行する。
- event は session、turn、tool call、subagent、task、compaction、file change などに分かれる。
- `PreToolUse` は tool call 前に allow / deny / ask / defer できる。
- permission deny / ask rules は hook の allow で bypass できない。
- blocking hook は allow rule より優先される。
- `UserPromptExpansion` は `/skillname` direct path の制御に関係する。
- `SubagentStart` / `SubagentStop` は evaluator / generator orchestration に使える。

## 公式 Settings / Permissions から抽出した主な仕様

- settings scope は Managed / User / Project / Local。
- precedence は Managed > command line > Local > Project > User。
- permission rules は deny -> ask -> allow の順で評価される。
- deny はどの scope にあっても allow より優先される。
- `permissions` は settings / `/permissions` で管理できる。
- `disableAllHooks`, `allowedHttpHookUrls`, `httpHookAllowedEnvVars`, `allowManagedHooksOnly` は Hook 運用に関係する。
- `includeGitInstructions` は自前 git workflow Skill と衝突する場合に検討する。

## 公式 Agent Teams から抽出した主な仕様

- Agent Teams は実験的機能で、明示的な有効化が必要。
- lead、teammates、shared task list、mailbox で構成される。
- teammate は lead conversation history を継承しない。
- same-file edits と依存過多 task には向かない。
- lead は同時に 1 team だけ管理でき、nested teams は不可。
- quality gate には `TaskCreated`, `TaskCompleted`, `TeammateIdle` hooks を使う。

## 仕様の扱い

Claude Code の仕様は更新されるため、この設計書では次の方針を取る。

- 具体値は 2026-05-17 時点の公式 Docs に基づく。
- token cap や field semantics は将来変更され得る。
- 設計判断は具体値だけに依存させず、「冒頭に重要情報」「詳細は補助ファイル」「危険操作は permissions / hooks」という構造原則へ寄せる。

## 公式更新時の再監査手順

1. https://code.claude.com/docs/llms.txt を取得し、関連ページ一覧を確認する。
2. `skills`, `sub-agents`, `hooks`, `settings`, `permissions`, `agent-teams` の更新有無を見る。
3. frontmatter field、permission mode、hook event、settings key、Agent Teams limitation の増減を確認する。
4. 差分を分類する。
   - `fact-change`: 公式事実のみ。`16` / `17` へ反映。
   - `design-impact`: 設計判断に影響。`03` / `04` / `05` / `07` / `10` / `13` へ反映。
   - `template-impact`: 生成物に影響。`11` / `24` へ反映。
   - `runbook-impact`: 手順に影響。`19` / `25` / `26` へ反映。
   - `breaking-change`: 既存設計と衝突。ユーザー確認または migration note を作る。
5. `16-official-skills-complete-reference.md` と `17-agent-teams-reference.md` を先に更新する。
6. 必要な中核ファイルへ設計判断として反映する。
7. `13-checklists.md` の「作成前: 公式 docs の `llms.txt` または What's New で更新差分を確認した」と、該当する P0/P1/P2 検証項目を PASS にする。

## 公式項目から設計判断への対応

| 公式項目 | 反映先 | 設計判断 |
|---|---|---|
| Skill frontmatter | `03`, `16` | 公式 field と独自 metadata を分離 |
| Invocation control | `04`, `16` | `disable-model-invocation` と `user-invocable` を混同しない |
| Skill lifecycle | `07`, `16` | 公式 500 行目安を `16` に保持し、生成対象 `SKILL.md` の 300 行 hard cap は `08` / `13` / `24` で判定 |
| Dynamic injection | `14`, `16` | facts と external LLM opinion を分離 |
| Permissions | `04`, `13` | deny priority、Bash wildcard、auto/bypass disable |
| Hooks | `10`, `13` | exit code 2、structured decision、TaskCompleted gate |
| Subagents | `10` | `skills` preload と `context: fork` の違い |
| Agent Teams | `05`, `10`, `17` | Subagent と別レイヤー、same-file conflict 回避 |

### 公式更新の自動化（poll-llms-txt.yml / update-yaml-spec.yml）

手順 1 の `llms.txt` 取得は `.github/workflows/poll-llms-txt.yml` により週次 cron で自動実行される。

- `poll-llms-txt.yml` は `llms.txt` 目次のチャーンを `eval-log/spec-drift.json` に記録する（Issue は起票しない）。
- `.github/workflows/update-yaml-spec.yml` は実仕様ページ群（skills / settings / sub-agents / hooks / permissions / agent-teams / commands / plugins / plugins-reference / output-styles / tools-reference）と製品 CHANGELOG を取得して `yaml-spec-cache.md` と `references/spec-diff-history.md`（consumer と同一 SSOT）を自動更新し、いずれかに変更を検知した時に dedup 付きの spec-drift Issue を起票する。監視対象の正本は `scripts/build-yaml-spec-cache.py` の `SOURCES`（上表の依存宣言と一致させる）。
- `ref-yaml-spec-fetcher/references/yaml-spec-cache.md` の `last_fetched` が 30 日を超えている場合、`lint-manifest-contents.py` が WARNING を出力する。
- 自動 Issue が起票された場合、手順 2〜7 を人間が実施する。自動化は取得・履歴更新・通知までで、設計判断の反映は人間レビューを通す。
