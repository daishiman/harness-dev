# Prompt: R1-fetch

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-fetch |
| skill | run-extract-blueprint |
| responsibility | R1 認可確定と低負荷取得 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/fact-inference-confidence.schema.json |
| reproducible | true (同一 URL・同一応答・同一 budget で同一 snapshot/台帳) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- C12 (`authz-classify.py`) が `allow` した AuthzEvidence 範囲外・認証必須領域へフェッチしない。`unknown` は `deny` として扱う。
- 対象 origin 並列 1・最小間隔・request/byte/pages budget・Retry-After・停止条件を single/full_site 両モードで緩めない (引上げはユーザー承認対象)。
- 全 fetch は C08 (`pre-fetch-authz-guard`) の fail-closed 境界内で走る。budget 超過・deny・期限切れは exit2 で遮断される。

### 1.2 倫理ガード
- 認可外スクレイピング・実侵入・DoS 相当の負荷をかけない。robots-deny/403/429 は停止条件として尊重する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: AuthzEvidence/request budget/crawl_profile の確定、URL discovery → scope 分類、C09 静的 HTTP snapshot + stdlib 静的 DOM/CSS 観測 (static-observation.json) の取得、鍵画面で任意の C15 browser-render (rendered DOM/screenshot) 取得 (in-scope 全画面)。
- 非担当: 分析 (R2)、文書化 (R3)。

### 2.2 ドメインルール
- `--crawl-mode single` は入口周辺、`full_site` は全 in-scope URL 被覆。full_site は per-run 有界予算 + cache/ledger による multi-run resume で全 URL へ到達する。
- 再開 run は前 run の site coverage manifest を C12 `--coverage-manifest-in` へ渡し、pending と未分類 discovered を分類対象へ再投入する (writer=C11 / reader=C12 を両辺契約化)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| url | string | yes | 対象システムの公開 URL 1 件 |
| crawl_mode | enum(single/full_site) | no | 既定 single |
| resume | flag | no | 前 run の coverage manifest から継続 |

### 2.4 出力契約
- AuthzEvidence (`authz.json`) + request budget (`budget.json`) + snapshot + stdlib 静的観測 (`static-observation.json`: DOM 構造/見出し/nav・link/form/meta/宣言色 font) + request ledger + discovered_urls 台帳 + scope manifest。fact は `fact-inference-confidence.schema.json` の provenance (source_url/locator/captured_at/method/snapshot_id) 必須。
- evidence/budget は C08 が参照する `ESB_AUTHZ_DIR` (既定 `.esb-authz`) へ配置する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| authz script | `$CLAUDE_PLUGIN_ROOT/scripts/authz-classify.py` | 認可 preflight + budget/crawl_profile 発行 |
| fetch script | `$CLAUDE_PLUGIN_ROOT/scripts/fetch-snapshot.py` | snapshot + URL discovery + stdlib 静的 DOM/CSS 観測 (static-observation.json) |
| authz guard | `$CLAUDE_PLUGIN_ROOT/hooks/pre-fetch-authz-guard.py` | fail-closed 境界 (fetch-authz 述語) |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/authz-classify.py" --url <url> --evidence-out <dir>/authz.json --budget-out <dir>/budget.json [--crawl-mode full_site --discovered-urls <f> --coverage-manifest-in <f> --scope-manifest-out <f>]`
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/fetch-snapshot.py" --url <url> --out-dir <dir> --authz-evidence <dir>/authz.json --request-budget <dir>/budget.json [--discover-urls --discovered-urls-out <f>]`
- 対象システムの公開 URL (WebFetch + 静的 HTTP snapshot)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- C12 が `deny`/`unknown` を返したら停止し理由を提示する。budget 超過・429/403/robots-deny は停止条件として扱い部分取得のまま fact を確定しない。
- 最大反復回数: 5。

### 4.2 観測 / ロギング
- request ledger に request 数・byte・pages・再読込を計上する。stdout に取得件数・coverage サマリ。

### 4.3 セキュリティ
- AuthzEvidence の TTL 内のみ有効。認証後情報・機微は取得段で持ち出さない (redact は R3 の C11 が担保)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 決定論 script (authz/fetch) 主体。取得は静的 HTTP (WebFetch + C09 fetch-snapshot.py) と、任意で browser-render (C15) の 2 経路。browser-render は MCP 非依存でローカル headless Chrome を Bash 経由 CLI 起動して JS 実行後 DOM + screenshot を取り、バイナリ不在時は exit 3 (browser-unavailable) で該当観測のみ observation_gap へ縮退する (静的観測は続行)。

### 5.2 ゴール定義
- 目的: 認可された範囲内で、全 in-scope 画面の観測入力 (静的 HTTP snapshot + discovery) を低負荷で揃える。
- 背景: 認可外取得や過負荷は倫理・法務リスクと後段判定の腐敗を招く。budget と fail-closed hook で機構的に抑止する。
- 達成ゴール: C12 allow のもと、全 in-scope 画面の静的 HTTP snapshot と site coverage manifest が budget 内で取得され、fact が provenance 付きで書き出された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] C12 が `allow` を返し AuthzEvidence/request budget/crawl_profile を発行した
- [ ] C09 discovery → C12 scope 分類で in_scope/excluded(+reason) 台帳を作った
- [ ] 全 in-scope 画面の静的 HTTP snapshot を budget 内で取得した (並列 1・budget 超過 0)
- [ ] 鍵画面で browser-render (C15) による rendered DOM/screenshot 取得を試み、成功時は fact 化・ブラウザ不在時のみ observation_gap(reason=browser-unavailable) として記録した
- [ ] `--resume` 時は前 run の coverage manifest を `--coverage-manifest-in` へ再投入した
- [ ] 認可外 URL・認証必須領域へフェッチしていない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (authz 実行 / budget 調整 / discovery 追加 / observation 起動)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-extract-blueprint` SKILL の R1-fetch 局面。
- 後続 phase: R2-analyze が観測 fact を入力に分析へ進む。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (url/crawl_mode)・対象システム (HTTP)。
- 受領先: R2 (analyzer 群)。
- 引き渡し形式: snapshot fact records (成果物ディレクトリ配下の JSON) + site coverage manifest + request ledger。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に取得件数・in_scope/excluded 件数・budget 消費サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI 引数 / JSON キー / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`authz-classify.py` で AuthzEvidence/request budget/crawl_profile を確定し (`unknown` は deny)、allow のときだけ `fetch-snapshot.py` で全 in-scope 画面の静的 HTTP snapshot + URL discovery を取る (WebFetch + 静的 HTTP snapshot)。鍵画面では加えて browser-render で rendered DOM/screenshot 取得を試みる (MCP 非依存の headless Chrome を Bash 経由 CLI 起動・不在時は exit 3 で observation_gap 縮退):
`python3 "$CLAUDE_PLUGIN_ROOT/scripts/browser-render.py" --url <url> --out-dir <dir> --authz-evidence <dir>/authz.json --request-budget <dir>/budget.json --screenshot --request-ledger <ledger>`
evidence/budget を `ESB_AUTHZ_DIR` へ配置し、全 fetch (browser-render の Bash 起動を含む) を C08 の fail-closed 境界内で走らせる。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。対象 origin 並列 1・budget・Retry-After・停止条件を緩めない。出力は件数・coverage サマリのみ、前置き禁止。
