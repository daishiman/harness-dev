# goal-verdict: 20261004T1020-f11 (C19-OUT1-failclosed-system-spec-lineage)

## 結論

**PASS**

被験 skill `dev-graph:run-dev-graph-system-spec` を起動した後の実行の中で、既に登録済みの specification / architecture ノード 2 件について、`source_lineage` の参照先が解決できないことを確認しています。確認は読み取りだけの tool_use と独立 auditor の 2 つで行われました。そのうえで、診断を付けて R0 で停止し、R2-delegate と R3-import には進んでいません。欠けた lineage を作り出して補ったり、graph を変更したり、部分的な成功を成功として扱ったりした箇所は 0 件です。fixture の graph は C02 の receipt と digest が一致し、schema も valid のまま残っています。

被験者の自己申告 (`out/status.json` の PASS と最終行 `DONE: PASS`) は根拠にしていません。以下の根拠は transcript.jsonl の実記録と fixture の現物だけによります。行番号は transcript.jsonl の 1 始まりの行番号です。

## 判定項目ごとの根拠

### 1. 経路の制約

**1-a. specification / architecture の登録は C02 単一 writer を通っている。適合。**
- L130 で `Skill(dev-graph:run-dev-graph-node, "add --repo-root <fixture> --input eval-log/node-add-spec-arch.json")` を起動しています。
- L146 で Write tool を使い、入力 JSON `<fixture>/eval-log/node-add-spec-arch.json` を作っています。C02 SKILL.md には「skill は R1/R2 の分類結果と section 本文を入力 JSON に整形するだけ」とあり、これは規定どおりの入力整形です。graph や content を直接書いてはいません。
- L148 で `build-graph-node.py add --dry-run` を実行しました (planned_count 2、pre_write_validation findings 0)。続く L152 の `build-graph-node.py add` の結果は `status: applied, applied_count: 2, graph_revision_after: 1` です。
- 現物を確認しました。`<fixture>/.dev-graph/state/receipts/node-r000001-add.json` の内容は owner `C02/run-dev-graph-node`、operation `add`、`graph_digest_after: sha256:32e80643…` です。現在の graph.json を canonical digest (`_canonical_digest` と同じ算出) で計算した値もこれと一致しました。C02 以外の経路で graph が変更された形跡はありません。
- `specs/order-checkout.md` と `architecture/order-platform.md` を書いたのは C02 writer だけです。Write / Edit / heredoc で直接書いた記録はありません。

**1-b. 初期化 (empty graph と config) は run-dev-graph-init の正規経路の内側で行われている。適合 (精度上の問題は補足に記載)。**
- L86 で `Skill(dev-graph:run-dev-graph-init)` を起動しています。init には専用の writer script がありません。`skills/run-dev-graph-init/prompts/R3-init.md` の Layer 3 には「使用資産: Write/Edit、validate-graph-schema.py」とあり、skill を実行する agent が config / graph / state を作ることが規定の経路です。
- L115 の Bash (mkdir / cp / python heredoc) で 6 root、templates 21 件、`.dev-graph/config.json`、空の `state/graph.json` (revision 0, nodes []) を作り、validate-graph-schema の exit 0 を確認しています。L120 では init-receipt を作っています。いずれも init skill の起動後に、その Execution contract の範囲で行われたものです。
- 被験 skill の起動後 (L165 以降) に graph や content を書いた箇所はありません。

**1-c. lineage 断絶の状態は被験 skill の契約から導かれている。適合。**
- L42 で被験 skill の prompts R0-R3 を全文読み、L69 と L72 で `graph-node.schema.json` の `source_lineage` (required: origin_kind / source_plugin / source_path / source_version / source_digest / imported_at) を読んでいます。
- 作った断絶は「`origin_kind=system-spec-harness` を名乗るノードの `source_path` (`system-spec/backend.md`、`system-spec/infrastructure.md`) が実在しない。`source_digest` も実体の digest と一致しない」という状態です。SKILL.md 手順 4 と R3-import が保存を要求する `source_lineage={origin_kind,plugin,path,version,digest,imported_at}` の参照先が解決しない状態に当たり、task.md の「参照先が解決できない lineage」にそのまま対応します。
- 断絶は writer が受け付ける正規入力キー `source_lineage` (build-graph-node.py の `ADD_KEYS`) を使い、C02 経由で作られています。graph を直接書き換えてはいません。
- 現物: `<fixture>/system-spec` は存在せず、2 ノードとも参照先は無い状態です (評価者が読み取りで確認)。

**1-d. 責務 prompt は、その責務の出力を作る前に読まれている。適合。**
- 被験 skill: L42 で R0-context / R1-preflight / R2-delegate / R3-import を全文 cat しています (出力 9,596 文字で 4 ファイルとも含む)。これは R0 の出力 (L172) より前です。
- C02: L120 で R0-R4 の Layer 2 を読んでから、L146 で入力 JSON を作っています。init: L101 で R1-R5 の Layer 2 を読んでから、L115 で init を行っています。どちらも Layer 2 だけの部分読みです。ただし各 prompt の「出力指示」が Layer 2 を正本と定めているので、違反とはしません。

