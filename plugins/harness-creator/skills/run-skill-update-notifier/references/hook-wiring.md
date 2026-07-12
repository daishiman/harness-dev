# Hook Wiring (plugin install 時自動配信)

本 Skill の hook は **`plugins/harness-creator/.claude-plugin/plugin.json` の `hooks` フィールドに同梱**されており、`claude plugin install harness-creator` 時に自動配線される。ユーザーが settings.json を手で触る必要はない。

## 配信定義 (harness-creator/plugin.json 抜粋)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": ".*",
        "hooks": [
          { "type": "command", "command": "python3 $CLAUDE_PLUGIN_ROOT/skills/run-skill-update-notifier/scripts/hook-cache-refresh.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          { "type": "command", "command": "python3 $CLAUDE_PLUGIN_ROOT/skills/run-skill-update-notifier/scripts/hook-notify-skill-end.py" }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PLUGIN_ROOT` は plugin install 先ルートを指す公式変数。worktree / symlink でも追従する。

## 無効化

- 環境変数 `HARNESS_SKILLS_NOTIFY=off` で通知のみ抑制 (hook 自体は動くが no-op)
- 完全無効化したい場合は `claude plugin uninstall harness-creator` または plugin manifest から hooks を一時削除

## 設計判断

- `UserPromptSubmit` は **ブロッキングしない** (cache 鮮度確認のみ、24h TTL 以内なら即 return)
- `PostToolUse` matcher は `"Skill"` 限定 (Bash/Read/Edit 等の末尾には通知しない)
- 既存 `hooks.PostToolUse` が他にある場合は配列に追記する (上書き禁止)
- 抑制したいユーザーは shell rc で `export HARNESS_SKILLS_NOTIFY=off` を設定する

## hook スクリプトの責務分離

| script | 役割 | exit |
|---|---|---|
| `hook-cache-refresh.py` | `notifier-check.py --mode cache-status` を呼び stale 時のみ `--mode refresh` 起動 | 0 固定 |
| `hook-notify-skill-end.py` | stdin の hook payload から plugin 名を抽出し `notifier-check.py --mode notify --plugin <name>` を呼ぶ | 0 固定 |

両 hook とも exit 0 固定により Skill 実行を妨げない (graceful degradation の保証点)。
