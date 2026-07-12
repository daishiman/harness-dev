# 05. Layering: Skill / Subagent / Hook / MCP / CLI / API

## 基本原則

Skill は道具そのものではなく、道具の使い方を書くメタ層である。

## 責務分離表

| 層 | 責務 | 向いていること | 避けること |
|---|---|---|---|
| Skill | 使い方・知識・手順を書く | 運用プレイブック、判断基準、複数手段の使い分け | 決定論的検査の実装 |
| Subagent | 別コンテキストで作業する | 調査、評価、長い作業、初見レビュー | 単なる知識注入、worker 同士の協調 |
| Agent Team | 複数 Claude Code session を協調させる | 複数視点レビュー、競合仮説検証、独立 file ownership の並列作業 | sequential task、same-file edit、依存過多 |
| Hook | lifecycle event で自動実行 | LLM 判断に任せない強制、permission evaluation | 文脈判断 |
| MCP | agent 向け tool/resource/prompt | schema 付き外部接続、クラウド agent | チーム固有の運用判断だけを書く |
| CLI | shell から呼ぶ実装道具 | git/gh/rg/jq、自作 app、再現可能処理 | 文脈依存の判断 |
| API/SDK | プログラムから呼ぶ実装道具 | 内製サービス、SDK wrapper | エージェント向け手順説明 |

## Skill を作る前の決定木

1. 決定論で組めるか。
2. Yes なら Hook / CI / CLI / MCP / API へ寄せる。
3. No なら、文脈依存の判断か。
4. 独立コンテキストが必要か。
5. worker 同士の直接 communication / shared task list が必要なら Agent Team。
6. 独立 context だけでよいなら Subagent。
7. 同一文脈で十分なら Skill。

## 高級リンターにしない

次は Skill ではなく決定論に寄せる。

- lint
- format
- schema validation
- 禁止語チェック
- static file existence check
- frontmatter consistency check
- `pair:` missing check
- deployment precondition that can be scripted

Skill は「なぜその検査を使うか」「結果をどう扱うか」に集中する。

## 依存方向の原則

Skill 群は Clean Architecture（依存方向を守る設計）と同じく、依存方向を一方向に保つ。

```text
run-* / assign-* workflow
  -> ref-* / references/ policy
  -> scripts/ CLI / Hook / CI
  -> external API / filesystem
```

逆方向の依存は禁止する。`ref-*` は `run-*` を呼ばない。CLI は Skill を知らず、入力ファイルと設定だけを読む。Hook / CI は policy を強制するが、業務判断を自然言語で行わない。

| 層          | j依存してよい先                                 | 禁止                        |
| ---------- | ---------------------------------------- | ------------------------- |
| `run-*`    | `ref-*`, `assign-*`, `scripts/`, MCP/CLI | 他の `run-*` への暗黙依存         |
| `assign-*` | artifact, rubric, `scripts/`             | generator の会話履歴、rubric 編集 |
| `ref-*`    | 公式 docs、社内規約、domain dictionary           | workflow 実行、副作用           |
| `scripts/` | input file、config、schema                 | LLM 文脈、Skill 名のハードコード     |
| Hook / CI  | scripts、policy config                    | 文脈依存の曖昧判断                 |

この方向を守ると、評価基準や実行基準を後から追加しても循環依存が起きにくい。

## 実装層の昇華ラダー

| 段階 | 内容 | 例 | Skill 本文 |
|---:|---|---|---|
| 1 | 既存 CLI | `git`, `gh`, `rg`, `jq` | CLI の順序と team policy |
| 2 | 薄い script | `scripts/check.sh` | script をいつ叩くか |
| 3 | 自作 CLI | `mytool deploy --env staging` | 目的ベース API の使い方 |
| 4 | 自作 CLI + 既存 CLI | `mytool | jq | gh` | workflow orchestration |

上へ行くほど実装コストは増えるが、Skill 本文は薄くなる。

## macOS デフォルト前提の言語選定

