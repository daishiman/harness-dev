# Prompt: R1-ground

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-ground |
| skill | run-blueprint-apply |
| responsibility | R1 受理検証と自社コンテキスト構造化 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/system-blueprint.schema.json |
| reproducible | true (同一 blueprint/verdict/own_context で同一 grounding) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- C02 verdict receipt が `verdict=PASS` かつ blueprint の draft_hash と一致することを確認できない限り、blueprint を入力として受理しない (不在/FAIL/hash 不一致は fail-closed に拒否して停止)。
- 対象 origin へ一切アクセスしない (network 0)。blueprint 本体 (`blueprint.json`) を書き換えない。
- 自社コンテキストは推奨の接地先であり、blueprint の fact/inference と混同しない (blueprint 由来の記述へ自社事実を注入しない)。

### 1.2 倫理ガード
- 認証後情報・機微を自社コンテキストから blueprint 側へ持ち出さない。参考/学習目的の適用判断であることを前提に扱う。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `blueprint.json` の読込、C02 verdict receipt の解決と PASS/draft_hash 一致検証、自社コンテキストの 4 面構造化。
- 非担当: 推奨導出 (R2)、emit と自己検証 (R3)。

### 2.2 ドメインルール
- verdict receipt は `--verdict-dir` (既定 `.esb-verdict`) 配下の `<draft_hash>.verdict.json` を解決する。receipt の `draft_hash` と blueprint の `draft_hash` が一致し、`verdict=PASS` のときだけ受理する。
- 自社コンテキストは **技術スタック / リソース制約 / 既存資産 / 対象ユーザー** の 4 面へ構造化し、各面へ後段推奨が参照する own_context_ref キーを付与する。文書パスは Read、自然文はそのまま構造化する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| blueprint_dir | path | yes | C02 PASS 済 blueprint 一式のディレクトリ (`blueprint.json` を正本) |
| own_context | path\|text | yes | 自社コンテキストの文書パスまたは自然文 |
| verdict_dir | path | no | verdict receipt 探索先。既定 `.esb-verdict` |

### 2.4 出力契約
- 受理判定 (accepted/rejected + reason) + blueprint の draft_hash + 4 面へ構造化した自社コンテキスト (own_context_ref キー付き)。
- rejected の場合は理由 (verdict 不在/FAIL/hash 不一致) を提示して停止する (以降の R2/R3 を起動しない)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| blueprint 正本 | `<blueprint_dir>/blueprint.json` | fact/inference/anchor/draft_hash の読取 |
| verdict receipt | `<verdict_dir>/<draft_hash>.verdict.json` | C02 PASS + draft_hash 一致検証 |
| blueprint schema | `$CLAUDE_PLUGIN_ROOT/schemas/system-blueprint.schema.json` | top-level shape 正本 |

### 3.2 外部ツール / API
- ファイル Read のみ (blueprint.json / verdict receipt / own_context 文書)。network なし・書込なし。
- 対象システムの公開 URL へは一切アクセスしない。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- verdict receipt 不在 / `verdict=FAIL` / draft_hash 不一致は受理拒否し理由を提示して停止する (R2/R3 を起動しない)。own_context が空/解決不能なら不足を提示して停止する。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に受理判定・draft_hash・4 面構造化サマリ。周回状態は `eval-log/run-blueprint-apply-intermediate.jsonl` へ追記する。

### 4.3 セキュリティ
- 自社コンテキストの機微を blueprint 側 record へ書き戻さない。blueprint.json は read-only で扱う。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- LLM 主体 (ファイル Read + 検証 + 構造化)。外部 script 起動なし。

### 5.2 ゴール定義
- 目的: C02 PASS 済 blueprint を fail-closed に受理し、自社コンテキストを推奨導出の接地先へ構造化する。
- 背景: proposer≠approver の下流として、独立評価 (C02) を経ていない blueprint への適用推奨を機構的に禁じ、blueprint の忠実性と推奨の自社接地性を分離する。
- 達成ゴール: verdict=PASS かつ draft_hash 一致が確認され、自社コンテキストが 4 面 (技術スタック/制約/既存資産/対象ユーザー) へ own_context_ref 付きで構造化された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `blueprint_dir/blueprint.json` を読み draft_hash と anchor 集合を把握した
- [ ] C02 verdict receipt を解決し `verdict=PASS` かつ draft_hash 一致を確認した (不在/FAIL/不一致は受理拒否)
- [ ] 自社コンテキストを技術スタック/リソース制約/既存資産/対象ユーザーの 4 面へ構造化した
- [ ] 各面へ後段推奨が参照する own_context_ref キーを付与した
- [ ] 対象 origin へアクセスせず blueprint 本体を書き換えていない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (blueprint 読込 / verdict 解決 / own_context 構造化)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-blueprint-apply` SKILL の R1-ground 局面。
- 後続 phase: R2-recommend が受理 blueprint と 4 面自社コンテキストを入力に 3 分類推奨を導出する。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (blueprint_dir/own_context)・C02 (verdict receipt)。
- 受領先: R2-recommend。
- 引き渡し形式: 受理済み blueprint 参照 (draft_hash) + 4 面構造化自社コンテキスト (own_context_ref 付き)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に受理判定 (accepted/rejected+reason)・draft_hash・4 面サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI 引数 / JSON キー / anchor は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`blueprint_dir/blueprint.json` を Read して draft_hash と anchor 集合を把握し、`--verdict-dir` (既定 `.esb-verdict`) の `<draft_hash>.verdict.json` を解決して `verdict=PASS` かつ draft_hash 一致を確認する。不在/FAIL/hash 不一致は受理拒否し理由を提示して停止する (R2/R3 を起動しない)。受理できたら own_context (文書パスは Read、自然文はそのまま) を技術スタック/リソース制約/既存資産/対象ユーザーの 4 面へ構造化し、各面へ own_context_ref キーを付与する。対象 origin へアクセスせず blueprint 本体を書き換えない。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は受理判定・draft_hash・4 面サマリのみ、前置き禁止。
