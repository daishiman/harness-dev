# 16. Claude Code Skills 公式仕様 完全リファレンス

取得日: 2026-05-17  
参照元: https://code.claude.com/docs/en/skills

## このファイルの位置づけ（正本宣言）

このファイルは Claude Code Skills の **公式仕様の唯一の正本** である。同じフォルダ内の `02` / `03` / `04` / `07` / `10` は、本ファイルの該当章へリンクし、独自の設計判断・運用ノウハウ・Why（理由）のみを保持する。

**更新責務マトリクス（このファイル）**: 公式仕様の事実（frontmatter 仕様、lifecycle の 5000/25000 tokens、配置場所、permission 構文、`skillOverrides` 等）が変わったら本ファイルのみを更新する。設計判断・運用ノウハウは更新しない。

**リンク元**:
- 02-claude-code-skill-spec.md → 配置場所・lifecycle・補助ファイル仕様
- 03-yaml-frontmatter-reference.md → frontmatter 全項目仕様
- 04-invocation-permissions-settings.md → invocation control・permissions・settings
- 07-progressive-disclosure.md → lifecycle の token budget
- 10-subagents-hooks-integration.md → 公式 hook event 一覧

このファイルは、Claude Code Skills の公式ページに含まれる該当情報を、スキル設計で参照しやすいように網羅的に再構成したもの。代表例だけではなく、設定・呼び出し・ライフサイクル・補助ファイル・権限・可視性・共有・トラブルシュートまで含める。

## 1. Skill の位置づけ

Claude Code Skill は、Claude の能力を拡張するための `SKILL.md` ベースの仕組みである。Claude は関連すると判断したときに Skill を使い、ユーザーも `/skill-name` で直接呼び出せる。

Skill を作るべき典型:

- 同じ instruction / checklist / multi-step procedure を何度も貼っている。
- `CLAUDE.md` の一部が「事実」ではなく「手順」に育っている。
- 長い reference を必要な時だけ読ませたい。
- command / workflow / bundled script を Claude に扱わせたい。

Skill は Agent Skills open standard に準拠し、Claude Code はそれに invocation control、subagent execution、dynamic context injection などを拡張している。

## 2. Bundled skills と custom commands

Claude Code には `/simplify`, `/batch`, `/debug`, `/loop`, `/claude-api` などの bundled skills がある。多くの built-in command が固定 logic を実行するのに対し、bundled skills は prompt-based で Claude に詳細な手順を与え、tool orchestration させる。

custom commands は skills に統合されている。`.claude/commands/deploy.md` と `.claude/skills/deploy/SKILL.md` は同じ `/deploy` として機能する。既存 `.claude/commands/` は動作し続けるが、同名の skill と command がある場合は skill が優先される。

## 3. Skill の配置場所

| 種類 | パス | 適用範囲 |
|---|---|---|
| Enterprise | managed settings | 組織の全ユーザー |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | 全プロジェクト |
| Project | `.claude/skills/<skill-name>/SKILL.md` | 現在のプロジェクト |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | plugin 有効時 |

同名衝突:

- enterprise は personal を override。
- personal は project を override。
- plugin skills は `plugin-name:skill-name` namespace を持つため、他レベルと衝突しない。
- command と skill が同名の場合、skill が優先。

## 4. Live change detection

Claude Code は skill directory の file change を watch する。

反映される変更:

- `~/.claude/skills/` 配下の追加・編集・削除
- project `.claude/skills/` 配下の追加・編集・削除
- `--add-dir` directory 内の `.claude/skills/` の追加・編集・削除

再起動が必要:

- session start 時に存在しなかった top-level skills directory を新規作成した場合

## 5. 自動 discovery

Project skills は、Claude 起動 directory から repository root までの `.claude/skills/` で discovery される。subdirectory の file を作業している場合、下位の nested `.claude/skills/` も on demand で discovery される。

monorepo での意味:

- repository root に共通 Skill を置ける。
- `packages/frontend/.claude/skills/` のように package-specific Skill を置ける。
- 作業対象 file に応じて nested Skill が見つかる。

## 6. Additional directories

`--add-dir` は基本的には file access を追加するもので、configuration discovery ではない。ただし skills は例外で、additional directory 内の `.claude/skills/` は自動 load される。

注意:

- additional directory の subagents / commands / output styles などは load されない。
- additional directory の `CLAUDE.md` は既定では load されない。
- additional directory の `CLAUDE.md` を load するには `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` が必要。

## 7. Skill directory 構成

最小:

```text
my-skill/
└── SKILL.md
```

補助ファイルあり:

```text
my-skill/
├── SKILL.md
├── prompts/
│   └── sample.md
├── templates/
│   └── sample.md
├── reference/
│   └── sample.md
├── examples/
│   └── sample.md
└── scripts/
    └── validate.sh
```

