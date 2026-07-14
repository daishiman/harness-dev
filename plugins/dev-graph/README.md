# dev-graph

dev-graph は大きな構想を **macro feature graph** にし、tracker/worktree 実行を収束させる local-first harness です。1 feature の細かな実行仕様は system-dev-planner に委譲します。

## Quickstart

前提は Git repository の root、Python 3.10 以上、Claude Code です。GitHub binding を使う場合は認証済み `gh`、Beads binding を使う場合は初期化済み `bd` も必要です。`plugins/dev-graph/references/package-contract.json` が宣言する `system-spec-harness` と `system-dev-planner` を同じ repository の `plugins/` に配置してください。各 dependency の `.claude-plugin/plugin.json` は公式manifestの `name` と version `>=0.1.0 <1.0.0`、`references/package-contract.json` は次の entry point を満たす必要があります。

- system-spec-harness: `run-system-spec-elicit`, `run-system-spec-doc-fetch`, `run-system-spec-compile`, `assign-system-spec-completeness-evaluator`
- system-dev-planner: `run-system-dev-plan`, `assign-system-dev-plan-evaluator`

repository root で preflight と最小の初期化確認を行います。

```bash
claude plugin validate plugins/dev-graph
claude plugin validate plugins/system-spec-harness
claude plugin validate plugins/system-dev-planner
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/dev-graph}/scripts/resolve-repo-context.py" --repo-root "$PWD" --mode read
```

```text
/dev-graph init --repo-root "$PWD"
/dev-graph status --repo-root "$PWD"
```

仕様作成から feature plan までの正経路は次のとおりです。`plan` の context は absolute path ではなく caller repository 相対 path を渡します。

```text
/dev-graph spec --repo-root "$PWD"
/dev-graph decompose --repo-root "$PWD"
/dev-graph plan --feature-id F-001 --feature-context features/F-001.json
```

`spec` は宣言済み system-spec-harness を load し、confirmed + evaluator PASS の成果だけを source lineage 付きで C02 へ渡します。`plan` は ready feature と同じ id/source digest の context だけを system-dev-planner へ渡し、P01..P13 exact 13 package を atomic 登録します。

fail-closed 診断が出た場合は近似実行や installed/global plugin への fallback を行いません。

| 診断 | 確認するもの |
|---|---|
| dependency missing / manifest name mismatch / entry point missing | `plugins/<name>/.claude-plugin/plugin.json`、dependency側 `references/package-contract.json`、caller側 package contract の `depends_on` |
| repository mismatch / path escapes / broken symlink | repository root、`.dev-graph/config.json` の repository identity、入力 realpath |
| readiness/evaluation/source digest mismatch | feature の confirmed/evaluation/readiness、`--feature-context` の id と digest |
| graph/schema validation failure | 書込み前の node/package 必須 field、P01..P13 exact set、dependency DAG |
| GitHub/Beads auth or partial external failure | `gh auth status` / `bd where`、`pending_retry`。local confirmed generation は維持して未完 operation だけ再実行 |

## Flow

```text
want
  -> /dev-graph decompose
  -> feature + architecture + feature dependencies
  -> ready feature
  -> /system-dev-plan plan --feature-id F --feature-context features/F.json
  -> P01..P13 exact 13 task specs + intra-feature DAG
  -> dev-graph atomic registration
  -> Beads/GitHub projection and worktree execution
```

`spec` は system-spec-harness の確定成果物を lineage 付きで取り込みます。dev-graph は system spec compiler と exact-13 task generator を複製しません。

## Automatic and manual planning

- 自動: `run-dev-graph-decompose` が ready feature ごとに feature id/context digest を束縛して `run-system-dev-plan` を起動します。
- 手動: `/dev-graph plan --feature-id <id> --feature-context <repo-relative-json>` を実行します。
- `--feature-context` は caller repository 相対 path だけを許可します。id/digest、repository、readiness が一致しない場合は fail-closed です。

## Resume

失敗時は graph の確定世代を維持し、staging/receipt/pending retry を残します。同じ feature id と source digest で再実行し、別 feature や更新済み digest へ暗黙に再利用しません。`/dev-graph status` で状態、`/dev-graph next` で feature-ready/task-ready を確認します。

## Ownership

- dev-graph: program goal、feature、architecture、feature間依存、registration、tracker、lease、completion。
- system-dev-planner: 1 feature の P01..P13 exact 13 specs、inventory、intra-feature DAG、promotion。
- system-spec-harness: system specification と architecture の内容。
