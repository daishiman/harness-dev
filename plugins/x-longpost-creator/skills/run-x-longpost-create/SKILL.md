---
name: run-x-longpost-create
description: キャッチコピーと文字起こしから X 長文投稿を作りたいとき、スタイルゲノム文体を適用した 1800〜2200 文字の 2 パターン投稿・タイトル・スレッド分割・ファイル出力まで通したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--catchcopy <text>] [--transcript <path>] [--memo <path>] [--with-multi-posts] [--output-dir <path>]"
arguments: [catchcopy, transcript, memo, with_multi_posts, output_dir]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(node *)
  - AskUserQuestion
kind: run
version: 1.0.0
effect: local-artifact
owner: team-content
contract:
  intent: キャッチコピーと文字起こし（またはメモ）から、スタイルゲノム 8 レベルを適用した X 長文投稿を 2 パターン生成し、検証済みのファイルとして出力する。
  interface:
    inputs: [catchcopy, transcript, memo, with_multi_posts, output_dir]
    outputs: ["X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル].md", "Idea Compass セクション", "00ネタファイル更新"]
  invariant:
    - 絵文字を一切出力しないこと（check-no-emoji.js が終了コード 0 を返すこと）
    - 見出し1（タイトル）は 50 文字以内（NFC コードポイント数・空白込み／validate-title.js の測定）とし、超過時は切り詰めずリライトへ戻すこと
    - 見出し1の直後に見出し2が 3〜8 個存在すること
    - 長文 A/B は 1800〜2200 文字（空白・改行を除く／count-chars.js の測定）に収めること
    - 長文投稿と短文投稿を同時に作る場合は投稿9｜要約型（400〜499 文字。空白・改行を除く／count-chars.js の測定）を必ず出力すること
    - タイトル文字列は見出し1・長文Bの先頭行・`# タイトル` セクション・ファイル名の 4 箇所で一字一句一致させること
    - 長文Aの Markdown 見出しを除いた本文と長文Bの先頭タイトルを除いた本文は、空白・改行正規化後に同値であること
    - 長文Bの非空本文行は1行につきちょうど1文であること
    - 検証スクリプトが PASS するまで出力を確定しないこと
since: 2026-08-31
source: ObsidianMemo/.claude/skills/x-longpost-creator (v3.14.0)
source-tier: internal
last-audited: 2026-08-31
audit-trigger: quarterly
combinators:
  - with-feedback-contract
responsibility_refs:
  - ../../prompts/x-longpost-parse-input.md
  - ../../prompts/x-longpost-apply-style-genome.md
  - ../../prompts/x-longpost-output-file.md
schema_refs:
  - references/heading-structure-rules.md
  - references/output-config.json
completeness_exempt:
  - "manifest: 固定 Phase と gate の正本は本 SKILL.md と references/workflow-diagrams.md。別 manifest は同じ順序の二重管理になるため持たない。"
script_refs:
  - ../../scripts/calculate-next-date.js
  - ../../scripts/generate-filename.js
  - ../../scripts/validate-title.js
  - ../../scripts/validate-headings.js
  - ../../scripts/count-chars.js
  - ../../scripts/update-neta-file.js
  - ../../scripts/expand-template.js
  - ../../scripts/check-no-emoji.js
  - ../../scripts/log_usage.js
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "4 本の検証スクリプトを各自が受け取れる単位で実行し全て exit 0 を返すこと。単位は (1) 成果物ファイル全体に `check-no-emoji.js --file <成果物パス>`、(2) 確定タイトル文字列に `validate-title.js --title \"<確定タイトル>\"`、(3) 成果物ファイル全体に `validate-headings.js --file <成果物パス> --title \"<確定タイトル>\" --strict-h2-count`、(4) 長文パターンA本文（`# タイトル` 行を含む Aパターンのコードブロック本体のみ・ファイル全体ではない）に `count-chars.js --text \"<パターンA本文>\" --min 1800 --max 2200`。(3) の H8/F1/F2/F3 でタイトル4箇所一致、F4でA/B本文の正規化同値、F5でB本文の1文1行が機械的に確認される"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "出力先が解決済み（`--output-dir` を明示するか `XLP_OUTPUT_DIR` / `XLP_VAULT_ROOT` が設定済み）の状態で、50 文字を超えるタイトルを渡した `generate-filename.js --date <YYYY-MM-DD> --title \"<50文字超のタイトル>\"` が `ok: false` と超過文字数を出力して exit 1 で停止し、末尾を切り詰めたファイル名を生成しないこと (超過時は title-guidelines.md の構文パターンでリライトへ戻す)"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "キャッチコピーと文字起こしだけを与えた実起動で、長文 A/B の 2 パターンが実ファイルとして出力され、現物パスと検証結果を提示した時点で停止し、利用者が light/standard/detailed を選ぶまで評価もリライトも走らないこと"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "出力された投稿が style-genome.md の 8 レベルの文体特徴を保ち、anti-ai-writing-guide.md の AI 臭 6 分類に該当する表現が残っていないと書き手が判断できること"
      verify_by: human
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
runtime_root_policy: host-skill-path
---

