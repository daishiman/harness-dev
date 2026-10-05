# goal-verdict: dev-graph:run-dev-graph-init (20261005T1300-p83r)

VERDICT: PASS

## 根拠

判定者が fixture `eval-log/dev-graph/live-trial-fixtures/p83r-init` に対して自分で叩いたコマンドは、read-only の C24 (`--mode read`)、C11、`build-init-scaffold.py --dry-run`、digest 採取だけである。実行前後で fixture 全ファイル・ディレクトリの sha256 と mtime の一覧 (38 行、`.git` は除く) を取って diff したところ差分はなかった (FIXTURE UNCHANGED)。fixture を別の場所へ複製しての検証はしていない。

1. **6 content root が揃う**: `issues/ tasks/ specs/ architecture/ features/ docs/` の 6 つとも、symlink ではない普通のディレクトリとして実在する。`resolve-repo-context.py --repo-root <fixture> --mode read` は exit 0 で、`repo_root == content_roots.repository` は True だった。repository_id は `local:sha256:74f4…0aff` で、config と receipt に入っている値と一致する。`system-spec/` は作られていないが、script の CONTENT_KEYS で C19 の担当と明記されているので対象外である。
2. **repo-local の config / state / templates が揃う**: `.dev-graph/{config.json, state/graph.json, cache/, locks/, templates/}` と `state/receipts/init-20261005T001758436429Z.json` が実在する。receipt の `created` に並ぶ 32 件はすべて実在し、欠けは 0 だった。plugin の `templates/` にある 21 ファイルを再帰的に突き合わせると、欠落 0、余分 0 で、内容が違うのは利用者編集をした `api-contract.md` の 1 件だけだった。`template-contract.json` が列挙する dev-graph 側の資産も欠落 0 である。列挙の中に `system-task-spec-template.md` があるが、これは `system_plan.task_overlay_canonical` が指す system-dev-planner 側の外部正本なので、scaffold の対象外とした。
3. **plugin hook source が揃う**: config の `claude_hooks.source` と receipt の `hook_source` はどちらも `"plugin"` である。plugin の `hooks/hooks.json` には SessionStart(startup|resume)、PostToolUse(Bash)、TaskCompleted、PreToolUse(Bash, C10) が `${CLAUDE_PLUGIN_ROOT}` 経由で入っていて、インストール済みの cache (0.1.14) の hooks.json とも同一だった。`~/.claude/settings.json` では `dev-graph@harness-local: true` (user scope) になっており、被験 session の transcript にも plugin の SessionStart hook (`reconcile-task-lifecycle.py`) が exit 0 で発火した記録がある。つまり実際に効いている hook は plugin の経路である。fixture に `.claude/` は無く、project fallback 側の登録が 0 件なので二重登録も起きていない。
4. **2 回目の planned change が 0**: transcript [61] で 2 回目の `build-init-scaffold.py` は exit 0、`status=noop`、`planned_changes=0`、`write_count=0` で、前後の file digest diff も「NO FILE CHANGES」だった。判定者が今回 `--dry-run` で再確認しても exit 0、`status=noop`、`planned_changes=0`、`created=[]`、`write_count=0` になった。receipts ディレクトリには初回の 1 件しか無く、2 回目は receipt も書いていない。
5. **利用者編集を上書きしない**: `api-contract.md` は plugin 版の全文が先頭にそのまま残り、末尾に `<!-- user edit p83r -->` が付いた状態で保たれている。sha256 は local が `fac12af8…`、plugin が `22f48f17…` で異なる。2 回目の実行と判定者の dry-run のどちらでも、この差分は `migration_preview` に記録されるだけで上書きはされていない。
6. **config に absolute path / token / node ID が無い**: config.json の全キーと全値を走査した。`/` `~` で始まる値、`/Users/`、`..`、ドライブレター、`gh*_` や `github_pat_` 系の token、`PVT_`、`PVTI_`、`PVTF_`、`PVTSSF_`、`I_kw` 系の node ID、`token`、`node_id`、`project_id`、`item_id`、`field_id` といったキーは、どれも 0 件だった。GitHub 設定は `enabled:false` で、残っているのは owner_login、project_number、field name のマッピングだけである。`path_policy.stored_paths` は `repository-relative` になっている。receipt にも `/Users/` は含まれていない。
7. **初期 graph が C11 を通る**: `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` は exit 0 で、`valid: true`、`graph_validation.status: pass`、`violation_count: 0` だった。graph の中身は `{"graph_revision":0,"nodes":[],"schema_version":"1.0.0"}` である。component-inventory で C11 が validate-graph-schema.py であることも確認した。

