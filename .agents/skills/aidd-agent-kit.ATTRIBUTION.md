# ATTRIBUTION — 第三者著作物の帰属と改変告知

本ファイルは Apache License, Version 2.0 §4(b)（改変したファイルに「顕著な告知」を付す義務）
および §4(a)（ライセンス写しの頒布）を満たすための告知一覧である。

- ライセンス全文: [`LICENSE`](./LICENSE)
- 帰属表記: [`NOTICE`](./NOTICE)

## 1. 由来

| 項目 | 内容 |
| --- | --- |
| 上流リポジトリ | https://github.com/cloudflare/skills |
| 上流著作権者 | Copyright (c) Cloudflare, Inc. |
| 上流ライセンス | Apache License, Version 2.0 |
| 取り込み方式 | vendor（同梱コピー。submodule ではない） |
| vendor 対象 | 7 スキル / 84 ファイル |

> **2026-09-01 更新**: `skills/cloudflare/references/` の 63 トピックのうち 55 トピック
> （278 ファイル）を削除し、その内容の参照を `cloudflare-docs` MCP へ委譲した。
> これにより `skills/cloudflare/` は 321 ファイル → **43 ファイル**、vendor 対象は
> 361 ファイル → **84 ファイル** になった。スキル数は 7 のまま（`skills/cloudflare/` は残存）。
> 以下の集計はすべて削除後の実態を上流と再照合した実測値である。

## 2. 照合方法

キット側 84 ファイルと上流の同一パスのファイルを機械的に突き合わせ、次の規則で分類した。

1. **完全一致** — 改変告知行を除いてバイト単位で同一
2. **pnpm 機械置換** — `npm` / `npx` / `npm install` → `pnpm` / `pnpm dlx` / `pnpm add` の
   パッケージマネージャ表記を正規化すると完全一致
3. **軽微差分** — 上記正規化後の残差が 12 行以下で、意味を変えない範囲の修正
4. **日本語化** — frontmatter の `description` および本文の日本語訳
5. **実質改変** — 上記に当たらない内容の追加・変更
6. **キット独自** — 上流に同名パスのファイルが存在しない

## 3. 分類の集計

| 分類 | ファイル数 | 割合 | Apache §4(b) の改変告知 |
| --- | ---: | ---: | --- |
| 完全一致 | 28 | 33.3% | 不要（未改変） |
| pnpm 機械置換のみ | 16 | 19.0% | 本ファイルで一括告知（§5-3 参照） |
| 軽微差分 | 7 | 8.3% | 本ファイルで一括告知（§5-3 参照） |
| 日本語化 | 7 | 8.3% | **各ファイル冒頭に告知行を挿入**（§5-1） |
| 実質改変 | 12 | 14.3% | **各ファイル冒頭に告知行を挿入**（§5-2） |
| キット独自 | 14 | 16.7% | 対象外（Cloudflare 著作物ではない） |
| 合計 | 84 | 100% | |

> 割合は四捨五入のため合計が 100% にならない。
> 参考: 削除前の値は 完全一致 237 / pnpm 機械置換 82 / 軽微差分 7 / 日本語化 8 /
> 実質改変 14 / キット独自 13、合計 361 ファイルであった。

## 4. スキル単位の内訳

| スキル | ファイル数 | 完全一致 | pnpm 置換 | 軽微差分 | 日本語化 | 実質改変 | キット独自 | 判定 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `skills/cloudflare/` | 43 | 24 | 10 | 7 | 0 | 1 | 1 | vendor（references の 55 トピックは MCP へ委譲済み） |
| `skills/turnstile-spin/` | 15 | 0 | 0 | 0 | 2 | 11 | 2 | vendor（改変が多い） |
| `skills/wrangler/` | 12 | 0 | 0 | 0 | 1 | 0 | 11 | 混在（SKILL.md のみ vendor） |
| `skills/cloudflare-email-service/` | 6 | 2 | 3 | 0 | 1 | 0 | 0 | vendor |
| `skills/durable-objects/` | 4 | 2 | 1 | 0 | 1 | 0 | 0 | vendor |
| `skills/workers-best-practices/` | 3 | 0 | 2 | 0 | 1 | 0 | 0 | vendor |
| `skills/web-perf/` | 1 | 0 | 0 | 0 | 1 | 0 | 0 | vendor |

## 5. 改変告知行を挿入したファイル

以下のファイルは Cloudflare, Inc. の著作物を改変したものであり、各ファイルの冒頭
（Markdown は frontmatter の直後、シェルスクリプトは shebang 直後）に次の告知行を挿入している。

```
> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。
```

### 5-1. 日本語化（7 ファイル）

frontmatter の `description` および本文を日本語へ翻訳したもの。手順・コマンド・数値は上流のまま。