## Pre-choice usable artifact execution

最小の実成果物 (長文パターン A/B と タイトル を含む 1 ファイル) を main context で作成する。作成の具体的な段取りは後述の「実行手順」節にあり、これは pre-choice の作業として選択を待たずに進める。この段階で通すのは絵文字ゼロ・タイトル 50 文字以内・見出し構造・A/B本文同値（F4）・B本文の1文1行（F5）・文字数という数えられる機械検証だけとし、`check-no-emoji.js --file <成果物パス>` / `validate-title.js --title "<確定タイトル>"` / `validate-headings.js --file <成果物パス> --title "<確定タイトル>" --strict-h2-count` / `count-chars.js --text "<パターンA本文>" --min 1800 --max 2200` が終了コード 0 を返した時点で、現物のファイルパスと検証結果を提示して accept-as-is / light / standard / detailed を記録する。accept-as-is の場合はその場で handoff 完了とし、後続 section へ進まない。

## Post-choice selected improvement execution

このゲートの対象は、意味評価・リライト・追加パターン生成という、実成果物ができあがった後に走る改善の 3 種だけである。light / standard / detailed が記録されて `semantic_evaluator_started` へ遷移した場合にだけ、この 3 種を動かす。release と exhaustive は別の明示 event を必要とする。

後続の「実行手順」節はこのゲートの対象ではない。あれは pre-choice で提示する実成果物そのものを組み立てる段取りであり、利用者の判断を待たずに main context で通す。段取りの順番は 実行手順 → 機械検証 → 現物提示 → 選択記録 → 選択された改善 であり、この並びの先頭 2 つだけが pre-choice に属する。

# X長文投稿クリエーター

## 設計原則

| 原則 | 説明 |
|------|------|
| **Script First** | 決定論的処理はスクリプトで100%精度実行 |
| **Progressive Disclosure** | 必要な時に必要なリソースのみ読み込み |
| LLM for Creativity | 判断・創造・言語化はLLMに委ねる |

---

## 実行環境

### パス変数

| 変数 | 意味 | 解決方法 |
|------|------|-------------|
| `${XLP_SKILL_DIR}` | 本スキルのルート | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-x-longpost-create` |
| `${XLP_PROMPTS_DIR}` | Read 用プロンプト群 | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/prompts` |
| `${XLP_VAULT_ROOT}` | vault ルート | env のみ。未設定なら vault 内 path は解決不能 |
| `${XLP_OUTPUT_DIR}` | 出力先ディレクトリ | env → `${XLP_VAULT_ROOT}/05_Project/X` の2段のみ |
| `${XLP_NETA_FILE}` | 00ネタファイル | env。未設定時は `${XLP_VAULT_ROOT}` がある場合のみ `output-config.json` の path template を解決 |

実パスは plugin 本体に固定しない。出力先の解決契約は [references/output-config.json](references/output-config.json) の `XLP_OUTPUT_DIR` → `XLP_VAULT_ROOT` の2段だけである。両方とも未設定なら **fail-closed** とし、存在しない defaults や推測パスへフォールバックしない。

