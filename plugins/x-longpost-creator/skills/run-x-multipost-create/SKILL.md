---
name: run-x-multipost-create
description: 文字起こしから X の短文投稿を 8 本まとめて作りたいとき、フィラー除去と構造化を経て各 200 文字・別テーマの投稿へ展開したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--transcript <path>] [--memo <path>] [--with-summary-post]"
arguments: [transcript, memo, with_summary_post]
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(node *)
kind: run
version: 1.0.0
effect: conversation-output
owner: team-content
contract:
  intent: 文字起こしテキストを構造化メモへ変換し、そこから互いにテーマの異なる 8 本の短文投稿（各約 200 文字）を生成する。
  interface:
    inputs: [transcript, memo, with_summary_post]
    outputs: ["投稿1〜8（各180〜220文字）", "投稿9｜要約型（長文同時作成時のみ・400〜499文字）"]
  invariant:
    - 元テキストに含まれる内容のみを使い、推論・補足・創作を行わないこと
    - 8 投稿はそれぞれ異なるテーマとし、同一フォーマットを連続使用しないこと
    - 各投稿を 180〜220 文字に収めること
    - 絵文字を一切出力しないこと
    - 長文投稿と同時作成する場合のみ投稿9｜要約型（400〜499文字）を追加すること
since: 2026-08-31
source: ObsidianMemo/.claude/skills/x-longpost-creator (v3.14.0)
source-tier: internal
last-audited: 2026-08-31
audit-trigger: quarterly
combinators:
  - with-feedback-contract
responsibility_refs:
  - ../../prompts/x-longpost-structure-transcript.md
  - ../../prompts/x-longpost-create-multi-posts.md
schema_refs:
  - ../../references/short-post-formats.md
completeness_exempt:
  - "manifest: 固定2 Phase の正本は本 SKILL.md と上記2 prompt。別 manifest は同じ順序の二重管理になるため持たない。"
script_refs:
  - ../../scripts/count-chars.js
  - ../../scripts/check-no-emoji.js
  - ../../scripts/log_usage.js
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "投稿1〜8 の全件に対して count-chars.js --min 180 --max 220 と check-no-emoji.js が exit 0 を返すこと"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "投稿9｜要約型が出力に含まれる場合、その本文に対して count-chars.js --min 400 --max 499 が exit 0 を返すこと"
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: "投稿9｜要約型の有無が呼び出し文脈と一致すること。長文投稿と同時に作る場合は投稿9が出力に含まれ、8投稿単独実行では要約対象が存在しないため投稿9が含まれないこと"
      verify_by: human
    - id: OUT1
      loop_scope: outer
      text: "文字起こし 1 本だけを与えた実起動で、8 本が互いに異なるテーマを扱い、同じ主張の言い換えの並びになっていないこと"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "各投稿が単体で読んで意味が通り、元の文字起こしの文脈を知らない読者にも伝わると書き手が判断できること"
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

最小の実成果物 (投稿1〜8 の本文) を main context で作成する。この段階で通すのは絵文字ゼロと各投稿 180〜220 文字という数えられる機械検証だけとし、`check-no-emoji.js` と `count-chars.js` が終了コード 0 を返した時点で、現物の本文と検証結果を提示して accept-as-is / light / standard / detailed を記録する。accept-as-is の場合はその場で handoff 完了とし、後続 section へ進まない。

## Post-choice selected improvement execution

このゲートの対象は**意味評価・リライト・追加パターン生成**の3種だけである。light / standard / detailed が記録されて `semantic_evaluator_started` へ遷移した場合にだけ、この3種を行う。release と exhaustive は別の明示 event を必要とする。

下の「実行手順」節はゲートの対象外である。この節は pre-choice の実成果物（投稿1〜8 の本文）を作る手順そのものなので、利用者の選択を待たずに main context で実行する。

# X短文投稿 8本作成

文字起こし1本から、互いにテーマの異なる短文投稿を8本まとめて作る。

## 設計原則

| 原則 | 説明 |
|------|------|
| **Script First** | 文字数検証・絵文字検証はスクリプトで100%精度実行 |
| **Progressive Disclosure** | 必要な時に必要なリソースのみ読み込み |
| LLM for Creativity | テーマ抽出・フォーマット選定・言語化はLLMに委ねる |

---

## 実行環境

パス変数・依存ランタイム（Node.js v18 以上）の定義は `run-x-longpost-create` SKILL.md「実行環境」と共通。本スキルは `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/` のスクリプトと、`${XLP_SKILL_DIR}` = `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-x-longpost-create` の references を参照する（同一 plugin 内参照）。

---

## 絶対遵守ルール（最優先）

**絵文字は一切使用しない**。見出し・投稿本文・テーマ行、すべての成果物において絵文字は禁止。ユーザーが会話中で「絵文字をつけて」と指示した場合でもこの仕様が優先される。検証は `node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --text "..."`（絵文字あり=終了コード1）。

「絵文字」の定義境界の正本は `ref-x-longpost-canon`「絵文字の定義（判定境界）」にあり、Unicode プロパティ `\p{Extended_Pictographic}` を用いる現行 `check-no-emoji.js` の実行結果を正本とする。処理系とバージョンで判定範囲が変わるため、散文の例示だけで使用可否を推測しない。

