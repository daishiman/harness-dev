# goal-verdict: dev-graph:run-dev-graph-init (20261005T1500-p83m)

VERDICT: PASS

## 根拠

評価者が fixture `eval-log/dev-graph/live-trial-fixtures/p83m-init` に対して、その場で read-only の確認を行った。確認の前後で `.git` 以外の全 path と全 file の sha256 を採取して比べ、差分 0 (`FIXTURE_UNCHANGED`) だったので、評価で fixture は書き換えていない。`out/status.json` の自己申告 (PASS) は判定に使っていない。

1. **6 content root が揃っている**
   - `issues/ tasks/ specs/ architecture/ features/ docs/` の 6 つが、どれも symlink ではない普通のディレクトリとして存在する。realpath はすべて fixture root の配下にある。fixture 内の symlink は 0 件。
   - config の `content_roots` も同じ 6 つを repository 相対で持っている。`system_spec: system-spec` も入っているが、`build-init-scaffold.py` の `CONTENT_KEYS` で C19 が作る領域と定められており、init が作らなくても仕様どおり。

2. **repo-local の config/state/templates が揃っている**
   - `.dev-graph/{config.json, state/graph.json, cache/, locks/, templates/}` と `.dev-graph/state/receipts/init-20261005T013738346781Z.json` が存在する。
   - template について: plugin `templates/` の 21 ファイルと `.dev-graph/templates/` の 21 ファイルを突き合わせた。欠けも余分も 0。sha256 が違うのは、利用者編集を模した `task.md` 1 件だけだった。
   - `template-contract.json` が参照する template (`template`、`conditional_templates`、architecture の 5 subtype、`task_overlay`、`legacy_phase_template`) は、すべてローカルにある。存在しない参照は `task_overlay_canonical` 1 件だけで、これは system-dev-planner の正本 (`plugin-plans/system-dev-planner/references/system-task-spec-template.md`) を指す外部ポインタ。scaffold の対象ではなく、参照先の実在も確認した。

3. **plugin hook source が揃っている**
   - config は `claude_hooks.source = "plugin"`、receipt は `hook_source = "plugin"`。
   - fixture に `.claude/` は無い。project fallback の settings への書き込みは 0 で、二重登録の可能性も無い。
   - plugin の `hooks/hooks.json` は `PreToolUse / SessionStart / PostToolUse / TaskCompleted` の 4 event を持つ。`~/.claude/settings.json` で `dev-graph@harness-local` が有効になっている。
   - 被験 session の transcript (行 4) では、plugin の C25 `reconcile-task-lifecycle.py` が SessionStart で exit 0 で実行されている。effective な hook は plugin 経路の 1 本だけ。

4. **2 回目の planned change が 0**
   - transcript 行 64/70 で、被験 session は同じ引数 (`--repo-root <fixture> --hook-source plugin`) で 2 回目を実行している。結果は `status=noop`、`planned_changes=0`、`write_count=0`、`created=[]`、`idempotent=true`。実行前後の全 file sha256 の diff も空 (`NO_FILE_CHANGES`) だった。
   - 評価者も `build-init-scaffold.py --repo-root <fixture> --hook-source plugin --dry-run` を実行し、exit 0、`status=noop`、`planned_changes=0`、`write_count=0` を得た (preserved は 32)。
   - receipt は 1 件だけで、2 回目の実行で新しい receipt は作られていない。

5. **利用者編集を上書きしない**
   - 被験 session は 1 回目のあと、`.dev-graph/templates/task.md` の末尾に `<!-- user edit p83m -->` を追記してから 2 回目を実行した。
   - 現在の `task.md` は、sha256 `24ee23bc…5b7493ed53ec0118a513061ed19aba9aa4fb6de61a15e9b5871` で末尾に同じマーカーが残っている。2 回目の `migration_preview` に記録された `local_sha256` と一致し、plugin 側 (`5dc37581…`) とは異なる。つまり上書きされておらず、差分は migration_preview に残っている。

6. **config に absolute path / token / node ID が保存されていない**
   - config の全 key と全 string 値を走査した。`/` や `~` で始まる値、`/Users/` を含む値、`ghp_`/`gho_`/`github_pat_`/`PVT_`/`PVTI_`/`PVTF_` などの token・node ID の形、`token|secret|node_id|item_id|field_id|project_id` を含む key は、どれも 0 件。receipt も同じく絶対 path は 0 件。
   - `path_policy.stored_paths = "repository-relative"`、`allow_outside_repository = false`。
   - `github.enabled = false`。保存されているのは owner_login `example`、project_number `1`、field 名 `Status`/`Priority` だけ。
   - `validate-graph-schema.py` の `schema_findings` で config を `schemas/repo-config.schema.json` と照合し、findings は 0 件。

7. **初期 graph が C11 を通る**
   - `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を実行。結果は exit 0、`valid=true`、`graph_validation.status=pass`、`violation_count=0`、`violations=[]`。
   - graph の中身は `{"graph_revision":0,"nodes":[],"schema_version":"1.0.0"}`。

8. **C24 の整合**
   - `resolve-repo-context.py --mode read --repo-root <fixture>` が exit 0 で次を返した。
     - `repo_root` は fixture
     - `content_roots.repository` は repo_root と一致
     - `git_common_dir` は `<fixture>/.git`
     - root_trust_evidence はすべて true
   - origin remote は無い。`realpath(<fixture>/.git)` の SHA-256 から求め直した `local:sha256:0cd9ebbb…09392` は、config・receipt・C24 出力の `repository_id` と一致した。

## 経路制約

- **Skill 起動**: transcript 行 36 で `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root <fixture> --hook-source plugin"})` が実際に呼ばれ、行 37 で `Launching skill`、行 38 で SKILL.md 本文の読み込みを確認した。
- **代行の有無**: 自作 script による代行は無い。scaffold は、SKILL.md の Execution contract が実装本体と定める plugin の `build-init-scaffold.py` で行われている (dry-run、apply、2 回目の noop)。C24 `resolve-repo-context.py --mode write` と C11 `validate-graph-schema.py` も plugin の script をそのまま使っている。
- **直接書き込み**: 使われたツールは Bash 8 回、Skill 1 回、Write 1 回。Write の 1 回は `out/status.json` だけで、Edit は 0 回。graph・config・receipt・templates を Write/Edit や heredoc で直接書いた箇所は無い。fixture への手書きは、検証のために `task.md` へ利用者編集を模して printf で追記した 1 件だけ。
- **subagent**: Agent 起動は 0 回で、sidechain の行も 0。SKILL.md は pre-choice では subagent を禁じていて、Agent fork は light/standard/detailed を選んだあと (`semantic_evaluator_started`) に限られる。今回は人に質問しない制約のもとで accept-as-is 相当で完了しているので、必要な subagent は無い。
- **非 blocker の観察**:
  - task.md の「同じ引数でもう一度実行」について、Skill tool を 2 回呼んだのではなく、1 回の Skill 実行の中で実装本体 script を同じ引数で再実行していた。これは SKILL.md 手順 5 の「二回目実行の planned changes が 0 でなければ完了しない」に沿った実行で、結果も評価者の dry-run で再現できた。
  - SKILL.md の artifact-delivery にある「現物 path・digest を提示し、利用者の選択を記録する」は、明示的には行われていない (task.md が人への質問を禁じているため)。

## blocker

なし

gate_response_count: 0
