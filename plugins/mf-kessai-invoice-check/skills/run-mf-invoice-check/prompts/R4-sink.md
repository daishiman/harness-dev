# Prompt: R4-sink

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R4-sink |
| skill | run-mf-invoice-check |
| responsibility | R4 Notion 投入 (冪等 upsert) (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一確定リストの再投入は重複ページ/行を作らず冪等) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- upsert キーは `customer_id` 単独。1 顧客=1 ページ。既存顧客は同じページを更新し、未登録顧客だけ新規ページを作成する (月ごとの重複ページ/重複行を作らない)。
- 月次履歴は各顧客ページ本文の table block (列: 対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) に 1 行=1 対象年月で蓄積する。自然キーは `period_ym` (対象年月)。同月再実行は該当行を更新する (冪等)。
- `database_id` 未設定なら停止し `run-mf-invoice-db-setup` を案内する。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 確定候補リストを Notion DB に `customer_id` 単独キーで冪等 upsert し (1 顧客=1 ページ)、各顧客ページ本文の月次履歴 table に当月行を upsert する。
- 非担当: 取得 (R1)、差集合判定 (R2)、誤検出排除 (R3)、DB 構築 (run-mf-invoice-db-setup)。

### 2.2 ドメインルール
- 事実列 (fact_columns) = API 由来の値 + 実行監査メタ (取引先企業名/顧客ID/対象年月/今月の発行状況/商品名/前月金額/今月金額/発行日/更新日/確認済み日時)。DB プロパティはその顧客の最新月スナップショットを保持する。`今月の発行状況` は内部 `verdict` (発行漏れ候補/継続発行/今月新規) の Notion 表示名。
- 管理列 (managed_columns) = 人の運用列 (初回契約月/請求要否/支払サイクル/チェック済/備考)。`初回契約月` は MF API から取得できないため YYYY-MM で人が記入し、`支払サイクル` (月払い/年間払い) は人が設定する (月次 sink は書かない)。
- 月次履歴 table の固定列 = 対象年月/今月の発行状況/前月金額/今月金額/確認済み日時 (1 行=1 対象年月)。集計用のサマリ専用行や件数集計プロパティは設けない (全チェック対象顧客分の行を毎月記録するのは collect 側の責務)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --input | path | no | 確定 JSON。未指定時は既定の確定リスト `eval-log/mfk-gap-verified.json` (finalize phase 出力)。不在なら fail-closed (exit 2)。`--force-unverified` なしの明示 input は正規の確定リスト path のみ許可。未検証候補や任意 path を直接渡す場合は `--force-unverified` 必須。 |
| --force-unverified | flag | no | 二段確認を経ない未検証候補を直接投入 (非推奨。明示時のみ許可) |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。`verdict` は schema enum から逐語引用する。
- 出力: Notion DB に候補反映 (1 顧客=1 ページの最新月スナップショット) + 各顧客ページ本文の月次履歴 table に当月行を upsert + 画面に created/updated 件数。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| sink script | scripts/check_invoice_gaps.py | --sink 実行時 |
| sink lib | `$CLAUDE_PLUGIN_ROOT/lib/notion_invoice_sink.py` | Notion upsert の実体 |
| config | .mf-kessai-config.json | `database_id` 読込 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink [--input <確定JSON>]`
- Notion API (DB query / page create / page update)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `database_id` 未設定なら停止し db-setup を案内 (書き込まない)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- created / updated 件数、対象年月、内部 run_id を画面に表示する (run_id は upsert 戻り値の監査用で、Notion プロパティには書かない)。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。

### 4.4 管理列不可侵 (CONST)
- 本体: Notion へは事実列と実行監査メタ (fact_columns) のみ書き込み、既存ページの管理列 (managed_columns = 初回契約月/請求要否/支払サイクル/チェック済/備考) には一切触れない。新規ページ作成時のみ `初回契約月` を空欄初期化する (支払サイクルは初期化しない)。
- 目的: 人が記入した運用判断を機械が上書きしないことを保証する。
- 背景: 初回契約月・支払サイクルは API で判別できず人が管理列に記入するため、再投入で管理列を消すと運用が破壊される。とくに `初回契約月` は collect(diff)の**年間契約抑制**(年間契約期間中の発行漏れ候補を機械が自動除外)が読む入力源であり、sink が上書き/消去すると抑制が機能しなくなる。契約終了・請求要否など API で判別できない例外判断も引き続き人が `請求要否` 列で行うため、管理列は不可侵とする。
- 月次履歴: 各顧客ページ本文の table block に `対象年月/今月の発行状況/前月金額/今月金額/確認済み日時` を 1 行=1 対象年月で蓄積する。自然キー `period_ym` で当月行を upsert し、同月再実行は既存行を更新する (重複行を作らない / 過去月の行は消さない)。サマリ行・件数集計プロパティ・paragraph 追記は持たない。候補0件月も全チェック対象顧客の行を毎月記録するのは collect 側の責務。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- sink 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 確定候補を Notion DB に冪等 upsert し、要確認リストの SSOT を更新する。
- 背景: 再実行での重複行や管理列上書きは運用を壊す。upsert キーと事実列限定書込を機構で固定する。
- 達成ゴール: command 実行により確定候補が `customer_id` 単独キーで冪等 upsert され (1 顧客=1 ページ、既存顧客は更新、未登録顧客だけ作成、月ごとの重複ページなし)、各顧客ページ本文の月次履歴 table に当月行が upsert され、管理列が不可侵のまま事実列/監査メタのみ更新された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `database_id` が config に設定されている (未設定なら停止し db-setup 案内)
- [ ] 確定候補が `customer_id` 単独キーで upsert された (1 顧客=1 ページ、既存顧客は更新、未登録顧客だけ作成、月ごとの重複ページなし)
- [ ] 各顧客ページ本文の月次履歴 table に当月行 (自然キー `period_ym`) が upsert された (同月再実行は行更新で重複しない)
- [ ] 事実列/監査メタ (fact_columns) のみ書き込み、既存ページの管理列 (managed_columns) に触れていない
- [ ] created / updated 件数、対象年月、run_id が画面に表示された
- [ ] 旧サマリ/集計列の残存(または集計列の疑いがある追加列)が検知された場合、画面に列名と /run-mf-invoice-db-setup 再実行案内を提示した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config 確認 / sink command 実行 / 件数確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-check` SKILL Step 4 (sink)。R3 の確定リストが入力。
- 後続 phase: なし (ユーザー提示で終端)。