`SKILL.md` は必須。その他は任意。補助ファイルは `SKILL.md` から参照し、Claude が何をいつ読むべきか分かるようにする。

注記: 上記の `reference/` は公式例の表記である。本設計書のプロジェクト規約では `references/` を使用し、命名 lint も `references/` を対象にする。

## 8. Skill content の種類

| 種類 | 内容 | 呼び出しの考え方 |
|---|---|---|
| Reference content（参照内容） | conventions, patterns, style guides, domain knowledge | 現在作業に inline で適用する |
| Task content（タスク内容） | deployment, commit, code generation など specific action | `/skill-name` で直接呼ぶことが多い |

Task content（タスク内容） で副作用がある場合は、`disable-model-invocation: true` を検討する。

## 9. `SKILL.md` 基本構造

```markdown
---
name: my-skill
description: What this skill does
disable-model-invocation: true
allowed-tools: Read Grep
---

Your skill instructions here.
```

全 frontmatter field は optional。`description` は Claude がいつ使うか判断できるようにするため推奨。

## 10. Frontmatter（先頭メタ情報） 全項目

| Field | Required | 公式上の意味 | 設計時の注意 |
|---|---:|---|---|
| `name` | No | Skill の display name。省略時は directory name | lowercase letters, numbers, hyphens のみ。最大 64 文字 |
| `description` | Recommended | 何をするか、いつ使うか。Claude が自動適用判断に使う | 省略時は markdown body の first paragraph。`when_to_use` と合算で 1,536 文字 cap。key use case を先頭に置く |
| `when_to_use` | No | invocation 条件の追加 context、trigger phrase、example request | `description` に append され、1,536 文字 cap に含まれる |
| `argument-hint` | No | autocomplete 中に期待引数を示す hint | 例: `[issue-number]`, `[filename] [format]` |
| `arguments` | No | `$name` substitution 用の named positional arguments | space-separated string または YAML list。順番で mapping |
| `disable-model-invocation` | No | Claude の automatic loading を防ぐ | manual trigger したい workflow 用。subagent preload も防ぐ。default `false` |
| `user-invocable` | No | `/` menu から隠す | user が直接呼ぶべきでない background knowledge 用。default `true` |
| `allowed-tools` | No | Skill active 中に permission prompt なしで使える tools | space-separated string または YAML list。tool availability の制限ではない |
| `model` | No | Skill active 中の model override | current turn の残りだけ適用。次 prompt で session model に戻る。`inherit` 可 |
| `effort` | No | Skill active 中の effort override | `low`, `medium`, `high`, `xhigh`, `max`。利用可能値は model 依存 |
| `context` | No | `fork` で forked subagent context 実行 | explicit task を持つ Skill に使う |
| `agent` | No | `context: fork` 時に使う subagent type | built-in `Explore`, `Plan`, `general-purpose` または custom subagent。省略時は `general-purpose` |
| `hooks` | No | Skill lifecycle に scope された hooks | hooks in skills and agents の形式に従う |
| `paths` | No | activation を file glob で制限 | comma-separated string または YAML list。matching files 作業時だけ auto load |
| `shell` | No | `!` command / `!` fenced block の shell | `bash` default、`powershell` 可。PowerShell は `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` が必要 |

## 11. String substitutions 全項目

| Variable | 意味 |
|---|---|
| `$ARGUMENTS` | skill invocation 時の全 argument。content に `$ARGUMENTS` がなければ末尾に `ARGUMENTS: <value>` が append される |
| `$ARGUMENTS[N]` | 0-based index で N 番目 argument を参照 |
| `$N` | `$ARGUMENTS[N]` の shorthand |
| `$name` | `arguments` frontmatter list で宣言した named argument |
| `${CLAUDE_SESSION_ID}` | current session ID。logging や session-specific files に使う |
| `${CLAUDE_EFFORT}` | current effort level。`low`, `medium`, `high`, `xhigh`, `max` |
| `${CLAUDE_SKILL_DIR}` | Skill directory。plugin skill では plugin root ではなく skill subdirectory |

Argument parsing:

- indexed arguments は shell-style quoting を使う。
- `/my-skill "hello world" second` なら `$0` は `hello world`、`$1` は `second`。
- `$ARGUMENTS` は typed された full argument string。

## 12. Supporting files

目的:

- `SKILL.md` を focused に保つ。
- large reference docs を必要時だけ読む。
- scripts を実行し、本文に大きな処理を書かない。
- templates / examples を分離する。

公式が示す構成例:

```text
my-skill/
├── SKILL.md
├── reference.md
├── examples.md
└── scripts/
    └── helper.py
```

設計ルール:

