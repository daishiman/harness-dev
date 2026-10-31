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
  - Bash(python3 *)
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
  - references/neutral-question-criteria.md
script_refs:
  - scripts/apply-spec-transition.py
  - ../../scripts/validate-knowledge-graph.py
  - ../../scripts/validate-coverage-matrix.py
  - ../../scripts/validate-design-knowledge-refs.py
schema_refs:
  - ../../schemas/spec-state.schema.json
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
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: inline goal-seek selects the next unmet interview/checklist responsibility dynamically; the SKILL body is the runtime SSOT."
deterministic_checks:
  - ../../scripts/validate-coverage-matrix.py
  - ../../scripts/validate-design-knowledge-refs.py
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-coverage-matrix.py が spec-state.json に対し 6 canonical platform 全存在・各セルが未収集/対象外/確定の3値・対象外に理由(または approval_ref)・確定に qa_ref・カテゴリ集約が真理値表一致・不正値0件を機械検証して exit0 になる。R0-foundation 完了後は --require-foundation も付け、requirements_foundation の U1-U9(値ありまたは明示 N/A・U1/U2/U3 は値必須)・decisions 契約・各確定セルの serves_goals トレースも exit0 で検証する(R0 完了前の foundation 未確定段階では --require-foundation を課さない段階条件)。加えて各確定セルの根拠 (qa_ref と qa_refs) のうち少なくとも 1 件が basis(user-decision/observed-fact/agent-inference) を宣言し、宣言がすべて agent-inference ではないことを --require-basis が exit0 で検証し、missing_effect=block の必須情報については confirm を含む writer apply/chunk を --required-info <catalog> 付きで実行し、既存 validate_required_info が候補 state の接地を確認してからだけ公開する(失敗時は元 state を変更しない。公開後は validate-knowledge-graph.py --profile required-info --state <spec-state> の coverage_certificate.ungrounded_blocking_items が空であることを再確認する)。schema_version 1.1 を opt-in した state では、確定セルの主根拠 qa_ref が指す qa entry (add-qa-ref で結んだ補足 qa_refs は対象外) の design_applications に knowledge_ref/principle/applicability/rationale/非空 tradeoffs を必須とし、あわせて validate-design-knowledge-refs.py --matrix <spec-state> --repo-root <project root> の exit0 で design_applications[].knowledge_ref の path と anchor 見出しの実在を検証する(coverage matrix 側は解釈の形状しか見ないため、参照先の無い引用はこのゲート無しでは緑のまま通る)。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 往復ヒアリングを経て全セルが確定または対象外(理由付き)で埋まり未収集0になった最終 spec-state.json を validate-coverage-matrix.py --require-complete --require-basis --require-foundation が exit0 で確認し(未収集0だけでなく、全確定セルの basis と U1-U9・serves_goals トレースまで最終条件に含める)、受入テストが resume 保存も含めて再現する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: 実対話のlive trialで、U1-U9確定、needs_guidance時の最新根拠付き2〜3案、free/low-cost候補、AI推奨保留、ユーザー確認、最終未収集0までを機密情報なしのsandbox stateで完走できる。
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

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-system-spec-elicit

## Purpose & Output Contract

**入力**: ヒアリング応答 (対話) / 既存 `spec-state.json` (resume 時) / C04 taxonomy。
**出力**: `spec-state.json` (`references/spec-state-contract.md` の形状。plugin 共有データ契約。schema 1.0 が既定で 1.1 は opt-in。上位概念 `requirements_foundation` を含む)。
**完了条件**: `requirements_foundation` が確定 (U1-U9 が値または明示 N/A+理由・ただし U1/U2/U3 は値必須で N/A 不可・U1-U9 要約のユーザー承認 `approval_ref` 付き・`confirmed: true`) し、全セルが `確定`(qa_ref 付き) か `対象外`(reason か approval_ref 付き) で、未収集0。`validate-coverage-matrix.py --require-complete --require-basis --require-foundation` が exit0 (`--require-basis` は確定セルごとに、根拠 `qa_ref` と `qa_refs` のうち少なくとも 1 件が `basis` を宣言していることを課す。宣言された `basis` がすべて推定 `agent-inference` のセルは、このフラグが無くても違反になる)。加えて `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-knowledge-graph.py" --profile required-info --input "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/references/required-info-catalog.json" --state "$CLAUDE_PROJECT_DIR/system-spec/spec-state.json"` の `coverage_certificate.ungrounded_blocking_items` に残る ID が 0 件 (`missing_effect=block` の必須情報が全て確定に接地) である。`coverage_certificate.blocking_items` は未解決一覧ではなく `missing_effect=block` の収集必須 item ID 一覧であり、各 ID を確定 foundation/matrix/decision の利用者根拠へ接地する (非空であること自体は失敗ではない)。一次根拠は利用者入力に限る: 対話は `source.kind=user-dialogue`、書面は path/section・逐語 `answer`・SHA-256 を持ち、AI 生成文を一次根拠にせず、新しい利用者入力なしに approval を作らない。schema 1.1 の state では、加えて各 U が `effective_source_refs` の 1 論点 QA と承認へ遡及でき、確定セルが参照する qa が `design_applications[]` を持つ。

