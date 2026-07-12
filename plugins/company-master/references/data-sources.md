# データソースと確度マッピング (正本)

> 取得元ごとの責務・認証・確度ラベル対応を定義する。確度 4 ラベルの値域は `company-master-columns.md` を正本とする。

## 取得元一覧

| 取得元 | 取得項目 | 認証 | 既定確度 |
|---|---|---|---|
| gBizINFO (経済産業省 法人情報API) | 正式名称 / 所在地 / 13桁法人番号 | リクエストヘッダ `X-hojinInfo-api-token` (Keychain `gbizinfo-api-token.<keychain-prefix>`) | 公的データで確認済み |
| 日本郵便 addresszip API (郵便番号・デジタルアドレスAPI V2) | 郵便番号 (住所→NNN-NNNN 逆引き) | OAuth2 client_credentials (Keychain `japanpost-da-api.<keychain-prefix>` の client_id/secret_key) + 送信元IP認証 (`x-forwarded-for`。既定は自動検出、固定時のみ Keychain `egress_ip`)。**既定は BYO 直結 (各自が client_id/secret_key + 送信元IP を持ち直接叩く・`references/japanpost-api-setup.md`)。送信元IPを固定できない/拠点数>10 で IP 件数上限に達する場合のみ例外的に鍵を集約する中央プロキシ (`references/postal-proxy-deploy.md`) を使う**。 | 公的データ取得 |
| Web検索 | 電話番号 / 住所のみ入力時の会社名候補 | 不要 | ネット検索(要確認) |
| Notion REST API | 企業マスタ DB への upsert/backfill | Bearer token (`notion_config.get_token`, Keychain `notion-api-key.<keychain-prefix>`) | — (出力先) |

## gBizINFO 採用理由 (purpose_background)

法人番号マスタ基盤の取得元として gBizINFO を採用する。理由: APIトークンが即時〜数時間・無料(利用申請要)で発行され、同等の法人番号マスタ(正式名称・所在地・法人番号)を提供するため。他系の公的ID発行は数週間規模で即時取得不可。
REST API は **V1 を採用する** (実装の正本: `scripts/resolve_company.py` の `GBIZINFO_BASE`)。エンドポイントは `https://info.gbiz.go.jp/hojin/v1/hojin` 系。2026-06-10 に実トークンで疎通検証済み: V1=HTTP 200、`/hojin/v2/`=HTTP 404 (存在しない)。V1 が唯一の動作エンドポイントであり移行課題はない (DEDUCT-01 完全解消)。実装はフィールド名ゆれを吸収済みのため、将来 gBizINFO 側が新版を公開した場合も `GBIZINFO_BASE` の差し替えで追従できる。

## 確度ラベルの付与基準

| 確度ラベル | 付与条件 |
|---|---|
| 公的データで確認済み | gBizINFO で 13桁法人番号により一意確定した正式名称・所在地・法人番号 |
| 公的データ取得 | 日本郵便API等の公的データで一意確定した値 (例: 住所→郵便番号) |
| ネット検索(要確認) | Web検索由来の推定値 (電話番号 / 会社名推定)。検証用 URL (per-value 根拠ページ URL **または** 固定検索手段 URL=電話番号は番号埋め込み Google 検索) をページ本文の確認用URLセクション (`confirm-url-template.md` 正本) へ必須記録 |
| 未確定(要確認) | 一意確定不能で空欄保留した項目。『備考』へ remarks-templates の定型文言を記録 |

## フォールバック多段化 (fallback tier 表・正本)

per-field の取得は下表の tier 順で試行し、**確度ラベルは各 tier の上限を超えて付与しない** (確度昇格禁止 = フォールバックで上位ラベルを付けない。Goodhart 遮断)。定義済み全段 (下記ホワイトリスト内) を試行し尽くしてから空欄保留する。停止条件: 有限1巡・同一 `(source, pattern)` 再試行の機械スキップ・`MAX_ATTEMPTS_PER_FIELD=3` (Web/agent 等の外部試行上限。実装正本: `enrich_company.note_attempt`)。日本郵便 `postal_api` の sub-attempts は1回の決定論呼び出しの完結スナップショットとして冪等に全件転記する (`note_attempt` の gap-driven dedup/上限は Web/agent 専用。転記正本: `enrich_company.enrich` の郵便番号ブロック)。

| tier | 手段 | 確度ラベル上限 | 備考 |
|---|---|---|---|
| tier1 | gBizINFO (検索パターン複数化: 原文 → 正規化名 → 法人格除去名。正本 `resolve_company.name_query_patterns` / `normalize.strip_legal_form`) | 公的データで確認済み | 自動確定条件 (法人番号一致 or 会社名+住所2要素一致) は不変 |
| tier2 | 日本郵便 addresszip API (V2 逆引き。構造化検索（`pref_name`/`city_name`/`town_name`。`town_name` は素の町域→小字「字○○」/大字を段階剥離した複数バリアントで照会）→ `freeword`(番地除去) → `{pref/city}` 町域一覧の最長前方一致(`pick_best_prefix`。字マーカー無しの小字・枝番・カナ末尾や数字を含む町域名を拾える設計) の3段。実装正本 `postal_api.lookup_postal`) | 公的データ取得 | `pick_best`/`pick_best_prefix` がマッチングレベル(1=都道府県/2=市区町村/3=町域)と候補 zip 収束(前方一致段は最長一致+zip収束)で一意確定したもののみ採用 (誤値を入れない非対称コスト原則。前方一致段は一覧不返/不一致なら空欄に縮退するのみで誤値・回帰なし。`{pref/city}` 照会で実 API が町域一覧を返すかは再現率の実機確認対象であり、未実証でも精度には影響しない)。検証 URL は日本郵便トップ (郵便番号検索の入口) の固定 URL `https://www.post.japanpost.jp/` を共用 (weak。URL 単独では値を再確認できない=受容済み trade-off)。認証/通信失敗時は空欄+備考へ縮退 (auth→`postal_api_unauthorized` / network→`postal_api_unavailable`) |
| tier3 | WebSearch (Claude が実施・Python は検証のみ) | ネット検索(要確認) | **検証用 URL 必須** (origin=web で url 空は validate FAIL → 書き込みゲート reject)。電話番号は per-value 根拠ページの代わりに番号埋め込み Google 検索 URL (`enrich_company.phone_search_url`) を固定手段として持つ (weak。doc の web 定義=per-value 根拠URL または固定検索URL) |
| tier4 | 全段不成立 | 未確定(要確認) | 空欄 + 『備考』へ定型文言 (`remarks-templates.md` の `all_tiers_exhausted` 等・試行手段を列挙) で人間へ引き継ぎ |