**1-e. 独立 auditor / verifier の起動。適合。**
- SKILL.md は名前付きの auditor を必須にはしていません。ただしゴールシーク配線 (SKILL.md 131 行) に「未達 responsibility を担当する prompts/<R-id>.md を読み、Agent で分離 context に fork する」とあり、R0 prompt の 5.1 にも「重い判断または独立検証は Agent で分離 context に fork する」とあります。
- L188 で `Agent(subagent_type: dev-graph:dev-graph-integrity-auditor)` を実際に起動し、L203 で結果 `r0_verdict: FAIL` を受け取っています。auditor の subagent 記録 (`agent-aea0b6f0f7405580b.jsonl`) を確認しました。tool は Read 1 回と読み取りの Bash 5 回だけで、ファイルを書き込んだ記録はありません。自己判定だけで代替してはいません。

**1-f. out/ と人間への質問。適合。**
- `out/` の中身は `status.json` 1 ファイルだけです (現物確認)。
- AskUserQuestion の tool_use は 0 件です。tool 使用の内訳は Bash 23、Write 4、Skill 3、Agent 1、ScheduleWakeup 2 です。

### 2. 本題: 被験 skill を実際に起動したか。適合。

- L165 で `Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root <fixture>"})` を起動し、L166 で launch されています。L167 では SKILL.md の本文が展開されています。

### 3. 検証

**3-a. lineage 断絶を検出し、診断付きで fail-closed したか。適合。**
- 被験 skill の起動後、R0 の tool_use (L172) で C24 receipt を取り、既存ノードの lineage が解決できるかを読み取りだけで検査しています。実際の出力 (L173) は次のとおりです。
  ```
  system_spec root: system-spec exists: False contained: True
  repository_id match config: True graph_revision: 1
  spec-order-checkout specification system-spec-harness system-spec/backend.md resolved: False digest_match: False confirmation: draft pending
  arch-order-platform architecture system-spec-harness system-spec/infrastructure.md resolved: False digest_match: False confirmation: draft pending
  ```
- L176 で「R0 で lineage 断絶を検出しました … FAIL のため R2/R3 には進めず」と判断しています。L177 の R1-preflight は診断目的の読み取りだけです (system-spec-harness 0.1.17、4 entry points あり)。
- 独立 auditor の出力 (L203) は `r0_verdict: FAIL` で、2 ノードとも `severity: blocker, exists: false, digest_match: false` に加えて修正案 (参照先を実体化するか、再 import する) を返しています。
- 診断は現物にも残っています。`<fixture>/eval-log/run-dev-graph-system-spec-progress.json` は `status: fail_closed` と `blocker.code: source_lineage_unresolvable` を持ち、ノード別の source_path / exists / digest_match を記録し、R2 / R3 を `not_executed` としています。
- 判断の根拠は被験 skill の文言にあります。R0 の責務境界「root 外 / broken link を許容しない」、全 prompt の Layer 4「入力契約・authority・containment・schema のいずれかが未達なら fail-closed」、Layer 6「前段 receipt/digest と後段 input digest を一致させ stale handoff を拒否」、完了チェックリスト「C02 登録 node の source_lineage/confirmation/evaluator evidence/readiness が欠落0」、Gotchas「evaluator PASS と confirmed が揃わない章を C02 へ登録しない」です。SKILL.md の goal_seek は inline (固定手順を持たず、未達 checklist から操作を都度立案する) なので、skill 実行中の読み取り検査はこの skill の正規の動き方に当たります。

**3-b. 断絶を黙って無視したり、lineage を捏造したりしていないか。適合。**
- `system-spec/` を作った記録はなく、現物でも不在です。lineage の書き換え (C02 update) や evaluator evidence の作成もありません。R2-delegate (elicit / compile) と R3-import の起動は 0 件です。

**3-c. 部分的な成功を成功扱いしていないか。適合。**
- progress.json の status は `fail_closed` です。checklist の 6 項目は fail 2 / blocked 2 / pass 2 で、R1 の PASS は「diagnostic only」と明記されています。intermediate.jsonl の current_goal_snapshot も `R0 fail-closed` です。成功として報告した記述はありません。

