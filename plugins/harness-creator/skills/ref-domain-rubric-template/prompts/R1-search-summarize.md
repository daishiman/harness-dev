# Prompt: R1-search-summarize (ref-domain-rubric-template)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-domain-rubric-template |
| responsibility | R1-search-summarize (rubric.json 部分集合の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | inline (object: summary / matches / references / suggestions?) |
| reproducible | true (同 query + 同 rubric.json → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (version 明記)**: rubric.json の `version` と `rubric_version` を応答に必ず含める。
  - 目的: caller が後から rubric 改訂による結果差分を再現できるようにする (`rubric_version` が改訂追跡キー)。
  - 背景: version 無しの応答は採点結果の再現性を失わせる主因だった。
- **CONST_002 (捏造禁止)**: rule 違反例は実 rubric の `rules[].check` / `rules[].rationale` から派生させる。
  - 目的: 存在しない rule / メタキーで caller を誤誘導しない。
- **CONST_003 (summary 長制限)**: summary は 50-800 字に収める。
  - 目的: caller の token budget を保護する。

### 1.2 倫理ガード
- 存在しない rule / メタキー (axes 等の非実在構造) を捏造しない。
- rule 参照は rubric.json の `rules[].id` に実在するものだけ採用。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/rubric.json から query に該当する部分集合 (`rules[]` / メタキー: `upstream` / `merge_strategy` / `conflict_policy` / `threshold_override` 等) を返す。
- 非担当: rubric の改変、ドメイン採点本体、rubric_hash の再計算。

### 2.2 ドメインルール
- scope: `rubric_full | rules_only | meta_only` (rules_only=`rules[]` のみ、meta_only=トップレベルメタキーのみ)。
- matches[].path は JSON Pointer 風 (`#/rules/0/check`, `#/upstream/0` 等) に正規化する。
- summary は 50-800 字、800 字超過時は truncate + 省略マーカー。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 探したい domain / rule id / メタキー |
| scope | enum | no | rubric_full / rules_only / meta_only (既定 rubric_full) |
| locale | enum | no | ja / en (既定 ja) |

### 2.4 出力契約
- inline schema (object, required: [summary, matches, references])
  - `summary`: string (50-800 字)
  - `matches`: array<{path: string, value: any}>
  - `references`: array<string> (rubric.json 内の参照 path)
  - `suggestions`: array<string> (optional。該当ゼロ時に近傍 rule id / メタキーを返す。§5.3 停止条件で使用)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| rubric | references/rubric.json | パース時 (version 取得含む) |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- rubric.json 欠損 → exit 1 + stderr に欠損 path。
  - 目的: caller が rubric 配置不備を即座に検知できるようにする。
  - 背景: 空 rubric を黙認すると採点結果が常に空 `rules[]` になり debug 困難。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-domain-rubric-template 配下の R1 SubAgent (context fork 推奨。caller context を汚さない)。

### 5.2 ゴール定義
- **目的**: 呼出元 query に対し rubric テンプレート (`rules[]` / メタキー) の該当部分集合を JSON Pointer 付きで返す。
- **背景**: caller は domain rubric 構築のテンプレ参照のみを必要とし、rubric 改訂は ref-* の責務外。捏造 rule 違反例は scoring を誤らせるため実 rubric 由来のみ許可。
- **達成ゴール**: query に該当する rubric keys が version + JSON Pointer 付きで引用され、rule 違反例も `rules[].check` / `rationale` 由来で添えられ、呼出元責務外情報を含まず、概ね 50 行 / 2KB 以内で caller がそのまま参照に使える状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 matches[] が references/rubric.json の実在 key から逐語引用されている (捏造ゼロ)
- [ ] 呼出元責務外の情報 (rubric 改訂 / domain 適用判断) を含まない
- [ ] 出力が 50 行 / 2KB 目安以内に収まる
- [ ] rubric.json の version が応答に明記されている
- [ ] matches[].path が JSON Pointer 風 (`#/rules/0/check`) に正規化されている
- [ ] scope (rules_only 等) の絞り込みが守られている
- [ ] rule 違反例が実 rubric の `rules[].check` / `rationale` 由来で 1-3 件、summary が 50-800 字に収まる
- [ ] 該当ゼロ時は `matches: []` + `suggestions` を返す (exit 0)

### 5.4 実行方式
固定手順は持たず、完了チェックリストの未充足項目を都度特定 → 解消手順を自ら立案 → 実行 → 自己評価を反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: assign-* (rubric を domain 適用する skill)。
- 後続 phase: caller が matches[] を取り採点に利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON (summary / matches / references)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- query は NFKC + lowercase 後、`domain:<name>` / `rule:<id>` の prefix を分離して照合。
- rule 参照は references/rubric.json の `rules[].id` に実在するものだけ採用。
- 期待 matches.path は rubric.json の `rules[]` / トップレベルメタキーから動的解決 (本文に列挙しない)。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/rubric.json を `{{query}}` で検索し、scope に従って絞り込んだ
`summary` / `matches` / `references` を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