### 属性 × 許可 tier ホワイトリスト

| 属性 | tier1 gBizINFO | tier2 日本郵便API | tier3 WebSearch |
|---|---|---|---|
| company_name (会社名) | —(ユーザー入力を保持) | — | 可 (候補列挙のみ・要確認止まり) |
| official_name (正式名称) | 可 | — | 可 (要確認止まり) |
| address (住所) | 可 | — | 可 (要確認止まり) |
| postal_code (郵便番号) | — | 可 (唯一の供給段。**Web 不可**) | 不可 |
| hojin_bango (法人番号) | 可 | — | 可 (要確認止まり。信頼キー昇格は gBizINFO 再照会後のみ) |
| phone_number (電話番号) | — | — | 可 |

- **機械強制**: `validate_company_master.validate_row` (g) が `FIELD_ALLOWED_ORIGINS` (許可段) と `ORIGIN_CERTAINTY_CAP` (origin → 確度上限: gbizinfo=公的データで確認済み / japanpost=公的データ取得 / web=ネット検索(要確認) / none=未確定(要確認)。user_input は確度付与対象外) で照合し、違反は FAIL → 書き込みゲートが reject する。
- **gap-driven 単調前進**: enrich 出力の `missing_fields[]` + `attempts[]` (`{field, source, pattern, result, reject_reason}`) を replay JSONL へ併記し、agent は attempts に無い `(source, pattern)` のみ次試行する。「取得できるまで動く」とは定義済み有限段を尽くすことであり、無限探索は人間裁定へ明示移譲する。
- **backfill 2 パス運用**: backfill 1 パス目の `needs_web_search` (page_id + missing_fields + attempts) を agent が Web 検索し、`--web-findings <json>` (page_id キーの属性別候補マップ) で再投入する。
- **信頼キー不変条項**: Web 検索由来の住所 (`address_provenance=web`) では 2 要素一致が成立しても自動確定しない (候補列挙へ降格・確度上限『ネット検索(要確認)』)。再 resolve は最大 1 回、法人番号が初回確定値と不一致なら自動確定禁止。
- 国税庁法人番号公表サイト API はトークン発行が 2週〜1.5月かかるため optional tier (既定無効) として本表の対象外 (open_issues 管理)。

## 信頼キーと名寄せ (key_constraints[C] 参照)

- upsert 一意キーの正本: gBizINFO が確定返却した 13桁法人番号のみ。
- Web検索推定経由の法人番号は確定扱いせず『ネット検索(要確認)』止まり。gBizINFO 再照会で確定後にのみ信頼キーへ昇格。
- 法人番号を持たない/取得不能な事業者は代替キー = 正規化会社名 + 住所ハッシュで仮同定し、『未確定(要確認)』として新規追記のみ。

## 縮退とリプレイ

外部依存障害時は取れた項目だけ書き、取れない項目は要確認とする。中間結果を JSONL (`eval-log/backfill-replay.jsonl`) へ退避し次回リプレイ可能にする。

### 日本郵便 addresszip API の失敗時の縮退

郵便番号取得は日本郵便 addresszip API (V2) に一本化している (一括 DL データは廃止)。失敗は誤値を入れず空欄 + 備考 + `missing_fields` で人間へ引き継ぐ (可用性 > 完全性、ただし誤値は出さない)。

- **認証失敗** (`x-forwarded-for` の送信元IPが日本郵便の登録IPと不一致、または client_id/secret_key 不正): token 発行が HTTP 401/403。`postal_api` は attempts に `result=error` + `reject_reason` を `auth:` 始まりで記録 → 郵便番号は空欄 + 備考 `postal_api_unauthorized`。ローカル回線のグローバルIPが固定でない場合に発生しうる。`company_master.py doctor --probe` が token 発行 + テスト検索で登録IPとのズレを検知する。
- **通信失敗** (ネットワーク不達 / 5xx / timeout): attempts に `result=error` + `reject_reason` を `network:` 始まりで記録 → 空欄 + 備考 `postal_api_unavailable`。時間をおいて再試行する。
- **一意確定不能** (API は応答したが `pick_best` がマッチングレベル不足・町域複数該当で確定できない): `result=miss` → 空欄 + 備考 `postal_code`。誤値を入れずに保留する。
- セットアップ (for Biz 登録 → 送信元IP登録 → client_id/secret_key の Keychain 保存) は `references/japanpost-api-setup.md` を正本とする。`doctor` が鍵/IP 未設定を WARN で案内する。