- **platforms (6)**: `web` / `mobile` / `tablet` / `desktop-windows` / `desktop-linux` / `desktop-macos`。
- **cell states (3値, loop 中)**: `未収集` / `対象外` / `確定`。最終時は `未収集` を0にする。
- **category_aggregate (4値)**: 真理値表から導出 (直接指定しない)。全セル未収集=未着手 / 未収集混在=収集中 / 全セル対象外=対象外 / それ以外で未収集0=確定。
- **カテゴリ初期集合の正本**: C04 `plugins/system-spec-harness/skills/ref-system-design-knowledge/references/system-category-taxonomy.json` を Read して得る (prompt へ直書き禁止)。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

> システム構築の仕様を、まず **上位概念 (本質的目的/背景/ゴール/目標/成功基準/具体的やりたいこと U1-U9)** を深掘りヒアリングで確定し (R0-foundation)、その上で **カテゴリ×canonical platform id** の収集マトリクスを往復ヒアリングで終端化する L1 skill。ユーザーが決めきれない項目は R5 が最新公式根拠付き2〜3案（無料/低コスト案を含む）を目的適合で比較し、AI推奨・理由・注意点を示してユーザー確認へ導く。foundation / decisions / matrix の書込は本 skill 所有の**単一 transition writer**のみ。

監査 fork の genuine Agent 応答・verdict 台帳は completeness evaluator (C05) の所有であり、C01 の状態遷移受領条件へ重複して持ち込まない。C01 は設計適用を構造化した spec-state を作り、C05 がその内容と独立監査 evidence を評価する。

## 上位概念 anchor (要件 C9・spec drift 防止)

> 上位概念がブレると、仕様が整ってもブレる。技術マトリクス (下位概念) の**手前**で上位概念 (U1-U9) を最初にしっかり抽出して `requirements_foundation` に固定し、各技術決定 (確定セル) を `serves_goals` でそこへトレース (anchor) する。どのゴールにも資さない収集は drift として検出する。