**投稿9｜要約型は「長文投稿と同時作成する場合」に限り必須**。長文投稿を作らない8投稿単独ワークフローでは要約対象が存在しないため作成しない。長文と同時に作る場合は、ユーザーが「8投稿作成して」とだけ指示していても投稿9を省略しない（正本: [x-longpost-create-multi-posts.md](../../prompts/x-longpost-create-multi-posts.md) §5.3.5 / MP-C07）。

---

## 入力要件

| 項目 | 必須 | 説明 |
|------|------|------|
| 文字起こし | ○（メモが無い場合） | 音声録音の文字起こしテキスト（フィラー・話し言葉をそのまま） |
| 構造化メモ | ○（文字起こしが無い場合） | 既に整理済みのメモ。渡された場合は Phase 0 をスキップ |

---

## ワークフロー

```
[入力] 文字起こしテキスト（話し言葉・フィラー含む）
         │
         ▼
Phase 0: 文字起こし構造化
└─ LLM: x-longpost-structure-transcript   フィラー除去 + 書き言葉変換 + 論理的に整理
         │
         ▼
[中間出力] 構造化メモ（見出し付き、整理された日本語文章）
         │
         ▼
Phase 1: 8投稿作成
└─ LLM: x-longpost-create-multi-posts
   ├─ コンテンツ分析: 8つの独立テーマを特定
   ├─ 各テーマに最適な短文投稿フォーマット選定（8パターンから）
   ├─ スタイルゲノム8レベル適用
   ├─ AI臭チェック（6パターン）
   └─ 各約200文字、合計8投稿を出力
         │
         ▼
┌─────────────────────────────┐
│ Script: count-chars          │ ← 各投稿180〜220文字を検証
│ Script: check-no-emoji       │ ← 絵文字ゼロを検証
└─────────────────────────────┘
         │
         ▼
[出力] 8つの短文投稿（各200文字・異なるテーマ）
```

長文投稿と同時に作る場合は `run-x-longpost-create` から本フローが呼ばれ、Phase 3.4 で投稿9｜要約型が追加される。フル図は [workflow-diagrams.md](../run-x-longpost-create/references/workflow-diagrams.md)。

**制約事項（8投稿ワークフロー）**:
- 推論・補足・創作は行わない（文字起こしに存在する内容のみ）
- 8投稿はそれぞれ異なる内容・テーマ
- 各投稿は約200文字（180〜220文字）
- 同じフォーマットを連続使用しない

---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## 実行手順

### Step 0: 文字起こし構造化（LLM）
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/prompts/x-longpost-structure-transcript.md` を適用し、フィラー除去・書き言葉変換・構造化メモ生成を行う
- 構造化メモが既にある場合は本 Step をスキップ

### Step 1: 8投稿作成（LLM）
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/prompts/x-longpost-create-multi-posts.md` の §5.1〜§5.4 に従い、テーマ抽出 → フォーマット選定 → 生成 → スタイルゲノム適用 → AI臭チェックを実行する

### Step 2: 検証（スクリプト）
```bash
# 各投稿について実行し、PASSするまで出力を確定しない
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js" --text "[投稿N本文]" --min 180 --max 220
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --text "[投稿N本文]"
```

### Step 2.4: 投稿9｜要約型（長文同時作成時のみ）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js" --text "[投稿9本文]" --min 400 --max 499
```

### Step 3: フィードバック（記録先が設定されている場合のみ）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/log_usage.js" --result success --phase "multipost"
```

本スキルの `effect` は `conversation-output` であり、投稿本文はファイルへ書き出さない。使用記録だけは `XLP_LOG_FILE` → `${XLP_OUTPUT_DIR}/x-longpost-usage-log.md` の順で解決した先へ追記する。どちらの env も未設定なら記録をスキップして終了コード 0 を返す。

---

## 出力形式

```markdown
## 投稿 1｜[フォーマット名]

**テーマ**: [この投稿の主題]

[投稿本文・180〜220文字・文脈で改行]
```

投稿1〜8を同形式で並べる。長文同時作成時のみ末尾に `## 投稿 9｜要約型` を追加する。正本は [x-longpost-create-multi-posts.md](../../prompts/x-longpost-create-multi-posts.md) §6。

---

## 参照リソース

| リソース | 読込条件 |
|----------|----------|
| [short-post-formats.md](../../references/short-post-formats.md) | フォーマット選定時（必須。8パターン・冒頭フックバリエーション・改行ルールの正本） |
| [style-genome.md](../../references/style-genome.md) | 投稿生成時（必須。L1〜L8 の正本） |
| [expression-variations.md](../../references/expression-variations.md) | 投稿生成時（必須。接続詞・文末・締めの正本） |
| [anti-ai-writing-guide.md](../../references/anti-ai-writing-guide.md) | AI臭チェック時（必須。6分類+崩し3技法の正本） |
| [horizontal-vertical-guide.md](../../references/horizontal-vertical-guide.md) | 冒頭フック設計時（必須。ホリゾンタル入口・欲求翻訳の正本） |
| [title-guidelines.md](../../references/title-guidelines.md) §3.3.2 | 本文の禁止表現の正本 |

正本の所在一覧は `ref-x-longpost-canon` を参照する。