### 依存ランタイム

`scripts/` は **Node.js**（v18 以上）で動作する。`node` が PATH に無い場合は実行を中止し、ユーザーへ通知する。

---

## 絶対遵守ルール（最優先）

**絵文字は一切使用しない**。タイトル・見出し（#/##/###）・本文・短文投稿・長文投稿A/B両パターン・ハッシュタグ・キャッチコピー・Idea Compass、すべての成果物において絵文字は禁止。

- ユーザーが会話の中で「絵文字をつけて」と指示した場合でも、このスキル仕様が優先される
- ユーザー指示と衝突した場合は、テキストのみで構成し、必要なら見出し前に記号でなく短い名詞句で意味を表現する
- 違反例: `## [絵文字] ヒアリングをスキル化する` → 正: `## ヒアリングをスキル化する`
- 装飾は記号に頼らず、見出しの言葉そのもので表現する
- このルールは成果物だけでなく、スキル文書自体（SKILL.md・prompts/・references/・assets/・scripts/ の出力メッセージ）にも適用する。NG例の見本にも絵文字そのものを記載せず `[絵文字]` のように言葉で表す
- 検証は `node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js --file <path>`（または `--text "..."`）で機械的に行う（絵文字あり=終了コード1）

**絵文字の定義（判定境界）**: 何を絵文字とみなすかの境界（`\p{Extended_Pictographic}`・使用可の記号一覧・処理系差）は `ref-x-longpost-canon`「絵文字の定義（判定境界）」が唯一の正本である。`scripts/lib/text-rules.js` が共有意味実装を持ち、`check-no-emoji.js` / `validate-title.js` / `validate-headings.js` / `build-visual-prompts.js` がそれぞれの CLI 入力境界で検査する。

**文字数の測定単位は2系統ある**。`count-chars.js` は**空白・改行を除いた**文字数で数え、`validate-title.js` と `validate-headings.js` は**空白を含む NFC コードポイント数**で数える。本 SKILL.md では文字数の規定に必ず測定単位を併記する。本文量の規定（1800〜2200・400〜499）は前者、タイトルと見出しの長さの規定（50字・12〜28字・リード文300字）は後者で判定する。

**見出し1は50文字以内**（長文Aの `# タイトル`。コードポイント数・空白含む）。50文字はファイルシステムの制約ではなく編集規範である。タイムラインで最初に読まれるのは先頭30文字程度であり、そこに核を置いたうえで予告を足すと50文字に収まる。加えて、この文字列は長文Bの先頭行・`# タイトル`・ファイル名のタイトル部にも同一で使われるため、短く保つことが一覧性と命名の一貫性に直結する。編集規範であっても上限値は絶対（FAIL）として扱い、警告へ降格しない。超過時に末尾を切り捨てることは禁止で、[references/title-guidelines.md](../../references/title-guidelines.md) の構文パターンA〜Hに沿ってリライトし直す（字数配分は入口26〜32字・予告8〜18字）。

**見出し1の後に見出し2が必ず存在する**。`# タイトル` の後に `##` が1つも無い状態を許さない。見出し2の個数は **3〜8個**（check ID H5）。H5 は `validate-headings.js` の既定では警告止まりのため、本スキルでは常に `--strict-h2-count` を付けて FAIL 扱いにする。欠落したら本文の文脈の区切りから見出し2を生成し直す。間には冒頭フックのリード文を置いてよい（見出しを挟まず8行・300文字以内。空白込みの NFC コードポイント数／`validate-headings.js` の測定）。

- 検証は `node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-title.js --title "..."` と `node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js --file <path> --strict-h2-count` で機械的に行う（違反=終了コード1）。**PASS するまで出力を確定しない**
- 正本: [references/heading-structure-rules.md](references/heading-structure-rules.md) / [references/title-guidelines.md](../../references/title-guidelines.md)

