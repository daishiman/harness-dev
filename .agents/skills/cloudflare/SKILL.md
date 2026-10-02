---
name: cloudflare
description: Cloudflare全体の製品選択と対象Accountの文脈を確定するルータースキル。Workers、Pages、KV、D1、R2、Workers AI、Vectorize、Agents SDK、Flagship、Tunnel、WAF、Terraform等のどの製品・参照・専用Skillを使うか判断する。Cloudflare要件が複数製品にまたがる、製品名が未確定、Accountの選択が必要な場合に使う。Wrangler操作、Durable Objects、Turnstile、Email Service、Workersコード、本番デプロイは責務表の専用Skillへ委譲し、本Skillで実行手順を重複定義しない。数値・API・設定は記憶よりCloudflare公式ドキュメントの取得を優先する。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Cloudflare製品選択ルーター

Cloudflareの要件を実装する前に、以下の判断木で対象製品を1つ以上確定し、専用Skill・同梱reference・`cloudflare-docs` MCPのいずれか1つだけを読み込む。本Skillの責務は「何を使うか」と「どのAccountを使うか」の確定までであり、個別製品の実行手順は専用Skillに委譲する。

CloudflareのAPI、型、上限、価格は更新される。**事前知識より最新情報の取得を優先する**。同梱referenceは既定スタックと要件フラグ経由の製品に絞ってあり、それ以外の製品仕様は`cloudflare-docs` MCPで取得する。同梱referenceも探索の起点であり、最新仕様の正本ではない。

## 最新情報の取得先

具体的な数値、APIシグネチャ、設定オプションを記載・実装する前に、必ず最新情報を取得する。事前知識や同梱referenceだけで確定しない。

**第一手段は `cloudflare-docs` MCP**(認証不要、`https://docs.mcp.cloudflare.com/mcp`)。本Skillが同梱するreferenceは、キット既定スタック(Workers / D1 / R2 / KV とそのbinding)と、要件フラグ経由で確実に使う製品(Queues / Workflows / Vectorize)だけに絞ってある。**それ以外のCloudflare製品のreferenceは同梱していない**。判断木で製品を確定したら、その製品名でdocs MCPを検索する。

| 取得先 | 取得方法 | 使う場面 |
|--------|----------------|---------|
| **Cloudflare docs (MCP)** | `cloudflare-docs` MCPで製品名・API名を検索 | **既定の第一手段**。上限、価格、API reference、compatibility dates/flags、および同梱referenceのない全製品 |
| Cloudflare docs (Web) | `https://developers.cloudflare.com/<product>/` を取得 | docs MCPが使えないときの代替 |
| Workers types | `pnpm pack @cloudflare/workers-types`または`node_modules`を確認 | 型シグネチャ、binding形状、handler型 |
| Wrangler config schema | `node_modules/wrangler/config-schema.json` | 設定フィールド、binding形状、許容値 |
| Product changelogs | `https://developers.cloudflare.com/changelog/` | 上限、機能、廃止予定の最新変更 |

同梱referenceは探索の起点であり、最新仕様の正本ではない。referenceと公式docsが食い違う場合は**公式docsを正とする**。特に数値上限、pricing tier、型シグネチャ、設定オプションは必ずdocs MCPで再取得する。

MCP の配置 scope と Cloudflare OAuth の認可 scope は別物であり、`cloudflare-docs` は認証不要、Bindings 等は**そのcapabilityを初めて使う時だけ対象1件を認可**する。詳細と MCP 不通時の復旧(未登録 / 不通 / legacy sse / scope 衝突)は `skills/wrangler/references/mcp-vs-cli-routing.md` が唯一の正本。docs MCP が使えないときの手順は下記「docs MCPに接続できないとき」。

## 専用Skillとの責務分担

次の領域は本Skillで実行手順を展開せず、対応する専用Skillをロードする。Account文脈が必要な場合は、本Skillで確定した結果を委譲先へ渡す。

| 要件・作業 | 責務を持つSkill | 本Skillが行うこと |
|---|---|---|
| Wrangler CLIのコマンド、設定、トラブルシュート | `wrangler` | 対象製品とAccount文脈の確定のみ |
| Durable Objectsの設計・実装・テスト | `durable-objects` | Durable Objectsを選ぶべきかの判断のみ |
| Turnstile / CAPTCHA / bot対策 | `turnstile-spin` | Turnstileを選定しAccount文脈を渡す |
| Email Sending / Email Routing / deliverability | `cloudflare-email-service` | Email領域へのルーティングのみ |
| Workersコードの作成・レビュー | `workers-best-practices` | Workersの採用判断と関連製品の選定のみ |
| 本番デプロイ、D1 migration、secret、セキュリティ設定 | `cloudflare-secure-deploy` | 対象Accountと利用製品の確定のみ |

