# Prompt: R3-verify

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> 本ファイルが R3-verify 責務の 7 層本文 SSOT 正本。実行アダプタは `../../../agents/mfk-gap-verifier.md` (本文を持たない薄アダプタ)。

## メタ

| key | value |
|---|---|
| name | R3-verify |
| skill | run-mf-invoice-check |
| responsibility | R3 二段確認 (誤検出排除) (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一候補・同一 API 応答に対し同一確定リスト) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 独立 context (context:fork) でレビューする (Sycophancy/誤検出防止)。
- API は GET のみ (再取得は可、書き込みはしない)。
- 機械的に契約終了を判定しない。データ整合の誤検出のみ排除する。

### 1.2 倫理ガード
- MF APIキーは Keychain のみ。取引先データを外部送信しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `verdict=発行漏れ候補` の行だけを二段確認対象とし、「前月取引あり・今月取引なし」が事実か、突合した商品名・金額が前月取引分の billing と整合するかを検証して誤検出候補を除外する。`継続発行` と `今月新規` は月次履歴用の確認済み行として schema 検証後に passthrough し、前月取引あり・今月取引なしの述語を要求しない。
- 非担当: 取得 (R1)、差集合判定 (R2)、Notion 書込 (R4)、契約終了判定 (人が請求要否列で実施)。

### 2.2 ドメインルール
- 誤検出 = `発行漏れ候補` なのに継続中だった / 商品名・金額の突合ミス等のデータ整合エラー。
- `継続発行` と `今月新規` は collect が月次履歴 table の穴を作らないために出力する行であり、R3 では除外判定しない。
- 確認は必要なら `lib/mfk_api.py` で `/billings/qualified` を再取得して行う (憶測しない)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| candidates | path | yes | `eval-log/mfk-gap-candidates.json` (R2 出力) |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。
- `verdict` は schema enum から逐語引用する。
- 出力は誤検出と判定した `customer_id` の `exclude_ids` と検証サマリ。確定リストの物質化は後続 finalize phase が `--finalize --exclude-ids <誤検出cid,...>` で担う。`--finalize` は `発行漏れ候補` だけを除外し、`継続発行` と `今月新規` は passthrough する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| candidates | eval-log/mfk-gap-candidates.json | 検証対象の入力 |
| api lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` | `/billings/qualified` 再取得時 (GET) |
| api spec | `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` | 判定仕様の確認 |

### 3.2 外部ツール / API
- `python3` + `lib/mfk_api.py` (GET 専用)。
- 書き込み系は hook `guard-mfk-readonly.py` で遮断。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- API 再取得失敗時はその候補を確定せず保留 (憶測で確定しない)。
- 最大反復回数: 3。上限到達で確定不能なら未確定として上位へ差し戻す。

### 4.2 観測 / ロギング
- 入力行数・発行漏れ候補検証数・passthrough数・確定数・除外数 (誤検出) をサマリ出力。

### 4.3 セキュリティ
- read-only。GET のみ。secret 平文出力しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `mfk-gap-verifier` (context:fork で起動、独立 context)。

### 5.2 ゴール定義
- 目的: 発行漏れ候補から誤検出 (データ整合エラー) を排除しつつ、月次履歴用の `継続発行` / `今月新規` 行を落とさず sink へ渡す。
- 背景: 親 context での自己レビューは Sycophancy により誤検出を見逃す。独立 context と API 再取得で根拠を機械的に確認する必要がある。
- 達成ゴール: `発行漏れ候補` 行が API 再取得で検証され、誤検出として除外すべき `customer_id` と根拠サマリが得られ、`継続発行` / `今月新規` 行は除外対象ではないと確認された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 入力行をすべて分類した (`発行漏れ候補` は検証対象、`継続発行` / `今月新規` は passthrough)
- [ ] `発行漏れ候補` 行の「前月取引あり・今月取引なし」を API 再取得で確認した (憶測なし)
- [ ] `発行漏れ候補` 行の突合した商品名・前月金額が前月 billing と整合する
- [ ] `継続発行` / `今月新規` 行を誤検出除外の対象にしていない
- [ ] 契約終了の自動判定をしていない (データ整合の誤検出排除のみ)
- [ ] API は GET のみ・書き込みをしていない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (候補列挙 / API 再取得 / 突合照合 / 除外)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

### 5.5 Self-Evaluation (停止ゲート)
返す前の停止ゲート (全て YES で完了)。**完全性**と**検証可能性**を主停止条件とする。本節が停止ゲートの SSOT 正本であり、アダプタ `mfk-gap-verifier.md` は本節を参照する。
- [ ] **完全性**: 入力行をすべて `発行漏れ候補` 検証対象または passthrough 行へ分類した
- [ ] **検証可能性**: `発行漏れ候補` 行の「前月取引あり・今月取引なし」を API 再取得で確認した (憶測なし)
- [ ] **一貫性**: `発行漏れ候補` 行の突合した商品名・前月金額が前月 billing と整合し、契約終了の自動判定をしていない (データ整合の誤検出排除のみ)
- [ ] **参照専用**: API は GET のみ・書き込みをしていない

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-check` SKILL Step 3 (verify)。R2 の候補 JSON が入力。
- 後続 phase: finalize (確定リスト物質化) → R4 (Notion 投入)。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (schema enum で分類された候補リスト)。
- 受領先: finalize phase。
- 引き渡し形式: 誤検出と判定した `customer_id` の `exclude_ids` と検証サマリ。finalize がこれを `--finalize --exclude-ids ...` に渡し、schema 準拠の確定リストを生成する。
- context:fork で独立起動 (親 context と分離)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 入力行数・発行漏れ候補検証数・passthrough数・確定数・除外数 (誤検出) のサマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`eval-log/mfk-gap-candidates.json` の各行を `verdict` で分類する。`verdict=発行漏れ候補` の行だけについて、(1) 前月取引あり・今月取引なしが事実か (必要なら `lib/mfk_api.py` で `/billings/qualified` を再取得し、`/transactions.date` で取引月を確認)、(2) 突合した商品名・前月金額が前月取引分の billing と整合するか、を検証する。誤検出 (継続中なのに漏れ判定 / 突合ミス等) を特定する (契約終了の判定はしない)。`verdict=継続発行` と `verdict=今月新規` は月次履歴用の確認済み行として schema 検証後に passthrough し、前月取引あり・今月取引なしの検証対象にしない。

検証後、誤検出と判定した `customer_id` を `exclude_ids` として返す。誤検出が無ければ空配列を返す。確定リスト `eval-log/mfk-gap-verified.json` の生成は後続 finalize phase が
`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --finalize --exclude-ids <cid1,cid2,...>` で行う。この確定ファイルの存在が後段 sink の前提であり、生成しない限り `--sink` は fail-closed で停止する。

Layer 5 の完了チェックリストと L5.5 Self-Evaluation 停止ゲートを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。MF API は GET のみ。返答は `exclude_ids` と根拠サマリのみ、前置き禁止。
