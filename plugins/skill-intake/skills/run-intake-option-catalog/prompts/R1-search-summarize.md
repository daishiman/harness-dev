# Prompt: R1-catalog-lookup-and-options-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | run-intake-option-catalog |
| responsibility | R1-catalog-lookup-and-options-emit (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (なし — SKILL.md schema_refs:[]、IN1/IN2 lint で形式検証) |
| reproducible | true (カタログ照合は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- カタログを Read-only で参照、新規連携は追加しない。
- tier=required の連携が selected から欠けてはならない。

### 1.2 倫理ガード
- ユーザー却下時は `reason` を必ず記録 (恣意的除外の防止)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: purpose.json の true_purpose.verb_object を入力に、integration カタログから候補連携を引き tier 付きで options.json を生成。
- 非担当: 連携の実装、認証情報取得、Notion 公開。

### 2.2 ドメインルール
- tier は `required | optional` の 2 値。required は欠けたら exit 非 0。
- options.json は `selected_integrations[{id, name, tier}]` と `rejected[{id, reason}]` を必ず含む。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| purpose | resource://intake/purpose.json | yes | true_purpose.verb_object を含む |
| integration-catalog | resource://run-intake-option-catalog/references/integration-catalog-pointer.md | yes | カタログ実体への pointer |
| tier-criteria | resource://run-intake-option-catalog/references/tier-criteria.md | yes | tier 判定基準 |

### 2.4 出力契約
- 契約: JSON schema は持たない (SKILL.md `schema_refs: []`)。形式検証は IN1/IN2 lint。
- 必須フィールド: `selected_integrations[{id, name, tier}]`, `rejected[{id, reason}]`
- 任意フィールド (mode P 判定入力、Phase 11 `run-intake-next-action` の `decide-mode.py` が読む): ヒアリングで plugin 規模構想 (hook/command 等の複数コンポーネント) が明示された場合のみ `plugin_scale` (boolean) / `component_requests[]` (string[]: skill/hook/command/agent/mcp 等) を options.json に転記する。明示がなければ出力しない (無指定は非 plugin 規模とみなす)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| catalog-pointer | references/integration-catalog-pointer.md | カタログ参照前 |
| tier-criteria | references/tier-criteria.md | tier 付与時 |

### 3.2 外部ツール / API
- AskUserQuestion (候補提示と選択取得)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 必須連携がユーザーに却下された → exit 1 (warn)、stderr で再考を促す。
- カタログ不在 → exit 3。

### 4.2 観測 / ロギング
- rejected[].reason をすべて options.json に残す (監査用)。

### 4.4 最大反復回数
- AskUserQuestion 反復上限: **5 問** (候補提示 1 問 + 却下 reason 収集最大 4 問)。上限到達で必須連携が未 selected の場合は exit 1 で中断。

### 4.3 セキュリティ
- 連携の API キー / トークンはこの責務では扱わない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@option-presenter` (対話あり、AskUserQuestion 経由、Read-only カタログ参照)

### 5.2 ゴール定義
- 目的: purpose.json の意図に対し、整備済みカタログから候補連携を抽出・tier 付与し、ユーザー合意を経て options.json を確定すること。
- 背景: 必須連携の脱落・恣意的却下・カタログ外追加は後段の実装/認証 phase を破綻させる。
- 達成ゴール: tier=required が全て selected に含まれ、rejected には reason が記録された SKILL.md 出力契約 (IN1 lint) 準拠の options.json が `output/<hint>/` に出力されている状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] purpose.json の `true_purpose.verb_object` と `time_freed_intent` を抽出済み
- [ ] `integration-catalog-pointer.md` 経由でカタログを参照し、verb_object に親和する候補を列挙済み
- [ ] 各候補に tier (required | optional), id, name を付与し tier=required の漏れがないことを確認済み
- [ ] AskUserQuestion でユーザー提示 → selected / rejected の判断を取得済み
- [ ] rejected 全項目に空でない reason が記録済み (tier=required を除外する場合も必須)
- [ ] `output/<hint>/options.json` を SKILL.md 出力契約 (selected_integrations[]/rejected[], IN1 lint) 準拠で書き出し済み
- [ ] plugin 規模構想 (hook/command 等) がヒアリングで明示された場合のみ `plugin_scale` / `component_requests[]` を options.json に転記済み (未明示なら未出力)
- [ ] カタログ外の連携を追加していないことを自己確認済み (Read-only 遵守)

### 5.4 実行方式
- 固定手順を持たない。完了チェックリストを唯一の停止条件とし、未充足項目 (例: 必須欠落 / reason 欠落 / schema 違反) を特定→必要処理 (再抽出 / 追加質問 / reason 収集 / schema 修正) を都度立案・実行→checklist で自己評価を反復する (上限: Layer 4 最大反復回数)。
- AskUserQuestion は 1 問ずつ (並列禁止)。反復は分離 context で完結させ、親へは options.json + exit code のみ返却。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` の Phase 6 (options 選定)
- 後続 phase: `run-intake-visualize` / `run-intake-next-action`

### 6.2 ハンドオフ / 並列性
- 直列: options.json (受領先 = run-intake-visualize / run-intake-next-action) を後続 phase の入力 (提供元 = option-presenter) に接続。
- 並列: AskUserQuestion は 1 問ずつ (並列禁止)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- options.json (SKILL.md 出力契約 / IN1 lint 準拠)

### 7.2 言語
- 本文: 日本語 (id / tier 値は英語)

---

## Self-Evaluation

options.json 生成後に以下を自己確認する。未達があれば対応 exit code を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 必須連携完全性 | tier=required の全連携が selected_integrations[] に含まれている | PASS/FAIL |
| 却下理由記録 | rejected[] の全項目に空でない reason が記録されている | PASS/FAIL |
| カタログ遵守 | カタログ外の連携を追加していない (Read-only 遵守) | PASS/FAIL |
| 形式適合 | options.json が SKILL.md 出力契約 (selected_integrations[]/rejected[]) に適合し IN1 lint を通る | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{purpose_json_path}}` を読み、integration カタログから候補連携を抽出、tier-criteria に従い tier を付与せよ。ユーザー提示と選択取得後、rejected には reason を必須で記録し、options.json (SKILL.md 出力契約 selected_integrations[]/rejected[] 準拠、IN1 lint 通過) を出力すること。前置き禁止。
