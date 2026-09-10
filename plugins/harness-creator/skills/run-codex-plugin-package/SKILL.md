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
  activation_state: semantic_evaluator_started
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
responsibility_refs:
  - prompts/R1-package.md
manifest: workflow-manifest.json
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  spec: eval-log/goal-spec.json
  progress: eval-log/run-codex-plugin-package-progress.json
  intermediate: eval-log/run-codex-plugin-package-intermediate.jsonl
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

Purpose & Output Contractの最小の実成果物をmain contextで作成する。parse/open・secret・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-codex-plugin-package

## Runtime root contract

`runtime_root_policy: host-skill-path` の製品別root解決、cwd推測禁止、prompt継承は
[ref-cross-platform-runtime の共有正本](../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約)
をそのまま適用する。生成対象repository rootはplugin runtime rootと混同せず `--repo-root` で明示する。

## Purpose & Output Contract

Claude plugin実体、明示override、package contract、compositionを入力に、Codex manifestとrepository marketplace entryを不可分にupsertする。成功出力は実在surfaceとの双方向一致、plugin境界、再check、capability parityを証明する検証証拠を含む。user-global install/enable/hook trustは変更せず、検証済みpackageを `run-codex-plugin-install` へ引き渡す。

Claude Code plugin の実体と明示的な Codex override を入力として、Codex が読む
plugin manifest と repository marketplace を決定論的に upsert する。新規作成と
既存改善は状態から自動判定し、同じ generator を使う。

## ゴールシーク実行

### ゴール (Goal)

指定されたplugin scopeのCodex manifestとrepository marketplace entryが実在資産・package contract・compositionと一致し、単独配布境界と再checkがexit 0で証明されている。

### 目的・背景 (Why)

生成物の存在だけでは、実在surfaceの漏れ・plugin境界外依存・marketplace driftを見逃す。書込み前差分と書込み後検証を分け、installとは異なるlocal-artifact境界で収束させる。

### 完了チェックリスト (Checklist)

- [ ] Claude/Codex manifestの `name/version/description/author` が一致する
- [ ] Codexの `skills/hooks/mcpServers/apps` が実在資産と双方向一致する
- [ ] marketplace entryがofficial fieldsだけを持ち、sourceが対象pluginを指す
- [ ] package entry points・composition公開surface・実体が双方向一致する
- [ ] plugin root外を指すsymlinkが0件である
- [ ] 生成後の `sync-plugin-platforms.py --check` とcapability parity auditがexit 0である
- [ ] user-global install/enable/hook trust状態が変更されていない

### ゴールシークループ

`workflow-manifest.json` の依存とR1 promptを読み、未充足のチェックを1つ選ぶ。preflight・drift check・apply・verifyから、現状に必要な最小操作を都度立案・実行して再評価する。全項目充足まで反復し、3周で未達なら追加書込みを行わず `open_issues` に残して停止する。

### ゴールシーク配線

反復はfrontmatter `goal_seek.fork=subagent` で親contextから分離する。周回状態は `eval-log/run-codex-plugin-package-progress.json`、アンカーは `eval-log/run-codex-plugin-package-intermediate.jsonl` に追記し、`original_goal` を不変として次周の `merged_directive_for_next` に必ず合流させる。

### ゴールシーク検証

アンカーの機械検査は [goal-seek正本](../run-build-skill/references/goal-seek-paradigm.md#中間成果物ドリフト圧縮アンカー) を適用する。各行の `required_keys`、progressの `original_goal_hash`、`hashlib.sha256` による不変アンカー照合が通らなければ完了にしない。

## 検証

- 対象scopeで `sync-plugin-platforms.py --check` を再実行する
- `audit-capability-parity.py --plugin <name>` で実体・entry points・composition・semantic routeを照合する
- `git diff --check` と `git status --short` で部分書き・指定外変更がないことを確認する

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
3. 先に check を実行する。`PLUGIN_ROOT` はRuntime root contractに従って、このSkillの
   absolute `SKILL.md` pathから解決済みのabsolute plugin rootを使う。

   ```bash
   python3 "$PLUGIN_ROOT/scripts/sync-plugin-platforms.py" \
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
   python3 "$PLUGIN_ROOT/scripts/sync-plugin-platforms.py" \
     --repo-root . --all --apply
   python3 "$PLUGIN_ROOT/scripts/sync-plugin-platforms.py" \
     --repo-root . --all --check
   ```

   一括処理は削除済みpluginのrepo-local marketplace entryも除去する。
   各pluginは単独cacheで動くよう、plugin root外を指すsymlinkを残さない。

## install 境界

package生成は user-global 状態を変更しない。ユーザーが install を明示依頼した場合だけ
`run-codex-plugin-install` に委譲する。local/Git sourceの登録、Git snapshot更新、
install、`codex plugin list --json` によるreceipt確認を一操作で行う。

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source /absolute/path/to/repository --plugin <plugin-name>
```

GitHub では marketplace 定義が merge された ref を指定する。

```bash
python3 "$PLUGIN_ROOT/scripts/install-codex-plugin.py" \
  --source owner/repo --ref main --plugin <plugin-name>
```

hook trust はinstallerも代行しない。current command/eventを `/hooks` またはPlugins画面で
確認してユーザーがtrustし、新規threadで確認する。

## 失敗時

- Claude manifest が無い、name 不一致、plugin が `plugins/` 外なら書き込まず停止。
- `--check` は常に無書込。
- install / enable / hook trust は package generator が代行しない。
- Codex で公式対応されない Claude 固有 surface を推測配置しない。
