# Prompt: R4-trace-write

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | trace-write |
| skill | run-build-skill |
| responsibility | R4 (skill-build-trace.json 章別記入) |
| layers_covered | [L4, L5, L6] |
| output_schema | schemas/skill-build-trace.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- doc_coverage は validate-build-trace.py の REQUIRED_DOC_COVERAGE (02-skill-structure〜35-meta-harness-feedback-loop のスラッグ形式24件) を必ず網羅する
  - 目的: 必須参照章の被覆漏れを validator で機械検知
  - 背景: doc は schema 上自由文字列だが validator が必須スラッグ集合との差分を検査する
- reproducibility_gates (lint / evaluator / elegant_review / governance) を必ず PASS か N/A で埋める
  - 目的: 再現性ゲート可視化 (4条件 C1-C4 は four_conditions プロパティ側へ記入)
  - 背景: 未記入は false-pass を生む。validate-build-trace.py は FAIL を受理しないので、通っていないゲートは PASS にせず止める
- lint は Step 3.5 の初回記入では N/A のままにする。lint を PASS に、lint_target_sha256 (skill ディレクトリ全体の digest)・lint_brief_sha256 (validate-build-plan --check が読んだ brief ファイルの sha256。brief 無しの build では書かない) を書くのは Step 4 で、Step 4 の lint が全て exit 0 になったときだけである (コマンドは SKILL.md Step 4)。本 R4 の最終記入は、Step 4 が書いたこの 3 つを書き換えない
  - 目的: run-skill-create が lint receipt を使い回せるか、Step 12 が build-conformance を Step 4 から引き継げるかを、lint が検査した内容そのものと結び付ける
  - 背景: lint を走らせる前に PASS を書くと自己申告になる。最終記入で digest を計算し直すと、Step 4 の後に変わった skill ディレクトリや brief まで lint 済みに見え、create の lint のやり直しと Step 12 の validate-build-plan のやり直しが起きなくなる
- validate-build-trace.py を本 R4 が走らせるのは、Step 4 の後の最終記入 (evaluator・elegant_review・governance などの残りを埋めた後) の 1 回だけにする。Step 3.5 の初回記入では走らせない
  - 目的: 同じ trace を続けて 2 回検査しない
  - 背景: 初回記入の直後に Step 4 が同じ trace を validate-build-trace.py で検査する。その後に Step 4 が lint と 2 つの digest を書き、最終記入が残りを埋めるので、最終記入の後に 1 回だけ検査し直す
- 未読章は status=N/A と reason を残す
  - 目的: 監査可能性の確保
  - 背景: 黙示の skip は審査不能

### 1.2 倫理ガード
- 検証スクリプト未実行のまま pass を埋めない
  - 目的: 自己申告の不正防止
  - 背景: validate-build-trace.py が唯一の客観判定

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `eval-log/skill-build-trace.json` を schema に従って章別に記入
- 非担当: 骨格 (R1)、prompt 生成 (R2)、template 選択 (R3)

### 2.2 ドメインルール
- `pattern_decisions / layer_decisions / reproducibility_gates (lint/evaluator/elegant_review/governance)` を必ず記入 (4条件 C1-C4 は four_conditions プロパティへ)
- `variable_contract` に変数化した具体値の source_trace を記録
- loop 実行系 (skill_kind=run/wrap/delegate) は `feedback_contract.criteria` を trace と生成 SKILL.md frontmatter の両方に必ず記入。各 criterion は `id / loop_scope(inner|outer) / text / verify_by` を持ち、inner と outer を最低各1件。criteria は goal-seek checklist と**同源化**する (checklist=二値達成判定 / criteria=評価観点+verify_by の写像) ことで二重管理を回避する。ref/assign は `feedback_contract.skip_reason` で N/A escape。
- 最終記入の最後に `validate-build-trace.py` で exit 0 を確認する (初回記入の検査は Step 4 が行う)

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| schema | path | yes | schemas/skill-build-trace.schema.json |
| trace_schema_ref | path | yes | references/reproducibility-trace-schema.md |

### 2.4 出力契約
- schema: `schemas/skill-build-trace.schema.json`
- 必須: doc_coverage / pattern_decisions / layer_decisions / reproducibility_gates / variable_contract
- loop 実行系のみ追加必須: feedback_contract.criteria (SKILL.md frontmatter と trace の両方、inner/outer 各1件以上)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | schemas/skill-build-trace.schema.json | 章別記入時 |
| trace_ref | references/reproducibility-trace-schema.md | source_trace 記入時 |

