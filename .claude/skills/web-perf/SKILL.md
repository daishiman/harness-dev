---
name: web-perf
description: Chrome DevTools MCPを使ってWeb performanceを分析する。Core Web Vitals（LCP、INP、CLS）とFCP、TBT、Speed Indexを計測し、render-blocking resources、network dependency chains、layout shifts、cache、accessibilityの問題を特定する。表示速度の監査・計測・デバッグ・最適化、Lighthouse scoreの改善で使用する。既定スタックの必須スキルではないoptional群であり、要件で明示された場合、またはapp-orchestratorがv1前の計測として指示した場合のみロードする。事前学習の知識より最新の公式ドキュメントを優先する。
---

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。

# Web Performance監査

Web performanceの計測名、閾値、tooling APIsは更新される。具体値や推奨を示す前に、**事前学習の知識ではなく最新の公式情報を取得する**。

## 最新情報の取得先

Cloudflare製品ではないため`cloudflare-docs` MCPは使わず、次のWebページを第一手段にする(列構成はキット共通)。

| 取得先 | 取得方法 | 使う場面 |
|--------|----------|---------|
| web.dev | `https://web.dev/articles/vitals` を取得 | Core Web Vitalsの閾値と定義 |
| Chrome DevTools docs | `https://developer.chrome.com/docs/devtools/performance` を取得 | Tooling APIsとtrace analysis |
| Lighthouse scoring | `https://developer.chrome.com/docs/lighthouse/performance/performance-scoring` を取得 | score weightsとmetric thresholds |

## 最初にMCP toolsを確認する

**監査開始前に必ず行う。** `navigate_page`または`performance_start_trace`を呼び出す。利用できなければchrome-devtools MCP serverが未登録なので、計測したように報告せず、**エージェントが登録を代行する**(利用者にコマンドを打たせない。方針は`app-orchestrator`のMCP接続原則と同じ)。登録後にclientを再起動し、上記toolを再確認してから監査へ進む。

```bash
# Claude Code(user scope。作業フォルダに依らず使える)
claude mcp add chrome-devtools --scope user -- npx -y chrome-devtools-mcp@latest
# Codex
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
```

`claude` / `codex` コマンドが無い環境では登録をスキップし、計測を未実施として残課題に1行残す。

## 分析原則

- **根拠を確定する**: network requests、DOM、codebaseで確認した事実だけを断定的に述べる。
- **推奨前に検証する**: 削除を提案する前に未使用であることを確認する。
- **影響を数値化する**: insightsのestimated savingsを使う。0msの改善は優先項目にしない。
- **問題でない項目は分ける**: render-blocking resourcesのestimated impactが0msなら記録のみとし、改善対象にしない。
- **具体的に書く**: 「画像を最適化」ではなく、例えば「`hero.png` (450KB)をWebPへ圧縮」と示す。
- **実測値で優先順位を付ける**: 十分高速な項目はそのように報告し、不要な改修を増やさない。

## Tool call早見表

| 目的 | Tool Call |
|------|-----------|
| ページを開く | `navigate_page(url: "...")` |
| traceを開始する | `performance_start_trace(autoStop: true, reload: true)` |
| insightを分析する | `performance_analyze_insight(insightSetId: "...", insightName: "...")` |
| requests一覧を取得する | `list_network_requests(resourceTypes: ["Script", "Stylesheet", ...])` |
| request詳細を取得する | `get_network_request(reqid: <id>)` |
| accessibility snapshotを取得する | `take_snapshot(verbose: true)` |

## 監査フロー

次のchecklistで進捗を管理する。

```
監査の進捗:
- [ ] 手順 1: Performance traceを取得
- [ ] 手順 2: Core Web Vitalsを分析（CLSの原因を含む）
- [ ] 手順 3: Networkを分析
- [ ] 手順 4: Accessibility snapshotを取得
- [ ] 手順 5: Codebaseを分析（第三者siteは省略）
```

### 手順 1: Performance traceの取得

1. 対象URLを開く。
   ```
   navigate_page(url: "<target-url>")
   ```

2. reload付きでperformance traceを開始し、cold-load metricsを取得する。
   ```
   performance_start_trace(autoStop: true, reload: true)
   ```

3. trace完了を待って結果を取得する。

**トラブル時:**
- traceが空または失敗なら、先に`navigate_page`でページが正常に開いたか確認する
- insight nameが一致しない場合は、trace responseから利用可能なinsightsを確認する

### 手順 2: Core Web Vitalsの分析

`performance_analyze_insight`で主要metricsを取得する。

**注意:** insight namesはChrome DevToolsのversionで変わることがある。動作しない場合は、trace responseの`insightSetId`から利用可能なinsightsを確認する。

主なinsight names:

| Metric | Insight Name | 確認内容 |
|--------|--------------|------------------|
| LCP | `LCPBreakdown` | TTFB、resource load、render delayの内訳 |
| CLS | `CLSCulprits` | layout shiftsを起こす要素（寸法のない画像、後から挿入されるcontent、font swap） |
| Render Blocking | `RenderBlocking` | first paintを妨げるCSS / JS |
| Document Latency | `DocumentLatency` | server response timeの問題 |
| Network Dependencies | `NetworkRequestsDepGraph` | critical resourcesを遅らせるrequest chains |