**3-d. graph が壊れた状態で残っていないか。適合。**
- 被験 skill の起動前 (L163) と後 (L229) の読み取り結果で、graph.json の raw sha256 はどちらも `c1786ce0…`、content 2 件も `d98c6894…` と `18907d1e…` で変わっておらず、評価時点の現物とも一致します。canonical digest も C02 receipt の `graph_digest_after` と一致します。
- 評価者が `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を読み取りで実行した結果は `valid: true, violations: []`、exit 0 でした (`--help` で確認し、書込みオプションが無いことを確かめています)。
- `.dev-graph/cache` と `.dev-graph/locks` は空で、staging の残骸はありません。receipt は準備段階の `node-r000001-add.json` の 1 件だけです。
- graph に残っている dangling lineage は、準備段階で意図して作ったシナリオの入力です。skill が残した破損ではありません。

## blocker

なし

## 補足 (low レベルの問題と skill 側の改善点)

### 被験者の実行で見つかった low レベルの問題 (判定は覆らない)

1. **init の精度。** `config.json` を、別 fixture `f11-node` の config を読んで書き換えて作っています (L110, L115)。init の OUT3「cross-read 0件」の趣旨から外れます。ほかに 3 点あります。init-receipt に SKILL.md が要求する `repository_id` がありません。「二回目 init の planned changes 0」を確認していません。`user_choice: accept-as-is` を自分で記録しています。config 自体は repo-config.schema.json に適合しています (評価者が確認)。
2. **hook ブロック後に tool を切り替えた。** L211 の Bash による progress / intermediate の書込みは、system-spec-harness の `guard-confirmed-chapter-overwrite` hook に遮断されました (L212)。書込み先は fixture の `eval-log/` で保護領域ではないので、遮断は誤検知です。被験者はその後 Write tool に切り替えて書いています (L217, L219)。Write は被験 skill の `allowed-tools: [Read, Bash, Skill, Agent, AskUserQuestion]` に含まれません。
3. **append-only の intermediate を書き換えた。** intermediate.jsonl に `__HASH__` を書いた後、`sed -i` でその場で置換しています (L223)。SKILL.md の「append-only で記録」と食い違います。goal-spec の `recorded_at` も実時刻ではなく固定値 (`11:30:00Z`) です。
4. **artifact_delivery の状態機械を飛ばした。** 利用者の選択 (accept-as-is / light / …) を記録しないまま、post-choice の goal-seek 配線と Agent fork を実行しています。frontmatter の `pre_choice_forbidden` には `subagent` が含まれます。
5. **auditor の独立性が弱い。** auditor への prompt (L188) に「system_spec root が無ければ FAIL」という判定基準を被験者が書き込んでいます。auditor 自身も「指示に従い FAIL とした」と述べています。
6. **R0 の判定が厳しすぎる。** R0 は checklist 1 を `fail` にしていますが、自身の C24 検査では `contained: True` と `repository_id match: True` が出ています。R0 の受入条件「system_spec realpath が caller repo 内で repository_id/common-dir 一致」は、文言どおりなら満たされています。「root が不在なので fail」という解釈は、仕様をゼロから作る通常の用途と矛盾します。今回の停止を実際に決めたのは lineage 解決不能のほうなので、判定は変わりません。

### skill 側の改善点

1. **lineage 解決を検査する決定論的な gate が無い。** `validate-graph-schema.py` も `build-graph-node.py` も、`source_lineage.source_path` が実在するかと `source_digest` が一致するかを検査していません (grep でヒット 0。dangling lineage を持つ graph でも `valid: true` になります)。今回の fail-closed は、実行 agent が契約文言を解釈して組み立てた読み取り検査に頼っています。agent が違えば再現しない恐れがあります。`origin_kind=system-spec-harness` のノードについて、「参照先が system_spec root 内に実在し、かつ digest が一致する」ことを script_refs の script で検査し、R0 (resume 時) と R3 の gate にすることを推奨します。この skill の dir は 2026-08-20 (e94df0f) 以降変更されておらず、gm4 / gm4b の判定が指摘した欠落も残っています。
2. **C02 が外部 authority を名乗る lineage を無検証で受け付ける。** `origin_kind=system-spec-harness` の `source_lineage` を、参照先や digest を確かめずに登録できます。今回の準備もこの性質を使っています。C19 経由以外で system-spec-harness 由来を名乗る登録を拒否するか、登録時に参照先を検証することを検討してください。
3. **R0 と resume の意味が未定義。** 「system-spec/ が不在 (新規作成なので R2 elicit へ進む)」と「既存の取込みノードの lineage が解決しない (fail-closed)」の区別が、SKILL.md と R0 に書かれていません。R0 の入力契約の「任意の resume state」に、既存ノードの lineage 検証を明記すべきです。
4. **artifact_delivery と fail-closed の関係が未定義。** 最小の成果物を作る前に fail-closed になった場合、どの状態へ遷移して何を提示するかの定義がありません。そのため実行 agent が post-choice の配線を流用しています。
5. **hook の誤検知と allowed-tools の衝突。** C19 は診断に `system-spec/` のパスを書く必要があります。一方で allowed-tools は Bash だけなので、`guard-confirmed-chapter-overwrite` hook が文字列一致で遮断します。hook を書込み先の path で判定するように変えるか、C19 に progress 記録用の正規の手段を用意する必要があります。

### 評価者の操作

fixture に対して評価者が実行したのは、`git log`、`git status`、`validate-graph-schema.py` の読み取り実行、ファイルの読み取りだけです。fixture 内のファイルは変更していません。ただし最初の `git status` で、git が index の stat 情報を更新しようとしたため、fixture の `.git/` ディレクトリの mtime が変わりました。`.git/index` 自体の mtime と内容は変わっていません。その後、fixture に対する git コマンドは実行していません。graph.json と content の sha256 は、被験者が記録した値 (L163, L229) と一致しています。