| ファイル | 備考 |
| --- | --- |
| `skills/cloudflare-email-service/SKILL.md` | 日本語化 + pnpm 置換 |
| `skills/durable-objects/SKILL.md` | 日本語化 |
| `skills/turnstile-spin/SKILL.md` | 日本語化 |
| `skills/turnstile-spin/README.md` | 日本語化 |
| `skills/web-perf/SKILL.md` | 日本語化 |
| `skills/workers-best-practices/SKILL.md` | 日本語化 + pnpm 置換 |
| `skills/wrangler/SKILL.md` | 日本語化 |

### 5-2. 実質改変（12 ファイル）

| ファイル | 改変の性質 |
| --- | --- |
| `skills/cloudflare/SKILL.md` | 日本語化に加え、判断木の参照先を全面書き換え・製品索引を新表へ置換・`cloudflare-docs` MCP 優先の取得先表へ改稿（差分 335 行） |
| `skills/turnstile-spin/references/astro.md` | 上流の旧版（2026-07-13 時点）を基に改変 |
| `skills/turnstile-spin/references/hugo.md` | 同上 |
| `skills/turnstile-spin/references/nextjs-app.md` | 同上 |
| `skills/turnstile-spin/references/nextjs-pages.md` | 同上 |
| `skills/turnstile-spin/references/sveltekit.md` | 同上 |
| `skills/turnstile-spin/references/vanilla-html.md` | 同上 |
| `skills/turnstile-spin/tests/validation.md` | 同上 |
| `skills/turnstile-spin/scripts/auth-probe.sh` | 同上（AIDD 固有の Account ID / 秘密値規律を追加） |
| `skills/turnstile-spin/scripts/validate.sh` | 同上 |
| `skills/turnstile-spin/scripts/widget-create.sh` | 同上 |
| `skills/turnstile-spin/scripts/persist-skill.sh` | 同上 |

> `skills/turnstile-spin/` の vendor 元は上流 `main` の最新版ではなく **2026-07-13 時点のコミット**である。
> このため上流 `main` との diff は大きく見えるが、`astro.md` `nextjs-app.md` `nextjs-pages.md`
> `sveltekit.md` `vanilla-html.md` の 5 ファイルは上流の過去コミットとバイト単位で一致する。
> 由来が Cloudflare, Inc. の著作物であることに変わりはないため、告知対象に含めている。

### 5-3. 一括告知するファイル（個別の告知行は挿入していない）

次の 2 群は Cloudflare, Inc. の著作物を改変したものであるが、変更が機械的・軽微であり
ファイル数が多いため、**本ファイルによる一括告知**をもって §4(b) の告知とする。

| 分類 | ファイル数 | 改変内容 |
| --- | ---: | --- |
| pnpm 機械置換 | 16 | `npm install` → `pnpm add`、`npx` → `pnpm dlx` 等のパッケージマネージャ表記の置換のみ。技術的内容の変更なし |
| 軽微差分 | 7 | `skills/cloudflare/references/` 配下の 7 ファイル。いずれも削除済みトピックへの相対リンクを Skill 名参照へ書き換えたもの（各 1〜4 行）: `kv/README.md`, `d1/README.md`, `workflows/README.md`, `workers/README.md`, `workers/api.md`, `workers/configuration.md`, `workers/patterns.md` |

## 6. キット独自ファイル（Apache-2.0 の対象外）

次のファイルは上流 `cloudflare/skills` に同名パスが存在せず、本キットのオリジナル著作物である。
Copyright (c) 2026 daishiman。

| ファイル |
| --- |
| `skills/cloudflare/references/account-context.md` |
| `skills/turnstile-spin/scripts/account-context.sh` |
| `skills/turnstile-spin/scripts/fetch-secret.sh` |
| `skills/wrangler/references/ai-vectorize-hyperdrive.md` |
| `skills/wrangler/references/config.md` |
| `skills/wrangler/references/containers.md` |
| `skills/wrangler/references/d1.md` |
| `skills/wrangler/references/deploy.md` |
| `skills/wrangler/references/dev-local.md` |
| `skills/wrangler/references/kv-r2.md` |
| `skills/wrangler/references/mcp-vs-cli-routing.md` |
| `skills/wrangler/references/observability-troubleshooting.md` |
| `skills/wrangler/references/queues-workflows-pipelines.md` |
| `skills/wrangler/references/secrets.md` |

また `skills/cloudflare-secure-deploy/` は名前に `cloudflare` を含むが、
上流 `cloudflare/skills` に対応するスキルは存在せず、**本キットのオリジナル著作物**である。
Apache-2.0 の帰属対象ではない。

同様に、`skills/` 配下の以下のスキルはすべてキットのオリジナルであり Apache-2.0 の対象外:
`app-excellence`, `better-auth-google-gate`, `ci-cd-pipeline`, `cloudflare-secure-deploy`,
`design-judgment`, `jp-web-design`, `launch-security`, `llm-api-integration`,
`llm-cost-simulator`, `mvp-first-development`, `solo-git-flow`, `testing-excellence`, `ux-design`。
