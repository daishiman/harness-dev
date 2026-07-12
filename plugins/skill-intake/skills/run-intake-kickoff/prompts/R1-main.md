# Prompt: R1-pattern-depth-pain-confirm

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-kickoff |
| responsibility | R1-pattern-depth-pain-confirm (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | true (確定後の kickoff.json は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- AskUserQuestion は 1 問ずつ。並列質問禁止。
- skill_name_hint に固有名詞 (社名 / 個人名) を直書きしない。

### 1.2 倫理ガード
- ユーザー回答を変更・要約しない (生回答を kickoff.json に保存)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 初期発話から pattern (A-E) / depth / pain_ranking 3 軸を確定し kickoff.json を生成。
- 非担当: 5 軸シート充足 (interview)、mode 判定 (next-action)。

### 2.2 ドメインルール
- pattern は A〜E の 5 値。
- depth ∈ {quick, standard, detailed}。
- pain_ranking は task ごとに `frequency_per_week` と `minutes_per_run` を持つ。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| initial-utterance | resource://orchestrator | yes | ユーザー初期発話 |
| pattern-catalog | resource://run-intake-kickoff/references/pattern-catalog.md | yes | A-E パターン定義 |
| depth-criteria | resource://run-intake-kickoff/references/depth-criteria.md | yes | depth 判定基準 |
| pain-ranking-template | resource://run-intake-kickoff/references/pain-ranking-template.md | yes | pain_ranking フォーマット |

### 2.4 出力契約
- schema: `schemas/output.schema.json`
- 必須フィールド: `pattern`, `depth`, `skill_name_hint`, `pain_ranking[]`, `initial_utterance`, `timestamp`, `qa_log[]`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| pattern-catalog | references/pattern-catalog.md | パターン候補絞り込み時 |
| depth-criteria | references/depth-criteria.md | Q2 を出す前 |
| pain-template | references/pain-ranking-template.md | Q3-N を出す前 |

### 3.2 外部ツール / API
- AskUserQuestion
- `scripts/validate-kickoff-json.py`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- validate-kickoff-json.py FAIL → exit 2、不足項目を stderr に列挙。

### 4.2 観測 / ロギング
- 質問・回答ペアを kickoff.json の `qa_log[]` に時系列で保存。

### 4.3 セキュリティ
- 個人名は kickoff.json に直書きせず変数化 (variable_abstraction)。

### 4.4 最大反復回数
- AskUserQuestion 反復上限: **10 問** (Q1 pattern / Q2 depth / Q3-N pain_ranking 合算)。上限到達で未確定軸がある場合は exit 2 で中断。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@intake-kickoff` (主スレッド Skill 実行ペルソナ。`workflow-manifest.json` P1 は `delegateType=skill` であり専用 agent ファイルは持たない。対話・AskUserQuestion 駆動、1 問ずつ)

### 5.2 ゴール定義
- 目的: 初期発話から pattern / depth / pain_ranking の 3 軸を確定し、後続 interview/visualize phase の起点となる kickoff.json を提供すること。
- 背景: この 3 軸が曖昧なまま深掘りすると後続 phase の質問数が爆発し、ユーザー離脱を招く。skill_name_hint への固有名詞混入は後続成果物全体に漏洩リスクを伝播する。
- 達成ゴール: pattern (A-E) / depth (quick/standard/detailed) / skill_name_hint / pain_ranking が確定し、schemas/output.schema.json 準拠の kickoff.json が validate-kickoff-json.py で PASS している状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] pattern / depth / skill_name_hint / pain_ranking が全て埋まっている
- [ ] AskUserQuestion を並列で出していない (1 問ずつ)
- [ ] skill_name_hint に固有名詞 (社名 / 個人名) を直書きしていない (variable_abstraction)
- [ ] validate-kickoff-json.py が PASS している
- [ ] 同 qa_log で生成される skill_name_hint と pattern が一致する (determinism, sha256 一致)
- [ ] ユーザー回答を変更・要約せず生回答を qa_log に保存している
- [ ] qa_log[] に質問・回答ペアが時系列で保存され、timestamp が ISO8601 形式

### 5.4 実行方式
- 固定手順を持たない。完了チェックリストを唯一の停止条件とし、未充足軸を特定→次に出すべき AskUserQuestion (3 択+自由入力) を都度立案→回答取得→qa_log 追記→checklist で自己評価を反復する (上限: Layer 4 最大反復回数)。
- AskUserQuestion は完全直列。反復は分離 context で完結させ、親へは kickoff.json + exit code のみ返却。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` の Phase 1
- 後続 phase: `run-intake-interview` (5 軸シート充足)

### 6.2 ハンドオフ / 並列性
- 直列: kickoff.json (受領先 = run-intake-interview) を後続 phase の入力 (提供元 = intake-kickoff) に接続。
- 並列: AskUserQuestion は完全直列、並列禁止。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- kickoff.json + AskUserQuestion 質問文

### 7.2 言語
- 本文: 日本語 (pattern コード A-E / depth 値は英語)

---

## Self-Evaluation

kickoff.json 生成後に以下を自己確認する。未達があれば validate-kickoff-json.py 結果と合わせて exit 2 を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 出力完全性 | pattern / depth / skill_name_hint / pain_ranking が全て埋まり schema 準拠 | PASS/FAIL |
| 直列保証 | AskUserQuestion を並列で出していない | PASS/FAIL |
| 固有名詞排除 | skill_name_hint に社名 / 個人名を直書きしていない | PASS/FAIL |
| validate 通過 | validate-kickoff-json.py が PASS | PASS/FAIL |
| 原文保全 | ユーザー回答を変更・要約せず qa_log に生回答を保存している | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{initial_utterance}}` から pattern 候補を 3 件に絞り、AskUserQuestion で Q1 (pattern) → Q2 (depth) → Q3-N (pain_ranking) を 1 問ずつ確定せよ。skill_name_hint を決定論的に生成し、kickoff.json (schemas/output.schema.json 準拠) を出力、最後に `validate-kickoff-json.py` で PASS を確認すること。前置き禁止。
