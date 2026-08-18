---
name: run-handout-build
description: レクチャー資料や導入ガイドの handout を作りたいとき、題材のヒアリングから外部依存ゼロの単一 HTML 資料と同梱物一式を生成したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C01
kind: run
prefix: run
hierarchy: L1
user-invocable: true
output_language: ja
argument-hint: "[--config <handout-config.json>] [--out-root <dir>]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
depends_on: [C03, C04, C05, C11, C12, C13, C14, C15, C16, C17, C18, C19, C21, C22, C23]
script_refs:
  - ../../scripts/validate-handout-config.py
  - ../../scripts/resolve-handout-preset.py
  - ../../scripts/verify-handout-selfcontained.py
  - ../../scripts/verify-handout-a11y-print.py
  - ../../scripts/verify-handout-language.py
  - ../../scripts/verify-handout-narrative.py
  - ../../scripts/route-handout-output.py
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-design.md
  - prompts/R3-render.md
  - prompts/R4-verify.md
  - prompts/R5-refine.md
responsibilities:
  - id: R1-elicit
    prompt_required: true
    summary: "読み手・前提知識・用途・本質的課題・ゴール・分量・素材・日付・出力先に加え、R21 必須項目 (target_tasks / focus_theme / attainment_level / must_remember と no_need_to_remember の対) をヒアリングして確定する。検証済みの構成データを渡された場合はヒアリングを省く非対話経路も受け付ける"
  - id: R2-design
    prompt_required: true
    summary: "用途に対応するプリセットを C23 で解決し、構成データ設計を handout-content-architect (C05) へ委譲して部品選択と lead-line と判断軸を含む構成データを確定する"
  - id: R3-render
    prompt_required: true
    summary: "検証済み構成データからアセット埋め込み・図解・アイコン sprite・レンダリングを決定論 script 列で実行し単一 HTML を生成する"
  - id: R4-verify
    prompt_required: true
    summary: "4 ゲートを /handout-verify (C09) 経由で実行し集約結果を受け取り、出力先ルーティングまで通して生成レポートを返す"
  - id: R5-refine
    prompt_required: true
    summary: "第1稿への指摘を差分で反映し、指された箇所だけを作り直す"
hearing_required_items_r21:
  note: "R21 (goal-spec C47 / C54 / C57 / C58) の必須ヒアリング項目。plugin 全体で唯一の項目定義であり C05 は受け取る側で独自に増やさない"
  items:
    - field: target_tasks
      question_ja: "この資料を読んだ人が、自分の仕事で具体的に何をできるようになりたいですか (例 車両収支の集計を自動化する)"
      required: true
      min_count: 1
      checked_by: "C12 E-TARGET-TASKS-EMPTY / E-SECTION-UNTIED-TASK"
    - field: focus_theme
      question_ja: "冒頭で扱う主題を 1 つ (多くても 2 つ) に絞るとしたら何ですか"
      required: true
      min_count: 1
      max_count: 2
      checked_by: "C12 E-FOCUS-THEME"
    - field: attainment_level
      question_ja: "読み終えたときの到達点はどこですか (概要が分かる / 操作できる / 自分で再現できる / 自分でスキルを書ける)"
      required: true
      checked_by: "C12 E-ATTAINMENT-OVERRUN / E-ATTAINMENT-UNREACHED"
    - field: must_remember
      question_ja: "この場で覚えていただきたいことを 2 つまで挙げるとしたら何ですか"
      required: true
      max_count: 2
      paired_with: no_need_to_remember
      checked_by: "C12 E-REMEMBER-PAIR / E-REMEMBER-MAX"
    - field: no_need_to_remember
      question_ja: "逆に、覚えなくてよい (その場で調べれば足りる) のはどこまでですか"
      required: true
      paired_with: must_remember
      checked_by: "C12 E-REMEMBER-PAIR"
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "構成データが validate-handout-config.py を通り、lead-line と判断軸の一文・日付フィールド・用語言い換え宣言の欠落が 0 件で確定する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "生成した単一 HTML 資料 1 個が外部依存ゼロで開き 4 ゲートが exit0 になり、出力先に資料 HTML と構成データと素材と README が揃うことを受入テストが確認する"
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: "同梱された構成データから 2 回生成したとき出力 HTML がバイト一致することを受入テストが確認する"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "題材と素材だけを与えた実起動で、質問ラウンドが draft_first.max_question_rounds_before_first_draft 回以内に収まり、D1-D9 が揃った時点で completed を宣言せず停止して成果物のパス・仮置き項目・回さなかった工程を提示すること、および C03 委譲と挿絵生成 (C13) が draft 段で起動していないことを実走の痕跡で確認する"
      verify_by: live-trial
