---
name: cloudflare-email-service
description: Cloudflare Email Service（Email Sending + Email Routing）でトランザクションメールの送受信を実装するスキル。Workers bindingまたはREST APIによるメール送信、Email Routing、Agents SDKのemail handler、Workers・Node.js・Python・Go等への組み込みで使う。到達性、SPF/DKIM/DMARC、wrangler email設定、MCP email tools、coding agentからのメール送信も対象。「Workerにメール機能を追加」のような依頼でも、重要な設定要件があるため必ず使用する。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Cloudflare Email Service

Cloudflare Email Service、Email Routing、Email Sendingの仕様は更新されるため、すべての関連タスクで**事前知識より最新情報の取得を優先する**。

Cloudflare Email Serviceは、Cloudflare platform上でトランザクションメールを送信し、受信メールをroutingする。変更の速い製品なので、必ず現行仕様を取得してから進める。

**本Skillと以下の一次情報が食い違う場合は、必ず一次情報を正とする。** Cloudflare docs、REST API spec、`@cloudflare/workers-types`、Agents SDK repoが正本であり、本Skillは作業開始用のガイドである。

Accountを伴うドメイン有効化やAPI操作の前には、Skill `cloudflare`で対象Accountを確定する。Wrangler CLIを実行するときはSkill `wrangler`の現行commandと安全規律に従う。本Skill内でAccount選択やWrangler共通規律を再定義しない。

## 最新情報の取得先

