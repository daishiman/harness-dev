---
name: run-codex-plugin-install
description: Claude Code/Codexへlocal repositoryの全pluginをcwd非依存でuser installしたいとき、またはCodexへmerge済みGit refから単独installしたいときに、marketplace登録・install・receipt検証へ使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "--source <local-root> (--all|--plugin <name>) [--platform claude|codex] | <plugin-name> --source <local-root|owner/repo> [--ref <git-ref>]"
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
      text: 明示的に指定されたpluginとその依存closure (dependency_closure) だけがCodexでinstalledかつenabledと確認され、hook trustはユーザー判断のまま保持されること
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: 実セッションで親contextと分離したSubAgentがpreview・ユーザー確認・authorize・executeの順序を保ち、承認した対象plugin集合 (指定pluginとそのdependency_closure) のinstall結果だけをhandoffで返すこと
      verify_by: live-trial
responsibility_refs:
  - prompts/R1-install.md
manifest: workflow-manifest.json
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  max_loops: 3
  fork: subagent
runtime_root_policy: host-skill-path
artifact_delivery: artifact-delivery-v1
---

# run-codex-plugin-install

## Runtime root contract

`runtime_root_policy: host-skill-path` の製品別root解決、cwd推測禁止、prompt継承は
[ref-cross-platform-runtime の共有正本](../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約)
をそのまま適用する。installerに渡すrepository rootはplugin runtime rootと混同せず明示入力にする。

## Purpose & Output Contract

明示されたlocal/Git sourceとplugin scopeを入力に、marketplace登録・install・CLI実測を一連で実行し、検証済みreceiptを出力する。成功出力は `status=installed`、`verified=true`、installed/enabledの実測、runtime identity、`hook_trust=user-review-required` を含む。user-global install状態を変更する副作用はユーザーがinstallを依頼した場合に限り、hook trustは変更しない。

installの範囲 (対象plugin集合) は、指定したpluginと、その依存closure (`dependency_closure`) である。closureは各pluginの `references/package-contract.json` の `depends_on` を同じmarketplace/sourceの中でたどって求め、どちらのhelperもこの集合を依存の順 (`install_order`) で入れる。`--all` ではcatalogの全pluginが対象になる。

ユーザーが install を明示依頼した場合だけ、Claude Codeのuser scopeまたはCodexの
user-global marketplace/cache/configを変更する。package生成とは別の副作用境界とし、
hook trustは自動承認しない。

**禁則**: installの明示依頼が無いままuser-global状態を変更すること、previewで承認した対象plugin集合 (指定pluginとその`dependency_closure`) の外のpluginをinstall/disableすること、hook trustを自動承認すること、未検証のinstallを成功として返すことは禁止する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物またはremote mutation previewをmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方またはpreview receiptを提示してからaccept-as-is/diagnoseを記録する。accept-as-isはmutationを実行せずhandoff完了とし、後続sectionを実行しない。

本skillのaccept-as-isが返すのはinstall前のpreview (対象plugin集合として指定pluginと`dependency_closure`の全名・source/ref・変更されるuser-global marketplace/cache/config) だけで、user-global状態は変えず「preview only・未install」としてhandoffする。local sourceのclosureはcatalogと`package-contract.json`を読むだけでinstall前に求める。Git sourceのclosureはmarketplace登録の後にしか決まらないので、previewには指定pluginと「closure未確定 (marketplace登録の後に2段めのpreviewで確定)」を書く。diagnoseを記録した場合だけ下の`## ゴールシーク実行`のinstall workflowへ進み、実際のinstallは下のcanonical receipt flowを通る。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionおよびexternal mutation safety wrapperはdiagnoseが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。actual mutationはcanonical preview→hook-confirm→authorize→execute wrapperだけを通し、release/exhaustiveは別の明示eventを必要とする。

