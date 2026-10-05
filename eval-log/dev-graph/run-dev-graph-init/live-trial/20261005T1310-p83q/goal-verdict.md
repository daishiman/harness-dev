# goal-verdict: dev-graph:run-dev-graph-init (20261005T1310-p83q)

VERDICT: PASS

## 根拠

判定者が fixture `eval-log/dev-graph/live-trial-fixtures/p83q-init` に対して自分で実行したのは、read-only の C24 (`resolve-repo-context.py --mode read`)、C11 (`validate-graph-schema.py`)、`build-init-scaffold.py --dry-run`、digest 採取だけである。判定の前後で fixture の全パス一覧と全ファイルの sha256 (63 行、`.git` は除く) を採って diff したが、差分は無かった (FIXTURE_UNCHANGED_BY_JUDGE)。fixture を別の場所へ複製しての検証もしていない。`out/status.json` の自己申告 (`PASS`) は判定材料にしていない。

1. **6 content root が揃う**: `issues/ tasks/ specs/ architecture/ features/ docs/` の 6 つとも、symlink ではない普通のディレクトリとして実在する。fixture 内に symlink は 0 件だった。`resolve-repo-context.py --repo-root <fixture> --mode read` は exit 0 で、`repo_root == content_roots.repository` も、fixture との realpath 一致もどちらも True だった。`git_common_dir` は `<fixture>/.git` である。`repository_id` は `local:sha256:749f62b9…9483` で、config・receipt・C24 の 3 か所で一致した。`system-spec/` は作られていないが、`build-init-scaffold.py` の `CONTENT_KEYS` に「system_spec は C19 が作るので init は作らない」とあるので、6 root の対象外である。
2. **repo-local の config / state / templates が揃う**: `.dev-graph/{config.json, state/graph.json, cache/, locks/, templates/}` と `state/receipts/init-20261005T005453443494Z.json` が実在する。receipt の `created` 32 件はすべて実在し、欠落は 0 だった。plugin の `templates/` (21 ファイル) と `.dev-graph/templates/` (21 ファイル) はファイル集合が一致し、sha256 も 20 件が同一だった。違うのは利用者編集を模擬した `task.md` の 1 件だけである。`template-contract.json` が列挙する dev-graph 側の template (common-frontmatter、5 kind、architecture subtype 5 種、api-contract、task-graph-node、system-task-spec、system-phase-spec の計 16 件) も欠落 0 だった。被験 session が「未解決」と出した `plugin-plans/system-dev-planner/references/system-task-spec-template.md` は、`system_plan.task_overlay_status: pointer_to_canonical` が指す system-dev-planner 側の外部正本である。scaffold の対象ではなく、harness repo 側にも実在する。
3. **plugin hook source が揃い、project fallback script は起動されず、`.claude/settings.json` にも触れていない**:
   - config の `claude_hooks.source` と receipt の `hook_source` は、どちらも `"plugin"` である。
   - transcript で `build-project-hook-fallback.py` という文字列が出るのは、[38] で注入された SKILL.md 本文の 1 か所だけだった。Bash の tool_use 9 件のどれも、この script を起動していない。tool_use の内訳は Bash 9、Skill 1、Write 1 で、Agent・Edit は 0 である。
   - fixture の `.claude/` は存在しない。transcript [43] の初期状態 (`ls -la` の結果は `.git` と `README.md` だけ) でも無く、現在も無い。fixture の HEAD commit `9a379bb init` が追跡しているのも `README.md` だけである。`.claude/settings.json` は init によって作られても変えられてもいない。
   - `state/receipts/` には init receipt 1 件だけがあり、`hook-fallback-*.json` の rollback manifest は無い。
   - plugin の `hooks/hooks.json` には PreToolUse(Bash)、SessionStart(startup|resume)、PostToolUse(Bash)、TaskCompleted が `${CLAUDE_PLUGIN_ROOT}` 経由で入っている。`~/.claude/settings.json` も `dev-graph@harness-local: true` である。被験 transcript [4] には、plugin の SessionStart hook (`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/reconcile-task-lifecycle.py" --event session-start …`) が exit 0 で発火した記録がある。実際に効いている hook は plugin 経路の 1 つだけで、二重登録は 0 件である。
   - 以上は、SKILL.md 手順 4 の「plugin hook を既定とする」と、`prompts/R5-hooks.md` Layer 3 の「plugin hook 既定 (`hook_source=plugin`) では script を起動せず、settings に触れない」という契約に一致する。
