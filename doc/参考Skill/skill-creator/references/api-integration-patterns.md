# API連携パターン

> **読み込み条件**: api-client, webhook, ai-tool タイプのスクリプト設計時
> **相対パス**: `references/api-integration-patterns.md`

---

## 概要

外部APIとの連携パターン集。REST, GraphQL, Webhook, AI APIの実装パターンを提供。

---

## 1. REST API パターン

### 1.1 基本GETリクエスト (Node.js)

```javascript
async function fetchData(url, options = {}) {
  const { headers = {}, timeout = 30000 } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}
```

### 1.2 認証付きPOSTリクエスト (Node.js)

```javascript
async function postWithAuth(url, data, apiKey) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error: ${error}`);
  }

  return await response.json();
}
```

### 1.3 リトライ付きリクエスト (Node.js)

```javascript
async function fetchWithRetry(url, options = {}) {
  const { maxRetries = 3, retryDelay = 1000, ...fetchOptions } = options;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, fetchOptions);

      if (response.status === 429) {
        // Rate limit - 待機してリトライ
        const retryAfter = response.headers.get("Retry-After") || retryDelay;
        await sleep(parseInt(retryAfter) * 1000);
        continue;
      }

      if (!response.ok && attempt < maxRetries) {
        await sleep(retryDelay * attempt);
        continue;
      }

      return response;
    } catch (err) {
      if (attempt === maxRetries) throw err;
      await sleep(retryDelay * attempt);
    }
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

### 1.4 Python版

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session(max_retries=3):
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_data(url, api_key=None, timeout=30):
    session = create_session()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()
```

---

## 2. GraphQL パターン

### 2.1 基本クエリ (Node.js)

```javascript
async function graphqlQuery(endpoint, query, variables = {}, apiKey) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ query, variables }),
  });

  const result = await response.json();

  if (result.errors) {
    throw new Error(result.errors.map(e => e.message).join(", "));
  }

  return result.data;
}

// 使用例
const query = `
  query GetUser($id: ID!) {
    user(id: $id) {
      id
      name
      email
    }
  }
`;

const data = await graphqlQuery(endpoint, query, { id: "123" }, apiKey);
```

### 2.2 ミューテーション (Node.js)

```javascript
async function graphqlMutation(endpoint, mutation, variables, apiKey) {
  return graphqlQuery(endpoint, mutation, variables, apiKey);
}

// 使用例
const mutation = `
  mutation CreateUser($input: CreateUserInput!) {
    createUser(input: $input) {
      id
      name
    }
  }
`;