下のflowの `<TARGET_SCOPE>` には対象plugin集合の全名・source/ref・platformを、`<SIDE_EFFECT_SUMMARY>` にはmarketplace登録と各pluginのinstallで変わるuser-global marketplace/cache/configを書き、承認する範囲を実際の副作用と同じにする。Git sourceはrefをcommit SHAに固定し、このflowを2段で通す。1段めはmarketplace登録だけでpluginを入れず、登録したsnapshotからclosureを求める。2段めでは、対象plugin集合を名前ごとの `--approved-plugin` としてargvに入れたhelperを承認する。単一local routeでも同じ引数を渡す。helperは `plugin add` の前に、Git sourceならsnapshotの実際のcommitが固定したSHAと同じこと、どちらのsourceでも入れる集合が承認した集合と同じことを確かめ、違えば1件も入れずに止まる。実行の後はreceiptの `resolved_revision` (Git source) と `install_order` が承認した値と同じことを確かめ直す。手順は [install routeごとの詳細](references/install-routes.md#installの範囲-対象plugin集合) にある。

<!-- external-mutation-guard-cli:v1 -->
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

Resolve the guard plugin root once, before `preview`. An installed plugin cannot reach a sibling
plugin as `<plugin root>/..`, so never guess that path:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py" skill-governance-adapters
```

Use the printed absolute path as `<GUARD_PLUGIN_ROOT>` in `preview`, `authorize` and `execute`
(other Bash is blocked while the confirmation is pending, so do not resolve it again).
If the resolver exits non-zero, stop without any external mutation and tell the user to install
the `skill-governance-adapters` plugin.

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
<!-- /external-mutation-guard-cli:v1 -->

## 入力

routeは引数で決まる。`--all` か `--plugin` があればlocal全件route、位置引数の`plugin-name`があれば単一local/Git routeとする。

local全件route (`install-local-plugins.py`):

- `source`: harness repository rootの絶対path。`--repo-root <source>` として渡す
- 対象の選択: `--all` か `--plugin <name>` (複数指定可) のどちらか1つを必ず指定する
- `--platform claude|codex`: 片方だけに入れるときに指定する。省略時は両方
- このrouteは`plugin-name`も`ref`も求めない

単一local/Git route (`install-codex-plugin.py`):

- `plugin-name`: marketplaceに掲載済みのplugin identity
- `source`: repository rootの絶対/相対path、またはGit source (`owner/repo` 等)
- `ref`: Git sourceだけで指定可能。PR merge後のbranch/tag/SHA。最初のmutationの前にcommit SHAへ固定する

## ゴールシーク実行

### ゴール (Goal)

ユーザーが明示したpluginとその`dependency_closure` (previewで承認した対象plugin集合) だけが指定sourceからinstalledと検証され、runtime identityとhook trust境界を含むreceiptが後続へ渡せる状態になっている。

### 目的・背景 (Why)

CLIのexit 0だけではinstall実体、enabled状態、version/source/runtimeの一致は証明できない。操作と実測を分け、ユーザー指定scopeとtrust決定権を保ったまま収束させる。

### 完了チェックリスト (Checklist)

- [ ] local/Gitのsource種別とplugin名が明示入力と一致し、Git sourceはreceiptの `resolved_revision` (snapshotの実際のcommit。引数を写した `ref` ではない) が固定したcommit SHAと同じで、receiptの `install_order` がpreviewで承認した対象plugin集合と同じである
- [ ] receiptに `status/plugin_id/verified/enabled/runtime_path` が存在する
- [ ] `status=installed` かつ `verified=true` をCLI listのinstalled/enabled実測が支持する
- [ ] 同名多重activationが無い: receiptの各plugin (単一local/Git routeは`artifacts[]`、local全件routeは`plugins[]`) の`activation_collisions`に、`enabled=true`の候補が2つ以上無い。helperは同じhook digestのときしか`verified`を落とさないので、hookが違っても無くてもここで止める
- [ ] Git sourceは`revision_evidence.rechecked_after_plugin_add=true`で、`revision_evidence.git_head`があれば`git_dirty=false`である (`git_dirty=null`はgitが未commitの変更の有無を答えられなかった状態で、helperは止まらないので成功にしない)
- [ ] plugin名・version・source・runtime identityが一致する
- [ ] runtime pathがabsoluteかつ実在し、選択routeの検証が通る。local全件routeはinstallと同じ選択引数に `--repo-root <source> --check` を付けてrepository外cwdで実行しexit 0・`status=verified`、単一local/Git routeは `codex plugin list --json` が対象pluginのinstalled/enabledを示す
- [ ] hook trustが `user-review-required` として残り、自動承認されていない

### ゴールシークループ

`workflow-manifest.json` の依存とR1 promptを読み、未充足のチェックを1つ選ぶ。preflight・(Git sourceだけ) marketplace登録・install・receipt検証の候補から現状に必要な最小操作を都度立案・実行し、検証結果でチェックを更新する。全項目充足まで反復し、3周で未達なら残項目を `open_issues` に記録して成功扱いせず停止する。

### ゴールシーク配線

反復はfrontmatter `goal_seek.fork=subagent` で親contextから分離する。goal-specは `eval-log/run-codex-plugin-install-goal-spec.json` とし、iteration=0で「ゴール (Goal)」の文に今回のroute・source・ref・plugin scopeを埋めた文を `original_goal` として、完了チェックリストと一緒に書く。共有の `eval-log/goal-spec.json` はほかのskillのゴールが入りうるので読まない。周回状態は `eval-log/run-codex-plugin-install-progress.json` (`original_goal_hash` に `original_goal` のSHA-256を固定)、アンカーは `eval-log/run-codex-plugin-install-intermediate.jsonl` に追記し、`original_goal` を不変として次周の `merged_directive_for_next` に必ず合流させる。

### ゴールシーク検証

アンカーの機械検査は [goal-seek正本](../run-build-skill/references/goal-seek-paradigm.md#中間成果物ドリフト圧縮アンカー) を適用する。各行の `required_keys`、progressの `original_goal_hash`、`hashlib.sha256` による不変アンカー照合が通らなければ完了にしない。

## 検証

- local全件routeは、installと同じ選択引数 (`--all` か `--plugin`、`--platform`) に `--repo-root <source> --check` を付けた `install-local-plugins.py` をrepository外cwdから実行し、exit 0かつ `status=verified` を確認する
- 単一local/Git routeはreceiptの `status=installed` / `verified=true` / identityと `codex plugin list --json` の実測を照合する (このrouteのhelperに `--check` は無い)
- 非0・非JSON・同名多重activation (各pluginの`activation_collisions`に`enabled=true`の候補が2つ以上。helperが`verified=true`を返していても)・依存cache version不一致はPASSに変換しない
- routeごとのstatus・exit code・receipt fieldは [install routeごとの詳細](references/install-routes.md) を正とする

## Claude Code / Codexへlocal全件install

`--repo-root` に入力の`source` (harness repository rootの絶対path) を渡せば、どのcwdからでも実行できる。
登録するmarketplace rootと依存closureの扱いは [install routeごとの詳細](references/install-routes.md) にある。

```bash
python3 "$PLUGIN_ROOT/scripts/install-local-plugins.py" --all --repo-root /absolute/path/to/harness
```

別cwdからread-only verification (installと同じ選択引数に`--check`を足す):

```bash
cd /tmp
python3 "$PLUGIN_ROOT/scripts/install-local-plugins.py" --all --check --repo-root /absolute/path/to/harness
```

1件だけなら`--all`の代わりに`--plugin <name>`、片方だけなら`--platform claude|codex`を付ける。

## Codex単独のlocal / Git実行

local repository:

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source /absolute/path/to/repository \
  --plugin <plugin-name> \
  --approved-plugin <承認した名前> [--approved-plugin <承認した名前> ...]
```

merge済みGit ref (2段めのhelper。refはcommit SHAに固定した値):

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source owner/repo \
  --ref <commit-sha> \
  --plugin <plugin-name> \
  --approved-plugin <承認した名前> [--approved-plugin <承認した名前> ...]
```

`--approved-plugin` には、previewで承認した対象plugin集合 (指定pluginと`dependency_closure`) の全名を1つずつ渡す。このhelperに`--check`は無い。marketplace名の取り方、Git snapshotのupgrade、Git sourceの2段の承認、receipt fieldは
[install routeごとの詳細](references/install-routes.md) にある。

## 完了条件

- report `status=installed`
- `plugin_id=<plugin>@<marketplace>` が installed
- enabled状態をreportに記録
- local全件installでは両catalogのplugin集合一致、全cache pathの絶対path・実在を確認
- local全件routeでは、installと同じ選択引数に`--repo-root <source> --check`を付けてrepository外cwdで実行し`status=verified`
- 単一local/Git routeでは`--check`を使わず、`codex plugin list --json`が対象pluginのinstalled/enabledを示す
- 各pluginの`activation_collisions`に`enabled=true`の候補が2つ以上無い。Git sourceは`resolved_revision`が固定したSHAと同じ
- hook trustは `user-review-required` のまま保持
- current hook command/eventをユーザーが確認してtrust後、新規threadでskillを確認

## 失敗時

- local marketplaceに対象entryがなければglobal状態を変更する前に停止
- local sourceへ`--ref`を指定したら停止
- Git sourceのrefをcommit SHAに固定できない、または同じsourceが別のrefで登録済みなら、mutationの前に停止してユーザーに確かめる
- Git sourceで1段めのmarketplace登録の後、2段めのhelperの前に止まった (snapshotのrevisionが固定したSHAでない・closureが求まらない・ユーザーが2段めを承認しない) ら、pluginは1件も入っていないが登録は残る。そのこととsnapshotのrevisionを伝え、登録を残すかはユーザーが決める
- helperがexit 3を返したら、receiptの`added_plugins` (`plugin add`のJSONを読めたplugin id) と`failed_plugin`を見る。どちらも空なら、helperは`plugin add`を1件も出していない (「snapshotが固定したcommitに無い」「gitが答えられたcheckoutに未commitの変更がある」「入れる集合が承認した集合と違う」はどれも`plugin add`の前に止まる)。`added_plugins`のpluginは入ったまま残る。`failed_plugin`のpluginが入ったかはhelperには分からないので、`codex plugin list --json`で確かめてから、名前と`phase`・`error`をユーザーに伝える。Git sourceで2段めのhelperがupgradeを出していれば、snapshotが別のcommitへ動いたまま残ることがある。receiptにupgradeの印は無いので、`resolved_revision` (読めていれば) と固定したSHAの差を伝え、登録を残すかはユーザーが決める
- 同名多重activationがあれば成功にせず、同名のpluginの`plugin_id`・`marketplace`・`enabled`の一覧をユーザーに伝える。どれを無効にするかはユーザーが決める
- Git sourceで`revision_evidence.git_head`があるのに`git_dirty`が`null`なら、未commitの変更を確かめられていないので成功にせず、そのことを伝える。`git_head`も`null` (snapshot rootがcheckoutでない、またはgitを使えない) なら、commitはinstall metadataの`revision`だけで確かめ、未commitの変更は確かめていないことを報告に書く
- receiptの`install_order`か`resolved_revision`が承認した値と違えば成功にせず、承認していないpluginの名前をユーザーに伝える (uninstallはユーザーが決める)
- marketplace add/install/listのいずれかが非0または非JSONならexit 3
- hook trustを代行しない

## Gotchas

1. **`--repo-root`を省略しない**: `install-local-plugins.py`の既定rootはscriptの位置から導く (`Path(__file__).resolve().parents[3]`)。install済みpluginのcache (`<cache>/<marketplace>/<plugin>/<version>/scripts/`) から起動すると `<cache>/<marketplace>` を指し、`cannot read marketplace JSON` でexit 3になる。相対pathはcwd基準で解決され、`--check`はrepository外cwdで回すので、絶対pathを渡す。
2. **`--check`はlocal全件routeにしか無い**: `install-codex-plugin.py`の引数は`--source`/`--ref`/`--plugin`/`--approved-plugin`/`--codex-home`だけである。単一local/Git routeはreceiptと`codex plugin list --json`の照合で検証する。
3. **対象の選択は省略できない**: `install-local-plugins.py`は`--all`か`--plugin`のどちらか1つを要し、無指定でも併用でもexit 3になる。`--help`の「`--all`が既定」という説明は実装と違う。
4. **exit 1は成功ではない**: `pending_user_gate`はCLI実測が成功条件に届いていない。`stale_runtime`はversionが同じままsourceが変わりcacheに古いcopyが残った状態で、`scripts/build-plugin-release.py`でversionを上げてから入れ直す。
5. **installだけではhookは信頼されない**: receiptの`next_action`どおり、current hookのcommand/eventをユーザーが確かめてtrustした後、新しいClaude Code session / Codex threadで確かめる。
