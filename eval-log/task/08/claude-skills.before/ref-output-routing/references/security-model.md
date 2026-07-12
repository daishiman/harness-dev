# Security Model: APIキー管理

## 原則

1. **API key は Claude (LLM) context に絶対に乗せない**
2. **リポジトリ配下の任意のファイルに key を平文保存しない** (`.env` も禁止)
3. **macOS Keychain を唯一の信頼境界とする**
4. **adapter scriptが subprocess内で key を取得し、HTTP呼出しに直接使う**

## データフロー

```
[Keychain] ─security CLI─→ [adapter subprocess env]
                                      │
                                      ├─→ HTTP API
                                      │
                                      └─→ stdout (statusのみ、keyは含まず)
                                              │
                                              ▼
                                          [Claude]
```

Claude は adapter の **stdout (JSON status)** しか見ない。
key は subprocess の境界を越えない。

## やってはいけない経路

| ❌ NG パターン | 理由 |
|---------------|------|
| Claude が `security find-generic-password -w ...` を Bash 直実行 | stdout に key が出てcontextに乗る |
| `.env` や config JSON に key を平文保存 | リポジトリ・バックアップ・git履歴に残る |
| HTTP error response を adapter stdout にそのまま出力 | error body に key が混入する可能性 |
| `echo "Authorization: Bearer $KEY"` 等のdebug | shell history に残る |
| `subprocess.run(..., capture_output=True)` の stdout を rawで Claudeに返す | sanitize忘れリスク |

## OK パターン

### adapter内部での取得 (Python例)
```python
import subprocess, os, json, sys

def get_secret(service: str, account: str) -> str:
    """Keychainからsecret取得。stdoutには出さない。"""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    secret = get_secret("{{SECRET_NAMESPACE}}-notion", "api-token")
    # HTTP call使用、secretは関数外へ漏らさない
    response = http_post(url, headers={"Authorization": f"Bearer {secret}"}, json=payload)
    # secret変数はスコープ外で破棄
    
    # stdoutにはstatusのみ
    print(json.dumps({"status": "success", "location": response["url"]}))
```

### エラー処理 (sanitize)
```python
try:
    response = http_post(...)
except Exception as e:
    # エラーメッセージから secret を除去
    sanitized = sanitize_error(str(e), secrets=[secret])
    print(json.dumps({"status": "failure", "errors": [sanitized]}), file=sys.stdout)
    sys.exit(1)
```

## Keychain 登録手順 (1回のみ)

```bash
# Notion API token
security add-generic-password \
  -s {{SECRET_NAMESPACE}}-notion \
  -a api-token \
  -w <YOUR_NOTION_TOKEN>

# Slack webhook URL
security add-generic-password \
  -s {{SECRET_NAMESPACE}}-slack \
  -a webhook-url \
  -w <YOUR_WEBHOOK_URL>

# 一覧確認
security dump-keychain | grep "{{SECRET_NAMESPACE}}"
```

## output-routing.json内の参照記法

API key本体ではなく **参照のみ** を記載:

```json
{
  "routes": {
    "task-spec": {
      "adapter": "notion",
      "params": {
        "database_id": "abc123",
        "token_ref": "keychain:{{SECRET_NAMESPACE}}-notion/api-token"
      }
    }
  }
}
```

adapter scriptが `keychain:{{SECRET_NAMESPACE}}/<account>` 形式を解釈してKeychainから取得。

## permissions設定

`.claude/settings.local.json` で `security find-generic-password -w` の直接実行を許可しない。Claude/Skill が Bash tool で secret を読む経路は、stdout に secret が出て context 漏洩するため禁止する。

許可するのは `dispatch.py` または個別adapterの実行であり、Keychain読取りは adapter subprocess 内に閉じ込める。

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 scripts/adapters/dispatch.py:*)",
      "Bash(python3 scripts/adapters/sink_*.py:*)"
    ],
    "deny": [
      "Bash(security find-generic-password:*)",
      "Bash(security dump-keychain:*)",
      "Bash(security delete-generic-password:*)"
    ]
  }
}
```

## 監査

- `scripts/secrets/audit_secret_leak.py`: output-routing.json/adapter-registry.json/adapter scripts を grep し、key パターン (sk-*, Bearer *, AKIA*) の混入を検出
- pre-commit hook で実行推奨
