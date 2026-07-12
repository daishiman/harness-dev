# Skill ライフサイクル

## 発動フロー

1. **Trigger match**: モデルが description の "Use when" 句とユーザー発話を照合
2. **frontmatter load**: YAML headerだけ先に読まれ、`allowed-tools`/`context` を解決
3. **SKILL.md body 展開**: 本文がモデル context に投入される
4. **on-demand load**: 本文内で参照された `references/` や `scripts/` を必要時のみ読む（Progressive Disclosure, 07章）
5. **Tool 実行**: `allowed-tools` 範囲内
6. **Compaction**: 長対話で context を圧縮する際、SKILL.md は要約優先候補

## fork context

- `context: fork` を持つ Skill は **独立な context** で動く
- 親 context を汚染しない → evaluator が採点バイアスを受けない（Goodhart防止、09章）
- STDOUT/return value だけが親へ返る

## hook 連携 (17章)

| event | 例 |
|---|---|
| `PreToolUse` | Bash 実行前にコマンド検査 |
| `PostToolUse` | Write 後に lint 自動実行 |
| `Stop` | 会話終了時 |

Skill は hook と協調可能。`hooks/<event>.py` を Skill 内に置く。

## Subagent / Agent Teams

- Agent Teams: 複数 subagent を協調動作。`agent:` フィールドで指定
- delegate- prefix Skill は thin wrapper、ロジックは subagent 側

## 注意

- frontmatter は invocation 判定で **必ず** 読まれる → description は短く
- 本文 300 行は body のみ。frontmatter 行は数えない
- references/ は遅延ロード → 詰めても本体 token は増えない
