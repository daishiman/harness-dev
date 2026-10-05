# goal-verdict: dev-graph:run-dev-graph-render (20261005T1500-p83m)

VERDICT: PASS

## 根拠

judge は fixture を書き換えず、複製もせずに確認した。graph は元の場所から読んでいる。plugin script も編集していない。決定論の再 render は、fixture 内の graph を `--graph` に渡し、`--out` を judge の scratchpad (`.../scratchpad/judge-render-p83m/{a,b}/index.html`) にして実行した。

### 0. 前提: 入力 graph が C11/C24 を通り、変更されていない
- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <F>/.dev-graph/state/graph.json --repo-root <F>` の結果は `valid: true`、`violation_count: 0`、`node_readiness.complete: 15`、rc=0。
- `python3 plugins/dev-graph/scripts/resolve-repo-context.py --repo-root <F> --mode read` は rc=0。`repo_root` と `content_roots.repository` は同じ path (`<F>`) だった。`repository_id` は `local:sha256:a39167ca…db6c2f` で、`config.json` の `repository_id` と一致した。
- `shasum -a 256` で、graph.json (`2ed57eab…932fd0b`)、config.json (`6514f712…`)、package-registration-receipt (`cba8ce0d…`) を測った。3 つとも元 fixture `gm4b-render` の同名ファイルと同じ digest で、被験 session の前後で graph・config・receipt は変わっていない。
- `find <F> -newer <F>/.git -type f` で、trial 開始後に変わった file を調べた。出てきたのは `.dev-graph/render/index.html` と、SKILL.md のゴールシーク配線が指定する `eval-log/run-dev-graph-render-{goal-spec.json,progress.json,intermediate.jsonl}` だけだった。

### 1. 外部 resource 参照が 0 件で、feature / task / edge が inline SVG で描かれている → 一致
`<F>/.dev-graph/render/index.html` を python の正規表現で走査した。
- 次の件数はすべて 0 件: `<script src=`、`<link`、`http(s)://`、`src=` / `href=` 属性、`@import` / `url(`、`cdn|npm|unpkg|jsdelivr`、`<iframe|img|object|embed|use>`。
- `<svg>` は 1 個。inline の `<script>` (src 無し) が 1 個あり、ほかに `application/json` の data script が 1 個ある。
- SVG 内の `<g class="node">` は 15 個で、id は重複していない。この id の集合は graph の `graph_node_id` 15 件と一致した。kind の内訳は architecture 1、feature 1、task 13。
- SVG 内の `<path>` は 12 本で、重複は無い。graph の `depends_on` から期待される path 文字列を作り直すと、集合として完全に一致した。feature 同士の edge は 0 本で、12 本すべてが P01→…→P13 の task 内 edge。
- 補足: 被験の R3 subagent が撮った headless Chrome (network 遮断) の screenshot (`.../eb09355d…/scratchpad/shot.png`) を Read で目視した。SVG と `active · feature · 5/13` の表示を確認できた。

### 2. `LT-FEATURE-001` の X/13 と parent_feature 由来の実数が graph 実値と一致する → 一致
- graph.json で `parent_feature == "LT-FEATURE-001"` の node を数えると 13 件 (P01..P13、すべて artifact_kind=task) で、そのうち status=done は 5 件 (P01..P05)。
- HTML 上の feature pill は `active · feature · 5/13`。埋め込み JSON の `LT-FEATURE-001.progress` は `{"done":5,"total":13}`。
- judge が再 render したときの stdout receipt は `nodes:15`、`edges:12`、`feature_progress.by_feature.LT-FEATURE-001 = {done:5,total:13}` で、graph 実値と一致した。

### 3. registration receipt の applied_count/expected_count と source_digest が表示内容・graph 実値と一致する → 一致
- receipt (`package-registration-receipt-LT-FEATURE-001.json`) は `applied_count: 13`、`expected_count: 13`、`parent_feature: LT-FEATURE-001`。
- receipt の `node_ids` (P01..P13 の 13 件) は、graph の parent_feature=LT-FEATURE-001 の task 集合と完全に一致した。表示の分母 13 は applied/expected の 13 と一致する。
- receipt の `source_digest` は `sha256:d85dfa3dc8b6…7e84`。
  - `shasum -a 256 .dev-graph/cache/system-dev-planner-handoff/feature-execution-package.json` の結果は `d85dfa3dc8b6…7e84` で、一致した。
  - graph.json で値に `d85dfa3d…` を含む field を python で全走査した。13 個の task node すべてで `source_lineage.source_digest` と `confirmation_evidence.evaluated_digest` がこの値で、合計 26 箇所だった。全 task 一致。