const result = await graphqlMutation(endpoint, mutation, {
  input: { name: "John", email: "john@example.com" }
}, apiKey);
```

---

## 3. Webhook パターン

### 3.1 Webhook送信 (Node.js)

```javascript
async function sendWebhook(webhookUrl, payload, secret = null) {
  const body = JSON.stringify(payload);
  const headers = {
    "Content-Type": "application/json",
  };

  // 署名付きWebhook
  if (secret) {
    const crypto = await import("crypto");
    const signature = crypto
      .createHmac("sha256", secret)
      .update(body)
      .digest("hex");
    headers["X-Webhook-Signature"] = `sha256=${signature}`;
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers,
    body,
  });

  if (!response.ok) {
    throw new Error(`Webhook failed: ${response.status}`);
  }

  return response;
}
```

### 3.2 Webhook検証 (Node.js)

```javascript
function verifyWebhookSignature(payload, signature, secret) {
  const crypto = require("crypto");
  const expected = crypto
    .createHmac("sha256", secret)
    .update(JSON.stringify(payload))
    .digest("hex");

  return `sha256=${expected}` === signature;
}
```

### 3.3 Slack Webhook (Node.js)

```javascript
async function sendSlackMessage(webhookUrl, message) {
  const payload = {
    text: message.text,
    blocks: message.blocks || undefined,
    attachments: message.attachments || undefined,
  };

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Slack webhook failed: ${await response.text()}`);
  }

  return true;
}

// 使用例
await sendSlackMessage(process.env.SLACK_WEBHOOK_URL, {
  text: "デプロイ完了",
  blocks: [
    {
      type: "section",
      text: { type: "mrkdwn", text: "*デプロイ完了* :rocket:" }
    }
  ]
});
```

---

## 4. AI API パターン

### 4.1 Claude API (Node.js)

```javascript
async function callClaude(prompt, options = {}) {
  const {
    model = "claude-sonnet-4-20250514",
    maxTokens = 1024,
    systemPrompt = "",
  } = options;

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY is required");
  }

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`Claude API error: ${error.error?.message}`);
  }

  const result = await response.json();
  return result.content[0].text;
}
```

### 4.2 Claude CLI (Bash)

```bash
#!/usr/bin/env bash
set -euo pipefail

call_claude() {
  local prompt="$1"
  local output_format="${2:-text}"

  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY is required" >&2
    return 1
  fi

  # Claude CLI使用
  if command -v claude &> /dev/null; then
    echo "$prompt" | claude --print
  else
    # API直接呼び出し
    curl -s https://api.anthropic.com/v1/messages \
      -H "Content-Type: application/json" \
      -H "x-api-key: $ANTHROPIC_API_KEY" \
      -H "anthropic-version: 2023-06-01" \
      -d "{
        \"model\": \"claude-sonnet-4-20250514\",
        \"max_tokens\": 1024,
        \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}]
      }" | jq -r '.content[0].text'
  fi
}

# 使用例
result=$(call_claude "Hello, Claude!")
echo "$result"
```

### 4.3 OpenAI API (Node.js)

```javascript
async function callOpenAI(prompt, options = {}) {
  const {
    model = "gpt-4",
    maxTokens = 1024,
    temperature = 0.7,
  } = options;

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required");
  }

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      temperature,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`OpenAI API error: ${error.error?.message}`);
  }

  const result = await response.json();
  return result.choices[0].message.content;
}
```

---

## 5. エラーハンドリングパターン

### 5.1 統一エラーハンドラー

```javascript
class APIError extends Error {
  constructor(message, statusCode, response) {
    super(message);
    this.name = "APIError";
    this.statusCode = statusCode;
    this.response = response;
  }
}

async function handleAPIResponse(response) {
  if (!response.ok) {
    let errorMessage;
    try {
      const errorBody = await response.json();
      errorMessage = errorBody.error?.message || errorBody.message || response.statusText;
    } catch {
      errorMessage = response.statusText;
    }
    throw new APIError(errorMessage, response.status, response);
  }
  return response;
}

// 使用
try {
  const response = await fetch(url);
  await handleAPIResponse(response);
  const data = await response.json();
} catch (err) {
  if (err instanceof APIError) {
    console.error(`API Error (${err.statusCode}): ${err.message}`);
  } else {
    console.error(`Network Error: ${err.message}`);
  }
}
```

---

## 6. 環境変数パターン

### 6.1 必須環境変数チェック

```javascript
function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    console.error(`Error: 環境変数 ${name} が設定されていません`);
    process.exit(2);
  }
  return value;
}

// 使用
const apiKey = requireEnv("API_KEY");
const apiUrl = process.env.API_URL || "https://api.example.com";
```

### 6.2 .env読み込み (Node.js)

```javascript
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

function loadEnv(envPath = ".env") {
  const fullPath = resolve(process.cwd(), envPath);
  if (!existsSync(fullPath)) return;

  const content = readFileSync(fullPath, "utf-8");
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const [key, ...valueParts] = trimmed.split("=");
    const value = valueParts.join("=").replace(/^["']|["']$/g, "");
    if (key && !process.env[key]) {
      process.env[key] = value;
    }
  }
}

// スクリプト開始時に呼び出し
loadEnv();
```

---

## 関連リソース

- **タイプカタログ**: See [script-types-catalog.md](script-types-catalog.md)
- **ランタイムガイド**: See [runtime-guide.md](runtime-guide.md)
