# Prompt: R1-collect

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-collect |
| skill | run-mf-invoice-reconcile |
| responsibility | R1 MF掛け払い実績取得 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/reconcile-result.schema.json |
| reproducible | true (同一 target・同一 API 応答に対し同一 MF index) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- MF掛け払い API は GET のみ。変更系 (POST/PATCH/DELETE) は一切行わない (hook `guard-mfk-readonly.py` でも遮断)。
- 月帰属の判定軸は必ず `transaction.date` (取引日・月末締め)。例: 「6月分の請求書」は取引日 `2026-06-30` の請求で、発行日が翌月月初でも 6月分として扱う。
- 同一の取引日(締め)月軸が請求確認シートの人手入力『年月』select にも適用される (順方向 GAP 検知の期待集合キー)。シートの『年月』は取引日(月末締め)の月で記入する (例: 取引日 `2026/06/30` 締め→年月 `2606`)。発行月で記入すると当月の期待集合から外れ真の発行漏れを見逃すため、MF 側 (`transaction.date`) と軸を一致させる。
- `/billings/qualified` は `issue_date` で取得窓を [対象月初 .. 翌月末] に広げて over-fetch し、帰属確定は `/transactions` の `transaction.date` で行う。
- 一覧は `/billings/qualified` を使う (インボイスモードで `/billings` は空)。発行済み status は `invoice_issued` と発行後に進む `account_transfer_notified` (口座振替通知済み=発行後の後続段階) で、両者を発行済みの証跡として採用する (共有 `collect_mf`=C01 が `mfk_collect_status.is_issued_billing` で client 側判定・`account_transfer_notified` の実在発行を落とさない)。`scheduled` (発行予定) / `stopped` (停止) は非発行のため証跡に使わない。

### 1.2 倫理ガード
- MF APIキーは Keychain のみ。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象月 (`--target YYMM`) の MF掛け払い実績を参照専用 GET で全ページ取得し、照合用 MF index を作る。具体的には `/billings/qualified` (`issue_date` が対象月初〜翌月末) を over-fetch → 発行済み status (`invoice_issued`/`account_transfer_notified`・`mfk_collect_status.is_issued_billing` で client 側判定) の billing のみ採用 → 各 billing の `/transactions` を取得 → `transaction.date` が対象月の明細 (`transaction_details`: description/amount/unit_price/quantity/billing_id) だけを line 化 → `/customers` で顧客名を解決 → `{"customers": {customer_id: {name, lines[]}}}` を `build_mf_index` へ渡す。
- 非担当: 請求確認シート→契約マスタ生成・双方向照合 (R2)、二段確認 (R3)、Notion 書込 (R4)。

### 2.2 ドメインルール
- 月帰属の判定軸は `transaction.date` (取引日・月末締め)。一覧取得の `issue_date` は API 取得窓であり、月帰属の正本ではない。`transaction.date` 欠落時だけ `transaction.issue_date` → `billing.issue_date` に fail-safe fallback する。
- 発行済み status (`invoice_issued` と発行後に進む `account_transfer_notified`) を採用する。`account_transfer_notified` は口座振替通知済み=発行後の後続段階であり (実測: paws 型の実在発行が `status=invoice_issued` 限定取得で偽の発行漏れになっていた)、これを除外すると真の発行を漏れ扱いする。`scheduled` (発行予定・未発行) と `stopped` (停止・非発行) は「発行済み」と誤認すると逆に漏れを隠すため MATCH 証跡にしない。発行/非発行の境界判定は `scripts/mfk_collect_status.py` の `is_issued_billing` (ホワイトリスト SSOT) が担う。
- カーソルページングは `limit=200` 固定 (レート対策)。`pagination.has_next` が true で `pagination.end` が空なら部分取得のまま続行せず停止する。
- MF 明細は API 上で同一行が二重化されるため `(billing_id, desc, amount)` で dedup する前提 (dedup・立替/負額/0円除外は `build_mf_index` が担当)。ただし `status=canceled` かつ description/商品名が残る0円明細は、単純な0円除外ではなく取消証跡として raw line に残し、後段で `REVIEW_CANCELED` へ可視化できるようにする。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | yes | 対象月 (例 `2606`)。YYMM 形式の実在月でないと fail-closed (exit 2)。 |