例:
```
performance_analyze_insight(insightSetId: "<id-from-trace>", insightName: "LCPBreakdown")
```

**主要閾値（good / needs-improvement / poor）:**

下記は早見表であり、報告時は上記公式sourceの最新値を確認し、確認日を付ける。
- TTFB: < 800ms / < 1.8s / > 1.8s
- FCP: < 1.8s / < 3s / > 3s
- LCP: < 2.5s / < 4s / > 4s
- INP: < 200ms / < 500ms / > 500ms
- TBT: < 200ms / < 600ms / > 600ms
- CLS: < 0.1 / < 0.25 / > 0.25
- Speed Index: < 3.4s / < 5.8s / > 5.8s

### 手順 3: Networkの分析

全network requestsを取得し、改善候補を特定する。
```
list_network_requests(resourceTypes: ["Script", "Stylesheet", "Document", "Font", "Image"])
```

**確認項目:**

1. **Render-blocking resources**: `<head>`内で`async` / `defer` / `media` attributesのないJS / CSS
2. **Network chains**: 先に読まれるresourceへの依存で発見が遅れるresource（CSS imports、JS-loaded fontsなど）
3. **Missing preloads**: preloadされていないcritical resources（fonts、hero images、key scripts）
4. **Caching issues**: 不足または弱い`Cache-Control`、`ETag`、`Last-Modified` headers
5. **Large payloads**: 未圧縮または過大なJS / CSS bundles
6. **Unused preconnects**: 対象originへのrequestが0件であることを確認できた場合だけ削除を推奨する。requestが存在し後から読まれるならpreconnectに価値が残る。

requestの詳細は次で確認する。
```
get_network_request(reqid: <id>)
```

### 手順 4: Accessibility snapshotの取得

accessibility tree snapshotを取得する。
```
take_snapshot(verbose: true)
```

**主な検出対象:**
- 欠落または重複するARIA IDs
- contrast ratioが不足する要素（WCAG AA: 通常テキスト4.5:1、大きなテキスト3:1）
- focus trap、またはfocus indicatorの欠落
- accessible nameのないinteractive elements

## 手順 5: Codebaseの分析

**第三者siteでcodebaseへアクセスできない場合は省略する。** その場合は未実施として最終報告に明記する。

codebaseを読み、改善すべき実装箇所を特定する。

### Framework / bundlerの検出

設定ファイルからstackを特定する。

| Tool | Config files |
|------|--------------|
| Webpack | `webpack.config.js`, `webpack.*.js` |
| Vite | `vite.config.js`, `vite.config.ts` |
| Rollup | `rollup.config.js`, `rollup.config.mjs` |
| esbuild | `esbuild.config.js`, `esbuild`を使うbuild scripts |
| Parcel | `.parcelrc`, `package.json`のparcel field |
| Next.js | `next.config.js`, `next.config.mjs` |
| Nuxt | `nuxt.config.js`, `nuxt.config.ts` |
| SvelteKit | `svelte.config.js` |
| Astro | `astro.config.mjs` |

`package.json`のframework dependenciesとbuild scriptsも確認する。

### Tree-shaking / dead codeの確認

- **Webpack**: `mode: 'production'`、`package.json`の`sideEffects`、`usedExports`を確認する
- **Vite / Rollup**: tree-shakingは既定で有効。`treeshake` optionsを確認する
- **検出対象**: barrel files（`index.js`のre-exports）、一括importされた大きなutility libraries（lodash、moment）

### Unused JS / CSSの確認

- CSS-in-JSとstatic CSS extractionの使い分けを確認する
- PurgeCSS / UnCSS設定（Tailwindの`content` config）を確認する
- dynamic importsとeager loadingを識別する

### Polyfillsの確認

- `@babel/preset-env` targetsと`useBuiltIns`設定を確認する
- `core-js` importsのサイズを確認する
- `browserslist` configが必要以上に広い環境を対象にしていないか確認する

### Compression / minificationの確認

- `terser`、`esbuild`、`swc`のminificationを確認する
- build outputまたはserver configのgzip / brotli compressionを確認する
- production buildのsource mapsがexternalまたはdisabledであることを確認する

## 検証と出力形式

取得したtrace / insights / network requestsとcodebaseを相互照合し、推測のみの項目は確定事実と分ける。traceが取得できない、対象URLが開けない、codebaseへアクセスできない場合は、その範囲の断定を停止して未検証と明記する。

1. **Core Web Vitals要約** - metric、実測値、rating（good / needs-improvement / poor）、閾値の確認日を表で示す
2. **優先問題** - 根拠とestimated impactを付け、high / medium / low順に示す
3. **改善案** - 対象ファイルやresource、具体的な修正、期待効果を示す。必要なcode snippet / config changeだけを添える
4. **Codebase調査** - 検出したframework / bundlerと改善箇所を示す。codebaseへアクセスできなければ「未実施」とする
5. **制約と未検証項目** - 利用できないtools、未取得のdata、追加検証に必要な操作を日本語で簡潔に示す
