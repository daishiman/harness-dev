---
name: run-skill-intake
description: 非エンジニアからスキル要件を引き出したいとき、intake.md と Notion ページを manifest 駆動で生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
  - Skill
  - Task
kind: run
prefix: run
goal_seek:
  activation_state: semantic_evaluator_started
  engine: task-graph
  full_task_spec_graph: false  # workflow-manifest の phase 依存だけを扱う縮小 profile
  engine_profile: checklist-graph  # planner の full task-spec graph と非同等 (縮小 profile)
  fork: inline
  spec: eval-log/goal-spec.json
  progress: eval-log/run-skill-intake-progress.json
  intermediate: eval-log/run-skill-intake-intermediate.jsonl
  max_loops: 17  # 11 phase × 1.5 の追記余裕を切り上げ
user-invocable: true
disable-model-invocation: true
effect: external-mutation
runtime_root_policy: host-skill-path
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.2.0
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/intake-request.schema.json
  - schemas/output.schema.json
  - schemas/phase2-assumption.schema.json
  - schemas/phase3-profile.schema.json
  - schemas/phase5-purpose.schema.json
  - schemas/phase8-summary.schema.json
reference_refs:
  - ref-workflow-sequence
  - ref-handoff-contract
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: workflow-manifest.json の phases[] を本 SKILL.md へ複製せず manifest を唯一の SSOT として参照する(二重管理 drift がない)。lint-manifest-contents.py exit 0。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: スキル生成スキル(run-skill-create/run-build-skill/capability-build 等)の起動禁止が hook-guard-skillgen.py(PreToolUse, exit 2)で機械強制され、intake 実行中フラグ駆動の遮断が回帰テストで担保されている。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 業務ロジック(質問雛形・採点基準・Notion blocks 生成)を持たず 11 phase を Skill/SubAgent へ委譲し handoff JSON 契約のみで橋渡しする薄い orchestrator 設計が、非エンジニアの曖昧要望から実装可能な intake 仕様まで橋渡しする目的を最適に反映している。
      verify_by: elegant-review
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
---

## Purpose & Output Contract

非エンジニアの要望から、schema-valid な `intake.md` / `intake.json`、公開済み Notion URL、recommendation-only の `next-action.json` を作る薄い orchestrator。pre-choice はユーザー入力を推測補完しない `intake-request.json` と実行 preview の提示まで、選択後だけ manifest 駆動の phase 委譲と明示確認済み external mutation を実行する。

**Key Rule**: 必ず `workflow-manifest.json` の依存・skip/retry・exitHook 契約を正本とし、`next-action.json` を後続生成の自動起動へ変換しない。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

main context は依頼文を逐語保持した `output/<hint>/intake-request.json` (`schemas/intake-request.schema.json`) と、manifest digest・予定出力・外部 mutation 範囲を示す read-only preview だけを作る。最終 `intake.md` / `intake.json` を依頼文から推測生成しない。path・digest・開き方を提示してから accept-as-is/light/standard/detailed を記録する。accept-as-is は request snapshot のローカル handoff で終了し、正式 intake / Notion URL / next-action は未生成であることを明示する。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionおよびexternal mutation safety wrapperはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。actual mutationはcanonical preview→hook-confirm→authorize→execute wrapperだけを通し、release/exhaustiveは別の明示eventを必要とする。

<!-- external-mutation-guard-cli:v1 -->
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
<!-- /external-mutation-guard-cli:v1 -->


# run-skill-intake

## Runtime workflow details

intake plugin の中核 orchestrator。pre-choiceではmain contextが依頼文を `intake-request.json` へ損失なく保存し、schema guard と実行 preview を提示する。`workflow-manifest.json` の11 phaseを子Skill/SubAgentへ委譲する処理とNotion公開はlight/standard/detailed選択後だけ実行する。accept-as-isではSubAgent/公開とも0回で request snapshot のローカル handoffを完了し、正式 intake 完了とは表現しない。

**入力**: ユーザーの「スキルを作りたい」要望 (topic 引数任意) + 任意の Notion 明示指定 (`--page-url` / `--page-id` / `--database-id`)。Notion 明示指定は `notion_target` として intake.json に保持し、Phase 10 publish まで落とさない。

**出力**:

