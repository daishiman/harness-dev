---
name: workers-best-practices
description: Cloudflare Workersのコードを本番運用品質のベストプラクティスに照らして作成・レビューする。新しいWorkerの実装、Workerコードのレビュー、wrangler.jsoncの設定、streaming・floating promises・global state・secrets・bindings・observabilityなどのanti-pattern確認で使用する。事前学習の記憶よりCloudflare公式ドキュメントからの取得を優先する。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Cloudflare Workers ベストプラクティス

Cloudflare WorkersのAPI、型、設定は更新される可能性がある。Workersコードの作成・レビューでは、**事前学習の記憶ではなく最新資料の取得を優先する**。

## 最新情報の取得先

Workersコードを書く・レビューする前に最新版を取得する。API signature、設定field、binding形状を、このSkillに埋め込まれた知識だけで決めない。正本は [`cloudflare` Skill の「最新情報の取得先」](../cloudflare/SKILL.md#最新情報の取得先)(docs MCP 第一手段、不通時の復旧、workers-types / config-schema の取得方法)。ここには本Skill固有の取得先だけを書く。

| 取得先 | 取得方法 | 使う場面 |
|--------|----------|---------|
| **Cloudflare docs (MCP)** | `cloudflare-docs` MCPで `workers best practices` / API名を検索 | **既定の第一手段**。rules、API reference、compatibility dates/flags |
| Workers best practices (Web) | `https://developers.cloudflare.com/workers/best-practices/workers-best-practices/` | MCP不通時。正式なrules、patterns、anti-patterns |
| Workers types の検証手順 | `references/review.md` | 取得した型でbinding access・handler signatureを照合する手順 |

## 最初に最新referenceを取得する

レビューや実装の前に、現在のbest practicesページと必要な型定義を取得する。プロジェクトの`node_modules`が古い場合は、**公開済みの最新版を優先**する。

```bash
# Fetch latest workers types
mkdir -p /tmp/workers-types-latest && \
  pnpm pack @cloudflare/workers-types --pack-destination /tmp/workers-types-latest && \
  tar -xzf /tmp/workers-types-latest/cloudflare-workers-types-*.tgz -C /tmp/workers-types-latest
# Types at /tmp/workers-types-latest/package/index.d.ts
```

## 補足reference

- `references/rules.md` — code examplesとanti-patternsを含む全best practice rules
- `references/review.md` — 型・設定・binding access patternの検証とreview process

## Rules早見表

### 設定

| Rule | 要点 |
|------|------|
| Compatibility date | 新規projectは`compatibility_date`を当日に設定し、既存projectは定期更新する |
| nodejs_compat | 多くのlibraryがNode.js built-insへ依存するため`nodejs_compat` flagを有効化する |
| wrangler types | `wrangler types`で`Env`を生成し、binding interfaceを手書きしない |
| Secrets | `wrangler secret put`を使い、configやsourceへsecretをhardcodeしない |
| wrangler.jsonc | 非secret設定にはJSONC configを使う。新しい機能にはJSONのみ対応するものがある |

### RequestとResponse

| Rule | 要点 |
|------|------|
| Streaming | 大きさが不明または大容量のpayloadはstreamし、無制限のdataへ`await response.text()`しない |
| waitUntil | response後の処理には`ctx.waitUntil()`を使い、`ctx`をdestructureしない |

### Architecture

| Rule | 要点 |
|------|------|
| Bindings over REST | KV、R2、D1、QueuesはCloudflare REST APIでなくin-process bindingを使う |
| Queues & Workflows | async/background処理をcritical pathから分離する |
| Service bindings | Worker間呼び出しはpublic HTTPでなくservice bindingを使う |
| Hyperdrive | 外部PostgreSQL/MySQL接続には常にHyperdriveを使う |

### Observability

| Rule | 要点 |
|------|------|
| Logs & Traces | configで`observability`と`head_sampling_rate`を有効化し、structured JSON loggingを使う |

### Code patterns

| Rule | 要点 |
|------|------|
| No global request state | request固有dataをmodule-level変数へ保存しない |
| Floating promises | 全Promiseを`await`、`return`、`void`、または`ctx.waitUntil()`のいずれかで扱う |

### Security

| Rule | 要点 |
|------|------|
| Web Crypto | security用途には`crypto.randomUUID()` / `crypto.getRandomValues()`を使い、`Math.random()`を使わない |
| No passThroughOnException | 明示的なtry/catchとstructured error responseを使う |

## 検出するanti-patterns

| Anti-pattern | 問題になる理由 |
|-------------|----------------|
| 無制限のdataに`await response.text()` | 128 MB制限に達するmemory exhaustion |
| source/configにsecretをhardcode | version control経由のcredential漏えい |
| token/ID生成に`Math.random()` | 予測可能で暗号学的に安全でない |
| `await`も`waitUntil`もない裸の`fetch()` | floating promiseにより結果やerrorが失われる |
| request stateをmodule-level mutable変数へ保存 | request間data漏えい、stale state、I/O error |
| Worker内からCloudflare REST APIを呼ぶ | 不要なnetwork hop、認証負荷、latency増加 |
| error handlingに`ctx.passThroughOnException()` | bugを隠し、debug不能にする |
| `Env` interfaceの手書き | 実際のwrangler config bindingとdriftする |
| secret値の直接文字列比較 | timing side-channel。`crypto.subtle.timingSafeEqual`を使う |
| `ctx`のdestructure（`const { waitUntil } = ctx`） | `this` bindingが失われ、runtimeで`Illegal invocation` |
| `any` on `Env` or handler params | binding access全体のtype safetyを失う |
| `as unknown as T`のdouble-cast | 実際の型不整合を隠す。designを修正する |
| platform base classへの`implements` | legacy。`this.ctx`、`this.env`を失うため`extends`を使う |
| platform base class内の`env.X` | DurableObject、WorkerEntrypoint等をextendsするclassでは`this.env.X`を使う |

## レビュー手順

1. **Retrieve** — 最新best practices、workers types、wrangler schemaを取得する
2. **Read full files** — diffだけでなくfile全体を読み、binding accessの文脈を確認する
3. **Check types** — binding access、handler signatures、`any`、unsafe castsを確認する（`references/review.md`参照）
4. **Check config** — `compatibility_date`、`nodejs_compat`、observability、secrets、bindingとcodeの一致を確認する
5. **Check patterns** — streaming、floating promises、global state、serialization boundariesを確認する
6. **Check security** — crypto、secret handling、timing-safe comparison、error handlingを確認する
7. **Validate with tools** — `pnpm tsc --noEmit`と`no-floating-promises` lintを実行する
8. **Reference rules** — 各ruleの正しいpatternを`references/rules.md`で確認する

## 対象範囲

このSkillはWorkers固有のbest practicesとcode reviewを扱う。関連領域は次を使う。

- **Durable Objects**: `durable-objects` Skillをloadする
- **Workflows**: [Rules of Workflows](https://developers.cloudflare.com/workflows/build/rules-of-workflows/)を参照する
- **Wrangler CLI commands**: `wrangler` Skillをloadする

## 最終出力

レビュー結果は、重要度順に「対象file/line、観測した事実、該当rule、影響、最小の修正案、実行した検証」を日本語で報告する。問題がなければ、確認した範囲と未検証事項を明示する。

## 原則

- **断定前に取得する。** API、config field、patternに確信がなければ、指摘前に公式資料を取得する。
- **根拠を示す。** line number、tool output、docs linkを添える。
- **開発者がコピーする箇所を優先する。** examplesやdocsのWorkers codeは本番へコピーされる。
- **網羅性より正確性。** 動く短いexampleは、errorを含む包括的なexampleよりよい。
