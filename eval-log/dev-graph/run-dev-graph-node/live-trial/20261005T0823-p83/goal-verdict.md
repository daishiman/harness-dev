# goal-verdict: dev-graph:run-dev-graph-node (20261005T0823-p83)

VERDICT: PASS

## 根拠

被験 session の自己申告 (`out/status.json` = PASS) は使っていない。以下はすべて評価者が fixture の実体と plugin script を叩いて確かめた結果である。fixture への操作は読み取りと `--dry-run` だけで、複製もしていない。被験 session が scratchpad に残した更新前 snapshot (`.../b1ae671b-.../scratchpad/snap/`) を比較に使ったが、使う前に receipt の digest と照合し、本物の更新前状態であることを確かめた。

### 準備 (init と 5 kind の登録)
- `ls .dev-graph/state/receipts` の結果は `init-20261004T232447393768Z.json`、`node-r000001-add.json`、`node-r000002-update.json` の 3 件。
- `node-r000001-add.json` の中身: status=applied、applied_count=5、graph_revision 0→1、node_ids=[issue-login-timeout, task-extend-auth-timeout, spec-login-session, arch-auth-backend, doc-auth-runbook]。5 件とも classification.decision=auto で、confidence は 0.87 以上、margin は 0.47 以上。
- 現行の graph.json の nodes は issue / task / specification / architecture / document が 1 件ずつで、`tracker_binding` は 5 件とも `none`。
- `resolve-repo-context.py --repo-root <fixture> --mode read` は exit 0。repository_id `local:sha256:d0741c1e…` は config.json の repository_id とも、2 つの node receipt の repository_id とも一致した。

### 本題 1: 冪等な連続更新
- **apply が実際に起きたこと**: `node-r000002-update.json` は status=applied、operation=update、applied_count=1、graph_revision_before=1 / after=2。現行 graph.json は `graph_revision=2` で、その canonical digest (build-graph-node.py の `_canonical_digest` と同じ計算) を自分で計算すると `sha256:0c55023f…` になり、receipt の `graph_digest_after` と一致した。receipt の `input_sha256=cafb1cef…` も、`shasum -a 256 .dev-graph/cache/inputs/update-issue-append.json` の値と一致した。入力ファイルの中身は `expected_graph_revision: 1` と `append_sections: {"調査メモ": …}` だけである。
- **graph_node_id と file_path が変わっていないこと**: snapshot の `graph-r1.json` は、canonical digest が r1 receipt の `graph_digest_after` (`c3c3c226…`) と一致したので本物の r1 状態と判断した。これと現行 graph を比べると、issue は前後とも `issue-login-timeout` / `issues/login-timeout.md` で同じ。node のうち変わった field は `updated_at` と `implementation_readiness` (checked_at が変わっただけ) の 2 つだけだった。
- **本文が全置換されず、追記した section だけが増えたこと**: snapshot の issue ファイルの sha256 は r2 の `sha256_before` (`2e2f867d…`) と一致し、これは r1 の `sha256_after` とも同じだった。`diff` を取ると、本文の差分は末尾に追加された `## 調査メモ` とその本文 1 段落だけだった。frontmatter の差分は updated_at と readiness.checked_at の 2 行だけだった。更新前の本文は更新後の本文の先頭とバイト単位で一致し、見出しは 10 個から 11 個に増えた (増えたのは `## 調査メモ` だけ)。現行ファイルの sha256 は r2 の `sha256_after` (`1e5c0d30…`) と一致した。receipt にも `unmanaged_body_preserved=true` と `sections_replaced=[]` が記録されている。
- **他の 4 kind の node が無変更であること**: tasks / specs / architecture / docs の 4 ファイルは、現行の sha256 が r1 receipt の `sha256_after` と一致し、snapshot ともバイト単位で同じだった (`cmp`)。graph 上の 4 node の object も r1 snapshot と完全に一致した。graph のトップレベルで変わったのは `graph_revision` だけだった。