4. **2 回目の planned change が 0**: transcript [65]/[71] によると、2 回目の `build-init-scaffold.py --repo-root <fixture> --hook-source plugin` は exit 0、`status=noop`、`planned_changes=0`、`write_count=0`、`created=[]` だった。`receipt_path` は初回と同じで、実行前後の全ファイル sha256 の diff は `NO_FILE_CHANGES` だった。判定者が同じ引数に `--dry-run` を付けて再確認しても、exit 0、`status=noop`、`idempotent=true`、`planned_changes=0`、`write_count=0`、`created=[]` になった。receipts ディレクトリは初回の 1 件のままである。初回は [61] で `status=applied`、`planned_changes=33` (32 件と receipt)、`schema_result.violation_count=0` だった。
5. **利用者編集を上書きしない**: `.dev-graph/templates/task.md` は、plugin 版の全文に `<!-- user edit p83q -->` が 1 行だけ追記された状態で残っている (`diff` は `78a79` の追加 1 行だけ)。local の sha256 は `c70c49ed…f248`、plugin 版は `5dc37581…7300` である。この local digest は、被験の 2 回目実行の `migration_preview` に記録された値とも、判定者の dry-run が出した値とも一致する。つまり、編集は上書きされず、差分の所在が `migration_preview` に残るだけになっている。
6. **config に absolute path / token / node ID が無い**: config.json の全キーと全値を再帰的に走査した。`/`・`~`・ドライブレターで始まる値、`/Users/` を含む値、`gh*_`・`github_pat_` 系の token、`PVT_`・`PVTI_`・`PVTF_`・`PVTSSF_`・`I_kw` 系の node ID、`token`・`secret`・`node_id`・`project_id`・`item_id`・`field_id` を含むキー名は、いずれも 0 件だった。GitHub 設定は `enabled:false` で、保存されているのは `owner_login`・`project_number`・field name のマッピングだけである。`path_policy.stored_paths` は `repository-relative` になっている。repo-config.schema.json による検査結果 (`schema_findings`) も 0 件だった。receipt にも `/Users/` は含まれていない。
7. **初期 graph が C11 を通る**: `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` は exit 0 で、結果は `valid: true`、`graph_validation.status: pass`、`violation_count: 0`、`violations: []` だった。graph の中身は `{"graph_revision":0,"nodes":[],"schema_version":"1.0.0"}` である。

## 経路制約

- **Skill 起動**: transcript [36] で、task.md の指定どおり `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root …/p83q-init --hook-source plugin"})` が 1 回起動されている。[37] で `Launching skill`、[38] で SKILL.md の本文が注入されたことを確認した。
- **代行の有無**: skill の責務を自作 script で代行した形跡は無い。使われたのは plugin 同梱の `resolve-repo-context.py` (C24)、`build-init-scaffold.py` (SKILL.md が手順 1-3・5 の委譲先と明記している実装本体)、`validate-graph-schema.py` (C11) の 3 つである。inline python も使われているが、JSON の要約表示と template-contract の参照走査という検証用途に限られる。
- **2 回目の実行**: Skill tool を呼び直したのではない。同じ skill 起動の中で、`build-init-scaffold.py` を同じ引数 (`--repo-root` に同じ path、`--hook-source plugin`) でもう一度実行している。SKILL.md 手順 5 の「二回目実行の planned changes が 0 でなければ完了しない」と、手順 1-3・5 を script へ委譲するという契約の範囲内なので、代行とはみなさない。
- **hook fallback**: `build-project-hook-fallback.py` は一度も起動されていない。`--hook-source plugin` のときの契約どおりである (根拠 3)。
- **直接書き込み**: Write tool が使われたのは `out/status.json` への 1 回だけである。graph / config / scaffold / `.claude/settings.json` を Write や Edit で直接書いた形跡は無い。fixture への手書きは、利用者編集を模擬するために Bash で `.dev-graph/templates/task.md` へ 1 行追記した `echo >>` だけである。これは task.md の検証項目「利用者編集を上書きしない」を確かめるための操作で、graph / config には触れていない。
- **Agent (subagent)**: 起動は 0 回で、sidechain の行も 0 である。SKILL.md では subagent が `pre_choice_forbidden` に入っており、Agent への fork が求められるのは、light / standard / detailed が選ばれて `semantic_evaluator_started` に移った後だけである。今回はどれも選ばれていないので、Agent を起動しなかったのは契約どおりである。
- **out/ の中身**: `status.json` だけで、ほかのファイルは無い。
- **非 blocker の観察**: SKILL.md の pre-choice 節は「現物の path・digest・開き方を提示し、accept-as-is / light / standard / detailed を記録する」と定めているが、この提示と選択の記録は明示的には行われていない。task.md の「途中で人間に質問せず自走」「`DONE: <status>` を 1 行だけ報告」という制約とぶつかる部分で、成果物そのものには影響しない。

## blocker

なし

gate_response_count: 0
