# Secrets Management

## 原則

- API key / token / webhook は **macOS Keychain にのみ保存**
- リポジトリ配下に平文保存しない (`.env` も禁止)
- adapter scriptが subprocess内で取得し、HTTP呼出しに直接使う
- **Claude (LLM) は secret を見ない**

## 登録手順 (1回のみ)

```bash
# 例: Notion API token
security add-generic-password \
  -s harness-notion \
  -a api-token \
  -w "secret_xxxxxxxxxxxxxxxxxxxxxxxx"

# 例: Slack webhook
security add-generic-password \
  -s slack-bot-token.<keychain-prefix> \
  -a webhook-url \
  -w "https://hooks.slack.com/services/..."

# 例: 汎用HTTP API token
security add-generic-password \
  -s harness-metrics \
  -a api-token \
  -w "sk-..."
```

## 命名規則

```
service: harness-<service-name>
account: <secret-purpose>
```

例:
| service | account | 用途 |
|---------|---------|------|
| harness-notion | api-token | Notion Integration token |
| harness-google | oauth-token | Google OAuth token (Sheets/Drive) |
| slack-bot-token.<keychain-prefix> | webhook-url | Slack incoming webhook |
| harness-metrics | api-token | カスタムHTTP API |

## output-routing.jsonでの参照

```json
{
  "params": {
    "token_ref": "keychain:harness-notion/api-token"
  }
}
```

adapter scriptが `keychain:service/account` 形式を解釈し `scripts/secrets/keychain_helper.py` の `get_secret()` で取得。

## 確認

```bash
# 登録済み一覧 (値は表示されない)
security find-generic-password -s harness-notion -a api-token

# 値の確認 (debug時のみ。出力はターミナルにのみ表示しClaudeに見せない)
security find-generic-password -s harness-notion -a api-token -w
```

⚠️ `-w` フラグ付きで Claude Code の Bash tool から実行すると stdout に値が出てしまいます。確認は人間がターミナルで直接行ってください。

## 削除

```bash
security delete-generic-password -s harness-notion -a api-token
```

## 監査

```bash
python3 scripts/secrets/audit_secret_leak.py
```

output-routing.json / adapter-registry.json / adapter scripts を grep し、平文secret混入を検出。

## permissions設定

`.claude/settings.local.json` で許可するBashパターン:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 scripts/adapters/dispatch.py:*)",
      "Bash(python3 scripts/adapters/sink_*.py:*)"
    ],
    "deny": [
      "Bash(security dump-keychain:*)",
      "Bash(security find-generic-password:*)",
      "Bash(security find-generic-password * -w*)",
      "Bash(security delete-generic-password:*)"
    ]
  }
}
```

`security` の直接実行は禁止。adapter scriptが subprocess経由でのみ使用。
