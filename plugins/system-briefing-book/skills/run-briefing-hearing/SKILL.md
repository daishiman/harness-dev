---
name: run-briefing-hearing
description: 素材を読んだうえで、使う人や困りごとはあいまいなら促して聞き足し、画面や裏側のしくみと運用は既定案つきで短く聞き取りたいとき、確認点で増えた決めることを聞いてヒアリング.md に足したいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L2
version: 0.1.0
goal_seek:
  engine: inline
  fork: inline
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/run-briefing-hearing
user-invocable: true
disable-model-invocation: false
output_language: ja
argument-hint: "<資料フォルダ> [要望] | followup <資料フォルダ> <Q 番号の並び>"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
context: inherit
manifest: workflow-manifest.json
reference_refs:
  - references/hearing-guide.md
  - ../../assets/data/hearing-catalog.json
  - ../../references/document-structure.md
  - ../../references/plain-language.md
  - ../../references/quality-rules.md
  - ../../references/execution-contract.md
script_refs:
  - ../../scripts/validate-briefing-docs.mjs
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 2
  criteria:
    - id: IN1
      loop_scope: inner
      text: "ヒアリング.md が 1〜5 章の見出しどおりで、固定H01〜H36が揃いH番号が重複せず、未定Hの確認対象と確認先が5章に残り、出どころが 聞き取り/素材:<ファイル名>/既定案/未定/要望 のどれかで埋まり、validate-briefing-docs.mjs --stage hearing が exit0 する"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "1 回の質問は 4 問以内で、選択肢を出す質問は素材に合わせた具体的な選択肢の先頭が「(おすすめ)」つきになっており、聞いた回数は 6 回と聞き足しの 2 回以内に収まり、聞き足しが核心の 5 問 (A1・A2・A3・A6・A7) だけで 1 問 2 回以内であること、followup は聞き足しを除いて 1 回・4 問まで (初めのヒアリングの回数には数えない) で最後の選択肢が「打ち合わせで聞く」になっており、返した組の H が ヒアリング.md にあって、もとからある H 番号が変わっていないことを、実際の聞き取りで確かめる"
      verify_by: live-trial
    - id: OUT1
      loop_scope: outer
      text: "仕事の流れ、画面の共通ルール (骨組み・ヘッダー・メニュー・フッター・色・モーダル・メッセージ・空/読み込み中)、管理の画面と直す・消す・人の出し入れ、しくみと基盤 (動かす場所・データの置き場所・ログイン・外部とのつなぎ・自動処理・バックアップ・通知)、残す情報と量と見られると困る情報、止まったときの答えが、catalogのcaptureとdestinationsに沿って要件定義と仕様書へつながり、聞いた事実・設計の案・確認先付きの未定が分かれていると briefing-reviewer が確認する"
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: "技術に詳しくない利用者が質問を読んで迷わず答えられ、「全部おすすめ」の1回の返事でも案の作成まで進み、未確認の業務条件・安全・保持・復旧が未定Hと確認先に残ることを実際の聞き取りで確かめる"
      verify_by: live-trial
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

[execution-contract.md](../../references/execution-contract.md) の「6. 通常生成と確認の選択所有」に従う。L1 が確認点の選択を所有し、L2 は通常生成と既存検査を選択前から実行する。

## Post-choice selected improvement execution

light / standard / detailed が記録されて `semantic_evaluator_started` へ進んだ確認点だけ、独立レビューとその指摘に基づく改善を行う。release / exhaustive は別の明示 event を要する。
このスキルは分離した文脈を使わない (goal_seek.fork=inline)。独立レビューは呼び出し元 run-briefing が assign-briefing-evaluator へ渡し、このスキルは頼まれた指摘の行だけを直す。


# ヒアリング

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

文書とボードを書く前に、素材だけでは分からないことを短く聞く。使う人や困りごとのような核心は、答えがあいまいなら促して聞き足す。画面や基盤の設計は、業務の答えから案を作る。
確認点で 決めること が増えたら、今答えられるものだけを聞いて ヒアリング.md に足す。

| 入口 | 引数 | すること |
| --- | --- | --- |
| 新しいヒアリング | `<資料フォルダ> [要望]` | ヒアリング.md を 1〜5 章まで書く |
| followup | `followup <資料フォルダ> <Q 番号の並び>` | 決めること の Q を 4 つまで聞き、答えを ヒアリング.md に足す |

- 出力: `<資料フォルダ>/ヒアリング.md` だけを書く。ほかのファイルは書かない。
- 共通UIと実装の前提は hearing-guide.md の「回答に残す設計情報」に沿って既存の回答に残す。未確認の詳細を既定案から確定した事実へ置き換えない。
- 質問・選択肢・聞く回・行き先・収集観点・設計の案の正本は [hearing-catalog.json](../../assets/data/hearing-catalog.json)。聞き方と回答の扱いは [hearing-guide.md](references/hearing-guide.md)。固定質問を増やさず、素材由来の補足・追加要望・未定だけ末尾H番号で足す。
- 確認の深さを選ぶのと独立レビューは、呼び出し元の run-briefing が持つ。単独で呼ばれたときは結果を見せて終わる。