**被験の「non-zero exit」の自己解釈について**: 前提の事実が違う。2 回目の init 本体 (`build-init-scaffold.py`) は `run2 exit=0` で、non-zero ではない。Bash tool 呼び出しの最終 exit 1 は、同じコマンド列の末尾にあった `ls "$R/.claude"` が「No such file or directory」で失敗したためである。そのうえで「plugin hook source なら `.claude/` が無くて正常」という解釈は、契約に照らして正しい。根拠は次の 3 点である。

- `build-init-scaffold.py` は R5 の hook 配線を扱わず、`hook_source` を receipt に記録するだけである。
- SKILL.md の手順 4 と `references/claude-code-hooks-contract.md` によると、`.claude/settings.json` と `.claude/dev-graph-plugin` を使うのは project fallback のときだけである。
- 同じ hooks contract によると、`source=plugin` のときに求められるのは project 側 dev-graph hook の除去・rollback だけで、今回は除去する対象が存在しない。

## 経路制約

- **Skill 起動**: transcript [37] で `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root …/p83r-init --hook-source plugin"})` が task.md の指定どおりに 1 回起動され、[39] で SKILL.md が注入されている。
- **代行の有無**: skill の責務を自作 script で代行した形跡は無い。使われたのは plugin 同梱の `resolve-repo-context.py` (C24)、`build-init-scaffold.py` (SKILL.md が委譲先と明記している実装本体)、`validate-graph-schema.py` (C11) である。inline python はあるが、JSON の整形とテンプレートの digest 比較という検証用途に限られる。
- **2 回目の実行**: Skill を再起動したのではなく、同じ skill 起動の中で `build-init-scaffold.py` を同じ引数 (`--repo-root`、`--hook-source plugin`) でもう一度実行している。SKILL.md の手順 5「二回目実行の planned changes が 0 でなければ完了しない」と、手順 1-3・5 を script へ委譲するという契約の範囲内なので、代行とはみなさない。
- **直接書き込み**: Write tool が使われたのは `out/status.json` の 1 回だけで、graph / config / scaffold を Write や Edit で直接書いた形跡は無い。fixture への手書きは、利用者編集を模擬するために template へ 1 行を追記した `echo >> .dev-graph/templates/api-contract.md` だけである。これは task.md の検証項目のための操作で、graph / config には触れていない。
- **Agent (subagent)**: 起動は 0 回である。SKILL.md では subagent が `pre_choice_forbidden` に入っていて、Agent への fork は利用者が light / standard / detailed を選んで `semantic_evaluator_started` に移った後にしか要求されない。今回はそれ以外の選択肢 (light / standard / detailed) が選ばれていないので、Agent を起動しなかったのは正しい。
- **out/ の中身**: `status.json` だけで、ほかのファイルは無い。
- **非 blocker の観察**: SKILL.md の pre-choice 節には「現物の path・digest・開き方を提示し、accept-as-is / light / standard / detailed を記録する」とあるが、この提示と記録は明示的には行われていない。task.md の「質問せず自走」「`DONE:` を 1 行だけ報告」という制約と衝突する部分で、成果物そのものには影響しない。

## blocker

なし

gate_response_count: 0