- `SKILL.md` から補助ファイルを参照する。
- 何が入っていて、いつ読むべきかを書く。
- `SKILL.md` は 500 行未満を目安にする。
- detailed reference は separate files に移す。

## 13. Invocation control

| Frontmatter（先頭メタ情報） | User invoke（ユーザー起動） | Claude invoke（Claude起動） | Context loading（文脈読み込み） |
|---|---|---|---|
| default | Yes | Yes | description は常に context、full skill は invocation 時 |
| `disable-model-invocation: true` | Yes | No | description は context に載らず、user invocation 時に full skill |
| `user-invocable: false` | No | Yes | description は常に context、full skill は invocation 時 |

要点:

- `disable-model-invocation: true` は Claude の automatic / programmatic invocation を止める。
- `user-invocable: false` は `/` menu visibility の制御で、Skill tool access を止めない。
- `disable-model-invocation: true` は subagent preload も防ぐ。
- 副作用の強い workflow は user manual trigger に寄せる。

## 14. Skill content lifecycle

Skill が user または Claude により invoked されると、rendered `SKILL.md` content が conversation に single message として入り、session 中残る。

重要:

- later turns で Skill file は自動再読込されない。
- guidance は one-time step ではなく standing instruction として書く。
- auto-compaction 後は invoked skills が token budget 内で carry forward される。
- 最近呼ばれた Skill から順に、各 Skill 先頭 5,000 tokens、合計 25,000 tokens まで再付与される。
- 古い Skill は compaction 後に丸ごと drop される場合がある。
- 影響が弱くなった場合は description / instructions を強める、hook で deterministic enforcement する、または re-invoke する。

## 15. Pre-approve tools

`allowed-tools` は、Skill active 中に listed tools を approval prompt なしで使えるようにする。

```yaml
---
name: commit
description: Stage and commit the current changes
disable-model-invocation: true
allowed-tools: Bash(git add *) Bash(git commit *) Bash(git status *)
---
```

重要:

- tool availability の制限ではない。
- unlisted tools も callable だが、permission settings に従う。
- block したい場合は permission settings の deny rules を使う。
- project `.claude/skills/` の `allowed-tools` は workspace trust dialog 受諾後に効く。
- repository trust 前に project skills を review する。

## 16. Passing arguments

Skill は user からも Claude からも arguments 付きで invoked できる。

```markdown
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
---

Fix GitHub issue $ARGUMENTS following our coding standards.
```

`/fix-issue 123` は `$ARGUMENTS` を `123` に置換する。

位置指定:

```markdown
Migrate the $ARGUMENTS[0] component from $ARGUMENTS[1] to $ARGUMENTS[2].
```

shorthand:

```markdown
Migrate the $0 component from $1 to $2.
```

名前付き:

```yaml
arguments: [component, from, to]
```

```markdown
Migrate `$component` from `$from` to `$to`.
```

## 17. Dynamic context injection

`!` command syntax は、Skill content が Claude に送られる前に shell command を実行し、placeholder を output で置換する。

処理順:

1. `!` command が immediate execution される。
2. output が skill content の placeholder を置換する。
3. Claude は rendered prompt だけを見る。

inline:

```markdown
- PR diff: !`gh pr diff`
```

multi-line:

````markdown
```!
python3 --version
bash --version | head -1
git status --short
```
````

制約:

- preprocessing であり Claude が実行しているわけではない。
- substitution は original file に対して 1 回だけ。
- command output は plain text として挿入され、再スキャンされない。
- command output がさらに `!` placeholder を出しても展開されない。
- `disableSkillShellExecution: true` で user / project / plugin / additional-directory source の dynamic execution を無効化できる。
- 無効化時は command が `[shell command execution disabled by policy]` に置換される。
- bundled / managed skills はこの無効化の対象外。

## 18. Deeper reasoning

Skill 実行時に deeper reasoning を要求したい場合、skill content 内に `ultrathink` を含めるという公式パターンがある。常用ではなく、重い一回限りの reasoning が必要な Skill に限定する。

## 19. Run skills in a subagent

`context: fork` を frontmatter に追加すると、Skill は isolated forked subagent context で実行される。

意味:

- Skill content が subagent を動かす prompt になる。
- subagent は main conversation history に access しない。
- 結果は main conversation に summary として戻る。

適用条件:

- explicit instructions / actionable task がある Skill に使う。
- guidelines だけの Skill に `context: fork` を付けると、subagent は実行すべき task を持たず有意な output を返しにくい。

`context: fork` の関係:

| Approach | System prompt | Task | Also loads |
|---|---|---|---|
| Skill with `context: fork` | `agent` type | SKILL.md content | CLAUDE.md |
| Subagent with `skills` field | subagent markdown body | delegation message | preloaded skills + CLAUDE.md |