| 成果物 | パス | 生成 phase |
|--|--|--|
| intake-request.json | `output/<hint>/intake-request.json` | pre-choice (user input snapshot) |
| kickoff.json | `output/<hint>/kickoff.json` | P1 |
| assumption.json | `output/<hint>/assumption.json` | P2 |
| profile.json | `output/<hint>/profile.json` | P3 |
| sheet.md + interview.json | `output/<hint>/` | P4 |
| purpose.json | `output/<hint>/purpose.json` | P5 |
| options.json | `output/<hint>/options.json` | P6 |
| visuals.json + PNG 群 | `output/<hint>/visuals/` | P7 |
| summary.{md,json} | `output/<hint>/` | P8 |
| intake.{md,json} | `output/<hint>/` | P9 finalize |
| self-update.json + qb-candidates.json | `output/<hint>/` | P9 exitHook (post-finalize, inline) |
| notion-url.txt | `output/<hint>/notion-url.txt` | P10 |
| next-action.json | `output/<hint>/next-action.json` | P11 |
| intake-trace.json | `eval-log/intake-trace.json` | 全 phase 共通 |

**pre-choice handoff条件**: `intake-request.json` がschema guardを通りpath/digest付きで提示済み (正式 intake ではない)。**選択後の改善完了条件**: manifest 全 phase が PASS または条件付き SKIP + quality/cross-check PASS。Notion公開はさらにexplicit confirmation receiptがある場合だけ行う。

## Key Rules

1. **manifest を SSOT とする**: 固定 Steps を本文に書かず `workflow-manifest.json` の `phases[]` (id / dependsOn / delegateType / delegateName / fatal_exit_codes) を読み実行順を決める。
2. **業務ロジックを持たない**: 質問雛形 / 技法選択 / 採点基準 / Notion blocks 生成は子 Skill / SubAgent / references に閉じる。本スキルは起動順序と handoff JSON の受け渡しのみ。
3. **handoff JSON 必須**: 各 phase 完了時に対応 JSON ファイルが存在し、`workflow-manifest.json` と各 skill / SubAgent の `schemas/` 契約に通ること。違反時はその phase に戻す。
4. **SubAgent fresh context (context:fork)**: light/standard/detailed選択後のみ、Phase 2 / 3 / 5 / 8をTask toolでSubAgent起動する。accept-as-isと提示前は起動しない。
5. **失敗で停止**: phase が exit != 0 / handoff JSON 検証 fail / fatal_exit_codes hit なら停止し `intake-trace.json` に再開ポイントを記録、ユーザーへ提示。
6. **Secret-Out-of-Repo**: Notion トークンは Keychain から都度取得 (`scripts/keychain_get_secret.py`)。リポジトリへ書き込まない。
7. **Gate A (Phase 8) で停止可能**: summary 否認時は Phase 4 へ戻り再ヒアリング (最大 2 周)。
8. **lint 自動修正禁止**: P0 lint fail は根本原因をユーザー提示し AI 判断で勝手に修正しない。
9. **スキル生成を絶対に実行しない (hard stop / 機械強制)**: 本スキルは **ヒアリング〜Notion 公開〜Phase 11 next-action 推奨**までで完結し、`run-skill-create` / `run-build-skill` / `capability-build` 等のスキル生成スキルを **Skill / Task / Bash いずれでも起動しない**。Phase 11 の `next-action.json` の `mode` は**推奨情報**に過ぎず、本スキルがそれを実行に移すことはない。Phase 11 完了 = ワークフロー終了であり、完了レポート提示後は必ず停止する。現行 handoff は recommendation-only-v1 で、スキル生成はユーザーが別途明示的に開始する独立アクションである。
   - **この禁止は自然言語の指示だけに依存しない (100% 機械保証)**: `hooks/hook-guard-skillgen.py` (PreToolUse: Skill|Task|Bash) が、`run-skill-intake` 実行中フラグ (lock) を hook 駆動で立て、intake 実行中に生成スキルが起動されると **exit 2 でツール呼び出し自体をハーネスがブロック**する。lock の作成・遮断・解除は全て hook が行いモデル挙動に依存しない。本 Key Rule (プロンプト層) は「なぜ止まるか」の意図説明であり、保証の主体は hook 層である。配線は `.claude-plugin/plugin.json`、実証は `tests/test_skill_intake_guard_skillgen.py`。
10. **Phase 9 exitHook の inline 自己更新**: `run-intake-finalize` が `intake.json` を生成した後にだけ、`run-skill-intake` が `measure_value_realized.py` を起動して計測結果を `self-update.json` へ保存する。次に同じ `update_question_bank.py --derive-from-intake` で `sections.10_self_updater.question_bank_additions` を `qb-candidates.json` へ決定論的に導出し、`--apply` なしで preview する。別ターンの明示承認後だけ `--apply`し、`declining=true` なら適用しない。採点・候補導出・重複排除ロジックは各 script を正本とし、orchestrator に再実装しない。

## ゴールシーク実行