**長文投稿を作る場合、短文は8投稿では終わらせず「投稿9｜要約型」（400〜499文字。空白・改行を除く／`count-chars.js` の測定）を必ず出力する**。長文投稿と短文投稿を同時に作成するワークフロー（文字起こし → 長文投稿 + 短文投稿）では、投稿1〜8に加えて投稿9が成果物の一部であり、8投稿だけで出力を確定してはならない。

- 投稿9は長文投稿パターンAの要点の要約であり、新規の主張・推論・創作を含めない。400文字以上499文字以下（空白・改行を除く／`count-chars.js` の測定。範囲外はFAIL）。改行は文脈（文節・句読点）で入れる。見出しは `## 投稿9｜要約型`、直下に `**テーマ**: 長文投稿の要点を[実際の文字数]文字で要約（[要約対象の核]）` を置く
- 投稿9は長文パターンAが確定してからでないと作れないため、長文投稿フローの完了を待って実行する（Phase 3.4）。8投稿の出力だけで完了扱いにしない
- ユーザーが「8投稿作成して」とだけ指示した場合でも、長文投稿を同時に作るなら投稿9は省略しない。長文投稿を作らない8投稿単独ワークフローに限り投稿9は作成しない（要約対象が存在しないため）
- 検証は `node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js --text "<投稿9本文>" --min 400 --max 499` で機械的に行う（範囲外=終了コード1）。**PASSするまで出力を確定しない**。正本: [x-longpost-create-multi-posts.md](../../prompts/x-longpost-create-multi-posts.md) §5.3.5 / MP-C07

---

## クイックスタート

| 用途 | 開始方法 |
|------|----------|
| **長文投稿作成** | 文字起こし + キャッチコピーを入力（メモはAIが自動生成） |
| **8投稿作成** | `run-x-multipost-create` を使う（文字起こしを入力し「8投稿作成して」と指示） |
| **長文投稿 + 8投稿** | 文字起こし + キャッチコピーを入力し「8投稿も作成して」と指示（→ 投稿9｜要約型400〜499文字（空白・改行を除く）が必ず付く） |
| **短文投稿最適化（1つ）** | `run-x-shortpost-optimize` を使う |
| 日付計算のみ | `node ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/calculate-next-date.js --neta-file "${XLP_NETA_FILE}"` |

---

## 入力要件

**メモの構造化はAIが自動で行う。文字起こしを入力するだけでよい。**

### 標準フロー: 文字起こし → 長文投稿

| 項目 | 必須 | 説明 |
|------|------|------|
| 文字起こし | ○ | 音声録音の文字起こしテキスト（フィラー・話し言葉をそのまま） |
| キャッチコピー | ○ | 投稿の核となる一言メッセージ |

→ AIが自動で「構造化メモ生成 → 長文投稿作成」を実行する
→ 「8投稿も作成して」と指示すると8投稿も同時作成可能

### メモが既にある場合

構造化済みメモを「メモ」として渡すと Phase 0 をスキップする。

## 出力設定

| 項目 | 値 |
|------|-----|
| ベースパス | `${XLP_VAULT_ROOT}`（env のみ。必要な場合に明示） |
| 出力先 | `${XLP_OUTPUT_DIR}` → `${XLP_VAULT_ROOT}/05_Project/X/` の2段のみ |
| ファイル名 | `X長文投稿-prompt作成 - YYYY-MM-DD_[タイトル].md` |
| 日付決定 | 00ネタファイル（`${XLP_NETA_FILE}`）の最新日付 + 1日 |
| テンプレート | `output-config.json` の `paths.obsidianTemplate`（無い場合は同梱の [../../assets/output-template.md](../../assets/output-template.md)） |
| スタイルゲノム | `output-config.json` の `paths.styleGenomeSource`（無い場合は [references/style-genome.md](../../references/style-genome.md) が正本） |

出力先は自動コミット対象になりうるため、**検証未了のファイルを直接置かない**。一時パスで `validate-headings.js` を PASS させてから配置する。

---

## ワークフロー