## 手順 (新しいヒアリング)

### 1. 素材から先に埋める

1. `_check/materials.json`、素材、要望を読む。
2. hearing-catalog.json の質問ごとに、素材で答えが分かるものを先に埋める。出どころは `素材:<ファイル名>`。目安は hearing-guide.md の「6. 素材から先に埋めるときの目安」を読む。
3. 要望や素材で、名前を挙げて頼まれた機能があれば、出どころ `要望` の行にする (hearing-guide.md の「3. 答えの扱い」)。
4. 埋まらなかった質問だけを聞く。

### 2. 既定案つきで聞く

1. hearing-guide.md の「5. 回の組み方」の回ごとに聞く。問いの形 (1 回の問いの数、おすすめ、header、回の初めに添える 1 行) は「2. 聞き方」を読む。
2. 核心の 5 問 (A1・A2・A3・A6・A7) の答えがあいまいなら、「2. 聞き方」の「聞き足しと促し方」で聞き足す。
3. 答えごとの出どころは「3. 答えの扱い」を読む。

### 3. ヒアリング.md を書く

欄ごとの書き方は hearing-guide.md の「7. ヒアリング.md の書き方」を読む。章立ては [document-structure.md](../../references/document-structure.md) の「ヒアリング.md」、お手本は `examples/sample-haisha/打ち合わせ資料/ヒアリング.md`。

### 4. 検査して見せる

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-briefing-docs.mjs" --dir "<資料フォルダ>" --stage hearing
```

- exit 1 なら `_check/docs.json` の errors を見て ヒアリング.md を直し、exit0 になるまで通し直す。
- exit 2 と exit 3 は、[execution-contract.md](../../references/execution-contract.md) の「3. 終了コード」を読み、そこに書かれたとおりにする。
- exit0でも固定Hの欠落、空の回答、未定の確認先・引き渡しの不足は修正する。案と未定を含む資料の完成を、すべての設計が確定したとは報告しない。
- 終わったら次を見せる: ヒアリング.md の場所、聞き取り・既定案・素材・未定・要望 の件数、あとで相談すること の一覧。

## 手順 (followup)

呼び出し元 (run-briefing の確認点) から、その工程で 決めること に増えた Q を受け取って聞く。

1. 要件定義.md の「9. 決めること」と ヒアリング.md を読む。渡された Q から、最初の版への効き目が大きい順 (最初の版でやること・画面・しくみと基盤 を変えるものが先) に 4 つまで選ぶ。
2. 1 回で聞く。1 問に Q を 1 つ。決めること を問いの形にし、先頭の選択肢を 案 (おすすめ)、最後の選択肢を「打ち合わせで聞く」にする。問いの形のほかの決まりは hearing-guide.md の「2. 聞き方」のとおり。
3. 核心の 5 問 (A1・A2・A3・A6・A7) に当たる答えがあいまいなら、同じ章の「聞き足しと促し方」で聞き足す。
4. 答えを hearing-guide.md の「確認点で出た答えの書き方」のとおりに ヒアリング.md へ書く。「打ち合わせで聞く」「わからない」「あとで」の Q と、選ばなかった Q は何も変えない。
5. 新しいヒアリングの手順 4 と同じく `--stage hearing` を exit0 まで通す。
6. 返すもの: 答えが出た Q 番号と H 番号の組の一覧 (例: `Q04=H17, Q01=H37`)。答えが出なかった Q は入れない。文書への反映は、呼び出し元が run-briefing-docs の answers に頼む。

## Gotchas

- 聞き方の決まりは hearing-guide.md の「2. 聞き方」を読む。
- 素材から質問を足すときは、既定案を「最初の版はシンプルに」の向きで選ぶ ([quality-rules.md](../../references/quality-rules.md) の「1. シンプルさ」)。
- 人は役割名 (配車の担当者、運転手) で書く。素材にある名前を回答欄に写してよいかは briefing.json の `data_policy` で決まる ([quality-rules.md](../../references/quality-rules.md) の「名前と値の扱い (data_policy)」)。

## Additional Resources

- [hearing-catalog.json](../../assets/data/hearing-catalog.json): 固定質問・選択肢・聞く回・行き先・収集観点・設計案の正本
- [hearing-guide.md](references/hearing-guide.md): 聞き方と聞き足し、答えの扱い、catalogの使い方、記録の書き方
- [document-structure.md](../../references/document-structure.md): ヒアリング.md の章立て
- [plain-language.md](../../references/plain-language.md): 言い換え
- [quality-rules.md](../../references/quality-rules.md): 既定案の向き (1. シンプルさ)
- [execution-contract.md](../../references/execution-contract.md): 実行場所 (1 節)・スクリプトの終了コード (3 節)・確認の選択所有 (6 節)