---

# run-handout-build

## Purpose & Output Contract

- 入力: 題材と素材、または検証済みの構成データ。
- 出力: 出力ディレクトリ 1 個。同梱は `handout.html` (writer C11) / `handout-config.json` と `assets/` (writer C19) / `README.md` (writer 本 skill) の 4 点。
- 生成レポート: 適用部品・埋め込みサイズ・warning・ゲート結果の 4 項目を返す。
- 完了条件: 4 ゲートが exit0 で、同梱 4 点が既定の命名規則で揃っている。

HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。読みやすさの最終判定は assign-handout-readability-evaluator (C03) へ委譲し、本 skill は verdict を受け取って修正する側に回る。

## ヒアリングと非対話経路

frontmatter `hearing_required_items_r21` が項目定義の単一正本である。5 項目すべてを確定してから R2 へ進む。target_tasks は 1 件以上、must_remember と no_need_to_remember は対で揃って初めて要件を満たす。

提示順 (demo_first / explain_first) は質問しない。R19 が既に取得している prior_knowledge_level から C12 の CR-PRESENTATION-ORDER が決定論導出する。利用者が自発的に述べたときだけ明示値を構成データへ書く。

検証済みの構成データを直接渡された場合はヒアリングを省き、非対話経路として R2 以降へ進む。

## ゲートと出力配置

4 ゲート (C16 / C17 / C18 / C22) は `/handout-verify` (C09) 経由で実行し、その集約結果を受け取るだけにする。4 状態分類と全体 verdict の判定規則は C09 の CR-GATE-AGG が単一正本であり、本 skill では再実装も再解釈もしない。

`route-handout-output.py` (C19) へ `--place-config` と `--assets-src` を渡し、handout-config.json と assets/ の複製は C19 に行わせる。C19 が返した出力ディレクトリ直下へ `README.md` を書くのは本 skill の責務で、内容は原題・目的・適用プリセット・同梱物一覧・各同梱物の使い方の 5 節とする。

## ゴールシーク実行

### ゴール (Goal)

題材のヒアリングから構成データを確定し、外部依存ゼロの単一 HTML 資料 1 個と同梱物一式が既定の命名規則で出力され、全ゲートが exit0 になった状態。

### 目的・背景 (Why)

初心者・非エンジニア向けの資料は毎回ゼロから手書きされ、部品もデザイン言語も資産として残らない。構成データ駆動へ移せば反復配布できるテンプレートになる。

### 完了チェックリスト

- [ ] R21 必須 5 項目を含むヒアリングが確定している
- [ ] 構成データが validate-handout-config.py を通っている
- [ ] 単一 HTML が決定論 script 列で生成されている
- [ ] 4 ゲートの集約結果が C09 から返り exit0 である
- [ ] 出力先へ同梱 4 点が揃っている

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` / `max_loops: 5` を実行契約とする。未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。

### ゴールシーク配線

- 元のゴールを `eval-log/run-handout-build-goal-spec.json` へ、進捗を `eval-log/run-handout-build-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み `Agent` で分離 context に fork する。
- 各周回末に `eval-log/run-handout-build-intermediate.jsonl` へ append-only で記録する。

### ゴールシーク検証

各周回後に中間成果物の欠落と goal drift を fail-closed で検査し、5 周で未達が残れば完了扱いにせず親へ handoff する。

## Criteria acceptance

- `criteria:IN1`: validate-handout-config.py が exit0 で必須項目欠落 0 件である。
- `criteria:OUT1`: 4 ゲートが exit0 で同梱 4 点が揃うことを受入テストが確認する。
- `criteria:OUT2`: 同梱構成データからの 2 回生成で出力 HTML がバイト一致する。
- `criteria:OUT3`: 実起動で第1稿が 1 質問ラウンド以内に出て D1-D9 到達時に停止し、C03 委譲と C13 挿絵が draft で起動しないことを確認する。

## Gotchas

- ゲート結果を自分で数え直さない。集約は C09 の責務である。
- 対話は既定経路であって唯一経路ではない。自動実行と逆抽出からの再生成を塞がない。