`scripts/` 配下の実装は **macOS に最初から入っている処理系だけ** で完結させる。`brew install` / `npm install` / `pip install` を前提にしない。理由は配布性: 「人によって動かない」を排除するため。

| 言語 | macOS 同梱 | 採否 | 用途 |
|---|---|---|---|
| Bash 3.2 (`/bin/bash`) | ✅ 標準 | **第一候補** | 段階 1〜2。既存 CLI orchestration、決定論チェック、50 行以内の pipeline |
| Python 3 (`/usr/bin/python3`、Xcode CLT 同梱) | ✅ 標準 | **補助** | 段階 3。JSON/YAML の構造書換、100 行超、stdlib のみ (`json`, `pathlib`, `subprocess`, `argparse`, `re`, `urllib`) |
| TypeScript / Node.js | ❌ 非同梱 | **不採用** | Node を別途 install する前提になり配布性を損なうため |

判定フロー:

1. 既存 CLI (`git` / `gh` / `rg` / `jq` / `yq` / `curl`) を呼ぶだけで済むか → Bash。
2. JSON/YAML を構造的に書き換える、正規表現を超える文字列処理、または 100 行を超えそうか → Python 3。
3. 追加 package が必要か → 設計を見直して stdlib + 既存 CLI に戻す。

Shebang 規約:

- Bash: `#!/usr/bin/env bash` + `set -euo pipefail`
- Python: `#!/usr/bin/env python3` (※ `python` は macOS に存在しないため `python3` 固定)

Skill 本文側からは `bash scripts/xxx.sh` / `python3 scripts/xxx.py` と interpreter を明示する。PATH と実行権限の差異を吸収するため。

## CLI と MCP の関係

CLI と MCP は対立しない。どちらも道具であり、Skill が状況に応じて使い分ける。

CLI が向く:

- local shell がある
- 既存 CLI が強い
- human reproducibility が重要
- bash pipeline が効く
- token cost を抑えたい

MCP が向く:

- shell がない cloud agent
- team に CLI を配布したくない
- schema 付き tool が必要
- browser / SaaS / DB など agent-friendly interface が必要

## MCP を選ぶ判断

MCP が必要な場合:

- shell がない環境
- 各自に CLI を書かせたくない
- tool schema を強くしたい
- resource / prompt も一緒に渡したい
- 外部 system を agent-friendly な意味単位に包みたい

API そのものを MCP に露出するだけでなく、操作・参照・型 prompt を agent が扱いやすい粒度へ設計する。

## MCP / CLI / API 統合の実装パターン

「どれを選ぶか」だけでは Skill 本文から実装層を呼び出せない。ここでは 3層それぞれの最小実装例と、Skill からの呼び出し方を示す。共通ルールは「Skill → CLI/MCP/API の一方向依存」。逆向き（CLI が Skill 名をハードコードする、MCP server が Skill 本文をパースする等）は禁止。

### CLI 層

適用条件:

- local shell がある（Claude Code, codex 等）。
- 決定論的に挙動し、終了コード・stdout が再現可能。
- `which <tool>` で PATH 上に存在することが保証できる。

最小実装例（`scripts/check-frontmatter.sh`）:

```bash
#!/usr/bin/env bash
set -euo pipefail
file="$1"
yq '.name, .description' "$file" >/dev/null || { echo "missing keys" >&2; exit 2; }
```

Skill 本文からの呼び出し例（Bash tool）:

```text
1. `bash scripts/check-frontmatter.sh SKILL.md` を実行する。
2. exit 0 ならば次フェーズ。exit 2 ならば「frontmatter修正」サブタスクに分岐する。
```

フォールバック: CLI が存在しない場合は `command -v` で検出し、`ref-*/manual-check.md` の手順を読み込む（後述の動的注入と組合せ）。

### MCP 層

適用条件:

- shell が無い環境（cloud agent, browser-based agent）。
- 複数 Skill から同じ外部 service を schema 付きで叩きたい。
- resource (file-like) や prompt template も配布したい。

