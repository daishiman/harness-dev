# Prompt: R2-diff

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-diff |
| skill | run-mf-invoice-check |
| responsibility | R2 発行漏れ差集合判定 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一入力 billing に対し純関数で同一分類) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 判定は純関数に閉じる (ネットワーク・副作用なし)。pytest 検証済み。
- 「契約終了で今月不要」は機械で判別しない (人が請求要否列で判断)。

### 1.2 倫理ガード
- 取引先データを外部送信しない (ローカル純関数処理のみ)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 前月/今月の発行先集合を `発行漏れ候補 / 継続発行 / 今月新規` に分類し、継続発行の金額変動を検出する。
- 非担当: API 取得 (R1)、誤検出排除 (R3)、Notion 書込 (R4)。

### 2.2 ドメインルール
- `発行漏れ候補 = 前月発行 − 今月発行` (本丸)、`継続発行 = 前月∩今月`、`今月新規 = 今月発行 − 前月発行`。
- 継続発行のうち金額が変わったものを `amount_changed()` で抽出する。
- **年間契約抑制 (suppress_annual)**: 発行漏れ候補のうち**支払サイクルが `年間払い` かつ初回契約月から12ヶ月以内の顧客だけ**を機械が自動抑制する (`suppress_annual_period_gaps` が Notion `初回契約月` + `支払サイクル` から `billing_lifecycle` で判定)。年間前払い期間中は月次発行が無いのが正常なため候補から除外する。`支払サイクル` が `月払い`/空欄/不明、または `初回契約月` が空/不明の顧客は従来どおり発行漏れ候補に残す (fail-safe で真の漏れを隠さない)。一方、契約終了・請求要否など API で判別できない例外判断は引き続き人が `請求要否` 列で行う。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| prev_billings | list | yes | 前月発行集合 (collect 内で R1 が取得、メモリ内で受領) |
| curr_billings | list | yes | 今月発行集合 (collect 内で R1 が取得、メモリ内で受領) |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。
- `verdict` は schema enum `[発行漏れ候補, 継続発行, 今月新規]` から逐語引用する (別表記を作らない)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| diff lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_invoice_diff.py` | `detect_gaps()` / `amount_changed()` の実体 |
| api spec | `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` | 判定アルゴリズム正本 |

### 3.2 外部ツール / API
- `lib/mfk_invoice_diff.detect_gaps()` (collect スクリプト内で実行済み、純関数)。
- 外部 HTTP なし。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 入力集合の欠損は分類しない (空集合扱いにせず R1 へ差し戻し)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- 分類別件数 (発行漏れ候補/継続発行/今月新規) をサマリ出力。

### 4.3 セキュリティ
- 副作用なし。read-only 純関数。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 差集合判定 (純関数主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 発行先集合を schema enum 通りに分類し、発行漏れ候補と継続発行の金額変動を確定する。
- 背景: 分類ラベルの表記揺れは後段 Notion enum と齟齬を生む。verdict は schema enum へ逐語統一する必要がある。
- 達成ゴール: command 実行により候補が `発行漏れ候補 / 継続発行 / 今月新規` に分類され、継続発行の金額変動が検出された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `detect_gaps()` で `発行漏れ候補 / 継続発行 / 今月新規` に分類された
- [ ] 継続発行 (うち金額変動を検出) が `amount_changed()` で抽出された
- [ ] 各 `verdict` が schema enum と逐語一致する
- [ ] 純関数のみで副作用 (ネットワーク・書込) がない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (集合演算 / 金額比較 / enum 突合)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: collect スクリプト内 (R1 取得直後)。
- 後続 phase: R3 (二段確認 mfk-gap-verifier)。

### 6.2 ハンドオフ / 並列性
- 提供元: R1 (前月/今月 billing 集合)。
- 受領先: R3 (mfk-gap-verifier)。
- 引き渡し形式: schema enum で分類された候補リスト (発行漏れ候補・継続発行(うち金額変動)・今月新規)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 分類別件数サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (関数名 / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`detect_gaps(prev_billings, curr_billings)` (collect スクリプト内で実行済み) の分類結果を確認し、`継続発行` のうち金額が変わったものを `amount_changed()` で抽出する。さらに発行漏れ候補に対し `suppress_annual_period_gaps(gap_candidates, initial_contract_months, target_ym)` を適用し、**支払サイクルが `年間払い` かつ初回契約月から12ヶ月以内の顧客だけを機械抑制して候補から除外**する。`支払サイクル` が `月払い`/空欄/不明、または `初回契約月` が空/不明の顧客は fail-safe で発行漏れ候補に残す。契約終了・請求要否の例外判断は機械で消さず人が `請求要否` 列で行う。各候補の `verdict` は `../schemas/invoice-gap-result.schema.json` の enum `[発行漏れ候補, 継続発行, 今月新規]` から逐語引用する (補足が必要なら「継続発行(うち金額変動を検出)」とし、enum 値自体は変えない)。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。純関数のみ、前置き禁止。