- **bootstrap** サブコマンドが空のstate envelope (`$CLAUDE_PROJECT_DIR/system-spec/spec-state.json`) を作り、**R0-foundation** が `set-foundation` op で `requirements_foundation` (U1-U9) を確定してから **R1-init** (`init` サブコマンド) がtaxonomyをpopulateする。R1は既存foundation/decisionsを保持し、上位概念が曖昧なまま技術ヒアリングへ進まない。
- **U ごとの根拠束縛 (`effective_source_refs`)**: schema 1.1 の確定 foundation は全 U に `effective_source_refs.U<N>.{qa_ref,approval_ref}` を持つ。writer と coverage validator は参照先の一意な実在、QA の question による対象 `U<N>` の明示、利用者一次入力の `source`、置き換え済み (`superseded_by`) でないこと、現行 approval との整合を強制する。canonical `qa-foundation-u1`〜`u9` は初回履歴として改変せず保持し、確定値を更新するときは変更対象 U の新 QA/approval とトップレベル `approval_ref` を同時に更新する (値だけを旧証拠へ付け替える操作は writer が拒否する)。既定の schema 1.0 で `effective_source_refs` を省いた state だけ canonical fallback を許す (1.1 は `--schema-version 1.1` の opt-in)。
- **共有 foundation QA は例外契約**: 複数 U が同じ `qa_ref` を指すときだけ、各 binding に consumer 別の `evidence_quote` / `evidence_sha256` を必須とする。writer と coverage validator は question の U marker 集合、answer 内の quote 完全一致、quote hash、consumer 間の独立性、approval 同一性を機械検査し、C06 が quote の意味的な裏付けと逐語性を監査する。
- 各 `確定` セルに `serves_goals: [<goal_id>, ...]` を付与 (confirm 同時付与 or `set-serves` op) し、どの上位概念に資するかを明示する。
- C03 (`run-system-spec-compile`) は `requirements_foundation` を `system-spec/00-requirements-definition.md` (要件定義書=憲法) として先頭章に生成し、各技術章 frontmatter に `serves_goals` を持たせて全章を貫通させる。
- 検証: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --require-foundation` が U1-U9 (U1/U2/U3 は値必須、他は値または理由付きの明示 N/A)・decisions 契約・各確定セルの serves_goals トレース・drift 候補を機械検証する (opt-in)。

## 単一 transition writer 防御 (SSOT)

`spec-state.json` への状態書込は **`scripts/apply-spec-transition.py` の一経路のみ**。本 writer は以下を機械的に強制する:

1. **確定巻き戻しの拒否**: `確定` セルを `confirm` / `exclude` で直接変更しようとすると `TransitionError` で拒否する。Bash や別 script から CLI を叩いても同じく拒否される (single-writer 防御)。
2. **R4-reopen 経由のみ確定変更**: `確定` セルの状態を動かせるのは `action=reopen` (要 reason) だけ。reopen は当該セルを `未収集` へ戻し `reopen_log` に根拠を残す。その後 `confirm` / `exclude` で再遷移できる。
3. **確定/対象外の付帯必須**: `confirm` は `qa_ref` (qa_log entry 参照) 必須、`exclude` は `reason` か `approval_ref` (approval_log 参照) 必須。
4. **集約は導出のみ**: `category_aggregate` は真理値表から再計算する。手書き代入を認めない。
5. **根拠参照と置き換えの整合**: `add-qa-ref` は `確定` セルにだけ追記でき、`qa_log` に実在する id だけを受ける。`supersede-qa` は旧 entry への write-once の追記で、旧 entry が確定セルの主たる接地根拠 (`qa_ref`) の間は拒否する。置き換え済みの entry を `qa_ref` にした `confirm` も拒否する。
6. **設計解釈の必須性と形状検証 (schema 1.1)**: `schema_version: "1.1"` を opt-in した state は `design_application_contract_version: "1.0"` を持つ。writer は turn の `design_applications` (具体原則・採否・章固有理由・非空 trade-off) を検証して回答原文とは別 field に保存し、`validate-coverage-matrix.py --require-complete` は確定セルの主根拠 `qa_ref` が指す qa entry で解釈と provenance の存在・形状を再検査する (`add-qa-ref` で結んだ補足 `qa_refs` は対象外)。`legacy_exempt: true` と非空理由を持つ既存 qa に限り、`set-qa-design-applications` が質問・回答を改変せず設計解釈だけを追記して `design_application_provenance.mode=legacy_backfill` を残す (provenance の無い既存解釈は対話経路として保護し、異なる解釈や provenance の上書きは拒否する)。C03 は `unrecorded|dialogue|legacy_backfill` を章へ描画し、C05 は `unrecorded` を未記録 finding とする。schema 1.0 (既定) の state にはこの契約を課さない。

> 本文・prompt・CLI いずれの経路でも、マトリクスの状態遷移は上記 writer を経由すること。直接 JSON 編集で `確定`→`未収集` を書くのは契約違反。

## 責務 (prompts/)

| id | prompt | 責務 |
|---|---|---|
| R0-foundation | `prompts/R0-foundation.md` | マトリクス収集の**手前**で上位概念 (U1-U9) を深掘りヒアリング (5 Whys で U1・JTBD で U6) し `set-foundation` で `requirements_foundation` を確定。未確定は再質問し放置しない。 |
| R1-init | `prompts/R1-init.md` | C04 taxonomy を Read し、カテゴリ×6必須platform の全存在(対象外は理由付き)を検証して初期化。カテゴリ軸の拡張発見もここ。 |
| R2-interview | `prompts/R2-interview.md` | 未収集セルを対象に 質問→回答→仕様反映 の往復で各セルを `確定` か `対象外+理由` へ遷移。 |
| R3-reask | `prompts/R3-reask.md` | 未確定セルを再質問。1 invocation の 5 loop 到達時は未完了状態と next_question を保存し resumable な結果を返す。未収集を完了扱いしない。 |
| R4-reopen | `prompts/R4-reopen.md` | 確定済みセルを根拠付きで再オープンし追加質問サイクルへ戻す。reopen 非経由の確定直接変更は writer が遮断する。 |
| R5-decision-guide | `prompts/R5-decision-guide.md` | `needs_guidance` を最新公式情報とC04 deep knowledgeから2〜3案へ展開し、無料/低コスト案を含めgoal fit/TCO/security/operations/lock-inで比較。AI推奨は`recommended_pending_confirmation`、ユーザー選択だけを`confirmed`にする。推奨は問に入れず、比較の後の別の段で「参考」として示し、最後に中立な問で選択を求める (N1-N4 と推奨の示し方の正本は `references/neutral-question-criteria.md`)。加えて `confirm` を含む writer `apply` / `chunk` に `--required-info "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/references/required-info-catalog.json"` を付け、既存接地検証を候補 state に適用して通過後だけ公開する収集ゲートを課し (`coverage_certificate.blocking_items` は収集必須 item ID 一覧で、確定を止めるのは未接地の ID だけ)、`--profile knowledge --order` の topo_order (上位概念→下位概念) 順で知識を消費する。 |

## ゴールシーク実行

- engine=inline / fork=subagent / max_loops=5 / loop_semantics = **per-invocation chunk limit**。
- 1 invocation で最大 5 loop (質問→回答→反映) を回す。5 loop 到達で未収集が残れば `hearing_progress.complete=false` と `next_question` を保存し、resumable に返す (`--resume` で続行)。
- 未収集0を満たしたときだけ `complete=true`・`next_question=null`。未収集セルを完了扱いしない。
- `chunk` へ上限を超える turn を渡すと超過分は適用されず、writer が未消化件数を stderr へ出す。全消化が必要な投入は `chunk --require-all` を付け、未消化があれば writer は書き戻さずに止まる。
- ループの各周回は「未達 = 未収集セル」を最小化する手順を都度立案→ writer で適用→ `validate-coverage-matrix.py` で検証、を繰り返す (固定手順を持たない)。

## feedback-contract (with-feedback-contract)

- **IN1 (inner / script)**: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --matrix spec-state.json` が exit0 (loop 中の網羅性)。R0-foundation 完了後は `--require-foundation` を付けて `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --matrix spec-state.json --require-foundation` も exit0 とし、上位概念 U1-U9・decisions 契約・serves_goals トレースを段階的に課す (foundation 未確定の R0 完了前には課さない)。確定セルを作った後は `--require-basis` も付け、確定セルごとに根拠 (`qa_ref` / `qa_refs`) の少なくとも 1 件に `basis` 宣言を課す。schema 1.1 の state では `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-design-knowledge-refs.py" --matrix "$CLAUDE_PROJECT_DIR/system-spec/spec-state.json" --repo-root "$CLAUDE_PROJECT_DIR"` も exit0 とし、`design_applications[].knowledge_ref` の path と anchor 見出しの実在を確かめる (coverage matrix 側は解釈の形状しか見ないため、参照先の無い引用はこのゲートが無いと緑のまま通る。`--repo-root` の既定は cwd で `knowledge_ref` は repo 相対なので省略しない)。
- **OUT1 (outer / test)**: 最終 `spec-state.json` を `--require-complete --require-basis --require-foundation` が exit0 で受理し (未収集0・全確定セルの `basis` 宣言・U1-U9 と serves_goals トレースを最終条件に含める)、下の収集ゲートも `ungrounded_blocking_items` に残る ID が 0 件で通る。受入テスト (`tests/`) が resume 保存を含めてこの最終状態を再現する。
- **収集ゲート (C16 / IN1 補完)**: `confirm` を含む writer `apply` / `chunk` は `--required-info "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/references/required-info-catalog.json"` を必ず付ける。writer がメモリ上の候補 state を既存 `validate_required_info` で検証し、`missing_effect=block` の必須情報が接地してからだけ正本 (または `--out`) へ公開する。失敗時は元 state を変更せず追加収集する。未収集の入力 state の事後接地を確定前条件にはしない。公開後の二重確認は既存 `validate-knowledge-graph.py --profile required-info --state <spec-state>` の exit0 と `coverage_certificate.ungrounded_blocking_items` に残る ID が 0 件であること。接地は候補の決着済みセル (`確定` または `対象外`) の `qa_ref`/`qa_refs` → qa_log の `required_info_items` で判定する。R2 の各 turn に `basis` と `required_info_items` を付ける。初回確定・再確定の双方で同じ候補検証を使う (詳細は `references/spec-state-contract.md`)。
- **情報優先度の責務境界 (ui-ux / `information-priority` item)**: 本 skill が確定させるのは**方針まで** — 表現物ごとに何を残し・落とし・加工するか、束の順位とその根拠 (task 頻度 × 失敗コスト) — であり、`spec-state.json` の該当セルへ qa_ref 付きで記録する (`missing_effect=degrade`。非適用なら理由を記録する)。この方針を `information-priority-map.json` として具体化し `validate-information-priority.py` で機械検証するのは**下流の生成工程**の責務であり、要件段階で成果物の生成は求めない。下流の現状は 2 系統に分かれる — **map ゲートまで実装済み**なのは slide-report-generator の構成設計 (`structure-designer` / `report-structure-designer` が構成着手前に exit 0 を要求) のみ。**C03 仕様書生成は原理カードの注入まで**で、`../run-system-spec-compile/scripts/compile-spec-doc.py` の `category_design_refs()` が C04 `resource-map.yaml` の `read_when` から ui-ux / frontend 章へ `information-design.md` を自動で引く (map ゲートの C03 への組込は follow-up)。原理の正本は C04 `../ref-system-design-knowledge/references/information-design.md`。

