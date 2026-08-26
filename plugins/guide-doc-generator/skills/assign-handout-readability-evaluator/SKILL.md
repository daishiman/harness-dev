---
name: assign-handout-readability-evaluator
description: 生成した handout 資料が初心者に伝わるか読みやすさレビューを依頼したいとき、独立 context のレビュアーから指摘と根拠つきの verdict を回収したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C03
kind: assign
effect: conversation-output
prefix: assign
# 読みやすさを採点する相手は run-handout-build が生成した資料である
# (proposer ≠ approver: 生成した本人が採点しない)
pair: run-handout-build
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
schema_refs:
  - ../../schemas/handout-config.schema.json
completeness_exempt:
  - "manifest: assign kind は 1 回の委譲と verdict 回収だけを行い phase 遷移を持たない。委譲入力と停止条件は prompts/R1-review-readability.md が正本のため workflow manifest は作らない。"
responsibilities:
  - id: R1-assign
    prompt_required: true
    summary: "生成 HTML と正規化済み構成データと決定論ゲートの json-report を独立 context のレビュアー (C06) へ渡し、返った verdict を無加工で呼び出し元へ回収する"
rubric_refs:
  - ref-handout-design-system
combinators: []
feedback_contract:
  skip_reason: "assign kind は評価委譲のみで自身は反復ループを持たない (evaluator verdict でカバーする)"
---

# assign-handout-readability-evaluator

## Purpose & Output Contract

資料が初心者に伝わるかは意味の判断であり、決定論ゲートでは測れない。本 skill はその
判断を独立 context の sub-agent handout-readability-reviewer (C06) へ委譲し、返った
verdict を呼び出し元 (C01 run-handout-build) へ運ぶ。委譲する理由は品質の上乗せでは
なく、生成した本人が自作を採点する構図 (proposer≠approver の崩れ) を構造で塞ぐこと
にある。

本 skill は判定基準を持たない。読みやすさの良し悪しを本 skill が判定しないこと、
そして資料を書き換えないことが境界である。修正は C01 の責務。

**委譲入力 (本 skill が組み立てて渡すもの)**

| キー | 内容 |
| --- | --- |
| `html_path` | 判定対象の生成 HTML 1 ファイルのパス |
| `config_path` | 出力先へ同梱された正規化済み構成データ JSON のパス |
| `gate_reports` | 決定論ゲート (C16 / C17 / C18 / C22) の json-report のパス一覧と各 exit code |
| `reader_profile` | 構成データの reader / prior_knowledge_level / usage_scene。誰の立場で読むかの指定 |
| `scope` | 任意。読む範囲を絞るときの section id 一覧。省略時は資料全体。指すのは「どこを読むか」だけで、どの軸をどれだけ厳しく見るかは変えない。節をまたぐ軸は C06 が `scope` に関わらず全体で見る |

`gate_reports` は本 skill が収集する。`verify-handout-language.py` は
`--json-report` つきで実行し、出力されたレポートのパスと exit code をそのまま載せる。
収集はするが中身の合否を本 skill が解釈し直すことはしない。

**回収する出力 (C06 の戻り値をそのまま返す)**

トップレベルは `status` / `verdict` / `reviewed_as` / `findings` / `strengths` /
`not_reviewed` / `blocked_reason`。`verdict` の値域は `PASS` と `FAIL`。
`findings[]` の各要素は `severity` / `axis` / `location` (section_id と逐語引用) /
`why_not_understood` (根拠) / `suggestion` (改善案) / `machine_gate_overlap`。

項目が欠けた戻り値は不完全な verdict として扱う。本 skill が補完も要約もせず、
欠落を欠落のまま呼び出し元へ報告する。

## Key Rules

- 決定論ゲート C16 / C17 / C18 / C22 が全て exit0 であることが委譲の前提である。FAIL が
  残る状態では意味レビューへ進まない。この状態で起動された場合 C06 は `status=blocked`
  と `blocked_reason` を返すので、握りつぶさずそのまま呼び出し元へ差し戻す。
- ゲート結果の集約規則 (未実行を通過と読まないことを含む) の正本は `/handout-verify`
  (C09) の CR-GATE-AGG である。本 skill は集約規則を持たず、C09 の結果を運ぶだけ。
- verdict の決め方 (severity=high の扱いを含む) は handout-readability-reviewer (C06)
  側の規則であり、本 skill は再判定しない。回収した verdict を書き換えない。
- 独立 context の価値は「親会話に載っている情報が載っていないこと」で決まる。次のもの
  は委譲入力に含めず渡さない: 構成データの設計意図や狙いの説明、ヒアリングの生ログ、
  参照 HTML の文面、これが何周目の loop かという情報、過去に C06 が出した findings。
- 再レビューの起動と打ち切りは C01 のゴールシークが持つ。本 skill は 1 回の委譲と
  1 回の回収で終わる。

## Gotchas

- verdict を要約して短くしない。`location` の逐語引用は C01 が修正箇所を特定する唯一の
  手掛かりであり、落とすと修正が当て推量になる。
- `findings` が空でも `strengths` と `not_reviewed` は落とさない。次の修正で壊しては
  ならない箇所と、そもそも読んでいない面が分からなくなる。
- レビュアーへ「前回ここを直した」と伝えたくなるが、それが最も独立 context を壊す。
  伝えた瞬間、直した箇所だけを見る Goodhart 化が起きる。

## Additional Resources

- `../../agents/handout-readability-reviewer.md` — 委譲先 (C06) の判定規範と出力契約
- `prompts/R1-review-readability.md` — R1-assign の責務プロンプト (7layer)
- `../../scripts/verify-handout-language.py` — 言語と日付の決定論ゲート (C18)
- `ref-handout-design-system` — 文章設計の型 (レビューの評価規範の正本)
