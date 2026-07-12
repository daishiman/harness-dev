# MF KESSAI API v2 — 発行漏れチェック用リファレンス

> 一次ソース: https://developer.mfkessai.co.jp/docs/v2/ (swagger 2.14.0)
> 本ドキュメントは `run-mf-invoice-check` / `run-mf-invoice-db-setup` が参照する実装知識。実レスポンス例は 2026-06 時点の本番疎通で確認した構造（企業名・口座等の機微値はマスク）。

## 1. 認証 / ベースURL

| 項目 | 値 |
|---|---|
| 認証ヘッダ | `apikey: <APIキー>`（Bearer ではない） |
| 本番 | `https://api.mfkessai.co.jp/v2` |
| サンドボックス | `https://sandbox-api.mfkessai.co.jp/v2` |
| Accept | `application/json` |
| キー保管 | macOS Keychain `mfkessai-api-key.<keychain-prefix>` / `harness`（`lib/mfk_keychain.py`） |

## 2. エンドポイント実レスポンス例（マスク済み）

### 2.1 GET /customers?limit=1
```json
{"items":[{"id":"XXXX-XXXX","name":"<企業名>","number":"<法人番号>","payment_method":{...口座情報(本チェックでは不要)...},"object":"customer"}],
 "pagination":{"end":"XXXX-XXXX","has_next":true,"total":121}}
```
→ `id`(顧客ID) と `name`(企業名) のみ使用。口座情報は使わない。

### 2.2 GET /billings/qualified?issue_date_from=...&issue_date_to=...&status=invoice_issued
```json
{"items":[
  {"id":"9PVV-GMYR","customer_id":"N4V9-R3E7","amount":110000,"issue_date":"2026-06-19",
   "due_date":"2026-07-31","status":"invoice_issued","invoice_ids":["XXXX-XXXX"],"object":"billing"}
 ],
 "pagination":{"end":"...","has_next":true,"total":89}}
```
→ 発行漏れ判定の母集合。`customer_id` を集合化し差集合を取る。`amount` は金額（前月/今月比較）。

### 2.3 GET /transactions?billing_id=9PVV-GMYR
```json
{"items":[
  {"id":"EW3E-PAWW","customer_id":"N4V9-R3E7","billing_id":"9PVV-GMYR","amount":110000,
   "date":"2026-05-31","issue_date":"2026-06-19","due_date":"2026-07-31","status":"passed",
   "created_at":"2026-06-19T15:47:39+09:00",
   "transaction_details":[
     {"description":"<商品名>（2026年4月分）","amount":50000,"unit_price":50000,"quantity":1},
     {"description":"<商品名>（2026年5月分）","amount":50000,"unit_price":50000,"quantity":1}
   ]}]}
```
→ 商品名(`description`)・金額(`amount`/`unit_price`×`quantity`)・更新日(`created_at`)を突合。

#### 2.3.1 取消(canceled)取引の形状（本番 2026-05・8件で確認）
取消された取引は **transaction 層にのみ** 取消情報が出る（billing keys には出ない）。
```json
{"id":"...","billing_id":"...","amount":2310000,"date":"2026-05-31","status":"canceled",
 "canceled_at":"2026-06-25T17:39:45+09:00",
 "transaction_details":[{"description":"<商品名>（…）","amount":2310000,"unit_price":2310000,"quantity":1}]}
```
- `status` が `"canceled"`（通常は `"passed"`）。← 取消判定シグナル(SSOT)。
- `canceled_at`（ISO8601+TZ）に取消日時。`passed` 取引には無い想定。
- `amount` と `transaction_details[].amount/unit_price/quantity` は **取消前金額を保持**（0化されない・商品名も読める）。
- 対応する `billing.amount == 0`（billing 集計のみ0）。**`billing.status` は `invoice_issued` のまま**。
- したがって status を無視すると取消前金額が有効供給に化け、発行確認OK（MATCH）に誤判定する。`run-mf-invoice-reconcile` は status=canceled を別バケットへ隔離し、有効供給ゼロかつ取消ありの当月期待を **要確認(取消)** で可視化する。`run-mf-invoice-check`（簡易差集合）は canceled を発行集合から除外する（最小 correctness）。
- `status` の有効供給判定は **ホワイトリスト方式**（`active = passed / 空 / None`）。`canceled` 以外でも `passed` でない状態（審査中・否決・取引停止・未処理 等）は非active として隔離し、有効供給ゼロかつそれらが存在する当月期待を **要確認(取引未確定)** で可視化する（発行漏れ＝赤への silent 誤分類を防ぐ前向き防御。現データでは `passed`/`canceled` のみ出現）。

