# goal-verdict: dev-graph:run-dev-graph-decompose (20261004T1020-f11)

VERDICT: PASS

評価者は被験 skill の実装者でも、実走させた orchestrator でもない。`out/status.json` の自己申告 (PASS) は根拠にしていない。以下の根拠はすべて、評価者が transcript.jsonl (全 243 行。idx は 0 始まりの行番号) と fixture / staging の現物に対して自分で行った Read / Bash / 正規 script 実行の出力による。

- 被験 session: `741b559f-88ba-435f-8a0d-c6b65fb6f5c9`。実走 model は `claude-opus-5-5` の単一値。
- staging preview の場所: 被験 session の scratchpad `.../741b559f-.../scratchpad/f11-c02-staging/` (fixture の外)。

## 根拠

### 1. 原 graph の digest が変わらず、fixture への decompose 由来の write も 0 件

- fixture `.dev-graph/state/graph.json` の現物は `{"nodes": []}`。評価者が計測した sha256 は `d14d7329304df05f244daa478ed0cc7f58e1a2d60a53d319e60e625395020728` だった。
  - これは decompose 開始直後の idx 130 (10:15:36Z) で被験 session が記録した値と一致する。
  - 終了直前の idx 225 で再計測した値とも一致する。
- 評価者が fixture 全ファイルの sha256 を取り直し、idx 130 で取られた事前 snapshot (`f11-before.sha`) と diff したところ差分は 0 件だった。
- content roots (`architecture` `features` `issues` `tasks` `specs` `docs`) はいずれも空。
- fixture の `git status` に出るのは C01 init が作った `.dev-graph/` 配下だけ。HEAD は `d800a3e init` のまま。

### 2. 外部への write が 0 件

- transcript の全 31 回の tool_use を機械走査した。`gh` / `bd` / `gh-bridge` / `bd-bridge` / `git commit|push|add|tag` / `curl` / `register-package.py` の実行は 0 件。
  - 唯一ヒットしたのは idx 130 の `shasum > <scratchpad>/f11-before.sha` で、被験 session の scratchpad への digest 記録にすぎない。
- Write の宛先は次の 3 種類だけ。
  - C01 init の実行本体 (idx 93/95)
  - scratchpad の staging 4 ファイル (idx 199/201/203/215)
  - `out/status.json` (idx 236)
- idx 225 の出力で、`.beads` と `.git/dev-graph` が存在しないことも確認されている。
- preview の全 3 node は次の値を持ち、tracker 投影の対象は 0 件。
  - `tracker_binding=none`
  - `github_publication.mode=local_only`
  - `beads_linkage=null` / `issue_linkage=null` / `github_project_linkages=[]`

### 3. feature+architecture の DAG に循環がなく、task 粒度の混入もない

評価者が staging の `graph.json` を自分でパースして再計算した結果は次のとおり。

- node は 3 件: `arch-todo-api` (architecture、subtypes `[backend, security]`)、`feat-auth` (feature)、`feat-todo` (feature)。
- `depends_on` の辺は `feat-todo→feat-auth` の 1 本だけで、task.md の「TODO は認証に依存」と一致する。
- `architecture_refs` は両 feature から `arch-todo-api` を指している。未解決の参照は 0 件。
- DFS で循環を検出した結果は `has_cycle=False`。
- `artifact_kind=task` の node は 0 件。kind の集合は `{architecture, feature}` だけ。
- 全 node で `parent_feature` / `feature_package_id` / `phase_ref` が null。P01..P13 の phase task は 1 件も生成されていない。

### 4. 全 node が draft preview である

- 3 node すべてが次の状態にある。
  - `status=draft` / `confirmation_status=draft` / `evaluation_status=pending`
  - `implementation_readiness.status=incomplete`
- C02 には `--dry-run` で入り (idx 161)、atomic replace はしていない (idx 224)。fixture 側の graph が不変であることは根拠 1 で確認済み。

### 5. schema gate (IN1) を評価者が独立に再実行した

```
python3 plugins/dev-graph/scripts/validate-graph-schema.py \
  --graph <staging>/.dev-graph/state/graph.json --repo-root <staging>
→ {"implementation_readiness":"complete","missing_sections":[],"valid":true,"violations":[]}  rc=0
```

被験 session が idx 219 で実行した同じ検証 (`--repo-root` は省略。`.dev-graph` の親を root と推定する) の結果とも一致する。

### 6. feature を「通常の C02 add」として直登録していない

- C02 は `Skill({skill:"dev-graph:run-dev-graph-node", args:"--dry-run --repo-root <fixture> run-dev-graph-decompose の macro batch preview (atomic, 3 node add) ..."})` として、decompose の Macro flow の中から呼ばれている (idx 161)。呼んだのは auditor PASS (idx 153) の後。
- 両 feature node の値は次のとおり。通常 artifact の内容から分類する routing を経ていない。
  - `classification_reason`: 「C14 macro contract (run-dev-graph-decompose) が feature として明示指定」
  - `classification_candidates`: `[]` (内容ベースの第二候補なし)
  - `classification_confidence`: 1.0
- C02 側の `R1-classify.md` は「feature は C14 macro contract 時だけ候補化する」と規定しており、上の値はこの規定に沿っている。
- `--dry-run` のため fixture の graph には何も登録されていない (根拠 1)。直登録は字義どおり 0 件である。

### 7. 独立 auditor を Agent tool で実際に起動し、その指摘が成果物に反映された

