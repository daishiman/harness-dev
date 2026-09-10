# goal-verdict: dev-graph:run-dev-graph-status (20260907T0330-gm4)

```
VERDICT: PASS
```

## 根拠 (独立裏取り)

対象 goal: 「特定の node を graph_node_id 等で検索し、依存関係・close/tombstone 状態を read-only で確認できる状態になっている」

### 1. 報告値と graph 実値の一致 (OUT1)

fixture の `.dev-graph/state/graph.json` を評価者が直接読み出した実値:

- `LT-TASK-001`: status=`closed`, closed_at=`2026-09-06T12:40:00Z`, depends_on=`["LT-TASK-000","LT-TASK-002"]`
- 逆引き dependents: `LT-TASK-003` (`depends_on: ["LT-TASK-001"]`) のみ
- tags=`["implementation","graph-store","read-only"]`, file_path=`tasks/lt-task-001-status-query-path.md`, tracker_binding=`beads`, parent_feature/feature_package_id=`null`

transcript の被験 skill 実行 (tool_use #41-#44) が返した report は上記と全項目一致。
result_count=1 / scanned_nodes=4 も graph の node 数 4 と一致。
node 本文 (`tasks/lt-task-001-status-query-path.md` frontmatter status: "closed") とも矛盾なし。
report は graph 由来の値をそのまま返しており、本文からの推測ではない。

### 2. C11 exit 0 (IN1)

評価者が独立実行:

`python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>`
→ `EXIT=0`, `"valid": true`, `"violations": []`

被験 skill 実行中 (#43) にも同 script が呼ばれ `C11_EXIT=0` を得ており、report 前の read-only validation gate が実際に通っている。
root 外 file_path 0 件・dangling dependency 0 件も評価者側で確認 (全 depends_on 参照先が graph 内に存在、全 file_path が tasks/ 配下)。

### 3. read-only (前後 digest 不変, OUT2)

- 実行者側の証跡: pre-digest (#40, skill 呼出前) と post-digest (#45) の全ツリー比較が `IDENTICAL: 0 changed files (30 files)`。
- 評価者による独立裏取り: 現時点の `.dev-graph/state/graph.json` の sha256 = `90a43fd0632354459092df4351b2dcb5fce7243e36106bc619d1fee757034003` で、実行者が post に記録した値と一致。
  さらに graph.json の mtime は `2026-09-07 14:16:56` であり、被験 skill 起動 (#41 以降, 14:17-14:18) より前。以後 graph は一切書き換わっていない。
- 被験 skill 区間 (#41-#45) の tool 呼出は Read/Bash の読み取りのみで、Write/Edit・writer/sync/render skill の呼出は 0 件。

### 4. GitHub / Beads write 0 件

- 被験 skill 区間に `gh` / `bd` / `bd-bridge.py` / `gh-bridge.py` の呼出なし (transcript 全 tool_use を走査。`gh auth status` は準備段階 #19 の read-only 照会のみ)。
- fixture 配下に `.beads` は生成されていない。`~/.beads/beads-app.log` の最終更新は 2026-07-14、`~/.beads/eventsData` の mtime は 14:09 で試行開始前。
- fixture の `git status` は `?? .dev-graph/ ?? tasks/` のみで commit/push なし。

### 5. 経路 (C02 単一 writer)

graph/content への書込みは準備段階のみで、いずれも Skill 起動を経由:
`dev-graph:run-dev-graph-init` (#3) が `.dev-graph/config.json` と初期 graph を、`dev-graph:run-dev-graph-node` (#26) が 4 件の task md と graph node を staging→C11 gate→lock 付き commit の順で作成している。
dev-graph plugin には node 登録用の独立 CLI writer script は存在せず (scripts/ は register-package.py など別責務のみ)、node skill の script_refs も resolve-repo-context / validate-graph-schema / register-package のみ。よって skill 本文手順としての書込みであり、被験 skill の責務を代行する自作スクリプトによる迂回ではない。
被験 skill 自身は graph に一切書いておらず、検索処理も C24 receipt→C11 gate→graph 読取という SKILL.md 記載の経路で行われている。

## 補足 (blocker ではない)

- SKILL.md の「ゴールシーク配線」(goal-spec.json / progress.json / intermediate.jsonl の生成、Agent fork) は実行されていないが、これらは `goal_seek.activation_state: semantic_evaluator_started` の post-choice section であり、accept-as-is 相当で終了した本試行では発火条件を満たさない。goal 達成判定の blocker としては扱わない。