### ゴール (Goal)

ユーザー要望から `output/<hint>/intake.{md,json}` と Notion ページ URL が生成され、`workflow-manifest.json` の全 phase が success または正本に明記された条件付き skip、`quality_gate.py` / `cross_check.py` PASS、`eval-log/intake-trace.json` に全 attempt の `{id, attempt, delegateType, delegateName, started_at, finished_at, handoff_path, handoff_sha256, status, exit_code}` が記録され、完了レポートが日本語本文で提示された状態になっている。

### 目的・背景 (Why)

非エンジニアの曖昧要望から実装可能な intake 仕様まで橋渡しする intake plugin の中核 orchestrator。固定 Steps は入力 (topic) ・Gate A 否認・Phase 5 スキップ条件・lint 失敗・Notion 公開失敗など実行時文脈に脆い。固定手順を踏まず、未達 phase を `workflow-manifest.json` の `phases[]` 順で都度埋める反復構造で達成する。各 phase は独立 Skill / SubAgent に委譲し、本スキルは制御 (依存解決・handoff 検証・再開ポイント記録) のみを担う。

### 完了チェックリスト (Checklist)

- [ ] `Step 0` 前提検証 PASS (`validate-notion-ready.py --check-api` exit 0)。PASS 済みなら API キー / Notion トークンをユーザーに再質問しない。exit 44 のときだけ `references/keychain-setup.md` を案内し停止
- [ ] `output/<hint>/` と `eval-log/intake-trace.json` 初期化済み (hint は topic から仮決定)
- [ ] `workflow-manifest.json` の全 phase を manifest 順・dependsOn 充足後に処理し、delegate/schema/handoff digest を attempt ごとに `intake-trace.json` へ記録済み。実行 phase 一覧や依存辺は本文へ複製していない
- [ ] manifest の `skipWhen` / `skipReason` と `retryOn` / `retryTo` / `maxRetries` に一致する場合だけ SKIP/RETRY とし、それ以外を成功へ畳んでいない
- [ ] manifest で exitHook を持つ phase は hook PASS 証跡を path+SHA-256 で記録済み。final verifier 自身は RUNNING 記録→exit 0→PASS 記録の順で確定する
- [ ] `intake.json.notion_target` が存在し、update mode では `notion-publish-result.json.page_id` と一致している。未公開・不一致なら `run-skill-create` を次アクションとして推奨していない
- [ ] `quality_gate.py output/<hint>/intake.json` PASS
- [ ] `cross_check.py output/<hint>/intake.json output/<hint>/intake.md` PASS
- [ ] `eval-log/intake-trace.json` が `schemas/output.schema.json` 準拠で、全 attempt の delegate・時刻・handoff path/digest・exit code と条件付き skip/retry、exitHook 証跡を保持している
- [ ] 完了レポート提示済み (項目: hint / phases_succeeded / gate_a_result / skip_reasons / notion_url / next_action_mode、日本語本文・パラメーター名は英語)。`next_action_mode` は**推奨として**提示し、「次に `run-skill-create` を起動するとスキル生成に進めます (任意・別アクション)」と案内するに留める
- [ ] 完了レポート提示後に **`run-skill-create` / `run-build-skill` / `capability-build` 等のスキル生成を起動していない** (Key Rule 9 / Gotcha 8。intake はここで停止する)

### ゴールシークループ

`workflow-manifest.json` の `phases[]` を SSOT として、現状評価 → 次の未達 phase 特定 → 起動 → 検証 → 反復 / 差し戻しを回す。本スキル固有の差分は以下:

