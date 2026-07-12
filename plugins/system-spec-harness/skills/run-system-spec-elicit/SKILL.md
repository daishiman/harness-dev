---
name: run-system-spec-elicit
description: システム仕様のヒアリングを開始するとき、システム構築の要件をカテゴリ×プラットフォームの収集マトリクスで往復ヒアリングして spec-state.json に確定させたいときに使う。
disable-model-invocation: false
user-invocable: true
kind: run
prefix: run
hierarchy: L1
effect: local-artifact
owner: team-platform
since: 2026-07-11
version: 0.1.0
output_language: ja
argument-hint: "[--spec-state <path>] [--resume]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebSearch
  - WebFetch
  - AskUserQuestion
  - Task
trigger_conditions:
  - システム仕様のヒアリングを開始
  - システム構築の要件収集
  - spec-hearing-start
responsibility_refs:
  - prompts/R0-foundation.md
  - prompts/R1-init.md
  - prompts/R2-interview.md
  - prompts/R3-reask.md
  - prompts/R4-reopen.md
  - prompts/R5-decision-guide.md
reference_refs:
  - references/resource-map.yaml
  - references/elicit-question-bank.md
  - references/spec-state-contract.md
  - references/required-info-catalog.json
script_refs:
  - scripts/apply-spec-transition.py
  - ../../scripts/validate-knowledge-graph.py
responsibilities:
  - id: R0-foundation
    name: elicit-foundation
    prompt_required: true
  - id: R1-init
    name: init-matrix
    prompt_required: true
  - id: R2-interview
    name: interview
    prompt_required: true
  - id: R3-reask
    name: reask
    prompt_required: true
  - id: R4-reopen
    name: reopen
    prompt_required: true
  - id: R5-decision-guide
    name: guide-decision
    prompt_required: true
combinators:
  - with-goal-seek
  - with-feedback-contract
deterministic_checks:
  - ../../scripts/validate-coverage-matrix.py
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-coverage-matrix.py が spec-state.json に対し 6 canonical platform 全存在・各セルが未収集/対象外/確定の3値・対象外に理由(または approval_ref)・確定に qa_ref・カテゴリ集約が真理値表一致・不正値0件を機械検証して exit0 になる。R0-foundation 完了後は --require-foundation も付け、requirements_foundation の U1-U9(値ありまたは明示 N/A・U1/U2/U3 は値必須)・decisions 契約・各確定セルの serves_goals トレースも exit0 で検証する(R0 完了前の foundation 未確定段階では --require-foundation を課さない段階条件)。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 往復ヒアリングを経て全セルが確定または対象外(理由付き)で埋まり未収集0になった最終 spec-state.json を validate-coverage-matrix.py --require-complete が exit0 で確認し、受入テストが resume 保存も含めて再現する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: 実対話のlive trialで、U1-U9確定、needs_guidance時の最新根拠付き2〜3案、free/low-cost候補、AI推奨保留、ユーザー確認、最終未収集0までを機密情報なしのsandbox stateで完走できる。
      verify_by: live-trial
---

# run-system-spec-elicit

> システム構築の仕様を、まず **上位概念 (本質的目的/背景/ゴール/目標/成功基準/具体的やりたいこと U1-U9)** を深掘りヒアリングで確定し (R0-foundation)、その上で **カテゴリ×canonical platform id** の収集マトリクスを往復ヒアリングで終端化する L1 skill。ユーザーが決めきれない項目は R5 が最新公式根拠付き2〜3案（無料/低コスト案を含む）を目的適合で比較し、AI推奨・理由・注意点を示してユーザー確認へ導く。foundation / decisions / matrix の書込は本 skill 所有の**単一 transition writer**のみ。

## 上位概念 anchor (要件 C9・spec drift 防止)

> 上位概念がブレると、仕様が整ってもブレる。技術マトリクス (下位概念) の**手前**で上位概念 (U1-U9) を最初にしっかり抽出して `requirements_foundation` に固定し、各技術決定 (確定セル) を `serves_goals` でそこへトレース (anchor) する。どのゴールにも資さない収集は drift として検出する。

- **bootstrap** サブコマンドが空のstate envelope (`$CLAUDE_PROJECT_DIR/system-spec/spec-state.json`) を作り、**R0-foundation** が `set-foundation` op で `requirements_foundation` (U1-U9) を確定してから **R1-init** (`init` サブコマンド) がtaxonomyをpopulateする。R1は既存foundation/decisionsを保持し、上位概念が曖昧なまま技術ヒアリングへ進まない。
- 各 `確定` セルに `serves_goals: [<goal_id>, ...]` を付与 (confirm 同時付与 or `set-serves` op) し、どの上位概念に資するかを明示する。
- C03 (`run-system-spec-compile`) は `requirements_foundation` を `system-spec/00-requirements-definition.md` (要件定義書=憲法) として先頭章に生成し、各技術章 frontmatter に `serves_goals` を持たせて全章を貫通させる。
- 検証: `../../scripts/validate-coverage-matrix.py --require-foundation` が U1-U5 非空・各確定セルの serves_goals トレース・drift 候補を機械検証する (opt-in)。