### 本題 2: feature を直接 add すると fail-closed になること
- **投入が拒否されたこと**: transcript では、被験 session が `--dry-run` を付けずに `build-graph-node.py add --input .dev-graph/cache/inputs/add-feature-direct.json` を実行している (`expected_graph_revision: 2`、`artifact_kind: "feature"`、classification は付いているが macro は無い入力)。その出力は `{"applied_count":0,"code":"feature_requires_c14_macro_contract","status":"rejected","valid":false,"write_count":0}` で exit=1 だった。評価者が同じ入力を `--dry-run` で投入し直しても、同じ code・status・applied_count=0・write_count=0 と exit=1 が再現した。拒否するコードは `build-graph-node.py` の `_reject_feature` (l.519-522) で、ここが実際に発火していることを確認した。
- **拒否後も features/ が 0 件で、graph が壊れていないこと**: `ls -la features` は空。graph.json に artifact_kind=feature の node は 0 件。receipt は r000002 までで、拒否された投入の receipt は作られていない。graph の digest は r2 receipt と同じままで、拒否の前後で変わっていない。評価者が dry-run を実行した前後でも graph.json のバイト列は変わっていない。

### 本題 3: 最終確認
- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph .dev-graph/state/graph.json --repo-root <fixture>` は exit=0 で、`valid: true`、`graph_validation.status=pass`、`violation_count=0` だった。

## 経路制約

- **Skill の起動**: transcript の idx36 で `Skill({skill:"dev-graph:run-dev-graph-init", …})`、idx81 で `Skill({skill:"dev-graph:run-dev-graph-node", …})` が実際に呼ばれ、それぞれ SKILL 本文が読み込まれている (idx38 と idx83)。
- **責務の代行**: なかった。init の書込みは `build-init-scaffold.py` (先に dry-run、その後 apply。2 回目は noop) を通している。node の add と update はどちらも `build-graph-node.py` を通し、先に `--dry-run` の preview を取ってから、そこで得た graph_revision_before (0 と 1) を `expected_graph_revision` に渡して apply している。session 内で書かれた inline python は、読み取りによる検証と、入力 JSON に `expected_graph_revision` を足す整形だけだった。整形は SKILL が skill 自身の役目として認めている範囲に入る。
- **graph / config / content への直接書込み**: なかった。Write tool の書込み先は `.dev-graph/cache/inputs/add-5kinds.json` (writer に渡す入力) と `out/status.json` の 2 か所だけ。Edit tool は `add-5kinds.json` だけ。Bash の heredoc で書いたのも入力 JSON 2 件だけだった。graph.json に触れた操作は scratchpad への `cp` (読み取り) だけである。
- **subagent (Agent tool)**: 0 回。SKILL.md の `artifact_delivery.pre_choice_forbidden` は利用者の選択前に subagent を使うことを禁じている。Agent による fork は light / standard / detailed を選んだ後の goal-seek でだけ求められる。この trial は人間に聞かずに最後まで進む条件なので、accept-as-is の経路になる。したがって Agent を起動していないのは SKILL の要求どおりである。
- **責務 prompt を先に読んだか**: init の R1〜R5 は idx49 で全文 `cat` しており、R1 を実行した idx59 より前である。node の R0〜R4 は idx86 で読んでおり、入力を作った idx114 より前である。
- **external mutation guard**: preview は発行していない。guard で Bash が塞がれたことも無い。
- **out/ への書込み**: `status.json` だけ。
- **人間への問い合わせ**: AskUserQuestion は 0 回。最初の指示以外に人間からの入力は無い。

### 判定に影響しない観察
1. node の R0〜R4 prompt は `sed` で Layer 2/3/6 などを抜き出して読んでおり、Layer 1、Layer 5、出力指示は読んでいない。ただし各 prompt の出力指示は Layer 2 を正本と定めており、Layer 5.3 の checklist は Layer 2 の受入条件と同じ文面である。規範になる内容は読めていると判断した。
2. node skill について、accept-as-is を選んだことを明示した発言は無い (init では idx80 で明示している)。
3. 準備で登録した task / specification / architecture / document の 4 node は readiness が `incomplete` のままである (`readiness_fill` は返されたが埋めていない)。ただし見出しは template どおりにすべて揃っており (OUT2 の「見出し欠落 0」は満たす)、schema 検証も pass している。task.md の検証項目にも含まれていない。

## blocker

なし

gate_response_count: 0
