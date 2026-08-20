---
name: run-codex-plugin-package
description: Claude Code 用に作った新規または既存 plugin を Codex からも install できるようにしたいとき、.codex-plugin/plugin.json と .agents/plugins/marketplace.json を同期・検査するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "<plugin-name> [--marketplace-name <name>] [--all]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Bash(git diff *)
  - Bash(git status *)
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-08-20
version: 0.1.0
source: https://developers.openai.com/plugins/build/plugins
source-tier: external-spec
last-audited: 2026-08-20
audit-trigger: on-doc-change
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 単一と全pluginのapply→checkが同じ入力で収束し、失敗時はmanifestとmarketplaceを部分書きしないこと
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 全Claude pluginが自己完結したCodex manifestと正確なmarketplace entryを持ち、localまたはmerge済みGit refからinstall可能なこと
      verify_by: test
runtime_root_policy: host-skill-path
---

# run-codex-plugin-package

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

Claude Code plugin の実体と明示的な Codex override を入力として、Codex が読む
plugin manifest と repository marketplace を決定論的に upsert する。新規作成と
既存改善は状態から自動判定し、同じ generator を使う。

## 入力と出力

- 入力: repo root 直下の `plugins/<plugin-name>/.claude-plugin/plugin.json`
- 任意入力: `plugins/<plugin-name>/.codex-plugin-overrides.json`
- 出力: `plugins/<plugin-name>/.codex-plugin/plugin.json`
- 出力: `.agents/plugins/marketplace.json` の対応 entry
- 非対象: user global config、plugin trust、plugin install 状態、`.claude/` projection

## 実行手順

1. repo root と `plugins/<plugin-name>` が実在し、Claude manifest の
   `name` が directory 名と一致することを確認する。
2. `references/package-contract.json` に `codex_distribution` がある場合、
   `distributable=true` と source/marketplace の一致を確認する。
3. 先に check を実行する。installed plugin root は `PLUGIN_ROOT`、
   Claude Code 互換環境は `CLAUDE_PLUGIN_ROOT` から解決する。

   ```bash
   python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/sync-plugin-platforms.py" \
       --repo-root . \
       --plugin "plugins/<plugin-name>" \
       --check
   ```

4. drift を確認後、同じ引数で `--apply` し、再度 `--check` を実行する。
   新規 marketplace 名を固定する場合だけ `--marketplace-name <name>` を追加する。
   省略時は既存 marketplace 名を保存し、無ければ repo directory 名から作る。
5. 次を確認する。

   - 両 manifest の `name` / `version` / `description` / `author` が一致
   - Codex 固有 interface/component は `.codex-plugin-overrides.json` だけが入力
   - Codex manifest の `skills` / `hooks` / `mcpServers` / `apps` が実在資産と一致
   - marketplace entry が official fields だけを持つ
   - plugin 配下に plugin root 外を指す symlink が無い

6. 複数pluginを量産した後は、Claude manifestを持つ全pluginを一括生成・検査する。

   ```bash
   python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/sync-plugin-platforms.py" \
     --repo-root . --all --apply
   python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/sync-plugin-platforms.py" \
     --repo-root . --all --check
   ```

   一括処理は削除済みpluginのrepo-local marketplace entryも除去する。
   各pluginは単独cacheで動くよう、plugin root外を指すsymlinkを残さない。

## install 境界

package生成は user-global 状態を変更しない。ユーザーが install を明示依頼した場合だけ
`run-codex-plugin-install` に委譲する。local/Git sourceの登録、Git snapshot更新、
install、`codex plugin list --json` によるreceipt確認を一操作で行う。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/install-codex-plugin.py" \
  --source /absolute/path/to/repository --plugin <plugin-name>
```

GitHub では marketplace 定義が merge された ref を指定する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/install-codex-plugin.py" \
  --source owner/repo --ref main --plugin <plugin-name>
```

hook trust はinstallerも代行しない。current command/eventを `/hooks` またはPlugins画面で
確認してユーザーがtrustし、新規threadで確認する。

## 失敗時

- Claude manifest が無い、name 不一致、plugin が `plugins/` 外なら書き込まず停止。
- `--check` は常に無書込。
- install / enable / hook trust は package generator が代行しない。
- Codex で公式対応されない Claude 固有 surface を推測配置しない。
