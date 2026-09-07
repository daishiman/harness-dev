# goal-verdict: dev-graph:run-dev-graph-init (20260907T0330-gm4)

```
VERDICT: PASS
```

## 根拠 (out/status.json を信用せず、独立に裏取りした内容)

status.json は実行者の自己申告として無視し、以下は評価者が fixture 実体と plugin script を直接叩いて確認した。

### 1. content root / repo-local 資産の実在

`/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-init` を `find` で走査:

- `issues/ tasks/ specs/ architecture/ features/ docs/` の 6 root が実在 (加えて `system-spec/`。これは `resolve-repo-context.py` の `DEFAULT_CONTENT_ROOTS` と `repo-config.schema.json` の `content_roots.required` が 7 key を要求しているためで、逸脱ではない)。
- `.dev-graph/config.json`、`.dev-graph/state/graph.json`、`.dev-graph/state/init-receipt.json`、`.dev-graph/cache/`、`.dev-graph/locks/`、`.dev-graph/templates/` が実在。
- templates は plugin `templates/` の 21 ファイルが欠落 0 でコピーされ、全件 digest が plugin 原本と一致。`template-contract.json` 列挙 15 資産も missing 0。

### 2. hook source

- `--hook-source plugin` に対し fixture 側へ `.claude/` は作られていない (`.claude` 不在を確認)。plugin hook source `plugins/dev-graph/hooks/hooks.json` が実在し、`PreToolUse / SessionStart / PostToolUse / TaskCompleted` の 4 event を定義。receipt の `hook_result.settings_write: "none"`, `duplicate_count: 0`, `project_settings_present: false` はこの実体と整合する。既存 settings への書込み・二重登録は発生していない。

### 3. 冪等性 (2 回目 planned change = 0 / 利用者編集を上書きしない)

評価者自身で再現:

- 実行前に fixture の全 file の sha256 を採取 → 追加実行 → `planned_change_count: 0`、`planned_changes: []`、`migration_preview: []`、`valid: true`。実行前後の digest 一覧は完全一致 (差分 0)。
- 利用者編集の非上書きは transcript の run3 で `.dev-graph/templates/task.md` に 1 行追記した状態で再実行し、編集後 digest が不変 (`9cce535f...`)、`planned_change_count: 0`、`migration_preview` に `reason: user_modified` + `current_sha256`/`plugin_sha256` が記録されたことを確認。
  これはコード上も構造的に保証されている: 既存 path は `planned` に載らず、apply ループは `planned` のみを走査するため、既存ファイルへの write 経路が存在しない。
- 評価者による隔離コピーでの再検証は `repo config repository_id does not match derived repository` で exit 2 となり実行不能だった。これは C24 の containment が正しく fail-closed した結果であり、上記 2 点 (in-place 再実行 + コード経路) を根拠として採用した。

### 4. config に絶対 path / token / node ID を保存していない

`repo-config.schema.json` で独立に検証:

- Draft 2020-12 validation エラー 0 件。
- 全 string 値を走査して `/` `~` 始まり・`Users/dm` 含有 = 0 件 (stored path は全て repository-relative)。
- token 系値パターン (`ghp_` `github_pat_` `PVT` `MDU6` `I_kw`) 該当 0 件、`token`/`node_id`/`item_id`/`field_id` 等の key 0 件。
- `github.enabled = false`、保存されているのは `owner_login`/`project_number`/`project_field_name`/`option_map` のみ。
- config 内容は plugin 同梱 `templates/repo-config.example.json` と照合し、差分は `repository_id`・repo 名由来の `issue_prefix`/`issue_repository`/`owner_login` の instance 固有置換のみ。

### 5. C11 gate

評価者が直接実行:

```
python3 validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>
→ {"valid": true, "violations": [], "missing_sections": []}  C11_EXIT=0
```

`resolve-repo-context.py --mode write` も exit 0 で、`repository_id` は config の値と一致 (`local:sha256:a5d4345...`)。

### 6. 実行者による責務の肩代わりについて

実行者は scratchpad に 477 行の `dev_graph_init.py` を書き、それ経由で init を行っている。ただし:

- 生成内容の正本は全て plugin 資産 (`repo-config.example.json`、`repo-config.schema.json`、`template-contract.json`、`templates/*`、`resolve-repo-context.py` の default roots) であり、実行者が独自にポリシーや config 形状を発明していない。
- 宣言済み `script_refs` の 2 本 (`resolve-repo-context.py`, `validate-graph-schema.py`) を subprocess で実際に呼んでおり、C11 の結果を捏造していない (評価者の独立実行と一致)。
- SKILL.md / prompts の実行方式は「固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する」であり、`Bash` も allowed-tools に含まれる。よってスクリプトは agent 操作の実行媒体であって、skill 責務の代行とは判定しない。

## 観察 (blocker ではない)

- SKILL.md 本文と完了チェックリストは graph store を `.dev-graph/graph.json` と書くが、`resolve-repo-context.py` と schema の正本は `.dev-graph/state/graph.json`。実物は後者に置かれており C11 も通る。仕様文の表記揺れ。
- plugin 同梱 `templates/repo-config.example.json` は `content_roots.features` を欠いており、schema の required を単体では満たさない。生成された config 側では補われている。