- 指示どおり、HTML 上に digest が表示されているかどうかは判定に使っていない。
- 参考 (判定対象外): receipt の `graph_digest_after` (`8a3f687e…`, revision 2) は今の graph.json (revision 3) の digest と一致しない。登録後に P01..P05 を done にしたことによる、予定どおりの差分。

### 4. 2 回 render して出力 digest が一致する (決定論) → 一致
- `python3 plugins/dev-graph/scripts/render-graph-html.py --graph <F>/.dev-graph/state/graph.json --out <scratch>/a/index.html` と、同じ graph を `--out <scratch>/b/index.html` にした 2 回目を実行した。
- 2 回とも `input_sha256 = 2ed57eab…932fd0b` (現在の graph.json の sha256 と一致) で、`output_sha256 = c4bf5ed6a687d824cfd30f3ffb5c87f530d05ac645370b836c78bc180d7eb838`。
- 被験 session が出力した `<F>/.dev-graph/render/index.html` の sha256 も `c4bf5ed6…eb838` で、`cmp` でも byte 単位で同一だった。3 つの出力の digest がすべて一致する。

### 5. checklist が PARTIAL ではない → 一致
- `<F>/eval-log/run-dev-graph-render-progress.json` を見ると、完了チェックリスト 5 項目はすべて `status: pass` で、`criteria` は `IN1: pass`、`OUT1: pass`。pending・partial・fail は 0 件。
- 各項目の evidence は、上の 1〜4 で judge が確かめた実値 (15 node、12 edge、5/13、13/13、d85dfa3d、2ed57eab、c4bf5ed6) と矛盾しない。
- SKILL.md の「ゴールシーク検証」の python 検査を judge が goal-spec.json と intermediate.jsonl に対して流し直し、`goal-seek verify OK` を得た。original_goal_hash は一致し、必須 key もそろっている。

## 経路制約

- **Skill 起動**: transcript の tool_use #4 で `Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root <F> --output <F>/.dev-graph/render/index.html"})` が実際に呼ばれ、`Launching skill` が返っていた。args は task.md の指定と同一。task.md が要求する dev-graph skill はほかに無い。
- **責務 prompt の事前読込**: #5 で `prompts/R1-elicit.md`、`R2-plan.md`、`R3-render.md` を全文 cat している。これは render 出力を作った #8 より前。R2/R3 subagent も、最初の tool call でそれぞれの `prompts/R*.md` と `references/prompt-common-layers.md` を読んでいる (subagent transcript `agent-af3dadd0d97e04a87.jsonl` と `agent-a847b1f68e17e836a.jsonl` の #1)。
- **代行実装の有無**: 無い。HTML を作ったのは plugin の `render-graph-html.py` だけで、main の #8 と R3 subagent の再 render の 2 回。自作の renderer や model 生成 script は無い。python heredoc は 2 種類だけで、ひとつは読み取り専用の検査、もうひとつは SKILL.md が指定するゴールシーク記録 (`eval-log/run-dev-graph-render-*.json(l)`) の書き込み。R3 subagent の JS 動作 probe は、HTML の写しを subagent 側の scratchpad に置いて行っており、fixture には書いていない。
- **graph / config / receipt への直接書き込み**: 無い。Write tool の呼び出しは `out/status.json` の 1 回だけで、Edit は 0 回。graph.json、config.json、receipt の digest は元 fixture と同一 (根拠 0)。
- **subagent 起動**: SKILL.md のゴールシーク配線は「未達 responsibility の prompt を読み、Agent で分離 context に fork する」と定めている。被験は R2-plan (#11) と R3-render (#12) を Agent tool (general-purpose) で起動し、両方とも完了通知と結果を受け取ってから progress を確定した。R1-elicit (C24/C11 の確定と出力 path の確定) は、Pre-choice 区間 (`pre_choice_forbidden: subagent`) に main context で実施しており、SKILL.md の state machine と矛盾しない。render SKILL.md は、これ以外の独立 auditor / verifier の起動を要求していない。
- **注記 (blocker ではない)**:
  - artifact-delivery の `user_choice` は人間に聞かず、`standard` を自律的に記録した (`choice_source: autonomous trial instruction`)。これは task.md の「人間に質問せず自走」に従った扱いで、選んだのは accept-as-is より手順を多く実行する側なので、省略にはあたらない。
  - 終了直前の #16/#17 は、hook が注入した `skill-governance-adapters/.../build-external-intelligence-runtime.py` の finish 呼び出しで、`invalid_request` で失敗している。skill の範囲外で、fixture にも成果物にも影響しない。

## blocker

なし

gate_response_count: 0
