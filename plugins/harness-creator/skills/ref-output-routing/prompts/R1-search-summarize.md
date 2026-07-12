# Prompt: R1-search-summarize (ref-output-routing)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-output-routing |
| responsibility | R1-search-summarize (sink-contract / security-model の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json (任意配置) |
| reproducible | true (同 query + 同 references → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (逐語抽出)**: 原文を改変しない (引用は逐語)。
  - 目的: sink 契約や security 条項の意味改変を防ぐ。
- **CONST_002 (warn 必須)**: security-model.md の禁止項目に抵触する箇所は `warn` フラグを付与する。
  - 目的: 禁止 sink への誘導を caller が確実に拒否できるようにする。
  - 背景: 禁止条項を本文に埋めて返すと caller LLM が読み飛ばす事故があった。
- **CONST_003 (契約要素保持)**: sink-contract.md の payload/result schema フィールドと exit code (0-4) の意味を欠落・改変させない。
  - 目的: caller が adapter の input/output 契約と失敗コードを即座に判断できるようにする。

### 1.2 倫理ガード
- 禁止 sink を黙認しない (必ず warn)。
- 未定義 sink を推定で許容しない (`suggestions` に返す)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/ (sink-contract.md, security-model.md) から query に該当する sink 種別 / セキュリティ条項を抽出・要約する。
- 非担当: sink への実書き込み、契約変更、security model 改訂。

### 2.2 ドメインルール
- sink-contract.md の payload/result schema フィールドと exit code (0-4) の意味を欠落させない。
- warn フラグの付与基準は security-model.md の明示行に紐付ける (推定禁止)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 知りたい sink 種別 (file/stdout/notion) や セキュリティ条項 |
| scope | array | no | [sink-contract, security-model]。未指定なら両方走査 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (任意)。
- 必須フィールド: `matches[]` (逐語引用 + `warn` 列。sink 契約は payload/result schema・exit code を保持)、該当ゼロ時 `suggestions[]`。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| sink_contract | references/sink-contract.md | sink 仕様抽出時 |
| security_model | references/security-model.md | warn 判定時 |

### 3.2 外部ツール / API
- Read のみ (全文読取・文中検索を含む)。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- references 欠損 → exit 1 + stderr に欠損 path。
  - 目的: 禁止条項が欠落したまま caller が判定するのを防ぐ。
- マッチゼロは exit 0 で `matches: []` + `suggestions`。

### 4.2 観測 / ロギング
- 標準出力に query-result JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 禁止 sink への誘導禁止 (warn を必ず添付)。
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-output-routing 配下の R1 SubAgent (context fork 推奨。caller context を汚さない)。

### 5.2 ゴール定義
- **目的**: 呼出元 query に対し sink-contract / security-model から最小十分な根拠抽出を返す。
- **背景**: caller は sink 契約 (payload/result schema・exit code)・禁止条項のみを必要とし、実書き込みや security model 改訂は ref-* の責務外。本文埋め込みでは caller LLM が禁止条項を読み飛ばす事故が発生したため、warn フラグで明示する。
- **達成ゴール**: query に該当する sink 契約と security 条項が references から逐語引用され、sink 契約は payload/result schema・exit code を保持しつつ warn フラグを添付し、呼出元責務外情報を含まず、概ね 50 行 / 2KB 以内で caller がそのまま判定に使える状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 matches[] が sink-contract.md / security-model.md の実在行から逐語引用されている (捏造ゼロ)
- [ ] 呼出元責務外の情報 (実書き込み / 契約変更 / security model 改訂) を含まない
- [ ] 出力が 50 行 / 2KB 目安以内に収まる
- [ ] sink 契約の payload/result schema フィールドと exit code (0-4) を欠落させていない
- [ ] warn フラグの付与基準が security-model.md の明示行に紐付いている
- [ ] sink-contract と security-model の整合 (禁止対象でないか) を検証済み
- [ ] 該当ゼロ時は `matches: []` + `suggestions` を返す (exit 0)

### 5.4 実行方式
固定手順は持たず、完了チェックリストの未充足項目を都度特定 → 解消手順を自ら立案 → 実行 → 自己評価を反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (sink 種別を確認したい skill)。
- 後続 phase: caller が sink 選定 / 書き込み実行に利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- task_kind: NFKC + lowercase + `-` を区切として先頭トークン抽出 (例 `notion-page` → `notion`、`file-write` → `file`。sink 種別は先頭トークン = `file/stdout/notion`)。
- sink alias: references/sink-contract.md の `aliases:` 表に明示されたペアのみ採用。
- 未定義 sink は `warn` フラグ + `suggestions` で返し、自動補完しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/ (sink-contract.md, security-model.md) を `{{query}}` で検索し、
`matches[]` + `warn` フラグ + (該当ゼロ時) `suggestions` を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
