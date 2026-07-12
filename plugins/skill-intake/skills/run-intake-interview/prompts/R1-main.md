# Prompt: R1-five-axes-sheet-fill

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-interview |
| responsibility | R1-five-axes-sheet-fill (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | true (5 軸充足の判定は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) を 1 問ずつ充足する。
- 5 軸より先に、ユーザーが言語化できない「何を入力し、何をどう出力してほしいか」を `intent_contract.input_spec` / `intent_contract.output_spec` に抽出する。
- 価値の深掘り質問は Phase 5 (purpose-excavator) の責務であり、本責務では行わない。

### 1.2 倫理ガード
- vocabulary_tier をセッション中に変更しない (ユーザー混乱回避)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 入力→出力 intent slot を固定 probe で充足し、sheet.md の 5 軸空欄を AskUserQuestion で 1 問ずつ充足する。
- 非担当: 深掘り (Phase 5)、3 軸確定 (run-intake-kickoff)、仮説検証 (Phase 2)、要約 (Phase 8)。

### 2.2 ドメインルール
- 抽象的回答に対しては `needs_excavation=true` を立てるのみ (再質問しない)。
- 5 軸質問は 3 択 + 自由入力 (4 択以上禁止)。intent probe は `probe-pattern-table.json` の選択肢を正とし、この制限の例外。
- 抽象回答でも、対象・素材・頻度・出力先・読者・粒度のいずれかを `normalized_answer` または `intent_contract` へ写像できなければ完了しない。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| profile | resource://intake/profile.json | yes | vocabulary_tier を含む |
| sheet | resource://intake/sheet.md | yes | 5 軸シート (空欄 / [?] 含む) |
| five-axes-priority | resource://run-intake-interview/references/five-axes-priority.md | yes | 軸の質問順 |
| question-plan | resource://run-intake-interview/references/question-plan.json | yes | depth×軸→Q-ID の決定論的選択正本 |
| question-bank | resource://skill-intake/references/question-bank.md | yes | Q-ID→文面の正本 (索引表) |
| abstract-patterns | resource://run-intake-interview/references/abstract-answer-patterns.md | yes | 抽象的回答の検出規則 |
| intent-contract | resource://skill-intake/references/intent-contract.schema.json | yes | 入力→出力 intent の正本 schema |
| probe-pattern-table | resource://skill-intake/references/probe-pattern-table.json | yes | 未充足 intent slot を引き出す固定 probe |

### 2.4 出力契約
- schema: `schemas/output.schema.json`
- 必須フィールド: `filled_ratio`, `five_axes_complete`, `unresolved[]`, `needs_excavation`, `abstract_answers[]` (各要素 `{axis, answer, reason}`), `five_axes`, `intent_contract`, `pending_probes[]`, `qa_log[]`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| five-axes-priority | references/five-axes-priority.md | 質問順序確定時 |
| question-plan | references/question-plan.json | 出す Q-ID の決定論的選択 (build-questions.py が使用) |
| question-bank | ../../references/question-bank.md | Q-ID→文面の正本 |
| abstract-patterns | references/abstract-answer-patterns.md | 回答後の判定 (validate-answer-abstraction.py が使用) |
| intent-contract | ../../references/intent-contract.schema.json | build-intent.py の schema 検証 |
| probe-pattern-table | ../../references/probe-pattern-table.json | pending_probes の文面解決 |

### 3.2 外部ツール / API
- AskUserQuestion
- `scripts/build-questions.py` — depth/pattern/既記入軸から出す質問列を Q-ID で決定論的に確定 (都度立案の代替)
- `scripts/validate-answer-abstraction.py` — 回答の抽象度を機械判定し needs_excavation を決定論化
- `scripts/build-sheet-json.py`
- `../../scripts/build-intent.py` — `qa_log` から `intent_contract` と `pending_probes` を決定論的に生成
- `scripts/validate-interview-json.py`
- `scripts/check-five-axes-coverage.py`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- validate-interview-json.py がスキーマ不整合 / 停止ゲート違反 → exit 1、該当項目を stderr に列挙。LLM 自動補完禁止 (exit 2 は引数不正 / ファイル不在 / jsonschema 未導入の環境エラー専用)。
- check-five-axes-coverage.py FAIL → exit 1、不足軸を stderr に列挙し再起動を促す。
- build-intent.py が pending_probes を返す → `probe-pattern-table.json` の文面を verbatim で 1 問ずつ聞く。推測補完で filled にしない。

### 4.2 観測 / ロギング
- 抽象的回答は `abstract_answers[]` (各要素 `{axis, answer, reason}`) に追記し `needs_excavation=true` を立てる。未解消空欄は `unresolved[]` に列挙する。

### 4.3 セキュリティ
- 個人情報は interview.json 本文に転記せず変数化。

### 4.4 最大反復回数
- AskUserQuestion 反復上限: **14 問** (intent slot 最大 9 + 5 軸 × 1 問。価値深掘りは Phase 5 の責務)。上限到達で `pending_probes` が残る、または five_axes_complete=false の場合は exit 1 で中断。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@intake-interviewer` (対話、vocabulary_tier セッション固定)

### 5.2 ゴール定義
- 目的: ユーザーが言語化できない入力仕様/出力仕様を `intent_contract` に抽出し、sheet.md の 5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) を AskUserQuestion で充足し、後続 purpose-excavator / visualize phase が必要十分な情報を持って起動できる状態にすること。
- 背景: 深掘りまで本責務で行うと Phase 5 (purpose-excavator) と責務が重複し再現性が破綻する。vocabulary_tier をセッション中に変えるとユーザー混乱と回答品質低下を招く。
- 達成ゴール: `intent_contract.slot_status` 全 slot filled=true、`pending_probes=[]`、five_axes_complete=true となり、抽象的回答は abstract_answers[] に追記 + needs_excavation=true で印付け、interview.json が validate-interview-json.py / check-five-axes-coverage.py 双方で PASS している状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] five_axes_complete=true になっている
- [ ] intent_contract.slot_status の 9 slot がすべて filled=true になっている
- [ ] pending_probes=[] になっている
- [ ] five_axes 出力先/情報源が intent_contract から派生している
- [ ] validate-interview-json.py が PASS している
- [ ] check-five-axes-coverage.py が PASS している
- [ ] vocabulary_tier をセッション中に変更していない
- [ ] 抽象的回答に対し深掘り質問をしていない (Phase 5 越境禁止、needs_excavation を立てるのみ)
- [ ] AskUserQuestion を並列で出していない (1 問ずつ、最大 3 択 + 自由入力)
- [ ] 同 profile + sheet + qa_log で interview.json の 5 軸 sha256 が一致する (determinism)
- [ ] 個人情報を interview.json 本文に転記していない (変数化)

### 5.4 実行方式 (決定論)
- **intent probe を先に解決する**: 既存 `qa_log[]` を `../../scripts/build-intent.py --table ../../references/probe-pattern-table.json --schema ../../references/intent-contract.schema.json` に通し、`pending_probes[]` があればその順に `probe-pattern-table.json` の `question_text` と `answer_options` を **verbatim (逐語)** で AskUserQuestion に出す。probe 回答は `qa_log[]` に `{probe_id,target_slot,question_text,selected_option,raw_answer,normalized_answer}` で残す。
- **5 軸質問は立案しない。機械選択する**: `build-questions.py --depth <kickoff.depth> --pattern <kickoff.pattern> --sheet <sheet.md>` を実行し、出力された `questions[]` の Q-ID と `text` を **verbatim (逐語)** で AskUserQuestion に出す。質問の自由立案・並べ替え・追加・削除は禁止 (tier に応じた言い換えも question-bank の文面を優先し、`vocabulary-tiers.md` の固定対応表による語置換のみ許可)。これにより実行者が変わっても同じ (depth/pattern/既記入軸) なら同じ質問列になる。
- **抽象判定は機械実行する**: 各回答取得後に `validate-answer-abstraction.py --answer "<回答>" --axis <軸>` を実行し、exit 3 (abstract=true) のときのみ `abstract_answers[]` に `{axis, answer, reason}` を追記し `needs_excavation=true` を立てる。LLM の定性判断で needs_excavation を決めない。深掘り質問はしない (Phase 5 の責務)。
- 流れ: build-intent.py で pending_probes 確定→probe を順に AskUserQuestion→intent_contract 全充足→build-questions.py で5軸質問列確定→順に AskUserQuestion→回答を sheet.md に Edit 反映 (出力先/情報源は intent_contract から派生)→validate-answer-abstraction.py で印付け→check-five-axes-coverage.py で充足確認→checklist で自己評価 (上限: Layer 4 最大反復回数)。
- AskUserQuestion は完全直列。反復は分離 context で完結させ、親へは interview.json + 更新後 sheet.md + exit code のみ返却。run-intake-kickoff で確定済の 3 軸 (pattern/depth/pain) は前提として読むのみ、再質問しない。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` の Phase 4
- 後続 phase: `purpose-excavator` (深掘り) / `run-intake-visualize`

### 6.2 ハンドオフ / 並列性
- 直列: interview.json + sheet.json + 更新後 sheet.md (受領先 = purpose-excavator / run-intake-visualize / run-intake-finalize) を後続 phase の入力 (提供元 = intake-interviewer) に接続。`intent_contract` は run-intake-finalize の §6 正本入力になる。
- 並列: AskUserQuestion は完全直列、並列禁止。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- interview.json + sheet.json + 更新後 sheet.md

### 7.2 言語
- 本文: 日本語。vocabulary_tier に従い語彙難易度を session 固定。

---

## Self-Evaluation

interview.json 生成後に以下を自己確認する。未達があれば該当 exit code を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 5軸完全性 | five_axes_complete=true / validate + coverage 双方 PASS | PASS/FAIL |
| intent完全性 | intent_contract.slot_status 全 slot filled=true / pending_probes=[] | PASS/FAIL |
| 越境禁止 | 抽象回答に深掘り質問をしていない (needs_excavation を立てるのみ) | PASS/FAIL |
| 直列保証 | AskUserQuestion を並列で出していない、3択+自由入力以内 | PASS/FAIL |
| tier 固定 | vocabulary_tier をセッション中に変更していない | PASS/FAIL |
| 個人情報管理 | 個人情報を変数化し interview.json 本文に転記していない | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{profile_path}}` の vocabulary_tier を読み込み、まず既存 `qa_log[]` を `../../scripts/build-intent.py --table ../../references/probe-pattern-table.json --schema ../../references/intent-contract.schema.json` に通して `intent_contract` と `pending_probes[]` を得よ。`pending_probes[]` が空でなければ、`../../references/probe-pattern-table.json` の `question_text` と `answer_options` を **verbatim** で 1 問ずつ AskUserQuestion で聞き、probe 回答を `qa_log[]` に `{probe_id,target_slot,question_text,selected_option,raw_answer,normalized_answer}` で記録してから再度 normalize する。`pending_probes=[]` になった後、`scripts/build-questions.py --plan references/question-plan.json --bank ../../references/question-bank.md --depth <kickoff.depth> --pattern <kickoff.pattern> --sheet {{sheet_path}}` を実行して 5 軸質問列を確定せよ。質問は立案せず、出力 `questions[]` の `text` と `options` を **verbatim** で `five-axes-priority.md` 順 (= build-questions.py の order) に 1 問ずつ AskUserQuestion で聞く。各回答は `sheet.md` に Edit 反映し、`qa_log[]` に記録する。ただし出力先は `intent_contract.output_spec.sink`、情報源は `intent_contract.input_spec.sources` を ` / ` で連結した値から派生させる。回答ごとに `scripts/validate-answer-abstraction.py --patterns references/abstract-answer-patterns.md --answer "<回答>" --axis <軸>` を実行、exit 3 のときのみ `abstract_answers[]` に `{axis, answer, reason}` を追記し `needs_excavation=true` を立てる (価値深掘りは行わない)。`scripts/build-sheet-json.py {{sheet_path}} --depth <kickoff.depth> --out output/<hint>/sheet.json` を実行し、その `five_axes` と `intent_contract` と `pending_probes` を `interview.json` に同梱する。最終的に `interview.json` (schemas/output.schema.json 準拠) を出力し、`validate-interview-json.py` と `check-five-axes-coverage.py` 双方で PASS を確認すること。前置き禁止。
