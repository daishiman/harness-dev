# goal-verdict: dev-graph:run-dev-graph-init (20261005T0758-p83)

VERDICT: PASS

## 根拠

判定者は fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83-init` を複製せず、その場で read-only の操作だけをした。`.git` を除く全ファイルの path と sha256 を検証の前後で採り、`diff` が空 (FIXTURE_UNCHANGED) であることを確かめた。`out/status.json` (PASS の自己申告) は根拠に使っていない。

1. **6 content root が揃っているか**: `issues/ tasks/ specs/ architecture/ features/ docs/` の 6 つが、symlink でない通常の directory として実在する。`build-init-scaffold.py --dry-run` が返す `content_roots` も同じ 6 key で、値は repo 相対 path だった。
   - `system-spec/` は作られていない。config には `content_roots.system_spec: "system-spec"` と書かれているが、`build-init-scaffold.py` 34 行目の注記「system_spec は system-spec-harness (C19) が作るので init は作らない」のとおりで、設計上の挙動である。SKILL.md の出力契約 (6 root) とも食い違わない。
2. **repo-local の config/state/templates が揃っているか**: `.dev-graph/config.json`、`.dev-graph/state/graph.json`、`.dev-graph/cache/`、`.dev-graph/locks/`、`.dev-graph/templates/`、`.dev-graph/state/receipts/init-20261004T225915828346Z.json` の実在を確かめた。
   - templates: plugin の `templates/` にある 21 ファイルと `.dev-graph/templates/` の 21 ファイルは名前の集合が一致した。digest が違うのは `issue.md` だけである。
   - `template-contract.json` が列挙する asset のうち、ローカルに置くべきものに欠落はない。外部の正本 `plugin-plans/system-dev-planner/references/system-task-spec-template.md` は配置対象ではない (README の規則 6)。
   - receipt には repository_id、repo 相対の roots、created (32 件)、preserved、migration_preview、hook_source=plugin、schema_result (valid、violation 0) が入っている。
3. **plugin hook source**: `config.claude_hooks.source = "plugin"` で、schema の enum `plugin|project|disabled` に収まる。receipt の `hook_source` も `"plugin"` である。
   - fixture に `.claude/` は無い。project fallback での settings merge は行われておらず、hook が二重に登録される経路も無い。
   - plugin 側の `plugins/dev-graph/hooks/hooks.json` には、C10 (PreToolUse) と C25 (SessionStart、PostToolUse、TaskCompleted) が登録されている。
4. **2 回目の planned change が 0 か**:
   - 判定者自身が `python3 build-init-scaffold.py --repo-root <fixture> --hook-source plugin --dry-run` を実行した。結果は exit 0、`status=noop`、`planned_changes=0`、`write_count=0`、`created=[]`、`idempotent=true` で、`receipt_path` は既存のものだった。
   - transcript の 2 回目の実行 (tool_use toolu_01PxxBJrsRSD2F5zs5NT5WQe) でも `noop 0 0` が出ており、前後の sha256 比較は `NO_DIFF` だった。
   - receipt は 1 件だけで、noop のときに receipt を追加で作らない仕様と合っている。
5. **利用者の編集を上書きしていないか**:
   - transcript では、1 回目の実行 (07:59:15) のあとに Bash で `issue.md` へ `<!-- user edit p83 -->` を追記し、そのあと 2 回目を実行している。2 回目は `migration_preview` に `issue.md` の local_sha256=006df57a… と plugin_sha256=00a3a972… を記録していた。
   - fixture 上の `issue.md` は今も sha256 `006df57a714aab0f41c9a68b0929f5e2948f6c3875a90d6ee8dbaee3668fa269` で、中身は「plugin 版 + 追記した 1 行」と完全に一致した。mtime は 07:59:21 で、編集した時点のまま。
   - 判定者の dry-run でも同じ migration_preview が出て、`preserved` は 32 件だった。
6. **config に absolute path、token、node ID が入っていないか**:
   - config を JSON として全走査し、次のものが無いことを確かめた。
     - `/`、`~`、`/Users/`、`..` で始まる、または含む値
     - token、node_id、secret を含む key
     - `ghp_`、`github_pat_`、`PVT_`、`PVTI_`、`PVTF_` の値
   - 走査で 1 件だけ引っかかった `create_follow_up_unless_issue_reopened` は、長い文字列を拾う正規表現の誤検出である。中身は enum 値にすぎない。
   - `grep -E '/Users/|ghp_|github_pat|PVT'` を config と state に当てても該当しなかった。
   - `github.enabled=false` で、残っているのは owner_login、project_number、field name だけである。`path_policy.stored_paths="repository-relative"`。
   - repository_id `local:sha256:6797…` は、`.git` の realpath の SHA-256 から再計算した値と一致した。
7. **初期 graph が C11 を通るか**: C11 は `validate-graph-schema.py` である (component-inventory で確認)。`python3 validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` は exit 0、`valid=true`、`graph_validation.status=pass`、`violation_count=0` だった。graph の中身は `{"graph_revision":0,"nodes":[],"schema_version":"1.0.0"}`。
   - あわせて C24 `resolve-repo-context.py --mode read --repo-root <fixture>` も exit 0 だった。repo_root は fixture と一致し、repository_id も config と一致、`claude_project_dir_verified` と `git_common_dir_ownership_verified` はともに true である。

## 経路制約

- **Skill の起動**: `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root <fixture> --hook-source plugin"})` が 1 回、実際に起動されている (transcript [36]、結果は "Launching skill")。
- **SKILL.md の手順をなぞったか**: 起動後は SKILL.md の Execution contract どおりに進めている。
  1. `resolve-repo-context.py --mode write` (root 一致を確認)
  2. `build-init-scaffold.py --dry-run` (preview、planned 33)
  3. `build-init-scaffold.py` (applied、33)
  4. 同じ引数での `build-init-scaffold.py` の再実行 (noop、0)
  5. `validate-graph-schema.py` と `resolve-repo-context.py --mode read`
- **自作 script による代行**: 無い。init の実体には plugin 同梱の `build-init-scaffold.py` だけを使っている。SKILL.md もこの script への委譲を正規の経路としている。
- **graph や config への直接書き込み**: 無い。Write tool は `out/status.json` に 1 回使っただけで、config、graph、receipt、templates はすべて script が作っている。Bash で触ったのは、利用者編集を模した `issue.md` への 1 行追記だけで、これは検証のための仕込みである。
- **Agent の起動**: 0 回で、SKILL.md と矛盾しない。SKILL.md は選択前の段階 (pre-choice) で subagent を禁じており (`pre_choice_forbidden`)、goal-seek の fork は light/standard/detailed が選ばれたあとにしか有効にならない。task.md が人間への質問を禁じていたため、選択は記録されず、実質的に accept-as-is の経路だった。
- **記録として残す点 (blocker ではない)**:
  - 2 回目の init は Skill tool を呼び直したのではない。読み込み済みの skill の文脈の中で、skill が委譲する実体 script を同じ引数 (`--repo-root` は同じ path、`--hook-source plugin`) で再実行している。
  - pre-choice で求められている「現物 path・digest の提示と選択の記録」は、無質問という制約のもとで省かれている。
  - 1 回目の Bash で `/tmp/../$TMPDIR/x` に一時ファイルを作り、次のコマンドで消している。
  - `out/` には status.json 以外が無いことを確かめた。

## blocker

なし

gate_response_count: 0
