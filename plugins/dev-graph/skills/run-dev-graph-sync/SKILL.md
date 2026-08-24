---
name: run-dev-graph-sync
description: tracker_binding に従い dev-graph と Beads を同期したいとき、GitHub Issues/Projects/PR lifecycle を冪等収束したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C03
kind: run
effect: external-mutation
runtime_root_policy: host-skill-path
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "[--repo-root PATH] [--dry-run] [--adapter-fixture PATH] [--resolve-conflicts PATH]"
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion, Skill]
script_refs: [../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/gh-bridge.py, ../../scripts/bd-bridge.py, ../../scripts/reconcile-github-lifecycle.py, ../../scripts/manage-worktree-lease.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/repo-config.schema.json]
reference_refs: [../../references/execution-tracker-contract.md, ../../references/github-lifecycle-contract.md]
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-sync.md
  - prompts/R4-tombstone.md
  - prompts/R5-dryrun.md
  - prompts/R6-confirm.md
  - prompts/R7-lifecycle.md
  - prompts/R8-scheduled.md
responsibilities:
  - id: R1-elicit
    name: elicit
    prompt_required: true
    summary: "repo-local configのissue repository、複数Projects target alias/owner/project number、default/auto-add policy、field name/type/option mappingを読み、GitHub node IDは実行時解決する"
  - id: R2-plan
    name: plan
    prompt_required: true
    summary: "Issueはid+updated_at、Projects custom fieldsはfield value updatedAtを競合hint、last-synced snapshotを削除/renameを含むcanonical baseとする3-way diffで同期計画を作る。Statusはlocal_to_project固定でremote変更を完了authorityにしない"
  - id: R3-sync
    name: sync
    prompt_required: true
    summary: "tracker_binding=githubだけをC12経由でIssue/Projects更新し、tracker_binding=beadsはC28でstatus・depends_on edge exact-setを突合する。Beads GitHub mirrorはbd github sync --push-onlyだけを使いC12 mutationを禁止する"
  - id: R4-tombstone
    name: tombstone
    prompt_required: true
    summary: "GitHub Issue の close/delete を検知し、C02 経由でローカルグラフノードを物理削除せず tombstone/status 遷移 (open→closed 等) として双方向伝播する"
  - id: R5-dryrun
    name: dryrun
    prompt_required: true
    summary: "--dry-run時はIssue作成/更新/close、Project item-add/item-editを一切実行せず、project alias・field別の反映予定差分だけを提示する"
  - id: R6-confirm
    name: confirm
    prompt_required: true
    summary: "id+updated_at 同時競合で立てた手動確認フラグを次回同期の入力として読み取り、利用者の確認結果を反映した上で当該ノードのフラグを解消する"
  - id: R7-lifecycle
    name: lifecycle
    prompt_required: true
    summary: "C26でlinked PRのmerged/default-branch/closing-reference evidenceとC27 pending worktree eventをreconcileし、cleanなdefault branch worktreeだけでtask status/completion_evidence/execution_contextsをatomic更新する"
  - id: R8-scheduled
    name: scheduled
    prompt_required: true
    summary: "configのinterval/owner/entry_pointとlast-reconciled時刻を読み、owner=claude_session_startならC25 SessionStart、owner=host_schedulerなら明示host invocationから同じC26 entry pointを冪等起動する"
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行を正本とする。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "validate-graph-schema.py と gh-bridge.py で同期ペイロードを送信前検証し取込/反映の必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "同一状態を二回同期し 2 回目のGitHubからの取込/ローカルからの反映が 0 件になることを受入テストが確認する"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "id+updated_at が同時競合するケースを注入した際、規定のタイブレーク規則 (更新が新しい方を採用・同時刻はGitHub優先+ローカル手動確認フラグ) どおりに競合解決されることを受入テストが確認する"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "GitHub Issue が close/delete された場合、次回同期でローカルノードが物理削除されず tombstone/status 遷移 (open→closed 等) として双方向伝播されることを受入テストが確認する"
      verify_by: test
    - id: OUT4
      loop_scope: outer
      text: "--dry-run 指定時に GitHub 側への書込みが 0 件のまま反映予定差分のみがプレビューされることを受入テストが確認する (暴発防止)"
      verify_by: test
    - id: OUT5
      loop_scope: outer
      text: "手動確認フラグが立ったノードについて、確認結果を反映した後の再同期でフラグが解消されることを受入テストが確認する"
      verify_by: test
    - id: OUT6
      loop_scope: outer
      text: "同一Issue contentを同一Projectへ二回同期してもProject itemが重複せずitem_idが安定し、複数Project targetにはaliasごとに1 itemだけがlinkされる"
      verify_by: test
    - id: OUT7
      loop_scope: outer
      text: "Projects fieldのlocal/remote双方変更を3-way fixtureで検出して自動上書き0件・manual conflict 1件となり、片側変更だけはmappingどおり同期されsnapshotが更新される"
      verify_by: test
    - id: OUT8
      loop_scope: outer
      text: "permission/rate-limit/field削除/option rename/pagination/途中失敗fixtureでローカルtask promotionを維持し、未完了Project writeだけpending_retryとして再実行できる"
      verify_by: test
    - id: OUT9
      loop_scope: outer
      text: "PR closed未mergeではdone 0件、default branchへmergedかつpolicy充足時だけdoneとなり、feature worktreeではpending event、clean default worktreeでのみdurable task spec/graphが更新される"
      verify_by: test
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

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物またはremote mutation previewをmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方またはpreview receiptを提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはmutationを実行せずhandoff完了とし、後続sectionを実行しない。

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