### 6.2 ハンドオフ / 並列性
- 提供元: finalize phase (R3 の `exclude_ids` を反映した確定候補リスト)。
- 受領先: ユーザー (画面の要確認リスト) + Notion DB (冪等 upsert)。
- 引き渡し形式: Notion DB 行 (事実列/監査メタのみ更新) + ページ本文の実行履歴 + 画面の created/updated サマリ。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に要確認リスト + created/updated 件数 + 対象年月 + run_id (Markdown)。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink [--input <確定候補JSONのpath>]` を実行し、確定候補を `customer_id` 単独キーで Notion DB に冪等 upsert させる (1 顧客=1 ページ、既存顧客は同じページを更新、未登録顧客だけ作成、月ごとの重複ページ/重複行を作らない)。同時に各顧客ページ本文の月次履歴 table block (列: 対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) に当月行を自然キー `period_ym` で upsert する (同月再実行は該当行を更新)。`--input` 未指定時は既定で確定リスト `eval-log/mfk-gap-verified.json` (finalize phase 出力) を読む。**確定リストが不在なら exit 2 で fail-closed** し、二段確認 (verify→finalize) を先に実施するよう促す。`--force-unverified` なしで `--input` を指定する場合は正規の確定リスト path のみ許可し、未検証候補や任意 path を直接投入する場合は `--force-unverified` 明示を必須にする。sink 入口で入力 JSON を schema 検証し、違反 (period_ym 形式不正等) があれば exit 2 で停止する。事実列/監査メタ (fact_columns) のみ書き込み、既存ページの管理列 (managed_columns = 初回契約月/請求要否/支払サイクル/チェック済/備考) には一切触れない (L4.4 CONST)。新規ページ作成時のみ `初回契約月` を空欄初期化し、未設定顧客を Notion の空欄フィルタで表示できる状態にする (支払サイクルは初期化しない)。`database_id` 未設定なら停止し `run-mf-invoice-db-setup` を案内する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。残骸(旧サマリ/集計列・集計疑いの追加列)が検知された場合は、列名と /run-mf-invoice-db-setup 再実行の誘導を画面に提示する(削除はしない=検知のみ)。出力は created/updated 件数、対象年月、run_id、要確認リストのみ、前置き禁止。