正本は [`cloudflare` Skill の「最新情報の取得先」](../cloudflare/SKILL.md#最新情報の取得先)(docs MCP 第一手段、不通時の復旧、workers-types / config-schema の取得方法)。ここには本Skill固有の取得先だけを書く。

| 取得先 | 取得方法 | 使う場面 |
|--------|----------|---------|
| **Cloudflare docs (MCP)** | `cloudflare-docs` MCPで `email-service` / `email routing` / `send_email` を検索 | **既定の第一手段**。API reference、上限、価格、最新機能 |
| Email Service docs (Web) | `https://developers.cloudflare.com/email-service/` | MCP不通時 |
| REST API spec | `https://developers.cloudflare.com/api/resources/email_sending` | Email Sending REST APIのOpenAPI spec |
| Agents SDK docs | `https://github.com/cloudflare/agents/tree/main/docs`の`docs/email.md`を取得 | Agents SDKのemail handling |

## 最初に前提条件を確認する

メール処理コードを書く前に、次の3点を確認する。

1. **ドメインが有効化済みか**: `pnpm wrangler email sending list`でEmail Sendingが有効なドメインを確認する。対象ドメインがなければ`pnpm wrangler email sending enable userdomain.com`を使うか、詳細を[cli-and-mcp.md](references/cli-and-mcp.md)で確認する。
2. **Bindingが設定済みか**: Workersでは`wrangler.jsonc`に`send_email`があるか確認する。
3. **`postal-mime`が必要か**: メールの受信・解析を行う場合だけ`pnpm ls postal-mime`で確認する。

## 要件から実装方式を選ぶ

次の表から要件に合う経路を1つ選び、対応するreferenceだけを読む。

| やりたいこと | 実装経路 | Reference |
|--------------|------|-----------|
| **Cloudflare Workerからメールを送る** | Workers binding（API key不要） | [sending.md](references/sending.md) |
| **[Cloudflare Agents SDK](https://developers.cloudflare.com/agents/)のAI agentからメールを送る** | Agent classの`onEmail()` + `replyToEmail()` | [sending.md](references/sending.md) |
| **外部アプリやagentからメールを送る**（Node.js、Go、Python等） | Bearer tokenを使うREST API | [rest-api.md](references/rest-api.md) |
| **coding agentからメールを送る**（Claude Code、Cursor、Copilot等） | MCP tools、wrangler CLI、またはREST API | [cli-and-mcp.md](references/cli-and-mcp.md) |
| **受信メールを処理する**（Email Routing） | Workers `email()` handler | [routing.md](references/routing.md) |
| **Email Sending / Email Routingを有効化する** | `wrangler email sending enable` / `wrangler email routing enable`、またはDashboard | [cli-and-mcp.md](references/cli-and-mcp.md) |
| **到達性を改善し迷惑メールフォルダを避ける** | authentication、content、compliance | [deliverability.md](references/deliverability.md) |

## 最短実装 — Workers Binding

`wrangler.jsonc`にbindingを追加し、`env.EMAIL.send()`を呼ぶ。`from`のドメインは事前に`pnpm wrangler email sending enable yourdomain.com`で有効化しておく。

```jsonc
// wrangler.jsonc
{ "send_email": [{ "name": "EMAIL" }] }
```

```typescript
const response = await env.EMAIL.send({
  to: "user@example.com",
  from: { email: "welcome@yourdomain.com", name: "My App" },
  subject: "Welcome!",
  html: "<h1>Welcome!</h1>",
  text: "Welcome!",
});
```

WorkersではAPI keyが不要なbindingを推奨する。利用者がWorker内からREST APIを使う理由を明示した場合（既存のAPI token workflowを使う等）は、[rest-api.md](references/rest-api.md)に従ってREST APIも利用できる。

完全なAPI、batch send、attachment、custom header、restricted binding、Agents SDK integrationは[sending.md](references/sending.md)を読む。

## 最短実装 — REST API

Workers以外のアプリ、または利用者が明示的にREST APIを指定したWorkersで使う。Workers bindingとの主な違いは次のとおり。

- Endpoint: `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/email/sending/send`
- `from` objectは`email`ではなく`address`を使う: `{ "address": "...", "name": "..." }`
- `replyTo`は`reply_to` (snake_case)
- Responseは`{ delivered: [], permanent_bounces: [], queued: [] }`を返す（`messageId`ではない）

curl例、response format、error handlingは[rest-api.md](references/rest-api.md)を読む。

## よくある間違い

| 間違い | 原因 | 対処 |
|---------|---------------|-----|
| wrangler configに`send_email` bindingがない | Email ServiceはAPI keyではなくbindingを使う | `wrangler.jsonc`に`"send_email": [{ "name": "EMAIL" }]`を追加 |
| 未検証domainから送信する | 初回送信前にEmail Sendingへのdomain登録が必要 | `wrangler email sending enable userdomain.com`を実行、またはDashboardで有効化 |
| email handlerで`message.raw`を2回読む | raw streamは1度しか読めず、2回目は空になる | 最初にbuffer化: `const raw = await new Response(message.raw).arrayBuffer()` |
| `text` fieldがない（HTMLのみ） | plain textしか表示しないclientがあり、spam scoreにも影響する | `html`と`text`を必ず両方用意 |
| marketing/bulk sendに使う | Email Serviceはtransactional email用 | newsletterやcampaignは専用marketing email platformを使う |
| 未検証の宛先へforwardする | `message.forward()`は検証済みaddressに限定 | `wrangler email routing addresses create user@gmail.com`またはDashboardで追加 |
| 架空addressでテストする | 存在しないaddressからのbounceでsender reputationが下がる | 開発中も自分が管理する実addressを使う |
| API tokenをソースコードに直書きする | commitされて漏えいする | environment variableまたはCloudflare secretsを使う |
| `from` domain要件を無視する | `from`はEmail Serviceに登録済みのdomainである必要がある | domainを先に検証し、`anything@that-domain.com`から送信 |
| REST APIの`from`で`email` keyを使う | REST APIは`email`ではなく`address`を使う | RESTは`{ "address": "...", "name": "..." }`、Workersは`{ "email": "...", "name": "..." }` |
| REST APIで`replyTo`を使う | REST APIのfieldはsnake_case | REST APIは`reply_to`、Workers bindingは`replyTo` |

## 詳細リファレンス

要件に対応するreferenceだけを読む。すべてを一度に読み込まない。

- **[references/sending.md](references/sending.md)** — Workers binding API、attachment、Agents SDK email。WorkersまたはAgents SDKで使う。
- **[references/rest-api.md](references/rest-api.md)** — REST endpoint、curl例、error handling。Workers以外のアプリで使う。
- **[references/routing.md](references/routing.md)** — 受信用`email()` handler、forward、reply、parse。
- **[references/cli-and-mcp.md](references/cli-and-mcp.md)** — Domain setup、wrangler command、MCP tools。初回設定で使う。
- **[references/deliverability.md](references/deliverability.md)** — SPF/DKIM/DMARC、bounce、suppression、best practices。

## 完了報告

実装・検証後は、次の順で日本語の報告を返す。

1. **できるようになったこと**（送信 / 受信 / routing / 到達性のどれか）
2. **採用した経路**（Workers binding / REST API / Email Routing / MCP tools）
3. **確認したこと**（domain有効化、binding、実送受信、error handling）
4. **利用者に残る操作**（Dashboard操作やdomain検証がある場合のみ）

token、secret、完全なAccount IDは報告に含めない。
