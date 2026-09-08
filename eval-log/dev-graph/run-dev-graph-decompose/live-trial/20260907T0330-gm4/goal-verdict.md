# goal-verdict: dev-graph:run-dev-graph-decompose (20260907T0330-gm4)

```
VERDICT: PASS
```

評価者は被験 skill の実装者でも実行者でもない。`out/status.json` の自己申告 (PASS) は根拠として採用せず、以下はすべて評価者が自分で実行した Read / Bash / スクリプト実行の出力に基づく。

## 根拠

### 1. dry-run write 0 / 原 graph digest 不変

- fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-decompose` の
  `.dev-graph/state/graph.json` は `{"graph_revision": 0, "nodes": [], "schema_version": "1.0.0"}` のまま。
  評価者が計測した sha256 = `27ef0078ae9bf6e61be1b9a6da5a5c94d30fbcd84db5f71d7c370e4e88e66177`。
- content roots (`architecture` `features` `issues` `tasks` `specs` `docs` `system-spec`) の実ファイル数はすべて 0。
- `git status --short` は `?? .dev-graph/` のみ (C01 init 由来)。decompose による fixture への write は 0 件。
- preview 成果物は fixture 外の staging (`<scratchpad>/staging/tmproot/`) にのみ存在する。

### 2. 外部 write 0

- transcript.jsonl 全 593 行の Bash tool_use を正規表現で走査し、`gh ` / `bd ` / `gh-bridge` / `bd-bridge` /
  `git commit` / `git push` の実行は 1 件も存在しない (唯一の hit は fixture の `ls` を含む点検コマンドで mutation ではない)。
- preview 全 node が `tracker_binding=none`、`github_publication.mode=local_only`、
  `beads_linkage=null`、`issue_linkage=null`、`github_project_linkages=[]`、`pull_request_linkages=[]`。

### 3. feature+architecture DAG 循環なし / task 粒度混入なし

評価者が staging preview graph を自前でパースして再計算:

- node 3 件: `arch-auth-todo-api` (architecture), `feat-auth-api` (feature), `feat-todo-api` (feature)。
- 辺 = `feat-auth-api→arch-auth-todo-api`, `feat-todo-api→feat-auth-api`, `feat-todo-api→arch-auth-todo-api`。
  DFS による循環検出結果 `has_cycle = False`。未解決 (orphan) 参照 0 件。
- `artifact_kind=task` の node は 0 件。全 node で `parent_feature` / `feature_package_id` / `phase_ref` が null。
  P01..P13 相当の phase task は 1 件も生成されていない。

### 4. 全 node が draft preview

- 3 node すべて `status=draft`、`confirmation_status=draft`、`evaluation_status=pending`、
  `implementation_readiness={"status":"incomplete","missing_sections":[],"checked_at":null}`。
- tracker 投影対象 0 件 (上記 2 と同じ根拠)。

### 5. schema gate (IN1) の独立再実行

評価者が自分で実行:

```
python3 plugins/dev-graph/scripts/validate-graph-schema.py \
  --graph <staging>/tmproot/.dev-graph/state/graph.json --repo-root <staging>/tmproot
→ {"implementation_readiness":"complete","missing_sections":[],"valid":true,"violations":[]} exit 0
```

### 6. feature を「通常 C02 add」として直登録していないこと

- graph/content の生成・適用は `Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root <fixture> --input <macro-contract> --dry-run"})` を経由している (transcript idx 353)。
- 渡された `--input` は C14 macro contract `macro-candidate-v2.json`。評価者が計測したそのファイルの
  sha256 = `98c97bff7df3cb0c70a3e9e86b78d1c2e68c372fb5a687232c07a4a1c6407971` は、preview 3 node すべての
  `source_lineage.source_digest` と一致する。すなわち feature の入口が macro contract であることは
  自己申告ではなく digest による lineage で裏取りできる。
- 両 feature node の `classification_reason` にも「通常 artifact routing ではなく macro contract 経路からのみ
  features/ へ写像した」と記録されている。C02 (`run-dev-graph-node`) の argument-hint は `add|update|register-package`
  で macro 専用 verb を持たず、`prompts/R1-classify.md` は「feature は C14 macro contract 時だけ候補化する」と規定する。
  したがって macro contract を input とした `add` が正規経路であり、通常 artifact classification routing 由来の
  feature 直登録は 0 件。

### 7. 独立 auditor の実起動 (自己判定による代替なし)

- transcript idx 186 で `Agent` tool により `subagent_type: dev-graph:dev-graph-integrity-auditor` を実起動 (name: macro-auditor)。
- 監査結果は実際に返っており (idx 301)、v1 候補に対し **overall_verdict: FAIL** と 3 件の schema violation
  (feature の `artifact_subtypes` maxItems 0 違反 / `evaluation_status: "not_evaluated"` は enum 外 /
  `implementation_readiness` が object でなく string) を提示している。
- 実行者はこれを受けて `macro-candidate-v2.json` を作成し、idx 343 で同 auditor が再監査、**overall_verdict: PASS** を返した。
  auditor が実際に拒否として機能し、その拒否が成果物を変えた履歴が残っているため、自作検査コードによる自己判定の代替ではない。
- 責務 prompt (`R1-elicit` `R2-plan` `R2b-feature-planning` `R3-decompose` `R4-project` `R6-dryrun`) は
  macro candidate 生成 (idx 181) より前の idx 148-166 で読まれている。

### 8. 被験 skill 責務の自作スクリプト代行なし

- transcript 中の Write は fixture の `.dev-graph/{config.json,state/graph.json,state/init-receipt.json}` (C01 init の実行本体)、
  macro candidate v1/v2、staging の preview graph・3 本の .md、receipt/report、`out/status.json` のみ。
  driver / build / guard に相当する自作 `.py` / `.sh` は 1 件も作成されていない。
- Bash 内の python3 heredoc はすべて schema/template-contract の読み取り、digest 計測、
  正規 script (`resolve-repo-context.py` / `validate-graph-schema.py`) の呼出しであり、成果物生成には使われていない。

## 付記 (blocker ではない)

- transcript idx 480 で C02 preview を対象とする 2 本目の auditor (`macro-final-auditor`) を起動したが、
  その verdict は返らないまま実行者は PASS を宣言している。ただし SKILL.md Macro flow step 2 が要求する
  「循環と実装粒度の task 混入を独立 auditor で拒否する」は idx 186/301/343 の監査で充足済みであり、
  かつ preview の循環・task 混入・draft・binding・schema は本評価者が独立に再検査して問題なしを確認した。
  成果物の実体に欠陥はないため blocker とはしない (プロセス上の弱点としてのみ記録)。
- ready feature `feat-auth-api` に対する `run-system-dev-plan` は起動されていない。`--dry-run` により C02 が
  macro graph を commit していない (applied=false / graph_revision 0) ため parent_feature が未確定で、
  R2b Layer 6 の digest 一致要件と R6-dryrun の責務境界 (C02/C28/C12 mutation を呼ばない) に従った判断として
  report に理由が記録されている。今回の trial 条件 (macro 分解 + dry-run) の下では goal 未達とは判定しない。
