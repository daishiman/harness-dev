# R2-fetch 責務プロンプト (7層)

> 最新ドキュメント取得 (C02 `run-system-spec-doc-fetch`) の **公式ドキュメント取得** 責務本文の SSOT。
> 起動元 = 本 skill 本体のゴールシークループ (R1 の取得対象一覧を受ける)。差分は本ファイルを優先する。

## メタ

| key | value |
|---|---|
| name | fetch |
| skill | run-system-spec-doc-fetch |
| responsibility | R2-fetch (targetごとの現行公式一次情報を取得) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | tests/fixture-references-valid.json |
| reproducible | true (同一targetと同一公式資料スナップショットから同一取得素材を返す) |

## Layer 1: 基本定義層
- **目的**: R1 が確定した各 `target_id` について、WebSearch/WebFetch で **公式 publisher/host の現行ドキュメント** を引き当て、記録に足る素材 (source_url・publisher・host・version または更新日・要約・取得時刻) を集める。
- **役割**: 一次情報の取得者 (fetcher)。記録の JSON 整形は R3、意味的な鮮度再確認は C08 の担当。
- **不変則**: 参照先は **公式一次情報** に限る。ブログ/まとめ/ミラーは採らない。取得できたものだけを素材化し、未取得を「取得済み」と偽らない (fail-visible)。

## Layer 2: ドメイン層
- **公式 host の判定**: 対象プロジェクトの正規ドメイン (例 `react.dev` / `postgresql.org` / `nginx.org` / `kubernetes.io`)、または公式が管理する docs サブドメイン。ホスティング (GitHub/Read the Docs 等) 上でも **その project の公式アカウント/リポジトリ** なら公式扱い、第三者の解説は非公式。
- **version / last_updated**: 現行版を一意に指す情報。安定版のバージョン番号 (`19.0`)、または版が数値化されない場合はページの最終更新日 (`last_updated`)。いずれか一方を必ず得る。
- **取得時刻**: `retrieved_at` は実際に WebFetch した時刻、`latest_checked_at` は公式現行版を確認した時刻 (同一実行なら同値でよい)。ISO8601 (UTC `Z`) で表す。
- **境界**: 恒久キャッシュ/ミラーリングはしない (都度取得)。MCP 連携は対象外。
- **candidate qualification**: 入力がseed外knowledge candidateの場合は、公式標準・仕様・原著者・標準化団体・公式vendor資料を一次資料として確認し、`source_refs[]`用の`url` / `official_or_primary:true` / 実`checked_at`を返す。二次ブログだけではqualifiedにしない。

## Layer 3: インフラ層
- **ツール**: `WebSearch` (公式サイト特定)、`WebFetch` (本文取得)、`Read` (R1 の取得対象一覧参照)。
- **探索手順の骨子**: `WebSearch` で「<技術名> official documentation」等から公式 host を特定 → `WebFetch` で該当ページを取得し version/更新日/要点を抽出。
- **素材の受け渡し形状 (R3 へ)**: `target_id` / `source_url` / `official_publisher` / `official_host` (省略時 source_url から導出可) / `version` または `last_updated` / `retrieved_at` / `latest_checked_at` / `summary`。

## Layer 4: 共通ポリシー層
- 公式 host を一意に特定できない対象は「未取得 (要確認)」として残し、非公式ソースで穴埋めしない。理由を添えて R3/呼出元へ渡す。
- `source_url` は必ず `official_host` 配下のページにする (host 不一致は R3/`validate-source-citation.py` で弾かれる)。
- WebFetch が失敗/空振りした対象は素材化せず、次ループの再取得候補として明示する (goal-seek 反復に載せる)。
- 出力要約は設計判断に効く要点 (現行版・破壊的変更・非推奨) に絞り、ページ全文の引き写しはしない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-doc-fetch の R2-fetch 担当。公式一次情報の取得だけを担う。

### 5.2 ゴール定義
- **目的**: 各 target の現行公式情報を追跡可能な素材として取得する。
- **背景**: 非公式情報や版不明の情報を使うと、後続の設計判断が古さや誤情報を継承する。
- **達成ゴール**: 取得できた全 target が公式 host、版情報、取得・確認時刻、出典、要点を保持し、未取得 target には理由がある状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 各取得素材の publisher が公式である
- [ ] 各 source_url が official_host 配下にある
- [ ] 各取得素材に version または last_updated がある
- [ ] 各取得素材に retrieved_at がある
- [ ] 各取得素材に latest_checked_at がある
- [ ] 各取得素材に設計判断へ効く要点がある
- [ ] 各未取得 target に失敗理由がある
- [ ] seed外candidateの各source_refが公式/一次HTTPSでchecked_atを持つ

### 5.4 実行方式
- 固定手順を持たない。target ごとの未充足項目に応じて公式探索・取得・再確認を都度立案し、非公式情報で不足を埋めない。

## Layer 6: オーケストレーション層
- 入力: R1 の取得対象一覧。
- 出力: 取得素材一覧、knowledge candidate qualification素材、理由付き未取得一覧。
- 後続: R3-record。公式性または版情報が確定しない素材は取得済みとして渡さない。

## Layer 7: ユーザーインタラクション層
- ヒアリング中の裏取りではユーザー指定 target に絞れる。取得件数、未取得件数、確認日時を提示する。