委譲先で MCP と wrangler CLI のどちらを使うかは `skills/wrangler/references/mcp-vs-cli-routing.md` の「作業別の既定経路」に従う(仕様の確認と調査は MCP、deploy / secret / migration は CLI 既定)。本Skillでは経路表を複製しない。

上記以外の製品は、本Skillの判断木で確定したうえで、同梱referenceがあればそれだけを読み、なければ`cloudflare-docs` MCPで検索する。別の専用Skillがあるのに、本Skill内の似たreferenceと両方を実行手順として読み合わせない。

## Account文脈の正本

Cloudflareのcreate/update/delete、secret、migration、deployの前に、[Account文脈の自動検出](references/account-context.md)を実行する。特定のrepository名、利用者名、Account名、Account IDを既定値として埋め込まない。

利用者へ最初からAccount情報を尋ねない。プロジェクト設定とread-onlyなCloudflare照合からAccount候補と既存resourceの所有先を自動検出し、次の順で決める。

1. 既存resourceの所有Accountが1つに定まる場合は、そのAccountを自動選択する。
2. 新規projectで既存resourceがない場合は、客観的にチーム用と確認できるAccountを既定推奨する。
3. 根拠が同率の候補が複数残る場合だけ、Account名・種別・一致したresourceを番号付きで示し、番号だけを選んでもらう。

選定結果のmodeは`existing` / `team` / `personal`のいずれかとする。既存resource所有先を選んだ場合は、Account種別を推測せず必ず`existing`にする。`team`既定はresourceが存在しない新規projectだけに適用する。

完全なAccount ID、token、secretはchat、ログ、最終報告、project fileへ出力・保存しない。選択結果はWranglerのdirectory-bound auth profileなど、プロジェクト単位の安全な仕組みで保持する。利用できない場合はsession内だけで扱い、次回は再検出する。CI/CDで資格情報が必要なら`ci-cd-pipeline`へ委譲し、Workers Buildsまたは外部CI/CDを選ぶ。どちらでも資格情報をrepositoryへ値として書かない。

## docs MCPに接続できないとき

判断木で `docs:<name>` に到達したのに `cloudflare-docs` MCP が使えない場合は、次の3段で埋め、どの段で止まったかを報告に残す。

1. **MCP 不通**: `claude mcp list` で状態を確認し、`skills/wrangler/references/mcp-vs-cli-routing.md` の「MCP 不通時の復旧」4分岐に従う。復旧を待たずに次段へ進んでよい。
2. **Web 取得**: `https://developers.cloudflare.com/<product>/` を直接取得する(Codex サンドボックス等でネットワーク不可なら次段へ)。
3. **同梱知識で埋める**: `references/<name>/gotchas.md` と `patterns.md`、`node_modules/wrangler/config-schema.json`(設定フィールド・binding形状)で埋め、確認できなかった数値・API・上限は推測で書かず「未確認」として報告に残す。

## 製品選択の判断木

判断木は「どの製品を選ぶか」を確定するためのものであり、選定後に読む先は2種類しかない。

- `→ references/<name>/` — 同梱referenceを読む(既定スタックと要件フラグ経由の製品のみ)。索引と「MCP で代替可か」は `references/README.md`
- `→ docs:<name>` — **`cloudflare-docs` MCPで `<name>` を検索する**(同梱referenceはない)
- `` → `<skill>` Skill `` — その専用Skillをロードする

### フィーチャーフラグが必要

```
フィーチャーフラグが必要?
└─ 機能のON/OFF、対象条件、割合配信 → docs:flagship
   ├─ Workers内で評価 → Flagship binding (env.FLAGS)
   ├─ Node.js / browserで評価 → OpenFeature SDK (@cloudflare/flagship)
   └─ APIでflagを管理 → Flagship REST API
```

### コードを実行したい

```
コードを実行したい?
├─ エッジで動くサーバーレス関数 → references/workers/
├─ Git連携で公開するフルスタックWebアプリ → docs:pages
│                                            (キット既定はPagesではなくWorkers。
│                                             mvp-first-development §3 を優先する)
├─ 状態を共有する協調処理/リアルタイム → `durable-objects` Skill
├─ 複数段階の長時間ジョブ → references/workflows/
├─ コンテナ実行 → docs:containers
├─ 顧客がコードを公開するマルチテナント → docs:workers-for-platforms
├─ 定期実行 (cron) → docs:cron-triggers
├─ HTTPを変更する軽量なエッジ処理 → docs:snippets
├─ Worker実行イベント（log/observability）の処理 → docs:tail-workers
└─ backend infrastructureまでの遅延を最適化 → docs:smart-placement
```

### データを保存したい