- **未達評価の単位は phase**: `intake-trace.json` の最新 disposition を読み、未完了 phase を次のターゲットにする。`dependsOn` は PASS または manifest の条件に一致する SKIP が前提。違反 (依存未満) なら依存元へ戻す。
- **委譲先**: `workflow-manifest.json` の `delegateType` / `delegateName` を唯一の起動契約とする。`delegateType=skill` は Skill tool、`delegateType=agent` は Task tool (SubAgent / context:fork) で起動する。本スキルは制御のみで業務ロジックを持たない。
- **context:fork 必須箇所**: Phase 2 / 3 / 5 / 8。主スレッド context を渡さず Task tool で fresh agent 起動 (バイアス回避・同意ループ防止)。
- **handoff 検証**: 各 phase 完了直後に `workflow-manifest.json` と各 delegate の `schemas/` 契約を確認する。fail / fatal exit は trace に記録して停止し、自動再試行しない。再開はユーザーが原因を解消した後の別実行とする。
- **intent 完了ゲート**: Phase 4 後、`interview.json.intent_contract.slot_status` に `filled=false` がある、または `pending_probes[]` が空でない場合は Phase 5 以降へ進まない。`pending_probes[]` の順に Phase 4 へ戻し、ユーザーへ固定 probe を 1 問ずつ聞く。
- **条件付き retry/skip**: 分岐条件・戻り先・上限・skip 理由は manifest の `retry*` / `skip*` が SSOT。attempt は trace へ追記し、上書きしない。
- **Phase 9 exitHook**: P8 success 後はまず `run-intake-finalize` で `intake.json` を生成する。その成功後にのみ2つの script resource を inline 起動し、計測と `qb-candidates.json` 導出→dry-run を行う。`--apply` は別ターンの明示承認後のみ。exitHook 失敗は P9 success にしない。
- **lint / quality_gate 自動修正禁止**: `quality_gate.py` / `cross_check.py` fail は根本原因をユーザー提示し AI 判断で勝手に直さない。
- **Notion target 保持**: `--page-url` / `--page-id` / `--database-id` は Phase 1 から `notion_target` として trace / intake.json に残し、Phase 10 へ同じ値を渡す。指定 page がある場合、create fallback は禁止する。
- **再開ポイント記録**: 各 phase 開始前 / 完了後に `eval-log/intake-trace.json` を append-only 更新。停止時は次回再開する phase id を末尾に明記。
- 各 phase の entryHook / exitHook / dependsOn / fatal_exit_codes / resourceIds は `workflow-manifest.json` を参照。プロンプトは `prompts/R1-main.md`。

### ゴールシーク配線（task-graph 変種）

`workflow-manifest.json` の `phases[]` を `eval-log/run-skill-intake-progress.json` の先頭 checklist へ `C<n>.text="[<phase-id>] <title>"`、`dependsOn`→`depends_on` として決定論射影する。別の task-graph 状態は作らず、progress.json を唯一の実行状態とする。Gate A の再試行は選択済み item を再消費せず、その item の実行中に manifest の retry 契約で処理し、attempt trace へ追記してから item を done にする。条件付き skip は phase disposition を trace に残したうえで対応 item を done (処理済み) とする。

- 各周回の冒頭で `scripts/extract-ready-set-from-checklist.py eval-log/run-skill-intake-progress.json` を実行し、返った ready 集合の最小 id だけを実行する。完了時は対象 item を `done` にしてから ready 集合を再計算し、依存順消費を拘束する。
- 実行中に必要な未網羅項目を発見した場合だけ、`scripts/build-self-reflection-entry.py` で新しい sink item を checklist 末尾へ追記する。未知の `depends_on` と cycle は exit 1 で拒否し、追記 item が done になるまで self-reflect 完了 gate を閉じる。
- 11 phase を 1 周回 1 item で消費できるよう `max_loops: 17` とし、self-reflect 追記分の余裕を保つ。17 周で未完了が残れば自動成功にせず `open_issues` へ差し戻す。
- 各周回の `eval-log/run-skill-intake-intermediate.jsonl` に `ready_set` と `selected_item` を追記する。完了検査はその申告値を信用せず、checklist の `depends_on` と過去の `selected_item` 列から各周回の ready 全集合を安定ソートで再計算する。申告 `ready_set` の欠落・余分・順序違反は exit 1、`selected_item` は再計算集合の最小 id と一致しなければならない。トレース不在は成功に畳まない。
- ドリフト圧縮用に `original_goal` を不変とし、次周回は `merged_directive_for_next` を必須入力にする。完了検査は `required_keys` と `original_goal_hash` を読み、`hashlib.sha256` で anchor 一致を検証する。
- final phase の delegate 完了後、`intake-trace.json` の当該 exitHook を RUNNING、trace/progress を in_progress として `scripts/validate-task-graph-progress.py eval-log/run-skill-intake-progress.json eval-log/run-skill-intake-intermediate.jsonl eval-log/intake-trace.json` を実行する。validator は manifest 全 phase の完全射影、dependsOn、skip/retry attempt、delegate、handoff/exitHook evidence digest、ready 消費、goal anchor を再計算する。pre-commit exit 0 後に exitHook=PASS・trace/progress=completed へ更新すると progress digest も変わるため、P11 evidence の progress SHA-256 を更新して同じ verifier を再実行する。2回目 exit 0 のときだけ完了レポートを出す。未生成・不一致は absence-as-violation で exit 1 とし、完了にしない。
- 着手前に `scripts/extract-capability-dependency-graph.py` で Skill / SubAgent / script の参照を確認し、未解決参照は停止する。実行時に再利用価値のある依存判断が増えた場合だけ `scripts/build-capability-graph-knowledge-entry.py` で dependency graph knowledge へ記録する。