# run-dev-graph-sync

## Purpose & Output Contract

- 入力: C24/C11 検証済み local graph/config、last-synced snapshot、binding 別 remote state、任意の dry-run/confirmation。
- 出力: 3-way imports/exports/conflicts/tombstones/pending-retry plan、binding 別 linkage、更新済み snapshot receipt。
- 完了条件: binding ごとの mutation authority が一意で、同一状態の2回目 changes=0、done は default-branch merge evidence 満足時にだけ反映される。

local graph が正本。`tracker_binding=beads` は C28 の status/depends_on exact-set parity と push-only viewer mirror、`github` は C12 の Issue/Projects、`none` は external write なし。authority の混在は拒否する。

## Protocol

1. schema と repo config を検証し、IssueはC12 `issue-fetch`、Project/field identityは`project-resolve`、itemは`project-item-find`、field現在値は`project-item-fields`で読み、last-synced snapshot を base に 3-way plan を作る。
2. beads は `bd-bridge.py` だけを使う。GitHub mutation を併用しない。github は `gh-bridge.py --dry-run` preview 後だけ apply する。
3. Issue は id+updated_at、Project field は field value updatedAt を conflict hint とする。双方変更は自動上書きせず manual conflict。同時刻は GitHub を表示値に採用し local confirmation flag を残す。Status は local→Project 一方向で、remote Status を done authority にしない。
4. close/delete は node 物理削除でなく tombstone/status transition。部分的な Project failure は local promotion を戻さず alias 単位 `pending_retry`。
5. C26 で default-branch merge evidence と C27 pending event を reconcile する。closed-unmerged、dirty/feature worktree、policy/evidence 不足は done にしない。

同一 state の二回目は changes=0。両passで各read opを再実行し、Project/Item/content IDと`project-item-fields.result.snapshot_sha256`が安定し、pass 1後snapshotがpass 2の3-way baseと一致することを測定する。`--dry-run` は外部 write 0。report は imports/exports/conflicts/tombstones/pending_retry/project snapshots を返す。

### Canonical Project field read

Project fieldの現在値はC12の次のread-only opだけから取得する。各fieldの`field_id/field_name/value/value_type/updated_at`、Project/Item/content ID、canonical `snapshot_sha256`を同じshapeで返す。

```bash
python3 "$PLUGIN_ROOT/scripts/gh-bridge.py" --op project-item-fields --repo "$ISSUE_REPOSITORY" --project-id "$PROJECT_ID" --item-id "$ITEM_ID"
```

offline trialで`--adapter-fixture` が指定された場合だけ同opにそのabsolute pathを渡す。C12は`network=disabled`と`repo`一致を検証し、GraphQLを呼ばず同じshapeを返す。Skill/プロンプト/一時driverからfixture JSONを直接loadしない。`--adapter-fixture`はmutation opでは拒否され、mutationは引き続きofficial receipt flowだけを通す。

Project field writeはrepo configの`value_type`と同じ`single_select|text|number|date|iteration`を`project-item-edit --value-type`へ渡し、それぞれ`--option-id|--value|--iteration-id`の1種類だけを使う。値削除は`--clear`で明示する。dry-runでtyped argvを検証した後、同一argvをcanonical external mutation receipt flowの`command-json`に入れ、bridgeを直接applyしない。

## ゴールシーク実行

### ゴール (Goal)

tracker_binding別のauthorityに従いローカルtask graphとBeadsまたはGitHub Issues/PRを同期し、Projects Statusはローカルから一方向投影、merged evidenceとworktree eventはdefault branch側task仕様へ収束した状態になっている

### 目的・背景 (Why)

二重管理を防ぐため、task nodeをローカル正本、Beads/GitHubをbinding別の実行projectionとする。tracker_binding=beadsではC28経由でstatusだけでなくdepends_on edge集合もparity突合し、GitHub mirrorはbd github sync --push-onlyのviewer専用とする。tracker_binding=githubではC12がIssue/Projectsを管理するが、Projects Statusの逆流でPR merge authorityを迂回させない