```
ストレージが必要?
├─ Key-value（config、session、cache） → references/kv/
├─ Relational SQL → references/d1/ (SQLite)またはdocs:hyperdrive (既存Postgres/MySQL)
├─ オブジェクト/ファイルストレージ (S3-compatible) → references/r2/
├─ バージョン管理されたファイルツリー（repo、build output、checkpoint） → docs:artifacts
├─ メッセージキュー（非同期処理） → references/queues/
├─ Vector embeddings (AI/semantic search) → references/vectorize/
├─ entity単位の強整合性を持つ状態 → `durable-objects` Skill
├─ シークレット管理 → docs:secrets-store
├─ R2へのstreaming ETL → docs:pipelines
├─ R2上のmanaged Apache Iceberg catalog → docs:r2-data-catalog
├─ Iceberg tableへのserverless SQL analytics → docs:r2-sql
└─ 長期保持の永続キャッシュ → docs:cache-reserve
```

### AI/MLを使いたい

```
AIが必要?
├─ 外部LLM API（既定） → `llm-api-integration` Skill
├─ 推論 (LLMs, embeddings, images) → docs:workers-ai
├─ RAG/search用ベクトルDB → references/vectorize/
├─ 状態を持つAI agent → docs:agents-sdk
├─ AI provider用Gateway（キャッシュ、ルーティング） → docs:ai-gateway
└─ AI search widget → docs:ai-search
```

### ネットワーク/接続が必要

```
ネットワークが必要?
├─ ローカルサービスをインターネットへ公開 → docs:tunnel
├─ TCP/UDP proxy (non-HTTP) → docs:spectrum
├─ WebRTC TURN server → docs:turn
├─ プライベートネットワーク接続 → docs:network-interconnect
├─ ルーティング最適化 → docs:argo-smart-routing
├─ backendまでの遅延を最適化（userまでではない） → docs:smart-placement
└─ real-time video/audio → docs:realtimekit または docs:realtime-sfu
```

### セキュリティ機能が必要

```
セキュリティ機能が必要?
├─ Web Application Firewall → docs:waf
├─ DDoS protection → docs:ddos
├─ botの検出/管理 → docs:bot-management
├─ API保護 → docs:api-shield
├─ CAPTCHA代替 → `turnstile-spin` Skill
└─ 資格情報の漏えい検出 → docs:waf (managed ruleset)
```

### メディア/コンテンツを扱いたい

```
メディア機能が必要?
├─ 画像の最適化/変換 → docs:images
├─ 動画の配信/encoding → docs:stream
├─ browser自動化/screenshot → docs:browser-rendering
└─ third-party script管理 → docs:zaraz
```

### 分析/メトリクスを扱いたい

```
分析が必要?
├─ Cloudflare全製品（HTTP、Workers、DNS等）の横断query → docs:graphql-api
├─ Workersからのcustom high-cardinality metrics → docs:analytics-engine
├─ client-side (RUM)のperformance data → docs:web-analytics
├─ Workers Logsとリアルタイムdebugging → `cloudflare-secure-deploy` Skill
│                                        (wrangler.jsonc の observability 設定と
│                                         head_sampling_rate を含む)
├─ Iceberg data lake（log、event）へのSQL → docs:r2-sql (+ pipelines, r2-data-catalog)
└─ raw logs（外部ツールへのLogpush） → docs:logpush
```

### Infrastructure as Code (IaC)が必要

```
IaCが必要? → docs:pulumi (Pulumi)、docs:terraform (Terraform)、またはdocs:api (REST API)
```

## 同梱referenceの一覧

同梱しているのは次の8製品だけ。**これ以外のCloudflare製品は判断木の`docs:<name>`に従い`cloudflare-docs` MCPで検索する**(公式ドキュメントに載っている製品はすべて取得できる)。

| 製品 | Reference | 同梱理由 |
|---|---|---|
| Workers | `references/workers/` | キット既定ランタイム(`mvp-first-development` §3) |
| D1 | `references/d1/` | キット既定DB(同上) |
| R2 | `references/r2/` | キット既定ファイルストレージ(同上) |
| KV | `references/kv/` | キット既定セッション/キャッシュ(同上) |
| Bindings | `references/bindings/` | 上記をWorkersへ接続する共通機構。全アプリで必ず使う |
| Queues | `references/queues/` | 要件フラグ「上記以外のCloudflare機能」で本Skillへ明示ルーティングされる |
| Workflows | `references/workflows/` | 同上 |
| Vectorize | `references/vectorize/` | 同上 |

Account文脈は `references/account-context.md`(本Skill独自。公式docsには存在しない)。

## 選定結果の出力

本Skill自体は製品の実装完了を報告しない。ルーティング完了時に、次の4点を日本語で簡潔に出力し、選定先のSkillまたはreferenceへ引き継ぐ。

1. **選んだCloudflare製品**
2. **選定根拠**（要件のどの部分に対応するか）
3. **使う専用Skillまたはreference**
4. **Account文脈**（`existing` / `team` / `personal`のいずれか。`existing`をteam/personalへ言い換えず、Account IDは表示しない）