## 使い方 (ゴールへ向けた反復)

> `spec-state.json` の正本位置は `$CLAUDE_PROJECT_DIR/system-spec/spec-state.json`。以下のパス例はこの正本を指す (別ディレクトリに二重生成しない)。

1. **bootstrap**: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" bootstrap --out $CLAUDE_PROJECT_DIR/system-spec/spec-state.json` で空foundation/decisions/targets/logsを持つstate envelopeを用意する (`init` は taxonomy から matrix を初期化する別subコマンドで、envelope 生成は `bootstrap`)。
2. **R0-foundation**: 技術ヒアリングの手前で上位概念 U1-U9 を深掘りし、U1/U2/U3 は値必須・U4-U9 は値または明示N/A理由で埋め、U1-U9 要約をユーザーへ提示して承認 `approval_ref` を得て確定する。`set-foundation` で `confirmed: true` を渡す前に、根拠 QA (初回は canonical `qa-foundation-u1`〜`u9`) を `chunk` の turn (`qa_id`) で記録しておく。承認は先に `chunk` の turn (`approval_id`) で記録するか、`set-foundation` の JSON に `approval_ref` と `approval_note` を添えて同時に登録する (根拠 QA か承認が欠けると writer が確定を拒否する)。初回 canonical QA は履歴として残し、schema 1.1 では全 U の `effective_source_refs` と現行 `approval_ref` を `set-foundation` で確定する。QA の question は binding 先の `U<N>` を明示する。後続の確定値変更は新 QA/approval・対象 binding・トップレベル `approval_ref` を同時に更新する。
3. **R1-init**: taxonomy を Readしてmatrixをpopulateする。既存foundation/decisionsを保持する。
4. **R2/R3/R5**: required-info の `collection_order` で未収集セルをヒアリングし、不明・未決定ならR5で根拠付き候補と推奨を提示する。問は `references/neutral-question-criteria.md` の N1-N4 に従い、推奨は問と別の段に置く。確定セル/decisionはgoalへトレースし、5 loop超でresume保存。
5. **R4-reopen**: 確定セルの見直しが要るときのみ reopen。
6. **検証**: 各周回でvalidator、最終で`--require-complete --require-basis --require-foundation`。source・設計解釈・knowledge ref の補完は各専用 writer (`set-qa-source` / `set-qa-design-applications` / `fix-qa-knowledge-ref`) を使う。歴史的な誘導 entry は本文を改変せず Gotchas 6 の `supersede-qa` で置き換えを記録し、置き換え済み entry を確定セルの主根拠や `effective_source_refs` に残さない。`chunk` で turn の全消化が必要なら `--require-all` を付ける。