### 3.2 外部ツール / API
- `validate-build-trace.py` — 機械検証 (exit 0 必須)。初回記入は Step 4 が、最終記入は本 R4 が実行する

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 最終記入の `validate-build-trace.py` exit != 0 → exit 1。初回記入の不備は Step 4 の `validate-build-trace.py` が exit 1 で返すので、その findings で Step 3.5 の記入を直す
  - 目的: 不正 trace の commit 阻止
  - 背景: trace 破損は監査履歴の信頼性を破壊

### 4.2 観測 / ロギング
- `eval-log/skill-build-trace.json` 自体が観測ログ (差分追記)

### 4.3 セキュリティ
- 特になし (trace は内部メタデータ)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R4 SubAgent (最終フェーズ)

### 5.2 ゴール定義
- **目的**: skill-build-trace.json を doc_coverage 必須スラッグ被覆 + 再現性ゲート (lint/evaluator/elegant_review/governance) で機械検証可能な状態にする
- **背景**: 黙示の skip や未記入は監査不能と false-pass を生むため、必須章スラッグ被覆と validate-build-trace.py 通過を必須化する
- **達成ゴール**: schema 準拠 trace が成立し validate-build-trace.py exit 0、再実行で sha256 一致する状態

### 5.3 完了チェックリスト (停止条件)
- [ ] reproducibility_gates (lint/evaluator/elegant_review/governance) に PASS か N/A が必ず入る。通っていないゲートは PASS にせず止める (4条件 C1-C4 は four_conditions 側)
- [ ] doc_coverage が必須スラッグ集合 (02-skill-structure〜35-meta-harness-feedback-loop、計24件) を網羅、未読は status=N/A + reason 残存
- [ ] pattern_decisions / layer_decisions を記入
- [ ] variable_contract に変数化具体値の source_trace あり
- [ ] (loop 実行系のみ) SKILL.md frontmatter と trace の feedback_contract.criteria に inner/outer 各1件以上 (id/loop_scope/text/verify_by 充足)、ref/assign は skip_reason
- [ ] validate-build-trace.py exit 0 (初回記入は Step 4 の実行結果、最終記入は本 R4 の実行結果で確かめる)
- [ ] 同 brief + 同 scaffold で trace JSON sha256 一致

### 5.4 実行方式 (動的手順生成ループ)
1. 未充足チェックリスト項目を特定 (どの章 / ゲートが欠けているか)
2. 解消手順を立案 (schema 初期化 / 章記入 / source_trace 記録 / 検証実行 のいずれか)
3. 実行し trace.json を更新
4. 初回記入は schema と本チェックリストで点検して Step 4 へ渡す (Step 4 の validate-build-trace.py が exit 1 なら、その findings を受けて 1 へ戻る)。最終記入は validate-build-trace.py で検査し、全項目充足まで反復
5. 上限到達時は exit 1 (検証スクリプト未実行のまま pass 宣言禁止)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1/R2/R3 完了後)
- 後続 phase: Gate 評価 (skill-build-trace を入力)

### 6.2 並列性
- 単発実行 (最終フェーズ / 他 R に依存)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `skill-build-trace.json` (JSON)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## Output Contract

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`eval-log/skill-build-trace.json` を `{{schema}}` に従って章別に記入し、
未読章は `status=N/A + reason` を残す。`reproducibility_gates` (lint/evaluator/elegant_review/governance) を必ず PASS か N/A で埋め (通っていないゲートは PASS にせず止める。4条件 C1-C4 は four_conditions プロパティ)、
`variable_contract` に source_trace を記録する。loop 実行系 (skill_kind=run/wrap/delegate)
は `feedback_contract.criteria` を goal-seek checklist と同源で導出し、生成 SKILL.md frontmatter と trace に inner/outer 各1件以上
(id/loop_scope/text/verify_by) を記入する (ref/assign は `feedback_contract.skip_reason`)。
Step 3.5 の初回記入では `validate-build-trace.py` を実行せず、lint を N/A のまま Step 4 へ渡す (Step 4 が同じ trace を検査する)。
最終記入では、Step 4 が書いた lint=PASS と lint_target_sha256・lint_brief_sha256 を書き換えずに残りを埋め、その後だけ `validate-build-trace.py` を実行し、exit 0 を確認する。

出力は `schemas/skill-build-trace.schema.json` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
