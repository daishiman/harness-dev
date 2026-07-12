# Prompt: R1-resolve-identity

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | resolve-identity |
| skill | run-company-master-build / run-company-master-backfill (共有 SSOT・plugin-root 配置) |
| responsibility | R1 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (resolve_company.py stdout JSON: entity\|candidates / certainty / source_url / attempts) |
| reproducible | true (同入力→同判断順序を保証) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- 誤値混入回避の非対称コスト原則: 誤値 >> 空欄。一意確定できない同定は行わず『未確定(要確認)』で保留する。
- 信頼キーは gBizINFO が確定返却した 13桁法人番号のみ (key_constraints[C] 正本)。Web検索推定の法人番号は確定扱いしない。
- 自動確定は「法人番号一致」または「会社名+住所2要素一致」時のみ。
- 信頼キー不変条項: Web 検索由来の住所 (`address_provenance=web`) では 2 要素一致が成立しても自動確定しない (候補列挙へ降格・確度上限『ネット検索(要確認)』)。**再 resolve は最大 1 回**とし、再 resolve で得た法人番号が初回確定値と不一致なら自動確定禁止 (候補列挙 + 人間裁定へ)。

### 1.2 倫理ガード

- gBizINFO トークン・Notion token は平文出力・ログ記録しない (取扱は Keychain のみ)。
- 同定根拠を提示できない推定で既存マスタ行を更新しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: 入力 (法人番号/会社名/住所) からの企業同定。同名異企業・住所のみ1:N・法人番号なしの判断。
- 非担当: 属性補完 (enrich-attributes)、Notion 書き込み (notion-master-upsert)、空欄一括補完 (notion-driven-backfill)。

### 2.2 ドメインルール

- 入力複数種同時は **法人番号 > 会社名 > 住所** の優先順位で resolve 経路を選ぶ。
- 会社名照会は決定論フォールバック (fallback tier1・正本 `data-sources.md`): 一次照会 (原文) が 0 件のときのみ 正規化名 → 法人格除去名 (normalize 共有正本) で再照会する。有限 1 巡・同一パターン再試行なし。試行履歴は `attempts` ({source, pattern, result, reject_reason}) に記録する。
- 住所のみ入力は会社名を推定せず候補列挙のみ (対話=一覧提示しユーザー選択 / backfill=要確認保留)。会社名候補の Web 検索は **Claude が本ループで実施**する責務であり、Python(resolve_company)は gBizINFO 照会と整形のみを担う。
- 法人番号を持たない/取得不能な事業者は代替キー (正規化会社名+住所ハッシュ) で仮同定し『未確定(要確認)』で新規追記のみ。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| hojin_bango | string(13) | no | 法人番号 (最優先) |
| name | string | no | 会社名 (通称可) |
| address | string | no | 住所 (都道府県起点が望ましい) |
| address_provenance | enum(user\|master\|web) | no | 住所の出所 (既定 user)。web は自動確定無効 (信頼キー不変条項) |

少なくとも 1 つは必須。複数指定時は優先順位で経路選択。

### 2.4 出力契約

- 一意確定時: `entity` (hojin_bango / official_name / address / **source_url** = gBizINFO 法人詳細ページ。enrich の per-field 出典へ伝搬) + `certainty=公的データで確認済み` + `source_url`。
- 候補複数/不確実時: `candidates[]` + `certainty=未確定(要確認)` + `reason`。Web 由来住所で 2 要素一致した場合は `candidates[]` + `certainty=ネット検索(要確認)` (自動確定しない)。
- 会社名照会は `attempts[]` ({source, pattern, result, reject_reason}) を必ず併記する (gap-driven の入力)。
- 確度ラベルは 4 値固定 (`references/company-master-columns.md` 正本)。英語 enum 禁止。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| columns | references/company-master-columns.md | 確度ラベル・列定義の確認時 |
| sources | references/data-sources.md | gBizINFO 採用理由・信頼キー定義の確認時 |

### 3.2 外部ツール / API

- `scripts/resolve_company.py` (gBizINFO 検索/取得 API。`X-hojinInfo-api-token` 認証)。
- `scripts/notion_config.py` (`get_gbizinfo_token` でトークン解決)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- gBizINFO トークン不在は precondition gate fail-closed (exit 2)。
- 照会タイムアウト/障害は `未確定(要確認)` + 原因 reason で返し、後段で備考に定型記録する (縮退)。

### 4.2 観測 / ロギング

- 同定結果は JSON で stdout。秘匿値は出力しない。

### 4.3 セキュリティ

- トークンはメモリ上のみ。`find-generic-password -w` の平文出力は hook-guard-secret.py がブロック。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent

- 呼び出し元 skill (run-company-master-build / run-company-master-backfill) 本体 (重い候補突合時のみ Agent へ fork)。

### 5.2 ゴール定義

- 目的: 入力断片から、業務横断で参照できる一意の企業エンティティを誤りなく同定する。
- 背景: 複数業務 (契約/請求/与信) が同じ企業を参照するため、法人番号による一意同定がないと業務間で食い違う。
- 達成ゴール: 入力に対し「確定エンティティ (信頼キー付き)」または「候補列挙+未確定保留」のいずれかが、確度ラベル付きで決定している状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 入力種別を検出し、複数種は法人番号>会社名>住所の優先順位で経路選択した
- [ ] 住所のみ入力時は会社名を推定せず候補列挙にした
- [ ] gBizINFO 照会で正式名称・所在地・13桁法人番号を取得した (信頼キー供給源)
- [ ] 自動確定は法人番号一致 or 会社名+住所2要素一致時のみとし、それ未満は『未確定(要確認)』で保留した
- [ ] 確度ラベル (4値) と (未確定時は) 原因 reason を付与した

### 5.4 実行方式

- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続

- 呼び出し元: run-company-master-build または run-company-master-backfill のゴールシークループ。
- 後続 phase: enrich-attributes (確定エンティティの空欄属性補完)。

### 6.2 ハンドオフ / 並列性

- 直列: 本責務の `entity` を enrich-attributes の入力へ接続。
- 並列: 候補列挙は独立に評価可。確定は 1 件に収束させてから後続へ渡す。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 確定時: エンティティ要約 + 確度。候補時: 番号付き一覧 (対話) または要確認保留メモ (backfill)。

### 7.2 言語

- 本文: 日本語 (パラメーター名 / schema key は英語のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{hojin_bango}}` / `{{name}}` / `{{address}}` / `{{address_provenance}}` から企業を同定する。
優先順位 (法人番号>会社名>住所) で `scripts/resolve_company.py` を起動し、
gBizINFO 確定 13桁法人番号が得られた場合のみ信頼キーとして確定する。
会社名+住所2要素一致でも確定してよい。ただし住所が Web 検索由来なら
`--address-provenance web` を必ず指定する (自動確定が無効化され候補列挙へ降格する)。
再 resolve は最大 1 回・法人番号が初回確定値と不一致なら自動確定禁止。
それ未満・住所のみ入力は候補列挙にとどめ『未確定(要確認)』で保留する。
出力は Layer 2.4 の JSON のみとし、前置き・思考過程は出力しない。