## Gotchas

1. **業務ロジック混入禁止**: 質問雛形・採点基準・Notion blocks 生成を本 SKILL.md に書かない (SRP 違反 → lint 警告)。子 Skill / SubAgent / references に閉じる。
2. **固定 Steps の本文記述禁止**: 実行順は `workflow-manifest.json phases[]` から都度読む。SKILL.md に Step 1 / 2 / ... を列挙しない (manifest との二重管理になり drift 源)。
3. **SubAgent context 漏洩**: Phase 2 / 3 / 5 / 8 で Task tool を使わず Skill tool で呼ぶと主スレッド context が混入し Sycophancy/バイアスが発生する。
4. **Phase 4→5 skip 条件**: `needs_excavation=false` のときのみ skip 可。理由を `intake-trace.json` に書かない skip は禁止。
5. **Gate A 周回上限**: Phase 8 否認 → Phase 4 戻しは最大 2 周。3 周目は停止。
6. **Notion トークン**: 環境変数 / リポジトリへ置かず Keychain から都度取得 (`scripts/keychain_get_secret.py`)。
7. **manifest 二重管理禁止**: phases[] を本 SKILL.md にコピペしない。`lint-manifest-contents.py` を必ず通す。
8. **next-action を実行と誤読しない (最重要)**: Phase 11 の `next-action.json` / `harness_creator_handoff_phase` / 「harness-creator 引き渡し」という語は **推奨の記述**であって実行指示ではない。完了レポート提示後に `run-skill-create` 等を続けて起動してはならない。「では作成します」と続行せず、`mode` と推奨を提示して停止する (Key Rule 9)。スキル生成が必要ならユーザーが明示的に別途開始する。

## Additional Resources

- `workflow-manifest.json` — phases[] (id / dependsOn / delegateType / delegateName / fatal_exit_codes / resourceIds) の SSOT
- `prompts/R1-main.md` — orchestrator 責務プロンプト
- `schemas/output.schema.json` — `intake-trace.json` 形式
- `schemas/intake-request.schema.json` — pre-choice の推測補完なし user-input snapshot
- `references/workflow-sequence.md` — 11 phase の起動順序と前提 JSON 依存図 (人間向け)
- `references/handoff-contract.md` — 各 phase の handoff JSON schema 一覧
- `references/keychain-setup.md` — Notion トークンの Keychain 登録手順 (Step 0 exit 44 案内先、単独配布で自己完結するよう本 skill に同梱)
- `references/resource-map.yaml` — 他 reference を読む前の最小読込先マップ
- `../../scripts/measure_value_realized.py` — Phase 9 exitHook の post-finalize 計測実装 (書込みなし)
- `../../scripts/update_question_bank.py` — Phase 9 exitHook の `qb-candidates.json` 導出・重複排除・dry-run・承認後適用実装
- `scripts/validate-task-graph-progress.py` — Phase 11 exitHook の task-graph 消費・anchor 機械検査
- 子 Skill: `run-intake-kickoff` / `run-intake-interview` / `run-intake-option-catalog` / `run-intake-visualize` / `run-intake-next-action` / `run-intake-finalize` / `run-notion-intake-publish`
- SubAgent: `skill-intake-assumption-challenger` / `skill-intake-user-profiler` / `skill-intake-purpose-excavator` / `skill-intake-summarizer`
- **単一発火点 (公開 SSOT)**: Notion 公開は `intake_publish_pipeline.py` のみを発火点とし、SubAgent / sibling `run-notion-intake-publish` から二重に render/publish を直叩きしない。指定 page がある場合 `--page-id` / `--page-url` を最優先で渡し、page_id 解決不能時は exit 51 で停止する。All-or-Nothing: PNG 1 枚でも欠けたら `verify_notion_assets.py` で停止し途中公開しない。quality_gate / completeness FAIL は LLM 判断で勝手に直さずユーザーへ提示する (推測補完禁止)。
- 既存スキルとの関係: `run-skill-elicit` (技術者向け `skill-brief.json` を作る別入口) / `run-skill-create` (ユーザーが別途開始する後続。現行は intake.json の直接消費ではなく Step 1 から開始し、Notion 指定時だけ公開証跡を検査) / `assign-notion-fidelity-evaluator` (Phase 10 内部起動)。intake は recommendation-only で停止する (Key Rule 9)。
- Slash command の起動正本は本スキル (`run-skill-intake`)。`/intake-publish <hint>` (Notion 再公開) / `/intake-status <hint>` (進行確認) は別 skill が担う。
