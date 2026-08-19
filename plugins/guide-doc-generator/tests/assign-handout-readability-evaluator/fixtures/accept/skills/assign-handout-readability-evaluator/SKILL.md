---
name: assign-handout-readability-evaluator
description: 生成した handout 資料が初心者に伝わるか読みやすさレビューを依頼したいとき、独立 context のレビュアーから verdict を回収したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C03
kind: assign
prefix: assign
hierarchy: L2
user-invocable: false
disable-model-invocation: false
output_language: ja
context: fork
agent: handout-readability-reviewer
argument-hint: "[--html <handout.html>] [--config <handout-config.json>] [--scope <section-ids>]"
allowed-tools: [Read, Bash(python3 *), Task]
depends_on: [C04, C18]
agent_refs:
  - ../../agents/handout-readability-reviewer.md
script_refs:
  - ../../scripts/verify-handout-language.py
responsibility_refs:
  - prompts/R1-review-readability.md
responsibilities:
  - id: R1-assign
    prompt_required: true
    summary: "生成 HTML と正規化済み構成データと決定論ゲートの json-report を独立 context のレビュアー (C06) へ渡し、verdict を回収して呼び出し元へ返す"
rubric_refs:
  - ref-handout-design-system
combinators: []
feedback_contract:
  skip_reason: "assign kind は評価委譲のみで自身は反復ループを持たない (evaluator verdict でカバーする)"
---

# assign-handout-readability-evaluator

## Purpose & Output Contract

生成した資料が初心者に伝わるかは意味判断であり、決定論ゲートでは測れない。本 skill は
その判定を独立 context の sub-agent handout-readability-reviewer (C06) へ委譲し、
verdict を回収して呼び出し元 (C01) へ返す運搬役である。生成した本人が自作を採点する
構図 (proposer≠approver の崩れ) を避けるために委譲する。

本 skill は判定基準を持たない。読みやすさの良し悪しを本 skill が判定しないこと、および
資料を書き換えないことがこの skill の境界である。修正は C01 run-handout-build の責務。

**委譲入力 (組み立てて渡すもの)**

| キー | 内容 |
| --- | --- |
| `html_path` | 判定対象の生成 HTML 1 ファイルのパス |
| `config_path` | 出力先へ同梱された正規化済み構成データ JSON のパス |
| `gate_reports` | 決定論ゲート (C16 / C17 / C18 / C22) の json-report のパス一覧と各 exit code |
| `reader_profile` | 構成データの reader / prior_knowledge_level / usage_scene |
| `scope` | 任意。特定セクションのみをレビューさせる場合の section id 一覧 (省略時は全体) |

**回収する出力 (C06 の戻り値をそのまま返す)**

`status` / `verdict` (PASS または FAIL) / `reviewed_as` / `findings` / `strengths` /
`not_reviewed` / `blocked_reason` の 7 項目。`findings[]` の各要素は `severity` /
`axis` / `location` (section_id と逐語引用) / `why_not_understood` / `suggestion` /
`machine_gate_overlap` を持つ。項目が欠けた戻り値は不完全な verdict として扱い、
埋めたり要約したりせずそのまま欠落として呼び出し元へ報告する。

## Key Rules

- 決定論ゲート C16 / C17 / C18 / C22 が全て exit0 であることが委譲の前提である。FAIL が
  残る状態では意味レビューへ進まない。この場合 C06 は `status=blocked` を返すので、
  そのまま呼び出し元へ差し戻す。
- `verify-handout-language.py` の json-report は本 skill が収集して `gate_reports` に
  載せる。判定はしない。
- verdict の決め方 (severity=high が 1 件でもあれば FAIL) は handout-readability-reviewer
  (C06) 側の規則であり、本 skill は再判定しない。回収した verdict を書き換えない。
- 独立 context の価値は「親会話に載っている情報が載っていないこと」で決まる。次のものは
  委譲入力に含めず渡さない: 構成データの設計意図、ヒアリングの生ログ、参照 HTML v1/v2 の
  文面、これが何周目の loop かという情報、過去に C06 が出した findings。
- 再レビューの起動と打ち切りは C01 のゴールシークが持つ。本 skill は 1 回の委譲と 1 回の
  回収で終わる。

## Gotchas

- verdict を要約して短くしない。`findings` の逐語引用 (`location`) は C01 が修正箇所を
  特定するための唯一の手掛かりであり、落とすと修正が当て推量になる。
- ゲートが未実行 (not-run) の面がある状態を「通った」と読み替えない。集約規則の正本は
  C09 の CR-GATE-AGG である。

## Additional Resources

- `../../agents/handout-readability-reviewer.md` — 委譲先 (C06) の判定規範と出力契約
- `prompts/R1-review-readability.md` — R1-assign の責務プロンプト
- `ref-handout-design-system` — 文章設計の型 (評価規範の正本)
