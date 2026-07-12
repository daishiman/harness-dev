---
name: ref-mf-kessai-api
description: MF掛け払いAPIのエンドポイント・認証仕様を確認したいとき、発行漏れ判定ロジック(前月−今月の差集合)の参照知識が必要なときに使う。
disable-model-invocation: false
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-06-19
version: 0.1.0
source: https://developer.mfkessai.co.jp/docs/v2/
source-tier: external-spec
last-audited: 2026-06-19
audit-trigger: official-update
allowed-tools:
  - Read
  - Bash(python3 *)
---

# ref-mf-kessai-api

## Purpose & Output Contract

マネーフォワード掛け払い (MF KESSAI) API v2 の**読み取り仕様と発行漏れ判定アルゴリズムの参照正本**。`run-mf-invoice-check` / `run-mf-invoice-reconcile` / `run-mf-invoice-db-setup` が本スキルを参照して、どのエンドポイントから何を取り、どう差集合を取るかを決める。

**入力**: なし (知識参照)
**出力**: 認証方式・主要エンドポイント・フィールド・発行漏れ判定アルゴリズムの知識。実行コードは `lib/mfk_api.py` / `lib/mfk_keychain.py`。
**完了条件**: 参照のみ。API 呼び出しの実行はしない (実行は lib/ が担う)。

## 認証・ベースURL

- 認証: HTTP ヘッダ `apikey: <APIキー>` (Bearer ではない)
- 本番: `https://api.mfkessai.co.jp/v2` / サンドボックス: `https://sandbox-api.mfkessai.co.jp/v2`
- APIキーは macOS Keychain (`mfkessai-api-key.<keychain-prefix>` / `harness`) から `lib/mfk_keychain.py` が取得。Claude context に生値を載せない。

## 主要エンドポイント (発行漏れチェックで使う)

| 用途 | パス | 主パラメータ | 返す主フィールド |
|---|---|---|---|
| 顧客一覧 (企業名名寄せ) | `GET /customers` | `ids`(最大200), `limit`(≤200), `after` | `id`, `name`, `number` |
| 発行済み請求一覧 (インボイスモード) | `GET /billings/qualified` | `issue_date_from/to`, `status`, `limit`, `after` | `id`, `customer_id`, `amount`, `issue_date`, `status`, `invoice_ids` |
| 請求単体 | `GET /billings/{id}` | — | 上記 + `due_date` |
| 取引・明細 (商品名・金額・取引日) | `GET /transactions` | `billing_id`, `customer_id`, `limit`, `after` | `date`, `transaction_details[].description`, `amount`, `unit_price`, `quantity`, `created_at`, `issue_date` |

> **重要 (インボイスモードの罠)**: 区分記載用の `GET /billings` はインボイス制度モードの事業者では **0件** を返す。一覧は必ず **`GET /billings/qualified`** を使う。`GET /billings/{id}` (単体) はどちらでも有効。

## 発行漏れ判定アルゴリズム

```
P = { b.customer_id | b in /billings/qualified(over-fetch) + /transactions(date=前月) }   # 前月取引先
C = { b.customer_id | b in /billings/qualified(over-fetch) + /transactions(date=今月) }   # 今月取引先

発行漏れ候補 = P − C      # 前月取引はあったのに今月取引がない取引先 ★本丸
継続発行     = P ∩ C      # 金額変動はここで検出 (前月取引 amount vs 今月取引 amount)
今月新規     = C − P
```

- 月帰属の軸は **`transaction.date` (取引日・月末締め) 基準**。例: 「6月分の請求書」は取引日 `2026-06-30` の請求で、発行日が翌月月初でも 6月分として扱う。`issue_date` は対象月初〜翌月末の over-fetch 窓に使い、帰属確定には使わない。
- 「契約終了で今月は請求不要」かどうかは **API から判別不能**。発行漏れ候補として出し、除外判断は人が Notion の `請求要否` 列で行う (この例外判断は機械化しない)。
- 「契約ID」「初回契約月」「支払サイクル」「月払い自動更新月」は **API から直接は判別不能**。企業ごとの契約開始月は Notion 管理列 `初回契約月` に YYYY-MM、`支払サイクル` (月払い/年間払い) を人が設定する。**年間契約期間中(初回契約月から12ヶ月)の発行漏れ候補の抑制は、機械がこの記入された初回契約月を読んで自動で行う** (`billing_lifecycle`/`suppress_annual_period_gaps`)。月次チェック(sink)はこれら管理列に触れない (読むのは抑制のため、書き込みはしない)。

## 取得できる要件フィールドの対応

| 要件 | 取得元 | フィールド |
|---|---|---|
| 商品名 | `/transactions` | `transaction_details[].description` |
| 取引日(月次照合の月帰属) | `/transactions` | `date` |
| 金額 | `/transactions` / `/billings/qualified` | `amount`, `unit_price`×`quantity` |
| 更新日 | `/transactions` | `created_at` / `accepted_at` (明示的 `updated_at` は無い) |
| 取引先企業名 | `/customers` | `name` (`customer_id` で名寄せ) |
| 発行状態 | `/billings/qualified` | `status` (`invoice_issued`/`scheduled` 等) |
| 初回契約月・支払サイクル | 直接取得不可 | Notion 管理列 `初回契約月` に YYYY-MM で手入力、`支払サイクル` を人が設定。**年間契約期間の発行漏れ抑制は機械がこの初回契約月を読んで自動判定** (`billing_lifecycle`) |

## ページネーション

カーソル型。`limit`(≤200, 既定20) + 応答 `pagination.end` を次回 `after=<end>` に渡し `has_next=false` まで反復。`pagination.total` で全件数。

## Key Rules

1. **参照専用**: 本スキルは仕様の参照のみ。実行は `lib/`。請求書発行 (POST) は行わない (`run-mf-invoice-check` の PreToolUse hook と GET 専用クライアントで抑止)。
2. **一覧は qualified**: インボイスモードで `/billings` は空。必ず `/billings/qualified`。
3. **月帰属を混同しない**: 月次チェックはいずれも `transaction.date` 基準。`issue_date` は over-fetch 用の取得窓に限る。
4. **キーは Keychain**: 生値を context に載せない。

## Gotchas

1. `GET /billings` が 0件でも異常ではない (インボイスモード)。`qualified` で確認する。
2. `updated_at` は存在しない。更新日は `created_at`/`accepted_at`/`billing_accepted_at` で代替。
3. レート制限は spec 未記載。保守的に `limit=200` カーソル + バックオフ。
4. 定期請求/自動延長/初回契約月/支払サイクルの概念は API に無い。契約開始月・支払サイクルは人が Notion 管理列 (`初回契約月`/`支払サイクル`) に設定する。**年間契約期間中の発行漏れ抑制は機械がこの初回契約月を読んで自動判定する** (`billing_lifecycle`)。「20万×3」等の個別スケジュール判断や契約終了の例外は引き続き人が `請求要否` 列で管理する。

## Additional Resources

- `references/mf-kessai-api.md` — 実レスポンス例・フィールド全定義・判定擬似コードの詳細
- `lib/mfk_keychain.py` — Keychain からの APIキー取得 (`get_api_key()`)
- `lib/mfk_api.py` — GET 薄ラッパ (`get(path, params)`) と疎通確認 (`--smoke`)
