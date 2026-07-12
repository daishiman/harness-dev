# Prompt: R1-search-summarize (ref-skill-design-rubric)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-skill-design-rubric |
| responsibility | R1-search-summarize (skill 設計 rubric の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | inline (object: rubric_version / summary / matches) |
| reproducible | true (同 query + 同 rubric.json → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (rubric_version 一致)**: 応答の rubric_version が references/rubric.json と一致する。
  - 目的: caller が evaluator 出力の再現性を担保できるようにする。
  - 背景: rubric_version 不一致は採点結果の再現失敗の主因だった。
- **CONST_002 (severity 忠実転記)**: matches[] 各要素の severity は rubric.json の当該 rule の severity を逐語転記し、減点値を併記する場合は severity_weights (high -20 / medium -10 / low -3) に一致させる。
  - 目的: severity や減点値を歪め採点が偏るのを防ぐ。
- **CONST_003 (hint の根拠)**: 改善 hint は rubric 内の rule に紐づける (rubric 外 hint 禁止)。
  - 目的: 存在しない rule での誤誘導を防ぐ。

### 1.2 倫理ガード
- 存在しない rule / severity / rationale を捏造しない。
- 検索キーは rubric.json の `rules[].id / area / check / rationale` に実在する語のみ採用し、別名を捏造しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/rubric.json から skill / agent / hook / command / plugin-composition / prompt / workflow 設計の採点 rule (rules[]) を query に応じて抽出する (kind 語彙は rubric.json の applies_to_kinds に一致)。
- 非担当: rubric の改訂、採点本体、SKILL.md の自動生成。

### 2.2 ドメインルール
- `target_layer`: `skill | agent | hook | command | plugin-composition | prompt | workflow | all` でフィルタ (all は rubric.json の applies_to_kinds='*' 共通核を含む全 kind)。
- scope: `rules_only | weights_only | rationales_only | full`。
- query は `rules[].id / area / check / rationale` にあいまい一致で検索する。
- 各 rule に rationale 1 行抜粋 + 改善 hint 1-3 件 (rubric 由来) を添える。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 探したい rule/area (例 progressive-disclosure / frontmatter / body) |
| target_layer | enum | no | skill / agent / hook / command / plugin-composition / prompt / workflow / all (既定 all) |
| scope | enum | no | rules_only / weights_only / rationales_only / full (既定 full) |

### 2.4 出力契約
- inline schema (object, required: [rubric_version, summary, matches])
  - `rubric_version`: string
  - `summary`: string (50-800 字)
  - `matches`: array<{id: string, area: string, severity: string, check: string, rationale?: string}>

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| rubric | references/rubric.json | パース時 (version 取得含む) |
| rationale | references/rubric-rationale.md | rationale 抜粋時 |
| changelog | references/CHANGELOG.md | version 経緯確認時 |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- rubric.json 欠損 → exit 1 + stderr に欠損 path。
  - 目的: silent fallback で空 matches[] を返し caller が誤判定するのを防ぐ。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-skill-design-rubric 配下の R1 SubAgent (context fork 推奨。caller context を汚さない)。

### 5.2 ゴール定義
- **目的**: 呼出元 query に対し skill 設計 rubric の該当 rules / severity / rationale を target_layer 単位で返す。
- **背景**: caller は skill 設計評価のみを必要とし、rubric 改訂は ref-* の責務外。改善 hint を rubric 外から捏造すると設計判断を誤らせるため rubric 内由来に限定する。
- **達成ゴール**: query に該当する rules が version + target_layer フィルタ + rationale 1 行 + 改善 hint (rubric 内由来) 付きで引用され、各 severity が rubric.json 記載通りで、呼出元責務外情報を含まず、概ね 50 行 / 2KB 以内で caller が評価にそのまま使える状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 matches[] が references/rubric.json の実在 rule から逐語引用されている
- [ ] 呼出元責務外の情報 (rubric 改訂 / skill 実装) を含まない
- [ ] 出力が 50 行 / 2KB 目安以内に収まる
- [ ] rubric_version が references/rubric.json と一致している
- [ ] target_layer フィルタが守られている
- [ ] matches[].severity が rubric.json の当該 rule の severity と一致している
- [ ] 改善 hint が rubric 内 rule に紐づいている (捏造禁止)
- [ ] summary が 50-800 字に収まる
- [ ] 該当ゼロ時は `matches: []` + `suggestions` を返す (exit 0)

### 5.4 実行方式
固定手順は持たず、完了チェックリストの未充足項目を都度特定 → 解消手順を自ら立案 → 実行 → 自己評価を反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: assign-skill-design-evaluator / run-build-skill 等。
- 後続 phase: caller が matches[] を取り評価 / 改善提案に利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON (rubric_version / summary / matches)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- query: NFKC + lowercase + 半角空白 → `-` 連結 (例 "progressive disclosure" → `progressive-disclosure`)。
- 期待マッチ rule は rubric.json の rules[].id / area を走査して動的解決。
- 0 件ヒット時は近傍 rule (Levenshtein <= 2) を `suggestions` に最大 3 件、超過は提示しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/rubric.json を `{{target_layer}}` + `{{query}}` で検索し、
`rubric_version` / `summary` / `matches` を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
