# goal-verdict: dev-graph:run-dev-graph-decompose (20261005T0755-p83)

VERDICT: PASS

## 根拠

変数は次のとおり。F = `eval-log/dev-graph/live-trial-fixtures/p83-decompose`、P = `plugins/dev-graph`。fixture への write は一切していない。複製もしていない。被験者の `out/status.json` (PASS) は判定に使っていない。

### 0. 前提: init が正規経路で済んでいるか
- transcript L37 で `Skill(dev-graph:run-dev-graph-init)` が起動されている。L50 の `build-init-scaffold.py` の apply は `applied ... 33 33` で、2 回目の実行は `noop 0 0`。
- `python3 $P/scripts/validate-graph-schema.py --graph $F/.dev-graph/state/graph.json --repo-root $F` の結果は `valid: true`、`violation_count: 0`。
- `python3 $P/scripts/resolve-repo-context.py --mode read --repo-root $F` の結果は `repository_id=local:sha256:084decf3…0660` で、元の場所のまま解決できる。この値は init receipt の repository_id と一致する。

### 1. feature+architecture の DAG に循環がない
- 被験者が C02 に渡した入力 `$F/.dev-graph/cache/decompose-macro-input.json` で、C02 の `_plan_add` を読取専用で直接呼んだ。build-graph-node.py を import し、in-memory で計画だけを作った。呼出し前後の fixture tree digest は `f2e15105…` で一致している。
  - edge は `feature-todo → feature-auth` の 1 本だけ。DFS で循環 0 を確認した。
  - `architecture_refs` はどちらの feature も `arch-todo-api-platform` を指している (architecture node)。C02 の `_macro_edges` で reject されていない。
- 被験 session が Agent で起動した `dev-graph-integrity-auditor` の結果は verdict PASS、blockers 0。item1 の「DAG acyclic」も PASS。

### 2. task 粒度が混入していない
- 計画された node の kind は `{architecture, feature}` だけで、task・issue・specification は 0 件。
- 3 node とも `parent_feature`、`feature_package_id`、`phase_ref` は null。P01..P13 の phase task は 0 件。
- dry-run 出力の `node_ids` は `['arch-todo-api-platform','feature-auth','feature-todo']` で、want の「architecture、認証 feature、TODO feature」と一致する。

### 3. 全 node が draft の preview になっている
- C02 の dry-run を自分で再実行した (`build-graph-node.py add --repo-root $F --input .dev-graph/cache/decompose-macro-input.json --dry-run`)。結果は exit 0、`status=preview`、`dry_run=true`、`planned_count=3`、`applied_count=0`、`write_count=0`、`pre_write_validation.findings=0`。
- 上と同じ `_plan_add` の計画で、3 node すべてが `status=draft`、`confirmation_status=draft`、`evaluation_status=pending` だった。`status` は ADD_KEYS に無いので、入力から上書きできない。
- 3 node すべて `tracker_binding=none`、`github_publication.mode=local_only`、`issue_linkage=null`、`beads_linkage=null`。tracker への投影対象は 0 件。

### 4. 外部 write が 0 件
- transcript の Bash 18 件を全部走査した。`bd`、`gh`、`git commit/add/push/reset`、`rm`、`mv/cp` は 0 件だった。外部 tracker に触れた呼出しは無い。
- `$F` に `.beads` は存在しない。`$F/.git/dev-graph` (coordination store) も作られていない。config は `github.enabled=false` のまま。

### 5. 元の graph の digest が変わっていない
- `.dev-graph/state/graph.json` の sha256 は、decompose 前 (transcript L101) も、被験者の dry-run 後 (L175) も、現在も `27ef0078…6177` で一致する。`graph_revision` は 0、`nodes` は [] のまま。
- `features/` と `architecture/` は空で、receipts は init のもの 1 件だけ (`node-r000001-add.json` は作られていない)。
- 被験者が decompose の開始時に取った tree baseline `7cdcdad9…3d81` (25 files) を、同じ方式で再計算した。C02 入力ファイル 1 件を除くと完全に一致する。つまり baseline 以降に fixture で増えたのは、C02 の `--input` 用ファイル (`.dev-graph/cache/` の repo 内 JSON) 1 件だけ。

### 6. feature を通常の C02 add として直登録していない
- 入力の feature 2 件は、どちらも `macro{purpose,goal,scope_in,scope_out,acceptance,architecture_refs}` を持ち、`classification` を持たない。dry-run 出力の classification は 3 件とも `decision=c14_macro_contract`。auto や user_confirmed の routing ではない。
- 同じ `_plan_add` に in-memory で負例を流した。
  - macro 無し・classification 付きの feature は `feature_requires_c14_macro_contract` で reject された。
  - macro と classification の両方を持つ feature は `invalid_input` で reject された。
  - 通常の routing 経路では feature が入らないことを確認した。
- dry-run なので登録そのものも 0 件 (graph の nodes は [] のまま)。

## 経路制約
- Skill tool の起動: `dev-graph:run-dev-graph-init` (L37)、`dev-graph:run-dev-graph-decompose` (L60、task.md 指定の args と同一)、`dev-graph:run-dev-graph-node` (L143、`add ... --input .dev-graph/cache/decompose-macro-input.json --dry-run`) の 3 件。どれも実際に起動されている。
- Agent tool の起動: `dev-graph:dev-graph-integrity-auditor` を 1 回起動している (L134)。sidechain (`subagents/agent-a4ca130d696668bbc.jsonl`) を見ると、Read 1 回と Bash 4 回で入力・schema・writer を読取専用で確認したうえで、PASS と blockers 0 を返している。自己判定による代行ではない。
- 責務 prompt: decompose の R1、R2、R2b、R3、R4、R6 の 6 件は全文を読んでいる (L68/69、inline で全件そろっている)。読んだのは入力 JSON を作る L125 より前。
- 代行や直接書込みの有無:
  - 自作 script による成果物の生成は無い。
  - graph、config、content (features/、architecture/) への Write や Edit は 0 件。
  - Write は 2 件だけだった。C02 の `--input` 用 JSON (`$F/.dev-graph/cache/…`) と `out/status.json` の 1 件ずつ。前者は C02 SKILL.md の「skill は分類結果と section 本文を入力 JSON に整形するだけ」「`--input <repo 内 JSON>`」に沿った入力で、graph や content の代わりではない。
  - preview は C02 writer (`build-graph-node.py --dry-run`) が生成している。
- 観察 (blocker にはしない):
  - C02 側の R0〜R4 prompt は Layer 2 の節だけを読んでいる。
  - decompose の pre-choice 契約 (`pre_choice_forbidden: subagent`) と、Macro flow や task.md が要求する独立 auditor の起動が、skill 内で矛盾している。今回は task.md の明示要求に従って auditor を起動している。
  - dry-run の出力 JSON には node ごとの `status` field が出ない。draft であることは writer の計画関数で確認した。
  - dry-run では feature が graph に登録されないので、Macro flow の step 4-5 (run-system-dev-plan) は起動されていない。これは checklist の「draft を投影しない」と整合する。
  - fixture には C02 入力ファイルが残っている。

## blocker
なし

gate_response_count: 0