最小実装例（stdio server frontmatter, `mcp-servers/notion.json`）:

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@notionhq/mcp-server"],
      "env": { "NOTION_TOKEN": "${NOTION_TOKEN}" }
    }
  }
}
```

server 側 tool 定義（抜粋）:

```yaml
name: notion-fetch
description: Fetch a Notion page as markdown
inputSchema:
  type: object
  properties:
    page_id: { type: string }
  required: [page_id]
```

Skill 本文からの参照:

```text
- Notion 仕様を取得するには `mcp__notion__notion-fetch` を `page_id` 指定で呼ぶ。
- 戻り値 markdown は `references/cache/notion-<id>.md` に保存して再利用する。
```

一方向依存: MCP server は Skill の存在を知らない。Skill 側だけが tool 名を参照する。
フォールバック: tool が unavailable な場合は CLI 層（`curl + jq`）に降格し、最終手段として「ユーザに手動取得を依頼」する。

### API / SDK 層

適用条件:

- 外部 HTTP / gRPC / 公式 SDK を直接叩くのが最短。
- 認証は `settings.json` の `env` や OS keychain で保持する。
- token cost や latency を skill 本文に書いて運用可能。

最小実装例（`scripts/openai-embed.py`、macOS 同梱 `python3` の stdlib だけで完結）:

```python
#!/usr/bin/env python3
import json, os, sys, urllib.request

req = urllib.request.Request(
    "https://api.openai.com/v1/embeddings",
    data=json.dumps({
        "model": "text-embedding-3-small",
        "input": sys.argv[1],
    }).encode(),
    headers={
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    },
)
with urllib.request.urlopen(req) as res:
    body = json.load(res)
sys.stdout.write(json.dumps(body["data"][0]["embedding"]))
```

`settings.json` 抜粋:

```json
{
  "env": { "OPENAI_API_KEY": "${env:OPENAI_API_KEY}" },
  "permissions": { "allow": ["Bash(python3 scripts/openai-embed.py:*)"] }
}
```

Skill 本文からの呼び出し例:

```text
1. 入力テキストを `python3 scripts/openai-embed.py "<text>"` に渡し JSON を受ける。
2. 失敗時（exit != 0 もしくは HTTP 5xx）は MCP 層の `embeddings.create` ツールに切替える。
```

一方向依存: API client は Skill 名を含めない。Skill 側で client を選択する。
フォールバック: 5xx / rate-limit → 指数バックオフ 3回 → MCP fallback → ユーザ通知。

### 動的注入と組合せた一例（14章連携）

「外部リソースを読みに行く」場合、Skill 本文に手順だけを置き、リソース本体は実行時に注入する。

```text
1. `mcp__notion__notion-fetch page_id=<X>` でページ markdown を取得。
2. 取得結果を `references/dynamic/notion-<X>.md` に書き出す。
3. 14章「動的注入」に従い、当該 markdown を次フェーズの context に追加する。
4. フェッチ失敗時は CLI 層 (`curl ... | pandoc`) にフォールバック。
```

これにより Skill 本文は「層の選択順序」と「成果物の置き場所」だけを規定し、リソース取得そのものは MCP/CLI/API 層に委譲される。

## Agent Team を選ぶ判断

Agent Team は Subagent より重い。次の条件を満たす場合に限定する。

| 条件 | 判断 |
|---|---|
| 複数視点が必要 | parallel review / competing hypotheses に向く |
| worker 同士が情報共有・反論する必要がある | Agent Team |
| file ownership を分けられる | Agent Team 可 |
| same-file edits が多い | Agent Team 不向き |
| dependency が直列 | single session / Subagent |
| routine task | single session |

公式上の運用目安:

- 3〜5 teammates から始める。
- 5〜6 tasks / teammate 程度に抑える。
- teammate は lead conversation history を継承しないため、spawn prompt に task-specific context を明記する。
- lead は 1 team だけ管理できる。nested teams は不可。
