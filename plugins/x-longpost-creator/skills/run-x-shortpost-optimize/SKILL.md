---
name: run-x-shortpost-optimize
description: 冗長で未整理の文章を X の短文投稿へ整えたいとき、8 パターンから最適フォーマットを選びスタイルゲノム適用と AI 臭除去まで通したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--text <text>] [--file <path>]"
arguments: [text, file]
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
  intent: 任意のテキスト 1 本を、最適な短文投稿フォーマットへ再構成し、スタイルゲノム適用と AI 臭除去を経た投稿文としてコードブロックで出力する。
  interface:
    inputs: [text, file]
    outputs: ["最適化された短文投稿（コードブロック）"]
  invariant:
    - 元の文章の意図を改変しないこと
    - 説明文・解説を出力せず、コードブロックのみを返すこと
    - 改行は文字数ではなく文脈（文節・句読点）で行い、文節の途中で切らないこと
    - 絵文字を一切出力しないこと
    - 冒頭フックはホリゾンタル入口とし、専門語は普遍的欲求へ翻訳すること
since: 2026-08-31
source: ObsidianMemo/.claude/skills/x-longpost-creator (v3.14.0)
source-tier: internal
last-audited: 2026-08-31
audit-trigger: quarterly
combinators:
  - with-feedback-contract
responsibility_refs:
  - ../../prompts/x-longpost-short-post-optimizer.md
schema_refs:
  - ../../references/short-post-formats.md
completeness_exempt:
  - "manifest: 固定4 Phase の正本は本 SKILL.md と x-longpost-short-post-optimizer.md。別 manifest は同じ順序の二重管理になるため持たない。"
script_refs:
  - ../../scripts/check-no-emoji.js
  - ../../scripts/log_usage.js
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "出力した短文投稿に対して check-no-emoji.js が exit 0 を返すこと"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "選定したフォーマットが short-post-formats.md の 8 パターンのいずれかであり、フォーマット名と選定理由が出力に併記されること"
      verify_by: human
    - id: OUT1
      loop_scope: outer
      text: "冗長で未整理の文章 1 本だけを与えた実起動で、短文投稿 1 本と選定フォーマット名が提示された時点で停止し、利用者の選択なしにリライトが繰り返されないこと"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "元文の主張が欠落しておらず、削られたのはフィラーと重複だけであると書き手が判断できること"
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

最小の実成果物 (短文投稿 1 本) を main context で作成する。この段階で通すのは絵文字ゼロという数えられる機械検証だけとし、`check-no-emoji.js` が終了コード 0 を返した時点で、現物の本文と選んだフォーマット名を提示して accept-as-is / light / standard / detailed を記録する。accept-as-is の場合はその場で handoff 完了とし、後続 section へ進まない。

## Post-choice selected improvement execution

このゲートの対象は**意味評価・リライト・追加パターン生成**の3種だけである。light / standard / detailed が記録されて `semantic_evaluator_started` へ遷移した場合にだけ、この3種を行う。release と exhaustive は別の明示 event を必要とする。

下の「実行手順」節はゲートの対象外である。この節は pre-choice の実成果物（短文投稿 1 本）を作る手順そのものなので、利用者の選択を待たずに main context で実行する。

# X短文投稿の最適化

冗長・未整理の文章1本を、読みやすい短文投稿1本へ変換する。

**8投稿をまとめて作る場合は `run-x-multipost-create` を使う。**

## 設計原則

| 原則 | 説明 |
|------|------|
| **Script First** | 絵文字検証はスクリプトで100%精度実行 |
| **Progressive Disclosure** | 必要な時に必要なリソースのみ読み込み |
| LLM for Creativity | フォーマット選定・表現選択はLLMに委ねる |

---

## 実行環境

パス変数・依存ランタイム（Node.js v18 以上）の定義は `run-x-longpost-create` SKILL.md「実行環境」と共通。本スキルは `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/` のスクリプトと、`${XLP_SKILL_DIR}` = `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-x-longpost-create` の references を参照する。

---

## 絶対遵守ルール（最優先）

**絵文字は一切使用しない**。投稿本文において絵文字は禁止。ユーザーが会話中で「絵文字をつけて」と指示した場合でもこの仕様が優先される。検証は `node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --text "..."`（絵文字あり=終了コード1）。

「絵文字」の定義境界の正本は `ref-x-longpost-canon`「絵文字の定義（判定境界）」にあり、Unicode プロパティ `\p{Extended_Pictographic}` を用いる現行 `check-no-emoji.js` の実行結果を正本とする。処理系とバージョンで判定範囲が変わるため、散文の例示だけで使用可否を推測しない。