### 2.4 出力契約
- schema: `../schemas/reconcile-result.schema.json` (additionalProperties:false)。`verdict`/`direction` 表記は schema enum から逐語引用する。
- R1 単体の成果物: 後段 R2 へ引き渡す MF index (`build_mf_index` の戻り値、メモリ内) と、画面の取得件数サマリ (`[collect] MF顧客 N社 / 明細 N行`)。`reconcile-result.schema.json` 準拠の最終候補は collect→reconcile 全体の生成物であり、collect 単独段では確定しない。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| orchestrator | `$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py` | `--steps collect` 実行時 (`collect_mf`) |
| api lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` | GET 専用 API クライアント (`iter_all` / `get`) |
| index lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` | `build_mf_index` (照合用 index 構築) |
| api spec | `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` | エンドポイント・判定仕様の正本 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --steps collect`
- MF掛け払い API (GET のみ。変更系は hook `guard-mfk-readonly.py` で遮断)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `--target` 未指定 / YYMM 不正は exit 2 (fail-closed)。
- API エラー (HTTP / 接続 / ページング異常) は stderr に出し非ゼロ終了。部分取得のまま MF index を確定しない。
- collect 単独実行は Notion DB id を要さない (MF API / 純関数のみで完結し、DB id 解決の対象外)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に `[collect] MF顧客 N社 / 明細 N行 を取得 (参照専用GET)` の取得件数サマリ。

### 4.3 セキュリティ
- GET のみ。secret は Keychain 参照のみで平文出力しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- collect 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 対象月の MF 発行済み請求実績を漏れなく取得し、双方向照合 (R2) の入力となる MF index を揃える。契約開始月などシート由来の情報は付与せず、MF API から得られる実績のみを忠実に index 化する。
- 背景: 取得漏れ・誤エンドポイントは後段の双方向照合を腐らせる。`/billings/qualified` 全ページ取得と `(billing_id, desc, amount)` dedup を機構で固定する。
- 達成ゴール: command 実行により対象月の qualified billing と各 `/transactions` 明細・`/customers` 名が全ページ取得され、`build_mf_index` で照合用 MF index (`{customer_id: {cust, names, services}}`) が構築された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 対象月初〜翌月末の `/billings/qualified` (`status=invoice_issued`) を全ページ取得した
- [ ] 各 billing の `/transactions` 明細 (`transaction_details`) を取得し、`transaction.date` が対象月の取引だけを line 化した (desc/amount/unit_price/qty/billing_id/txn_date/status/canceled_at)
- [ ] `/customers` で顧客名を解決した
- [ ] `build_mf_index` 用の `{"customers": ...}` を構築し MF index を作った
- [ ] POST 等変更系を一切呼んでいない (GET のみ)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (collect command 実行 / 引数調整 / 再取得)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-reconcile` SKILL Step 1 (collect)。
- 後続 phase: R2 (sync-master → reconcile) が同一実行内で続く。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (`--target`) / MF API (`/billings/qualified`・`/transactions`・`/customers`)。
- 受領先: R2 (双方向照合・判定)。
- 引き渡し形式: R2 へは collect 内で構築した raw mf (`{"customers": ...}`、`build_contracts` のサイクル推定シグナル) と `build_mf_index` の MF index (メモリ内)。`reconcile-result.schema.json` は R1→R2 の引き渡しではなく、collect→reconcile 全体の最終生成物。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に取得件数 (MF顧客数 / 明細行数) のサマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --steps collect` を実行し、対象月初〜翌月末の `/billings/qualified` (`status=invoice_issued`) を `limit=200` カーソルページングで全ページ取得する。各 billing の `/transactions` 明細を取得し、月帰属は `transaction.date` で確定する。例: `--target 2606` では取引日 `2026-06-30`・発行日 `2026-07-01` の請求を 6月分として採用し、取引日 `2026-05-31`・発行日 `2026-06-01` の請求は除外する。line には `status` / `canceled_at` / description を保持し、`status=canceled` かつ商品名が残る0円明細も取消証跡として後段へ渡す。`/customers` で顧客名を解決して `{"customers": {customer_id: {name, lines[]}}}` を組み立て、`build_mf_index` で照合用 MF index を構築させる。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。GET のみ (変更系を一切呼ばない)。出力は取得件数サマリのみ、前置き禁止。