### 完了チェックリスト

- [ ] 全 Issue/Project 差分が3-way planの一分類と snapshot digest を持つ
- [ ] task ごとの mutation authority が beads/C28、github/C12、none の一経路だけである
- [ ] `--dry-run` の local/Beads/GitHub/Projects write count が0である
- [ ] 双方変更は manual conflict、片側変更は mapping どおりの反映 receipt を持つ
- [ ] close/delete は graph_node_id を保持した tombstone/status transition になる
- [ ] default-branch merge evidence を満たす場合だけ done となり、dirty/feature worktree event は pending に残る
- [ ] 同一状態の二回目 sync の imports/exports/Project item add が0件で、Project/Item ID・3-way base・field snapshot digestが一回目と一致する

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: inline` / `max_loops: 5` を実行契約とする。固定手順は使わず、main context で未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。各周回で inner criterion を検証し、完了後は outer criterion の live trial/content review を最大 `feedback_contract.max_iterations=3` 周で評価する。

### ゴールシーク配線

- 開始時に C24 `resolve-repo-context.py --mode write` の JSON receipt を得て、`repo_root` が `content_roots.repository` の realpath と一致する場合だけ `DEV_GRAPH_ROOT=<receipt.repo_root>` に固定する。cwd から再解決しない。
- `--adapter-fixture` を受けた場合はabsolute pathに解決し、C12 `project-item-fields --adapter-fixture` のみへ渡す。その他のreadはC12、mutationはofficial receipt flowを使い、fixture JSONをSkill自身で読まない。
- 元のゴールを `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-sync-goal-spec.json` へ、各 checklist の status/evidence を `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-sync-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、main context でその周回の処理を実行する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-sync-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 5周到達時に未達が残れば完了扱いせず、progress と blocker を親へ handoff する。全 checklist と `feedback_contract.criteria` が PASS のときだけ完了する。

### ゴールシーク検証

各周回後に次の検査を実行し、中間成果物の欠落・goal drift・hash 不一致を fail-closed にする。

```bash
python3 - "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-sync-goal-spec.json" "$DEV_GRAPH_ROOT/eval-log/run-dev-graph-sync-intermediate.jsonl" <<'PY'
import hashlib, json, sys
goal = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [json.loads(line) for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
required_keys = {'original_goal','original_goal_hash','current_goal_snapshot','delta_from_original','merged_directive_for_next','drift_signal'}
expected = hashlib.sha256(goal['original_goal'].encode('utf-8')).hexdigest()
assert rows, 'intermediate.jsonl is empty'
for row in rows:
    assert required_keys <= row.keys(), required_keys - row.keys()
    assert row['original_goal'] == goal['original_goal']
    assert row['original_goal_hash'] == expected
PY
```

## Criteria acceptance

- `criteria:IN1`: `validate-graph-schema.py` と `gh-bridge.py` の送信前検証で必須キー欠落が0件である。
- `criteria:OUT1`: 同一状態をC12 read receipt経由で二回同期し、2回目のimports/exportsは`changes=0`、Project/Item ID・3-way base・field snapshot digestは一回目と一致する。
- `criteria:OUT2`: Issue `updated_at`競合は新しい方を採用し、同時刻はGitHub優先と手動確認フラグを残す。
- `criteria:OUT3`: close/deleteは物理削除せず`tombstone/status`遷移として反映する。
- `criteria:OUT4`: `--dry-run`ではGitHub/Beadsを含む外部write 0件である。
- `criteria:OUT5`: 手動確認フラグは確認結果を適用した再同期で解消する。
- `criteria:OUT6`: Project itemは重複0件でitem IDが安定し、aliasごとに1 itemだけを保持する。
- `criteria:OUT7`: Project fieldの双方変更は3-way snapshotでmanual conflict、片側変更だけを同期してsnapshotを更新する。
- `criteria:OUT8`: permission、rate-limit、field削除、option rename、pagination、途中失敗でもlocal task promotionを維持し、未完了操作だけを`pending_retry`へ残す。
- `criteria:OUT9`: PR closed未mergeはdoneにせず、default branch mergeだけを採用し、feature worktreeではpending eventへ送る。durable task spec/graph更新はclean default worktreeだけで行う。

## Gotchas

- `beads/github/none` の mutation authority を同一 node で混ぜない。Beads の GitHub mirror は push-only viewer に限定する。
- Project Status の remote 変更を local done authority として逆流させない。
- Project fieldをGraphQLやfixture JSONから直読みせず、C12 `project-item-fields`のnormalized receiptを3-way remote inputの正本とする。
- close/delete を物理削除に変換せず、`tombstone/status` transition として保存する。
- `--dry-run` では local/Beads/GitHub/Projects write をすべて0にする。
- 部分的な remote 失敗で local promotion を戻さず、未完了 operation だけを `pending_retry` に残す。