長文投稿は Phase 0（文字起こし構造化）→ 日付計算 → Phase 1（入力解析）→ Phase 1.5（タイトル確定。以後この文字列が唯一のタイトル）→ Phase 2（文章生成・文字数検証）→ Phase 3（出力整形・ファイル出力）→ Phase 3.5（アイデアコンパス）→ Phase 4（サムネイル・optional 図解生成）の順に進む。長文投稿と 8 投稿を同時に作る場合は Phase 0 の直後に 2 系統へ分岐し、Phase 3.4（投稿9｜要約型）で合流する。

Phase 4 は本スキルの範囲外であり、`run-x-visual-generate` が担う。パターン A が確定した後でしか画像を作れないため、接続点は Phase 3.5 の後に固定する。

各 Phase がどの `prompts/*.md` をどの順で Read するか、3 系統のフル図、フロー間の対応表は [references/workflow-diagrams.md](references/workflow-diagrams.md) が唯一の正本である。本 SKILL.md は図の実体を持たない。

8投稿フロー単独の仕様は `run-x-multipost-create`、短文1投稿の最適化は `run-x-shortpost-optimize` を参照する。

---

## リソース一覧

本 SKILL.md はリソース表の実体を持たない。正本は 2 つに分かれる。

| 正本 | 内容 |
|------|------|
| [references/resource-map.md](references/resource-map.md) | prompts / scripts / 共有 references / assets の所在と読込条件（散文・plugin 全体） |
| [references/resource-map.yaml](references/resource-map.yaml) | 本スキルの references を「いつ開くか」で引く機械可読索引 |

スクリプトは `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/`、prompts・共有 references・assets は plugin ルート直下、本スキル専用の references は `${XLP_SKILL_DIR}/references/` にある。規定が食い違って見えたときの決着は `ref-x-longpost-canon` が正本索引として担う。

---

## スタイルゲノム 8レベル

L1 表層 / L2 語彙 / L3 統語 / L4 談話 / L5 修辞 / L6 認知 / L7 価値観 / L8 対人 の 8 レベルすべてを文章生成時に適用する。各レベルの適用内容は [references/style-genome.md](../../references/style-genome.md) が唯一の正本であり、本 SKILL.md は要約表を持たない（要約を持つと正本と二重管理になる）。

---

## 出力形式

### 投稿文（長文）- 2パターン出力

**【重要】同一ファイルに2パターンを出力。文章内容は完全に同一、改行位置のみ異なる。**

| パターン | 特徴 | 用途 |
|----------|------|------|
| A: 文脈改行型 | 段落・意味の区切りで改行、見出し付き | PC閲覧向け（優先使用） |
| B: 短文改行型 | 先頭タイトルの後は1文=1行。非空本文行は文末記号で閉じ、1行へ2文を詰めない。文字数で機械的に切らず、Aと同じ本文を改行だけ変える | スマホ閲覧向け |

### 共通仕様（長文投稿A/Bの規定。投稿9｜要約型は400〜499文字で別枠）
- **1800〜2200文字**（中心値2000文字。空白・改行を除く／`count-chars.js` の測定）・タイトル付き

---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## 実行手順

### 【文字起こし入力時のみ】Step 0: 文字起こし構造化（LLM）
- `${XLP_PROMPTS_DIR}/x-longpost-structure-transcript.md` → 文字起こしをフィラー除去・書き言葉変換・構造化メモへ変換
- 出力した構造化メモを、以降の Step 2 で「メモ」として使用する
- 8投稿のみ作成する場合は本スキルではなく `run-x-multipost-create` を使う

### Step 1: 日付計算（スクリプト）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/calculate-next-date.js" --neta-file "${XLP_NETA_FILE}"
```

### Step 2-3: 入力解析（Phase 1・LLM）
- `x-longpost-parse-input.md` → 構成要素抽出（メモ = 手動メモ or structure-transcript の出力）
- `x-longpost-resolve-contradictions.md` → 矛盾解決

### Step 4: タイトル作成（Phase 1.5・LLM + スクリプト）
- `x-longpost-create-title.md` → 3案生成・最適選定
- `node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-title.js" --title "[タイトル案]"` を3案すべてに実行。PASSしない案は次へ渡さない
- ここで確定した文字列が唯一のタイトル。以降の見出し1・長文Bの先頭行・`# タイトル` セクション・ファイル名で一字一句そのまま使う