## Gotchas

1. カテゴリを prompt へ直書きしない。必ず C04 taxonomy が正本。
2. `確定`→`未収集` の直接書換は禁止 (reopen を使う)。
3. 5 loop 到達で未収集が残るなら未完了として保存する。未収集を勝手に確定/対象外にしない。
4. `category_aggregate` は writer が真理値表から再計算する (手書きしない)。
5. platform id は canonical 6 種のみ (別名を作らない)。
6. 問は `references/neutral-question-criteria.md` の N1-N4 に従う。凍結済みの問に違反が見つかったら、同じ論点を中立に問い直して回答を取り直し、`supersede-qa` op で旧 entry に置き換えを記録する (本文は書き換えない)。旧 entry が確定セルの `qa_ref` なら、R4-reopen で reopen → 問い直し → 新しい qa で再確定してから `supersede-qa` を記録する (旧 entry が主根拠のままだと writer が拒否し、置き換え済みの entry を `qa_ref` にした `confirm` も拒否する)。
7. `qa_log` は 1 entry = 1 論点。複数論点を束ねると C06 が論点別に中立性を検証できない。書面要件も利用者の一次入力なので、U1-U9 ごとに path/section・原文 SHA-256 を持つ source-index を記録する。既登録 entry の逐語は改変せず、束ねが判明したら分離索引を新規 entry として追記する (契約は `references/spec-state-contract.md` の「qa_log の論点分離」)。