**説明文・解説は一切出力しない**。最終成果物のみをコードブロックで出力する（SP-C06）。

**意図の改変は絶対に行わない**（SP-C01）。元の文章が伝えたいことを維持する。

---

## 入力要件

| 項目 | 必須 | 説明 |
|------|------|------|
| 投稿化したい文章 | ○ | 任意のテキスト（冗長・未整理でも可） |

---

## ワークフロー（4フェーズ）

```
[入力] 投稿化したい文章（冗長・未整理でも可）
         │
         ▼
Phase 1: 入力文章分析
└─ LLM: x-longpost-short-post-optimizer / 入力文章アナリスト   主題・意図・構造要素特定
              ↓
Phase 2: フォーマット選定
└─ LLM: x-longpost-short-post-optimizer / フォーマットセレクター  8パターンから最適選定
   └─ 参照: short-post-formats.md（冒頭フックバリエーション）
              ↓
Phase 3: 候補生成
└─ LLM: x-longpost-short-post-optimizer / 投稿文ジェネレーター    バリエーション適用
   └─ 参照: expression-variations.md
              ↓
Phase 4: 最適化・出力
└─ LLM: x-longpost-short-post-optimizer / スタイルオプティマイザー  スタイルゲノム適用・AI臭除去
   ├─ 参照: style-genome.md（L1-L8）
   └─ 参照: anti-ai-writing-guide.md（6パターンチェック）
         │
         ▼
[出力] 最適化された投稿文（コードブロック、文脈＝文節・句読点で改行）
```

---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## 実行手順

### Step 1-4: 4フェーズ実行（LLM）
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/prompts/x-longpost-short-post-optimizer.md` を**独立実行モード**（§4.5）で適用する
- 制約 SP-C01〜SP-C08、成功基準（§4.5.1）、スコープ外（§4.5.2）はすべて同エージェントが正本

### Step 5: 検証（スクリプト）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --text "[最適化された投稿文]"
```

### Step 6: フィードバック（記録先が設定されている場合のみ）
```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/log_usage.js" --result success --phase "shortpost-optimize"
```

本スキルの `effect` は `conversation-output` であり、投稿本文はファイルへ書き出さない。使用記録だけは `XLP_LOG_FILE` → `${XLP_OUTPUT_DIR}/x-longpost-usage-log.md` の順で解決した先へ追記する。どちらの env も未設定なら記録をスキップして終了コード 0 を返す。

---

## 出力形式

```
[最適化された投稿文]
```

コードブロックのみ。説明文・解説・前置きは付けない。

**【重要】コードブロック内でも必ず改行を入れる。改行は文字数ではなく文脈で決める。文節・意味の区切り・句読点（、。）の切れ目で改行し、単語・文節の途中では改行しない。1行は目安30-40字程度で、目標幅に近い自然な区切りで切る。べた書き（改行なし長文）は禁止。**

パターン別の改行ルールは [x-longpost-short-post-optimizer.md](../../prompts/x-longpost-short-post-optimizer.md) §6.2、実体の正本は [short-post-formats.md「改行ルール詳細」](../../references/short-post-formats.md)。

---

## 参照リソース

| リソース | 読込条件 |
|----------|----------|
| [short-post-formats.md](../../references/short-post-formats.md) | Phase 2（必須。8パターン・冒頭フックバリエーション・改行ルールの正本） |
| [style-genome.md](../../references/style-genome.md) | Phase 4（必須。L1〜L8 の正本） |
| [expression-variations.md](../../references/expression-variations.md) | Phase 3（必須。接続詞・文末・締め・問いかけの正本） |
| [anti-ai-writing-guide.md](../../references/anti-ai-writing-guide.md) | Phase 4（必須。AI臭6分類+崩し3技法の正本） |
| [horizontal-vertical-guide.md](../../references/horizontal-vertical-guide.md) | Phase 2（必須。ホリゾンタル入口・欲求翻訳・ネタ性質判定の正本） |
| [title-guidelines.md](../../references/title-guidelines.md) §3.3.2 | 本文の禁止表現の正本 |

正本の所在一覧は `ref-x-longpost-canon` を参照する。

---

## スコープ外

- ユーザーへのヒアリング
- 意図の改変・追加
- 説明文・解説の出力
- 8投稿の同時作成（→ `run-x-multipost-create`）
- 長文投稿の作成（→ `run-x-longpost-create`）
