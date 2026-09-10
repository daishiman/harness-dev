---
name: run-codex-plugin-install
description: Claude Code/Codexへlocal repositoryの全pluginをcwd非依存でuser installしたいとき、またはCodexへmerge済みGit refから単独installしたいときに、marketplace登録・install・receipt検証へ使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "<plugin-name> --source <local-root|owner/repo> [--ref <git-ref>]"
allowed-tools:
  - Read
  - Bash(python3 *)
  - Agent
kind: run
prefix: run
effect: external-mutation
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: team-platform
since: 2026-08-20
version: 0.2.0
source: https://developers.openai.com/plugins/build/plugins
source-tier: external-spec
last-audited: 2026-08-20
audit-trigger: on-doc-change
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: localとGit sourceのmarketplace登録・install・receipt検証が、失敗時に誤った成功を返さないこと
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 明示的に指定されたpluginだけがCodexでinstalledかつenabledと確認され、hook trustはユーザー判断のまま保持されること
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: 実セッションで親contextと分離したSubAgentがpreview・ユーザー確認・authorize・executeの順序を保ち、指定pluginのinstall結果だけをhandoffで返すこと
      verify_by: live-trial
responsibility_refs:
  - prompts/R1-install.md
manifest: workflow-manifest.json
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  spec: eval-log/goal-spec.json
  progress: eval-log/run-codex-plugin-install-progress.json
  intermediate: eval-log/run-codex-plugin-install-intermediate.jsonl
  max_loops: 3
  fork: subagent
runtime_root_policy: host-skill-path
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


# run-codex-plugin-install

## Runtime root contract

`runtime_root_policy: host-skill-path` の製品別root解決、cwd推測禁止、prompt継承は
[ref-cross-platform-runtime の共有正本](../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約)
をそのまま適用する。installerに渡すrepository rootはplugin runtime rootと混同せず明示入力にする。

## Purpose & Output Contract

明示されたlocal/Git sourceとplugin scopeを入力に、marketplace登録・install・CLI実測を一連で実行し、検証済みreceiptを出力する。成功出力は `status=installed`、`verified=true`、installed/enabledの実測、runtime identity、`hook_trust=user-review-required` を含む。user-global install状態を変更する副作用はユーザーがinstallを依頼した場合に限り、hook trustは変更しない。

ユーザーが install を明示依頼した場合だけ、Claude Codeのuser scopeまたはCodexの
user-global marketplace/cache/configを変更する。package生成とは別の副作用境界とし、
hook trustは自動承認しない。

## 入力

- `plugin-name`: marketplaceに掲載済みのplugin identity
- `source`: repository rootの絶対/相対path、またはGit source (`owner/repo` 等)
- `ref`: Git sourceだけで指定可能。PR merge後のbranch/tag/SHA

## ゴールシーク実行

### ゴール (Goal)

ユーザーが明示したplugin scopeだけが指定sourceからinstalledと検証され、runtime identityとhook trust境界を含むreceiptが後続へ渡せる状態になっている。

### 目的・背景 (Why)

CLIのexit 0だけではinstall実体、enabled状態、version/source/runtimeの一致は証明できない。操作と実測を分け、ユーザー指定scopeとtrust決定権を保ったまま収束させる。

### 完了チェックリスト (Checklist)

- [ ] local/Gitのsource種別、plugin名、refが明示入力と一致する
- [ ] receiptに `status/plugin_id/verified/enabled/runtime_path` が存在する
- [ ] `status=installed` かつ `verified=true` をCLI listのinstalled/enabled実測が支持する
- [ ] plugin名・version・source・runtime identityが一致する
- [ ] runtime pathがabsoluteかつ実在し、repository外cwdの `--check` がexit 0になる
- [ ] hook trustが `user-review-required` として残り、自動承認されていない

### ゴールシークループ

`workflow-manifest.json` の依存とR1 promptを読み、未充足のチェックを1つ選ぶ。preflight・install・receipt検証の候補から現状に必要な最小操作を都度立案・実行し、検証結果でチェックを更新する。全項目充足まで反復し、3周で未達なら残項目を `open_issues` に記録して成功扱いせず停止する。

### ゴールシーク配線

反復はfrontmatter `goal_seek.fork=subagent` で親contextから分離する。周回状態は `eval-log/run-codex-plugin-install-progress.json`、アンカーは `eval-log/run-codex-plugin-install-intermediate.jsonl` に追記し、`original_goal` を不変として次周の `merged_directive_for_next` に必ず合流させる。

### ゴールシーク検証

アンカーの機械検査は [goal-seek正本](../run-build-skill/references/goal-seek-paradigm.md#中間成果物ドリフト圧縮アンカー) を適用する。各行の `required_keys`、progressの `original_goal_hash`、`hashlib.sha256` による不変アンカー照合が通らなければ完了にしない。

## 検証

- local全件routeは `install-local-plugins.py --all --check` をrepository外cwdから実行する
- 単一local/Git routeはreceiptの `status=installed` / `verified=true` / identityと `codex plugin list --json` の実測を照合する
- 非0・非JSON・同名多重activation・依存cache version不一致はPASSに変換しない

## Claude Code / Codexへlocal全件install

絶対script pathを使えば、harness外のどのcwdからでも実行できる。helperはClaude側では
`<repo>/marketplaces/local`、Codex側では`<repo>`を別々の絶対marketplace rootとして登録する。

```bash
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all
```

別cwdからread-only verification:

```bash
cd /tmp
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all --check
```

1件だけなら`--plugin <name>`、片方だけなら`--platform claude|codex`を付ける。

## Codex単独のlocal / Git実行

local repository:

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source /absolute/path/to/repository \
  --plugin <plugin-name>
```

merge済みGit ref:

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source owner/repo \
  --ref main \
  --plugin <plugin-name>
```

helperはmarketplace名をCLI receiptから取得し、Git sourceが既登録ならsnapshotをupgrade、
pluginをinstallし、`codex plugin list --json`でinstalled/enabledを再確認する。

## 完了条件

- report `status=installed`
- `plugin_id=<plugin>@<marketplace>` が installed
- enabled状態をreportに記録
- local全件installでは両catalogのplugin集合一致、全cache pathの絶対path・実在を確認
- repository外cwdで`--check`が`status=verified`
- hook trustは `user-review-required` のまま保持
- current hook command/eventをユーザーが確認してtrust後、新規threadでskillを確認

## 失敗時

- local marketplaceに対象entryがなければglobal状態を変更する前に停止
- local sourceへ`--ref`を指定したら停止
- marketplace add/install/listのいずれかが非0または非JSONならexit 3
- hook trustを代行しない