## Additional Resources

- `references/spec-state-contract.md` — spec-state.json 形状 + 真理値表 + writer 契約の正本。
- `references/elicit-question-bank.md` — カテゴリ×platform で確認する論点の一覧 (聞き漏れを確かめるチェックリスト。問の文面の雛形ではない)。
- `references/resource-map.yaml` — Progressive Disclosure 索引。
- `references/neutral-question-criteria.md` — 中立な問の基準 N1-N4 と推奨の示し方の正本 (問を作る R0/R2/R3/R4/R5 と監査する R6/C06 が共有)。
- `prompts/R6-audit-hearing.md` — 往復ヒアリング監査 (C06 `system-spec-hearing-auditor`) の判定観点の正本。C06 が読む監査 SSOT で、本 skill の実行責務ではない。
- `prompts/R7-audit-matrix.md` — 収集マトリクス監査 (`system-spec-matrix-auditor`) の判定観点の正本。R6 と同じく本 skill の実行責務ではない。R6/R7 は本 skill の成果物を対象とする監査なので本文の正本は本 skill が持ち、起動アダプタ (`../../agents/system-spec-{hearing,matrix}-auditor.md`) は `assign-system-spec-completeness-evaluator` の `agent_refs` が所有する。監査対象と判定者を分けるため、本 skill のゴールシークが選ぶ責務の母集合は R0-R5 に限る。
- `../../scripts/validate-design-knowledge-refs.py` — schema 1.1 の `design_applications[].knowledge_ref` の path と anchor 見出しの実在ゲート。
- `scripts/apply-spec-transition.py` — 単一 transition writer。matrix 系 (bootstrap/init/add-category/apply/chunk/aggregate) と個別 writer (set-targets/set-foundation/set-decision/set-knowledge-candidate/set-qa-source/set-qa-design-applications/fix-qa-knowledge-ref) を持つ (一覧の正本は `--help`)。
- `../../scripts/validate-coverage-matrix.py` — 網羅性の決定論ゲート (IN1/OUT1)。
- `references/required-info-catalog.json` — C16 必須情報カタログ (domain 別 block/degrade/warn item・収集順序 depends_on・coverage certificate の正本)。
- `../../scripts/validate-knowledge-graph.py` — 知識グラフ / required-info の決定論ゲート (`--profile required-info` が domain 被覆・item 形状・blocking_items を (`--state` 併用で block item の確定接地も)、`--profile knowledge --order` が topo_order を検証)。
- C04: `../ref-system-design-knowledge/references/system-category-taxonomy.json` — カテゴリ初期集合の正本。
