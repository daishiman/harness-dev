# Cloudflare MCP と wrangler CLI のルーティング(経路裁定書)

> 2026-09-01 確認。**本ファイルがキット内の Cloudflare 経路判断の唯一の正本**。他スキル・エージェント定義・README は本ファイルへリンクし、経路表を複製しない。
> 仕様の正本は Cloudflare 公式資料:
> [Cloudflare's own MCP servers](https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/) / [Transport](https://developers.cloudflare.com/agents/model-context-protocol/protocol/transport/) / [domain-specific MCP repository](https://github.com/cloudflare/mcp-server-cloudflare) / [Cloudflare API MCP](https://github.com/cloudflare/mcp)

## 裁定(5行)

1. **仕様の確認と調査は MCP**(docs / bindings / observability)。
2. **deploy・`secret put`・`d1 migrations apply` は wrangler CLI 既定**(INV-2)。理由は監査性・可逆性・秘密保護であり、MCP にその能力が無いからではない。
3. **MCP の登録(user scope)はエージェントと setup-env が代行**する(INV-11)。利用者に登録コマンドを打たせない。
4. **OAuth 認可と、git 未追跡の `.mcp.json` の修正は本人**が行う。エージェントは差分を提示して承認を待つ。
5. **git 管理下の `.mcp.json` はリポジトリ所有物**として、承認後に PR で直す(「利用者の私物」として触らないのは未追跡ファイルだけ)。

## 判断原則

**MCP=読み取り、CLI=書き込みではない。** Cloudflare API MCP は Cloudflare API 全体の実行に対応し、Workers Bindings MCP にも作成・削除・query等の mutation がある。Workers Builds MCP も「確認専用」とは限らない。媒体名で決めず、毎回次の順で決める。

1. **capability**: その時点のツール一覧に必要な操作が本当にあるか
2. **risk**: 本番・削除・公開・権限・課金への影響はどの程度か
3. **auditability**: 入力と結果を再現可能な形でレビュー・記録できるか
4. **reversibility**: 失敗時の rollback と復旧手順が明確か

MCP と CLI の両方が使える場合、低リスクの探索は MCP、高リスクで再現性が必要な操作はコマンド・差分・ledgerが残る CLI を既定とする。どちらで実行する場合も、対象 Account、実行内容、必要権限を確定してから mutation する。

## 最小安全 profile

自動セットアップは次の3件だけとする。

| サーバー | 既定用途 | 権限の扱い |
|---|---|---|
| `cloudflare-docs` | 最新仕様の参照 | **認証不要** |
| `cloudflare-bindings` | Workers と D1 / KV / R2 等の構成確認、明示された開発用 mutation | OAuth。mutation 可能なため、必要な Account / 権限だけ認可 |
| `cloudflare-observability` | ログ・analytics の調査 | OAuth。調査対象に必要な最小権限だけ認可 |

- `cloudflare-builds` は**Workers Builds を実際に採用したプロジェクトだけ**追加する。「read-onlyだから常設」とはしない。
- `https://mcp.cloudflare.com/mcp` の Cloudflare API MCP は、約2,500 endpoint に `search` / `execute` で広くアクセスできる。**広い capability と認可権限を利用者が理解し、個別 MCP では足りないと明示選択したときだけ**追加する。自動登録しない。
- OAuth の認可画面では、使う操作に不要な write / Account 権限を認可しない。API token を使う CI/CD でも同様に最小権限とする。

**配置 scope と Cloudflare 認可 scope は別物。** `--scope user` は MCP の接続設定をそのPCのユーザー全体で使う「配置範囲」であり、Cloudflare OAuth / API token の Account・read・write 権限を広げない。後者は必要になった時点で、最小範囲だけ別途認可する。未使用 MCP が `Needs authentication` でも基本セットアップを未完了とは扱わず、そのcapabilityを初めて使う時だけ対象1件を認可する。

## 作業別の既定経路

「認証済み」はそのセッションで該当 MCP のツールが実際に呼べる状態を指す。未認証のとき、既定経路のためだけに認可を促さない(認可はそのcapabilityを本当に使う最初の時点で対象1件だけ依頼する)。

| 作業 | 既定経路 | 理由 |
|---|---|---|
| 公式仕様・上限・API・設定値の確認 | docs MCP(不通なら公式 Web) | 認証不要で最新の正本を検索できる |
| Account / resource / binding の調査 | 対応する domain MCP。未認証なら `wrangler <product> list` 等の read-only CLI | 目的に絞った typed tool で権限面を小さくできる |
| 開発用 D1 / KV / R2 等の作成・削除 | **Bindings MCP 認証済みなら MCP、未認証なら CLI(認証を促さない)** | どちらでも実行前に対象・影響・rollbackを確定する。削除は必ず利用者確認 |
| ログ・analytics の調査 | **observability MCP 認証済みなら MCP、未認証なら `wrangler tail`** | 調査は低リスク。`tail` はライブのみなので過去ログは Dashboard で代替 |
| local development | CLI `wrangler dev` | local process と対話セッションの管理が必要 |
| deploy / versions / rollback | **CLI 既定**(`wrangler deploy --dry-run` で事前検証) | コマンド、差分、デプロイ対象と復旧手順の再現性を残す |
| secret の登録・更新 | **CLI 既定** `wrangler secret put` | 秘密値を MCP context、設定、stamp、ログに残さない |
| D1 migration apply | **CLI 既定** `wrangler d1 migrations apply` | migration file と適用 ledger を正しく管理する。raw query で代用しない |

API MCP に対応 endpoint が存在しても、CLI 既定の3件を MCP へ切り替える理由にはならない。個別に capability・権限・監査・復旧を満たし、明示的に選ぶときだけ使う。

## transport と endpoint

`/sse` と 410 に関する説明は本節に集約する。他文書はここへリンクする。

- 新規接続は Streamable HTTP の `https://<name>.mcp.cloudflare.com/mcp` を使う。
- 過去の `/sse` URL は、現在は**同じ Streamable HTTP handler への互換 alias**であり、URLだけで「legacy SSE」とは判定しない。新規設定では将来互換のため `/mcp` を使う。
- deprecated な HTTP+SSE transport を強制する `type: sse` / legacy SSE `GET /sse` は別物。後者は `410 Gone` となるため、`type: http`(または自動判定) + `/mcp` へ移行する。
- project scope の `.mcp.json` は user scope より優先される。project 側に `type: sse` が残っていると、user scope に正しく登録済みでも `410` になり、`claude mcp list` に `[Conflicting scopes]` が出る。

## MCP 不通時の復旧

エージェントは状態確認から user scope への再登録まで行える。まず `claude mcp list`(Codex は `codex mcp list --json`)で現在状態を確認し、次の4分岐のどれかに当てはめる。正しい既存設定は触らない。

| 状態 | 見分け方 | エージェントが行うこと | 利用者が行うこと |
|---|---|---|---|
| **未登録** | `claude mcp list` に名前が無い | `claude mcp add --transport http --scope user cloudflare-<name> https://<name>.mcp.cloudflare.com/mcp` を代行 | なし(`bindings` / `observability` は必要時に OAuth 認可) |
| **不通** | 登録済みだが接続失敗(410 以外、またはネットワーク) | URL / transport が core profile と違えば `remove` → `add` で登録し直す。同じなら一時障害として CLI 代替で続行し、報告に残す | なし |
| **legacy sse(project `.mcp.json`)** | 直下の `.mcp.json` に `"type": "sse"` があり `410` | 該当エントリを `type: http` + `/mcp` へ書き換える diff を提示する。**docs は認証不要なので、承認後にエージェントがそのまま書き換える**。git 管理下なら PR に含める。承認前は触らない | diff を承認する。git 未追跡の `.mcp.json` は本人が書き換えるか、エントリを削除して user scope に委ねる |
| **scope 衝突** | `[Conflicting scopes]` 表示(project と user に同名) | どちらの設定が有効かと差分を提示する。project 側が legacy sse なら上の行、正しければ user 側との重複を報告して片方の削除案を提示する | どちらを残すか決める |

- `Needs authentication` は登録失敗ではない。`docs` は認証不要、それ以外は必要な場合だけ最小権限で認可する。Claude Code は `/mcp`、Codex は `codex mcp login <name>` を使う。
- MCP が使えない間も、CLI で再現可能に代替できる作業は続行する。docs は公式Web、過去ログは Dashboard を代替とし、推測で仕様を埋めない。docs の3段フォールバック(MCP → Web → 同梱 gotchas/patterns と `node_modules/wrangler/config-schema.json`)は `skills/cloudflare/SKILL.md` の「docs MCPに接続できないとき」に従う。