## Purpose & Output Contract

**入力**: ヒアリング応答 (対話) / 既存 `spec-state.json` (resume 時) / C04 taxonomy。
**出力**: `spec-state.json` (`references/spec-state-contract.md` の形状。plugin 共有データ契約。上位概念 `requirements_foundation` を含む)。
**完了条件**: `requirements_foundation` が確定 (U1-U9 が値または明示 N/A+理由・ただし U1/U2/U3 は値必須で N/A 不可・U1-U9 要約のユーザー承認 `approval_ref` 付き・`confirmed: true`) し、全セルが `確定`(qa_ref 付き) か `対象外`(reason か approval_ref 付き) で、未収集0。`validate-coverage-matrix.py --require-complete --require-foundation` が exit0。加えて `../../scripts/validate-knowledge-graph.py --profile required-info --input references/required-info-catalog.json` の `coverage_certificate.blocking_items` が空 (`missing_effect=block` の必須情報が全て確定に接地) である。

- **platforms (6)**: `web` / `mobile` / `tablet` / `desktop-windows` / `desktop-linux` / `desktop-macos`。
- **cell states (3値, loop 中)**: `未収集` / `対象外` / `確定`。最終時は `未収集` を0にする。
- **category_aggregate (4値)**: 真理値表から導出 (直接指定しない)。全セル未収集=未着手 / 未収集混在=収集中 / 全セル対象外=対象外 / それ以外で未収集0=確定。
- **カテゴリ初期集合の正本**: C04 `plugins/system-spec-harness/skills/ref-system-design-knowledge/references/system-category-taxonomy.json` を Read して得る (prompt へ直書き禁止)。

## 単一 transition writer 防御 (SSOT)

`spec-state.json` への状態書込は **`scripts/apply-spec-transition.py` の一経路のみ**。本 writer は以下を機械的に強制する:

1. **確定巻き戻しの拒否**: `確定` セルを `confirm` / `exclude` で直接変更しようとすると `TransitionError` で拒否する。Bash や別 script から CLI を叩いても同じく拒否される (single-writer 防御)。
2. **R4-reopen 経由のみ確定変更**: `確定` セルの状態を動かせるのは `action=reopen` (要 reason) だけ。reopen は当該セルを `未収集` へ戻し `reopen_log` に根拠を残す。その後 `confirm` / `exclude` で再遷移できる。
3. **確定/対象外の付帯必須**: `confirm` は `qa_ref` (qa_log entry 参照) 必須、`exclude` は `reason` か `approval_ref` (approval_log 参照) 必須。
4. **集約は導出のみ**: `category_aggregate` は真理値表から再計算する。手書き代入を認めない。

> 本文・prompt・CLI いずれの経路でも、マトリクスの状態遷移は上記 writer を経由すること。直接 JSON 編集で `確定`→`未収集` を書くのは契約違反。

## 責務 (prompts/)

| id | prompt | 責務 |
|---|---|---|
| R0-foundation | `prompts/R0-foundation.md` | マトリクス収集の**手前**で上位概念 (U1-U9) を深掘りヒアリング (5 Whys で U1・JTBD で U6) し `set-foundation` で `requirements_foundation` を確定。未確定は再質問し放置しない。 |
| R1-init | `prompts/R1-init.md` | C04 taxonomy を Read し、カテゴリ×6必須platform の全存在(対象外は理由付き)を検証して初期化。カテゴリ軸の拡張発見もここ。 |
| R2-interview | `prompts/R2-interview.md` | 未収集セルを対象に 質問→回答→仕様反映 の往復で各セルを `確定` か `対象外+理由` へ遷移。 |
| R3-reask | `prompts/R3-reask.md` | 未確定セルを再質問。1 invocation の 5 loop 到達時は未完了状態と next_question を保存し resumable な結果を返す。未収集を完了扱いしない。 |
| R4-reopen | `prompts/R4-reopen.md` | 確定済みセルを根拠付きで再オープンし追加質問サイクルへ戻す。reopen 非経由の確定直接変更は writer が遮断する。 |
| R5-decision-guide | `prompts/R5-decision-guide.md` | `needs_guidance` を最新公式情報とC04 deep knowledgeから2〜3案へ展開し、無料/低コスト案を含めgoal fit/TCO/security/operations/lock-inで比較。AI推奨は`recommended_pending_confirmation`、ユーザー選択だけを`confirmed`にする。加えて `../../scripts/validate-knowledge-graph.py --profile required-info --input references/required-info-catalog.json` の `coverage_certificate.blocking_items` (`missing_effect=block` の未充足 item) が空になるまで当該 domain の確定セルの `confirmed` を禁じる収集ゲートを課し、`--profile knowledge --order` の topo_order (上位概念→下位概念) 順で知識を消費する。 |