`agent`:

- built-in `Explore`, `Plan`, `general-purpose`
- custom subagent from `.claude/agents/`
- omitted の場合 `general-purpose`

## 20. Restrict Claude's skill access

Claude は既定で、`disable-model-invocation: true` がない Skill を invoke できる。さらに built-in commands の一部も Skill tool 経由で利用できる。

制御方法:

1. すべての Skill を deny:

```text
Skill
```

2. specific skills を allow / deny:

```text
Skill(commit)
Skill(review-pr *)
Skill(deploy *)
```

syntax:

- `Skill(name)` exact match
- `Skill(name *)` argument prefix match

3. individual skill を hidden:

```yaml
disable-model-invocation: true
```

注意:

- `user-invocable` は menu visibility だけ。
- programmatic invocation を止めるには `disable-model-invocation: true` または permissions を使う。

## 21. Override skill visibility from settings

`skillOverrides` は skill 自身の frontmatter を編集せず visibility を settings から制御する。

| Value | Listed to Claude | `/` menu |
|---|---|---|
| `"on"` | name and description | Yes |
| `"name-only"` | name only | Yes |
| `"user-invocable-only"` | Hidden | Yes |
| `"off"` | Hidden | Hidden |

例:

```json
{
  "skillOverrides": {
    "legacy-context": "name-only",
    "deploy": "off"
  }
}
```

補足:

- absent from `skillOverrides` は `"on"` と扱われる。
- shared project repo や MCP server provided Skill のように `SKILL.md` を編集したくない場合に使う。
- `/skills` menu から state を cycle し、`.claude/settings.local.json` に保存できる。
- plugin skills は `skillOverrides` の対象外。`/plugin` で管理する。

## 22. Share skills

配布方法:

- Project skills: `.claude/skills/` を version control に commit。
- Plugins: plugin の `skills/` directory に入れる。
- Managed: organization-wide managed settings で deploy。

## 23. Generate visual output

Skill は script を bundle して任意言語で実行できる。visual output の例では、interactive HTML を生成し browser で開く script を bundle している。

設計ポイント:

- script path には `${CLAUDE_SKILL_DIR}` を使う。
- personal / project / plugin level のどこに install されても path が解決される。
- `allowed-tools: Bash(python3 *)` のように script 実行を pre-approve できる。
- script は `scripts/` 配下に置き、`SKILL.md` は実行入口と output contract（契約） に集中する。

## 24. Troubleshooting

### Skill not triggering

確認:

- `description` の key use case が先頭にあるか。
- trigger phrase が実際の user request と一致しているか。
- `disable-model-invocation: true` で自動 invocation を止めていないか。
- `paths` が現在作業 file と match しているか。
- Skill が discovery 対象 directory にあるか。
- new top-level skills directory 作成後に session restart したか。

### Skill triggers too often

確認:

- `description` が広すぎないか。
- `when_to_use` で境界条件を書けないか。
- `paths` で対象 file pattern を絞れないか。
- `skillOverrides` の `"name-only"` / `"user-invocable-only"` / `"off"` を使うべきか。

### Skill descriptions are cut short

原因:

- `description` + `when_to_use` は skill listing で 1,536 文字 cap。

対策:

- key use case を先頭へ置く。
- trigger phrase を絞る。
- 手順や output format は本文へ移す。

## 25. スキル設計への公式仕様チェックリスト

- [ ] Skill directory は discovery される場所にある。
- [ ] `SKILL.md` が directory root にある。
- [ ] `description` は trigger 条件として機能する。
- [ ] `description` + `when_to_use` は 1,536 文字 cap を意識している。
- [ ] `disable-model-invocation` と `user-invocable` の意味を混同していない。
- [ ] dangerous workflow は manual trigger または permission deny で守っている。
- [ ] `allowed-tools` を deny と誤認していない。
- [ ] supporting files は `SKILL.md` から案内されている。
- [ ] `SKILL.md` は 500 行未満を目安に保っている。
- [ ] dynamic injection の command output が巨大・秘密情報・非決定論に寄りすぎていない。
- [ ] `context: fork` は explicit task のある Skill にだけ使っている。
- [ ] subagent preload したい Skill に `disable-model-invocation: true` を付けていない。
- [ ] settings の `skillOverrides` と frontmatter visibility が矛盾していない。


## 公式項目から設計判断への対応（追加）

以下は `15-official-source-notes.md` の対応表を補完する追加エントリ。

| 公式項目 | 反映先 | 設計判断 |
|---|---|---|
| frontmatter 全項目 | `skill-schema.json` | JSON Schema Draft-07 として機械検証可能に形式化。16章 §10 の公式 15 項目に、プロジェクト独自 metadata 11 項目を加えて `properties` に収録 |
