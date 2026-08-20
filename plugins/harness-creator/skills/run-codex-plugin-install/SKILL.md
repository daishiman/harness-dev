---
name: run-codex-plugin-install
description: Claude Code/Codexへlocal repositoryの全pluginをcwd非依存でuser installしたいとき、またはCodexへmerge済みGit refから単独installしたいときに、marketplace登録・install・receipt検証を行う。
disable-model-invocation: false
user-invocable: true
argument-hint: "<plugin-name> --source <local-root|owner/repo> [--ref <git-ref>]"
allowed-tools:
  - Read
  - Bash(python3 *)
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-08-20
version: 0.2.0
source: https://developers.openai.com/plugins/build/plugins
source-tier: external-spec
last-audited: 2026-08-20
audit-trigger: on-doc-change
feedback_contract:
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
runtime_root_policy: host-skill-path
---

# run-codex-plugin-install

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

ユーザーが install を明示依頼した場合だけ、Claude Codeのuser scopeまたはCodexの
user-global marketplace/cache/configを変更する。package生成とは別の副作用境界とし、
hook trustは自動承認しない。

## 入力

- `plugin-name`: marketplaceに掲載済みのplugin identity
- `source`: repository rootの絶対/相対path、またはGit source (`owner/repo` 等)
- `ref`: Git sourceだけで指定可能。PR merge後のbranch/tag/SHA

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
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/harness-creator}}/scripts/install-codex-plugin.py" \
  --source /absolute/path/to/repository \
  --plugin <plugin-name>
```

merge済みGit ref:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/harness-creator}}/scripts/install-codex-plugin.py" \
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