### Step 5: 文章生成（Phase 2・LLM）
- `x-longpost-apply-style-genome.md` → スタイル適用（見出しは出力しない）
- `x-longpost-optimize-length.md` → 2パターン生成・見出し2作成（タイトルは作らない。Step 4 の確定タイトルをそのまま見出し1に置く）

### Step 6: 文字数・見出し構造検証（スクリプト）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js" --text "[生成された投稿文]" --min 1800 --max 2200
# 見出し1の50文字・見出し2の存在（3〜8個）を検証（PASSするまで出力へ進まない）
# --text には「# タイトル」行を含むパターンA全文を渡す（--title は必須）
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js" --text "[# タイトル 行を含むパターンA全文]" --title "[Step 4 の確定タイトル]" --strict-h2-count
```

### Step 7: 出力（スクリプト + LLM）

出力手順の唯一の実体は [x-longpost-output-file.md §4.5.1](../../prompts/x-longpost-output-file.md) に置く。`generate-filename.js` が返す `filename`（正規 basename）を scratch 内でもそのまま使い、`expand-template.js` 展開後の見出し・タイトル一致・F4/F5・絵文字ゼロを検証する。全検証後にのみ同名の `fullPath` へ正規配置し、その後に00ネタファイルを更新する。いずれかが失敗した候補は scratch に留め、既存の `fullPath` を上書きしない。

### Step 7.4: 投稿9｜要約型（Phase 3.4・LLM + スクリプト）
- 長文パターンA確定後に `x-longpost-create-multi-posts.md` §5.3.5 → 長文Aの要点を400〜499文字（空白・改行を除く）で要約（新規主張なし）
- `node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js" --text "[投稿9本文]" --min 400 --max 499` がPASSするまで出力を確定しない。長文投稿を作らない8投稿単独ワークフローでは実行しない

### Step 7.5: アイデアコンパス生成（LLM）
- `x-longpost-generate-idea-compass.md` → 投稿テーマと00ネタファイルから4方向×5ノートを選定
- 投稿ファイルの `# Idea Compass` セクションに挿入

### Step 8: サムネイル・optional 図解生成（Phase 4・別スキルへ引き継ぐ）

成果物テンプレートの `図解` / `Xサムネイル（5:2）` / `noteサムネイル（1280×670px）` の 3 欄は、本スキルでは空のまま残す。長文成果物を提示して accept-as-is / light / standard / detailed の選択を完了し、本セッションを handoff_complete にした後、ユーザーが画像生成を明示したときだけ `run-x-visual-generate` を**別セッション**として起動する。引き継ぐのは検証済み投稿ファイルの絶対パス 1 つだけである。引き継ぎ先の標準成果物は X 5:2 と note 実 PNG 1280x670 の2枚で、図解は明示指定時のみ optional である。

- Step 7 の検証（`validate-headings.js` と `check-no-emoji.js`）が PASS し、パターン A が確定していることを引き継ぎの前提とする。**確定前に引き継がない**（本文を直すと図解が本文とずれるため）
- 画像生成は課金される。本スキルは起動も課金実行も自動で行わない

---

## ベストプラクティス

| すべきこと | 避けるべきこと |
|-----------|---------------|
| メモの内容を忠実に反映 | 固定フォーマットの使用 |
| スタイルゲノム8レベルを適用 | AIっぽい堅い表現 |
| スクリプトで決定論的処理 | 同じ表現の繰り返し |
| 1800〜2200文字（空白・改行を除く）に収める | 情報が行ったり来たりする構成 |
| 内容に即した具体的な見出し | 毎回同じパターンの見出し |
| 自然な流れの文章 | わざとらしい導入表現 |
| **主張の「軸」を1つに絞る** | **言いたいことが2つ以上ある曖昧な構成** |
| **冒頭に意外性のあるフックを作る** | **ありきたりな冒頭（「〜は大切です」等）** |
| **入口（タイトル・冒頭・フック）はホリゾンタル、中身はバーティカル** | **専門語・属性の重ね掛けで入口を狭める（TAMを潰す）** |
| **専門語は普遍的欲求（時間・お金・楽・不安解消・評価・変化）へ欲求翻訳して入口に置く** | **書き手の専門性起点でタイトル・冒頭を作る** |
| **ネタ性質判定の結果と根拠を出力に明示する** | **全ネタを一律の入口設計で処理する** |
| **具体的に書く（行動レベルまで）** | **抽象的なAI表現（「良い影響がある」等）** |
| **締めに印象的なフレーズを残す** | **当たり前すぎる締め（「成長につながります」等）** |
| **AI臭の記号を排除する** | **emダッシュ(—)、／並列、（）逃げ、「」多用** |
| **語尾・リズムに変化をつける** | **〜です連続、接続詞過多、温度一定** |
| **スタンスを取って言い切る** | **保険・中立装い・弱い否定で逃げる** |
| **動詞中心の具体表現にする** | **万能語(重要/効果的/最適)で押し切る** |
| **使い古された比喩を避ける** | **地図/羅針盤/土台/柱/DNA/車の両輪等** |
| **主観・感情・一次情報を入れる** | **客観的整理だけで終わる** |

### 禁止表現リスト（見出し・本文）

**正本**: [references/title-guidelines.md §3.3](../../references/title-guidelines.md)（タイトル用は §3.3.1、本文用は §3.3.2）。本 SKILL.md は実体を持たず、正本への参照のみを持つ。タイトル案は `validate-title.js` に通すことで機械的に検出される。

### 見出し作成のガイドライン

- 構成の役割（問いかけ、理想、現実、原因、リスク、解決策、未来）を直接見出しにせず、内容の核心を具体的に表現した見出しにする
- 毎回同じパターン（疑問形→理想→現実→...）を避け、内容に応じて変化をつける（絵文字は使わない）
- 具体的な作成手順とセクション別の例は [references/heading-title-guide.md](references/heading-title-guide.md)

---

## フィードバック（必須）

実行後は必ず記録:

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/log_usage.js" --result success --phase "Phase 4"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/log_usage.js" --result failure --phase "Phase 3" --error "ValidationError"
```

記録先は `XLP_LOG_FILE` → `${XLP_OUTPUT_DIR}/x-longpost-usage-log.md` の順で解決する。plugin ディレクトリの中には書かない（配布物を実行時に書き換えないため）。どちらの env も未設定の場合は記録をスキップして終了コード 0 を返す（推測パスへ書き出さない）。

---

## Anchors（設計の根拠）

| 出典 | 適用 | 目的 |
|------|------|------|
| スタイルゲノム基礎分析結果 | 8レベル文体特徴 | 一貫性ある個人文体 |
| On Writing Well (Zinsser) | 簡潔な文章作成 | 冗長削除・読みやすさ |
| Made to Stick (Heath) | 共感・感情駆動型構成 | 効果的な展開 |
| 中村昌弘 AI文章編集4原則 | AI文章の人間編集 | 主張明確化・フック・具体性・フレーズ |
| note公式タイトルガイド | タイトル設計 | 読まれやすいタイトル作成 |
| @genkaidokusho分析 | 8パターンフォーマット | 短文投稿最適化 |
| Continuous Delivery | Script First | 決定論的処理の自動化 |
| もとやま AIっぽい文章表現大全 (@ysk_motoyama) | AI臭6分類＋崩し3技法 | AI臭の体系的排除と人間らしさの注入 |
| 三連休 バーティカルすぎるnote論 (@san_renkyu) | ホリゾンタル入口×バーティカル中身・欲求翻訳・TAMチェック | 入口は広く解決策は深く |

変更履歴は [CHANGELOG.md](../../CHANGELOG.md)、正本の所在一覧は `ref-x-longpost-canon` を参照する。