## 3. 発行漏れ判定 擬似コード

```python
def detect_gaps(prev_billings, curr_billings):
    P = {b["customer_id"] for b in prev_billings if b["status"] == "invoice_issued"}
    C = {b["customer_id"] for b in curr_billings if b["status"] == "invoice_issued"}
    return {
        "gap_candidates": P - C,   # 前月取引あり・今月取引なし = 発行漏れ候補 ★本丸
        "continuing":     P & C,   # 継続発行 (金額変動を amount で検出)
        "new_this_month": C - P,   # 今月新規
    }
```

- 月帰属の軸は **`transaction.date` 基準（取引日＝月末締め）**。当月取引分（例「6月分」＝取引日 2026/06/30）の請求書は翌月月初に発行される（発行日＝翌月）ため、`issue_date` で当月内に絞ると当月取引分を取りこぼし・前月取引分を誤混入する。月次フローは `issue_date` 窓を翌月末まで広げて over-fetch し、`transaction.date` が当月のものだけを採用して当月帰属を確定する。1 transaction に複数役務月の明細（例「4月分」「5月分」）が混在する場合は `transaction.date` を代表帰属とする。
- `gap_candidates` の各 customer は `/customers?ids=` で企業名、`/transactions?billing_id=`(前月billing) で商品名・前月金額を解決。
- **年間契約期間中(初回契約月から12ヶ月)の発行漏れ候補は機械が自動抑制する** (Notion 管理列 `初回契約月` を読み `billing_lifecycle` で判定、年間前払い期間中は月次発行が無いのが正常)。`初回契約月` は API で取得できないため人が YYYY-MM で記入し、機械はそれを読んで抑制に用いる。初回契約月が空/不明の顧客は fail-safe で候補に残す。
- 「契約終了で今月不要」は API で判別不能 → 候補として出し、除外は Notion `請求要否` 列で人が判断 (この例外判断は機械化しない)。

## 4. フィールド定義（使用分）

| フィールド | 型 | エンドポイント | 用途 |
|---|---|---|---|
| `customer_id` | string | billings/transactions | 差集合キー・名寄せキー |
| `name` | string | customers | 取引先企業名 |
| `amount` | int | billings/transactions | 金額(税込) |
| `date` | date | transactions | 取引日(月末締め)。**月帰属の判定軸**(当月分の確定に使う) |
| `issue_date` | date | billings | over-fetch 取得窓([当月初..翌月末])に使う。月帰属の判定軸ではない(帰属確定は `transaction.date`) |
| `status` | enum | billings | `invoice_issued`/`scheduled`/`account_transfer_notified`/`stopped` |
| `status` | enum | transactions | `passed`(有効) / `canceled`(取消)。**取消判定シグナル**。取消は別バケットへ隔離 |
| `canceled_at` | datetime | transactions | 取消日時(ISO+TZ)。`status=canceled` のみ存在。取消前金額は `amount` に保持される |
| `invoice_ids` | string[] | billings | 発行済み請求書の実体(発行確証) |
| `transaction_details[].description` | string | transactions | 商品名 |
| `unit_price`/`quantity` | int | transactions | 単価×数量(継続/期間明細) |
| `created_at` | datetime | transactions | 更新日の代替(updated_at は無い) |

## 5. ページネーション

カーソル型。`limit`(≤200, 既定20)。応答 `pagination.end` を次回 `after=<end>` に渡し `has_next=false` まで反復。`pagination.total` で全件数。

```python
def iter_all(get, path, params):
    params = dict(params, limit=200)
    while True:
        page = get(path, params)
        yield from page["items"]
        if not page["pagination"]["has_next"]:
            break
        params["after"] = page["pagination"]["end"]
```

## 6. 注意点

1. `GET /billings`(区分記載) はインボイスモードで **0件**。必ず `GET /billings/qualified`。
2. `updated_at` は存在しない。更新日は `created_at`/`accepted_at`/`billing_accepted_at`。
3. レート制限は spec 未記載 → `limit=200` カーソル + バックオフを保守的に。
4. 定期請求/自動延長の概念は API に無い。契約開始月・支払サイクルは Notion 管理列 `初回契約月`(人が YYYY-MM で記入)/`支払サイクル` に持ち、**年間契約期間中の発行漏れ抑制は機械がこの初回契約月を読んで自動で行う**。「20万×3」等の個別スケジュール判断や契約終了の例外は引き続き人が `請求要否` 列で管理する。
5. 全て GET（参照専用）。POST/PATCH/DELETE は `run-mf-invoice-check` の PreToolUse hook で遮断。
