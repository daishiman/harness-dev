# goal-verdict: dev-graph:run-dev-graph-decompose (20261005T1500-p83m)

VERDICT: PASS

## 根拠

評価者自身が fixture `eval-log/dev-graph/live-trial-fixtures/p83m-decompose` に対して read-only の操作だけを行い、確認した。複製はしていない。評価前後に fixture 全体 (.git を除く 39 entry) の sha256 snapshot を取って diff を見たところ、差分は 0 だった (`FIXTURE-UNCHANGED`, `FIXTURE-UNCHANGED-2`)。

### 準備: init が正規経路で済んでいるか
- transcript #3 で `Skill(dev-graph:run-dev-graph-init, "--repo-root <fixture> --hook-source plugin")` を起動していた。#4 では SKILL.md 134 行目の「実装本体」である `build-init-scaffold.py` が `status=applied`、`write_count=33`、`schema_result.valid=true` を返し、receipt `init-20261005T013723924268Z.json` を作った。#5 の再実行は `noop 0 0` で、冪等だった。
- 評価者が `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を実行した結果は `graph_validation.status=pass`、`violation_count=0`、exit 0 だった。
- 評価者が `resolve-repo-context.py --repo-root <fixture> --mode read` を実行した結果は exit 0、`repository_id=local:sha256:4821e263…c61989` で、init receipt や dry-run preview の値と一致した (C24 は通る)。

### 検証1: feature+architecture DAG に循環が無いか
- 評価者がスクラッチパッドの read-only スクリプト `inspect_plan.py` から `build-graph-node.py` の `_plan_add` を直接呼び、被験者が使った同一入力 `.dev-graph/cache/c14-macro-add-input.json` から提案 node を得て、DFS で循環を検査した。
- 辺は `feature-auth → arch-todo-api-platform`、`feature-todo → feature-auth`、`feature-todo → arch-todo-api-platform` の 3 本だった。結果は `acyclic: True`。
- `depends_on` の先は feature、`architecture_refs` の先は architecture になっていた。writer の `_macro_edges` も拒否しなかった。

### 検証2: task 粒度の node が混じっていないか
- 提案 node の kind は `['architecture', 'feature']` だけで、合計 3 node (arch-todo-api-platform、feature-auth、feature-todo) だった。
- 全 node で `parent_feature`、`feature_package_id`、`phase_ref` が null だった。task/issue の node や P01..P13 の phase task は 0 件 (`task-grain nodes: []`)。
- 提案 node をメモリ上で `VGS.schema_findings` と `domain_findings` にかけた結果は `[]` だった。dry-run preview の `pre_write_validation.findings` も 0。

### 検証3: 全 node が draft の preview になっているか
- 評価者が `build-graph-node.py add --repo-root <fixture> --input .dev-graph/cache/c14-macro-add-input.json --dry-run` を自分で実行した。結果は exit 0、`status=preview`、`dry_run=true`、`planned_count=3`、`applied_count=0`、`write_count=0`、`graph_revision_before=0` で、`node_ids` は 3 件だった。
- `_plan_add` で得た全 node は `status=draft`、`confirmation_status=draft`、`evaluation_status=pending`、`tracker_binding=none`、`github_publication.mode=local_only`、`issue_linkage=null`、`beads_linkage=null` だった。tracker への投影対象にはならない状態である。

### 検証4: 外部 write が 0 か
- transcript の全 23 tool call を走査した。`gh`、`bd`、`gh-bridge`、`bd-bridge`、`build-github-projection`、`register-package`、`git push/commit`、`curl` を呼んだ痕跡は無かった。
- fixture に `.beads` は無く、`remote.origin` に URL は無い。`.dev-graph/locks` は空で、receipts は init の 1 件だけ。preview が予告した `node-r000001-add.json` は存在しない。

### 検証5: 元の graph digest が変わっていないか
- 被験 session の #10 (dry-run 前) と #18、#23 (dry-run 後) の graph.json の sha256 は、すべて `27ef0078ae9bf6e61be1b9a6da5a5c94d30fbcd84db5f71d7c370e4e88e66177` だった。
- 評価時点で評価者が測った値も `27ef0078…e66177` で一致した。内容は `graph_revision=0`、`nodes=[]` のままだった。

### 検証6: feature を通常の C02 add で直接登録していないか
- 入力 JSON の feature 2 件 (auth、todo) はどちらも `macro{purpose, goal, scope_in, scope_out, acceptance, architecture_refs}` を持ち、`classification` は持っていなかった (`macro=True classification=False`)。architecture は `classification.decision=c14_macro_contract` で、candidates は持たない。
- preview の全 artifact は `classification.decision=c14_macro_contract` だった。feature の `classification_reason` は "declared by the C14 macro contract (run-dev-graph-decompose)" だった。
- writer のコードも確認した。`_plan_add` は macro を持たない feature を `feature_requires_c14_macro_contract` で、classification を持つ feature を `invalid_input` で拒否する。この入力はその経路を通っていないので、通常の artifact routing として直接登録された feature は 0 件である。実際の commit も行われていない (dry-run のみ)。

## 経路制約

- Skill の起動 (Skill tool): `dev-graph:run-dev-graph-init` (#3)、`dev-graph:run-dev-graph-decompose` (#6、args は task.md どおり `--dry-run` 付き)、`dev-graph:run-dev-graph-node` (#16、C02 single writer) の 3 件。task.md が要求した skill はすべて実際に起動されていた。
- 独立 auditor (Agent tool): #15 で `subagent_type=dev-graph:dev-graph-integrity-auditor` が実際に起動されていた。task-notification で返った結果は監査 6 項目 (循環、task 粒度、feature 必須 field、edge の先、tracker_binding、C14 macro contract) がすべて PASS、overall PASS、blocker なしだった。自作の検査コードで自己判定して代わりにした跡は無い。
- 責務 prompt を出力より先に読んだか: #7 で decompose の `prompts/R1-elicit, R2-plan, R2b-feature-planning, R3-decompose, R4-project, R6-dryrun` を全文 cat していた。これは R2 出力 (#14 の macro-plan.json) より前である。#9 で C02 の `prompts/R0..R4` を読んでいた。これは C02 の入力 JSON (#17) より前である。
- 代行の有無: init は `build-init-scaffold.py`、C02 preview は `build-graph-node.py add --dry-run` で、どちらも SKILL.md が「実装本体」と明記する plugin script である。成果物を作る自作 script は無かった。自分で書いた python ワンライナーは preview JSON の表示と grep/sed によるコード閲覧だけだった。
- 直接書込みの有無: Write は 2 件だけだった。(1) スクラッチパッドの `macro-plan.json` (R2 の分解案で、auditor に渡す入力)。(2) fixture 内の `.dev-graph/cache/c14-macro-add-input.json` (C02 SKILL.md が求める「repo 内 `--input` JSON」の整形)。graph.json、config.json、content、receipt を Write/Edit で直接書いた跡は無い。config、graph、templates は init script が作ったものである。Edit は 0 件。
- tool error は 0 件だった。

参考 (blocker ではない):
- C02 への入力 JSON が fixture の `.dev-graph/cache/` に残っている。C02 の `--input` は repo 内 path を要求するので、これは正規の入力経路である。graph、content、receipt への write ではないので、dry-run の「write 0」には当たらないと判断した。
- 完了マーカー `out/status.json` は Write tool ではなく Bash の printf で書かれていた。内容は task.md の形式どおり。
- C02 の R4-apply-template prompt は `head -150` で末尾 (受入条件以降) が切れた状態で読まれていた。ただし本 run では R4 の出力 (section の補完) を作っていない。architecture node の readiness が incomplete なのは、placeholder のままの draft として扱いどおりである。
- R2b (system-dev-planner の起動)、R3 (登録と投影)、R4 (Projects) は実行されていない。全 feature が draft で ready ではなく、`--dry-run` なので R6 の preview で止まった。これは SKILL.md の Macro flow 手順 3〜4 と R6 に合っている。

## blocker

なし

gate_response_count: 0