## goal-seek 実行 (with-goal-seek)

- engine=inline / fork=subagent / max_loops=5 / loop_semantics = **per-invocation chunk limit**。
- 1 invocation で最大 5 loop (質問→回答→反映) を回す。5 loop 到達で未収集が残れば `hearing_progress.complete=false` と `next_question` を保存し、resumable に返す (`--resume` で続行)。
- 未収集0を満たしたときだけ `complete=true`・`next_question=null`。未収集セルを完了扱いしない。
- ループの各周回は「未達 = 未収集セル」を最小化する手順を都度立案→ writer で適用→ `validate-coverage-matrix.py` で検証、を繰り返す (固定手順を持たない)。

## feedback-contract (with-feedback-contract)

- **IN1 (inner / script)**: `python3 ../../scripts/validate-coverage-matrix.py --matrix spec-state.json` が exit0 (loop 中の網羅性)。R0-foundation 完了後は `--require-foundation` を付けて `python3 ../../scripts/validate-coverage-matrix.py --matrix spec-state.json --require-foundation` も exit0 とし、上位概念 U1-U9・decisions 契約・serves_goals トレースを段階的に課す (foundation 未確定の R0 完了前には課さない)。
- **OUT1 (outer / test)**: 最終 `spec-state.json` を `--require-complete` が exit0 で受理し、受入テスト (`tests/`) が resume 保存を含めて再現する。
- **収集ゲート (C16 / IN1 補完)**: `../../scripts/validate-knowledge-graph.py --profile required-info --input references/required-info-catalog.json` が exit0 かつ `coverage_certificate.blocking_items` が空。`missing_effect=block` の必須情報 (product-goal / target-platforms / domain-model / auth-model / security-posture) が確定に接地するまで当該 domain の確定セルの `confirmed` を許さない (R5 が prose ゲートとして施行し、決定論 writer=apply-spec-transition への block 検査組込は follow-up)。

## 使い方 (ゴールへ向けた反復)

> `spec-state.json` の正本位置は `$CLAUDE_PROJECT_DIR/system-spec/spec-state.json`。以下のパス例はこの正本を指す (別ディレクトリに二重生成しない)。

1. **bootstrap**: `apply-spec-transition.py bootstrap --out $CLAUDE_PROJECT_DIR/system-spec/spec-state.json` で空foundation/decisions/targets/logsを持つstate envelopeを用意する (`init` は taxonomy から matrix を初期化する別subコマンドで、envelope 生成は `bootstrap`)。
2. **R0-foundation**: 技術ヒアリングの手前で上位概念 U1-U9 を深掘りし、U1/U2/U3 は値必須・U4-U9 は値または明示N/A理由で埋め、U1-U9 要約をユーザーへ提示して承認 `approval_ref` を得て確定する。
3. **R1-init**: taxonomy を Readしてmatrixをpopulateする。既存foundation/decisionsを保持する。
4. **R2/R3/R5**: 未収集セルをヒアリングし、不明・未決定ならR5で根拠付き候補と推奨を提示する。確定セル/decisionはgoalへトレースし、5 loop超でresume保存。
5. **R4-reopen**: 確定セルの見直しが要るときのみ reopen。
6. **検証**: 各周回でvalidator、最終で`--require-complete --require-foundation`。

## Gotchas

1. カテゴリを prompt へ直書きしない。必ず C04 taxonomy が正本。
2. `確定`→`未収集` の直接書換は禁止 (reopen を使う)。
3. 5 loop 到達で未収集が残るなら未完了として保存する。未収集を勝手に確定/対象外にしない。
4. `category_aggregate` は writer が真理値表から再計算する (手書きしない)。
5. platform id は canonical 6 種のみ (別名を作らない)。

## Additional Resources

- `references/spec-state-contract.md` — spec-state.json 形状 + 真理値表 + writer 契約の正本。
- `references/elicit-question-bank.md` — カテゴリ×platform 質問テンプレ集。
- `references/resource-map.yaml` — Progressive Disclosure 索引。
- `scripts/apply-spec-transition.py` — 単一 transition writer (init/apply/chunk/aggregate)。
- `../../scripts/validate-coverage-matrix.py` — 網羅性の決定論ゲート (IN1/OUT1)。
- `references/required-info-catalog.json` — C16 必須情報カタログ (domain 別 block/degrade/warn item・収集順序 depends_on・coverage certificate の正本)。
- `../../scripts/validate-knowledge-graph.py` — 知識グラフ / required-info の決定論ゲート (`--profile required-info` が domain 被覆・item 形状・blocking_items を、`--profile knowledge --order` が topo_order を検証)。
- C04: `../ref-system-design-knowledge/references/system-category-taxonomy.json` — カテゴリ初期集合の正本。