- idx 146 で `Agent` により `subagent_type: dev-graph:dev-graph-integrity-auditor` を起動した。依頼内容は監査観点 A–F (循環 / task 混入 / 必須 field / orphan / tracker 投影 / 分解粒度)。
- auditor 自身の transcript (`subagents/agent-a5068207ab33817d8.jsonl`、meta の `agentType=dev-graph:dev-graph-integrity-auditor`) にも、次の記録が残っている。
  - 4 回の read-only Bash 実行 (`graph-node.schema.json` / `template-contract.json` の読取り)
  - 最終応答 `overall: PASS`
- 返却は idx 153。A–F はすべて PASS で、low severity の指摘が 3 件あった。
  - `evaluation_status` を enum 値 `pending` にする
  - `github_publication` を object にする
  - `file_path` を付け、architecture node の feature 専用 field を null / `[]` にする
- idx 161 の C02 入力と staging の現物には、この 3 件がすべて反映されている。auditor の判定が成果物を実際に変えている。自作検査コードによる自己判定で代替したものではない。

### 8. 責務 prompt を出力前に読んでいる。被験 skill の責務を代行する自作スクリプトも書いていない

- decompose の prompts は、macro brief / DAG candidate を出す前 (idx 145–146) に、idx 115 と idx 125 で読まれている。
  - R1 / R2 / R3 / R6: Layer 2 / 3 / 6 / 7
  - R2b / R4: Layer 2
- C02 の prompts (R0–R4 の Layer 2–3) は、staging への書込み (idx 199 以降) より前の idx 167 で読まれている。
- 出力 shape を定める Layer 2 (入出力契約・責務境界・受入条件) は、全 prompt について出力の前に読まれている。
- Bash 内の `python3 -c` / heredoc の用途は次の 3 つだけで、成果物を生成するものはない。driver / build / guard に当たる自作 `.py` / `.sh` は 1 本も作られていない。
  - schema の読取り (idx 70/77/135)
  - config の jsonschema 検証 (idx 99)
  - 正規 script (`resolve-repo-context.py` / `validate-graph-schema.py`) の呼出し
- staging の graph / md は、C02 SKILL.md の「frontmatter/body/path と graph node を一時領域で構成し `validate-graph-schema.py` を通してから atomic replace」に従って、C02 Skill 起動後の文脈で組み立てられている。dev-graph には通常 node 用の add CLI が存在しない。この経路は先例 gm4 と同じ。

## 付記 (blocker ではない)

1. **macro candidate と C02 入力が digest で結ばれていない**
   - auditor に渡した candidate は prose で、ファイルにはなっていない。auditor 自身も「has no digest, so nothing was bound to a digest」と明記している。
   - preview の `source_lineage` は `origin_kind=manual` / `source_digest=null` だった。C14 由来であることの裏付けは `classification_reason` の記述と呼出し文脈だけで、先例 gm4 (macro-candidate ファイルの sha256 と全 node の `source_digest` が一致) より lineage が弱い。
   - 各 R prompt の Layer 6「前段 digest と後段 input digest を一致させる」を厳密には満たしていない。
   - ただし、評価者が auditor 入力 (idx 146) と C02 入力 (idx 161) を突き合わせたところ、次の差分しかなかった。成果物の実体に欠陥はない。
     - auditor 指摘 3 件の反映
     - title の付与
     - 句読点の差
   - feature の purpose / goal / scope_in / scope_out / acceptance / depends_on / architecture_refs は同一だった。
2. **prompt は Layer 単位の抜粋で読まれている**
   - Layer 1 / 4 / 5 は読まれていない。ただし、出力 shape を定める Layer 2 は全件読まれているので、経路制約違反にはしない。
3. **macro report / publication report をまとめた成果物がない**
   - target・digest・write 0 の情報は tool 出力 (idx 219/225) と staging の現物にしかない。
   - pre-choice 契約の「現物 path・digest・開き方の提示 → choice 記録」も行われていない。これは task.md の「人間に質問しない」「DONE を 1 行だけ報告」と衝突するための省略と判断する。
4. **ready feature に対して `run-system-dev-plan` が起動されていない**
   - 全 feature が draft / unconfirmed / readiness incomplete のため、tracker 投影も per-feature planning も対象外になる。その条件は、各 feature の md の `## Handoff` 節に「confirmed/pass/readiness complete 後に ready となれば起動」と記録されている。
   - dry-run で parent_feature も確定していない。先例 gm4 と同じ扱いとし、今回の trial 条件 (macro 分解 + dry-run) の下では goal 未達としない。
5. **preview の時刻が実行時刻より後になっている**
   - preview の `created_at` / `updated_at` は `2026-10-04T10:30:00Z` で、実行時刻 (Write は idx 199–215 の 10:17–10:18Z) より後の値が埋め込まれている。preview の忠実性としては小さな瑕疵。
6. **pane に被験 skill と無関係なファイル更新が表示されている**
   - pane.txt / transcript の idx 51・100 に、無関係なファイルの更新表示 (`bashEditDiff`) がある。
     - `eval-log/ubm-goal-setting/run-ubm-consult/content-review/*-verdict.json`
     - 別 trial の `poll-state.json`
   - 該当コマンド (idx 50・99) はどちらも読取り専用 (`cat` / `--help` / validate)。表示されたのは、同じ時間帯に別プロセスが書いた変更である。本 trial の副作用ではない。
