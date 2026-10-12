# Hook Wiring (plugin install 時自動配信)

本 Skill の hook は **`plugins/harness-creator/hooks/hooks.json` に同梱**されている。`hooks/hooks.json` は
Claude Code が plugin の既定の場所として読むファイルなので、`claude plugin install harness-creator` で
自動配線される (`.claude-plugin/plugin.json` に `hooks` キーは無く、要らない)。ユーザーが settings.json を
手で触る必要はない。

## 配信定義 (harness-creator/hooks/hooks.json の該当 entry 抜粋)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          { "type": "command", "command": "python3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/notify-skill-end.py\"" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": ".*",
        "hooks": [
          { "type": "command", "command": "python3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/cache-refresh.py\"" }
        ]
      }
    ]
  }
}
```

同じ event・matcher には他の hook (例: PostToolUse の `content-review-queue.py`) も並ぶ。正本は
`hooks/hooks.json` そのもので、上はそのうち本 Skill に関わる command だけを抜き出したもの。

`hooks/notify-skill-end.py` と `hooks/cache-refresh.py` は plugin の公開 entry point で、
`os.execv` で本 Skill の `scripts/hook-notify-skill-end.py` / `scripts/hook-cache-refresh.py` に委譲する
(stdin の hook payload と exit code はそのまま渡る)。実処理は Skill 側に置き、plugin 側は 1 hook 1 ファイルの
入口だけを持つ。`$CLAUDE_PLUGIN_ROOT` は plugin install 先ルートを指す公式変数で、`PLUGIN_ROOT` が
設定されていればそちらを優先する。

## 無効化

- 環境変数 `HARNESS_SKILLS_NOTIFY=off` で通知のみ抑制 (hook 自体は動くが no-op)
- 完全無効化したい場合は harness-creator を無効化 / `claude plugin uninstall harness-creator` する。hook は plugin 単位で配線されるので、本 Skill の hook だけを利用者側で外す設定は無い (repo 側で外すなら `hooks/hooks.json` の該当 entry を消す)

## 設計判断

- `UserPromptSubmit` は 24h TTL 以内なら `cache-status` だけで即 return する。stale/absent のときだけ `refresh` を同期で走らせる (timeout 15 秒)。どちらでも exit 0 でプロンプトを止めない
- `PostToolUse` matcher は `"Skill"` 限定 (Bash/Read/Edit 等の末尾には通知しない)
- `PostToolUse` の素の stdout は debug log に行くだけで利用者に見えないので、通知は `systemMessage` を持つ JSON 1 個で出す (表示経路の正本は `output-format.md`)
- `hooks/hooks.json` の `PostToolUse` には他の hook も並ぶ。足すときは配列に追記する (上書き禁止)
- 抑制したいユーザーは shell rc で `export HARNESS_SKILLS_NOTIFY=off` を設定する

## hook スクリプトの責務分離

| script | 役割 | exit |
|---|---|---|
| `hook-cache-refresh.py` | `notifier-check.py cache-status` を呼び stale/absent 時のみ `refresh` 起動 (plugins/ と自 plugin root を絶対パスで渡す) | 0 固定 |
| `hook-notify-skill-end.py` | stdin の hook payload から plugin 名と `session_id` を抽出し `notifier-check.py notify --plugin <name> --session-id=<id>` を呼ぶ (同じ session・同じ plugin は 1 回だけ通知)。通知があれば `{"systemMessage": "<plugin>: <通知>"}` の JSON 1 個を stdout に出す | 0 固定 |

両 hook とも exit 0 固定により Skill 実行を妨げない (graceful degradation の保証点)。
