# goal-verdict: dev-graph:run-dev-graph-node (20261004T2237-f11r4)

VERDICT: PASS

- `L<n>` は transcript.jsonl の 1 始まりの行番号を指す。前々回 (f11r3) の判定は 0 始まりなので、行番号はそのまま比べられない。
- out/status.json の自己申告 (`PASS`) と、最後の `DONE: PASS` (L179) は根拠にしていない。
- f11r3 の結論は引き継いでいない。transcript の全 tool_use 24 件 (Bash 20 / Skill 2 / Write 2。Edit・AskUserQuestion・Agent は 0 件) を機械的に走査した。そのうえで、fixture の実物 (graph・receipt・本文・入力 JSON) を評価者が独立に突き合わせた。
- 被験者が使った writer は repo 側の `plugins/dev-graph/scripts/build-graph-node.py` である (L138 / L142 / L148 / L156 / L166 / L171 で `P=/Users/dm/dev/dev/個人開発/harness/plugins/dev-graph`)。評価者が確かめた結果は次のとおり。
  - インストール済みの `~/.claude/plugins/cache/harness-local/dev-graph/0.1.13/scripts/build-graph-node.py` とバイト単位で同一だった (sha256 `6e747381…`)。
  - repo 側の mtime は 22:09:22 で、trial の開始 (22:37) より前である。trial 中に writer は変わっていない。
  - `validate-graph-schema.py`・`_common.py`・`resolve-repo-context.py`、node の `SKILL.md` と `prompts/R0〜R4`、`schemas/` も 0.1.13 と同一だった。

## 結論

PASS。5 つの判定項目すべてを、transcript と fixture の実物で確認できた。

- graph・content・receipt は、init の正規経路 (空 graph store の scaffold) と C02 単一 writer (`build-graph-node.py add|update`) だけで書かれている。
- 本題 1 (issue への 1 section 追記の apply)、本題 2 (feature 通常入力の writer への投入と拒否)、本題 3 (最終 graph の schema 検証) は、いずれも実際に実行されている。
- receipt の `input_sha256`・`sha256_before/after`・`graph_digest_after` が、fixture に残る入力 JSON・本文・graph と鎖のように一致した。改ざんや手書きの痕跡は無い。

今回は writer に placeholder 判定と feature projection の再投影の変更が入った後の再実走である。この 2 つの変更は、本題の結果を変えていない。

- 本題 1 の update では、writer が placeholder の 7 section を `readiness_fill` (`via: set_sections`) として返しただけで、本文には触れていない。
- 本題 2 の拒否メッセージは、新しい経路 (`macro{...}` 付きの add) を案内する文言に変わった。macro の無い通常入力が拒否される点は変わらない。

## 判定項目ごとの根拠

### 1. 経路の制約: PASS

#### 書込みを伴う操作の全件

Write 呼び出しと、Bash 内の `mkdir` / `cp` / `tee` / リダイレクト / heredoc / `open(...,'w')` を全件抽出した。

| L | 操作 | 書込み先 | 判定 |
|---|---|---|---|
| L98 | Bash: `mkdir -p`、`.gitkeep`、python heredoc (`open(dst,"w")`)、`printf … >`、templates の欠落分だけ `cp` | 6 root、`.dev-graph/{state,cache,locks,templates}`、`.dev-graph/config.json`、`.dev-graph/state/graph.json` (`{"graph_revision": 0, "nodes": []}`) | init の正規経路。init には専用 script が無く、SKILL.md の Execution contract 2・3 と R3-init の出力契約 (config/graph/state/cache/locks を作る) に当たる。graph は空の初期 store で、node は 1 件も書いていない。手段が Write ではなく Bash だった点は補足 2 に記す |
| L134 | Write | `.dev-graph/cache/inputs/add-5kinds.json` | writer への入力 JSON |
| L142 | python heredoc (`open(...,'w')`) と writer 出力のリダイレクト | `cache/inputs/add-5kinds-apply.json` (入力に `expected_graph_revision: 0` を足しただけ)、`cache/add-result.json` (writer の stdout) | 入力 JSON と、writer の結果の保存。graph・content・receipt ではない |
| L148 | `mkdir` / `cp`、heredoc、python (`open(...,'w')`) | `cache/snap-r1/` (本文 5 件と graph のコピー)、`cache/inputs/update-issue-append.json`、`cache/inputs/update-issue-append-preview.json` | 比較用スナップショットと入力 JSON。fixture の cache 内である (補足 6) |
| L156 | writer 出力のリダイレクト | `cache/update-result.json` | writer の結果の保存 |
| L166 | `cp`、heredoc、`tee` | `cache/graph-before-feature.json`、`cache/inputs/add-feature-direct.json`、`cache/feature-reject.json` | スナップショット、入力 JSON、拒否出力の保存 |
| L176 | Write | `out/status.json` | 規定の完了マーカー |

- 上の表以外で graph・content・receipt に書いたのは writer だけである。
  - L142 `build-graph-node.py add` (applied)
  - L156 `build-graph-node.py update` (applied)
  - L166 と L171 `build-graph-node.py add` (feature 入力。2 回とも rejected)
- receipts/ の 2 ファイルは writer の実行結果 (L143 / L157) の `receipt_path` と一致する。さらに、各 receipt の `input_sha256` は、writer に渡した入力ファイルの sha256 と一致した。
  - `node-r000001-add.json` の `fc79ea81…` は `add-5kinds-apply.json` と一致
  - `node-r000002-update.json` の `34f5e6ea…` は `update-issue-append.json` と一致
  - 被験者が receipt を書いた形跡は無い。
- 読み取り目的の python は L65 / L93 / L103 / L138 / L156 の後半 / L166 の後半にある。いずれも json の表示・`jsonschema.validate`・`difflib`・`cmp` による検証である。

#### 責務 prompt を出力の前に読んだか

- init:
  - L51 で `cat skills/run-dev-graph-init/prompts/*.md` を実行し、R1〜R5 を全文読んでいる。
  - init の出力 (L98) より前である。
- node:
  - L112 → L118 で、R0〜R4 の Layer 2 (入力契約・出力契約・責務境界・受入条件) を `sed` で読んでいる。
  - 最初の入力 JSON (L134) より前である。
  - Layer 1 と Layer 3〜7 は読んでいない (補足 3)。ただし、各 prompt の「出力指示」は Layer 2 を正本と定めている。読まなかった層で責務に固有の指示は Layer 3 の 3 点だけで、どれも SKILL.md (L66 → L73 で全文読了) 118 行目・131 行目・195 行目に同じ内容がある。
    - R2: preview は `--dry-run`
    - R3 / R4: graph・content・receipt を Write/Edit や自作 script で直接書かない
  - 被験者はこの 3 点とも守っている。そのため違反とは扱わない。

#### その他の制約

- external mutation guard の preview は発行していない。
  - `build-external-*`・`gh`・`bd` の呼び出しは 0 件である。
  - L15 の hook (external-intelligence-runtime の候補提示) にも反応していない。
  - pending guard context による Bash の遮断も起きていない (pane.txt にも遮断の表示は無い)。
- out/ には `status.json` の 1 ファイルしか無い (評価者が `ls` で確認)。
- 人間への質問は無い。AskUserQuestion は 0 件である。

### 2. 準備: PASS

- L39 で `Skill dev-graph:run-dev-graph-init` を実行し、L108 で `Skill dev-graph:run-dev-graph-node` を実行している。
- init の検証:
  - L99: `validate-graph-schema.py` exit 0
  - L104: `jsonschema` による config の検証が OK、2 回目の init で予定される変更 0、`.claude/` は無し (hook_source=plugin で fallback は書いていない)、config に絶対 path 0 件
- 5 kind の登録:
  - L138 → L139: `--dry-run` の結果は `preview`、`graph_revision_before: 0`、planned 5
  - L142 → L143: 本実行の結果は `status: applied`、`applied_count: 5`、`graph_revision_after: 1`、receipt は `node-r000001-add.json`
  - 分類はどれも `decision: auto` で、confidence は 0.88〜0.92、第二候補との差 (margin) は 0.80〜0.87 だった (L134 の入力)。
- 実物の確認 (評価者):
  - `.dev-graph/state/graph.json` の 5 node は、issue / task / specification / architecture / document が各 1 件だった。
  - 5 node とも `tracker_binding: "none"` である。入力 `add-5kinds.json` の 5 件も、すべて `"none"` だった。

### 3. 本題 1 (issue への 1 section 追記の apply): PASS

- 入力 `cache/inputs/update-issue-append.json` (L148) の中身:
  - `expected_graph_revision: 1`
  - `updates[0]` は `graph_node_id: issue-login-timeout` と `append_sections: {"暫定回避策": …}` だけである。
- 実行:
  - L148 → L154: `--dry-run` の結果は `preview`、`graph_revision_before: 1`、planned 1
  - L156 → L157: 本実行の結果は `status: applied`、`applied_count: 1`、`graph_revision 1 → 2`、receipt は `node-r000002-update.json`
- apply の発生 (評価者が実物で突合):
  - `receipts/node-r000002-update.json` の中身は次のとおりだった。
    - `operation: update`、`graph_revision_before 1 / after 2`
    - `sections_appended: ["暫定回避策"]`
    - `sections_replaced: []`、`sections_regenerated: []`、`node_fields_patched: []`
    - `unmanaged_body_preserved: true`
  - 最終 graph の `graph_revision` は 2。
  - 最終 graph の canonical digest を writer の `_canonical_digest` と同じ方法 (`sort_keys`、区切り詰め) で計算すると `sha256:5ed89f8a…` になった。update receipt の `graph_digest_after` と一致する。
  - 更新前のスナップショット `cache/snap-r1/graph.json` の canonical digest は、add receipt の `graph_digest_after` (`d9391977…`) と一致した。スナップショットが本物の revision 1 であることの裏付けになる。
- id と path は不変である。
  - graph でも、本文の frontmatter でも、更新前後とも `graph_node_id: issue-login-timeout` と `file_path: issues/login-timeout.md` のままである。
  - graph node で変わったフィールドは `updated_at` と `implementation_readiness` (中身は `checked_at` だけ) の 2 つである。
- 本文は全置換されていない。sha256 の鎖は次のとおり。
  - add receipt の issue の `sha256_after` (`b49a315b…`) = update receipt の `sha256_before` = `snap-r1/login-timeout.md` の sha256
  - 現在の `issues/login-timeout.md` の sha256 = update receipt の `sha256_after` (`de27815c…`)
  - snap-r1 と現在の本文を評価者が diff すると、変化は 3 か所だけだった。
    - frontmatter の `updated_at` 1 行
    - frontmatter の `implementation_readiness` の `checked_at` 1 行
    - 末尾の `## 暫定回避策` と本文 1 段落の追加 (`@@ -96,0 +97,4 @@`)
  - 既存の見出し 10 個 (`# 概要` から `## 検証証跡` まで) は順序も内容もそのままで、最後に `## 暫定回避策` が 1 つ増えただけである。
- 他 4 kind は無変更である。
  - 本文: 現在の sha256 が、add receipt の `sha256_after` と 4 件とも一致した (task `63441303…`、spec `27e045a7…`、architecture `e23cd75e…`、doc `acb5a5bd…`)。
  - graph node: snap-r1 との差分は 4 件とも 0 フィールドだった。`updated_at` も add 時刻 (`13:39:25.033023Z`) のままである。

### 4. 本題 2 (feature 入力の writer 投入と拒否): PASS

- 入力 `cache/inputs/add-feature-direct.json` (L166) の中身:
  - `artifact_kind: "feature"` を含む通常の add 入力である (classification の `decision: auto` と sections を持つ)。
  - `macro{...}` も C14 package 用のキー (`parent_feature` / `feature_package_id` / `phase_ref`) も含まない。
  - `expected_graph_revision` は 2。
- 投入: L166 と L171 の 2 回、通常の add と同じ `build-graph-node.py add` に実際に渡している。
- エラー出力そのもの (L167。fixture の `cache/feature-reject.json` にも同じ内容が残っている):

  ```json
  {
    "applied_count": 0,
    "code": "feature_requires_c14_macro_contract",
    "error": "feature nodes are declared by the C14 macro contract (add with artifact_kind=feature and macro{...}); R1/R2 routing never yields them",
    "findings": [],
    "status": "rejected",
    "valid": false,
    "write_count": 0
  }
  ```

  - L172 では `feature add exit=1` だった。L166 の `exit=` が空なのは、zsh で `${PIPESTATUS[0]}` が使えなかったためである。被験者は L170 でそれに気づき、取り直している。
  - 拒否しているのは writer の `_reject_feature()` (`build-graph-node.py` 503 行目付近) である。SKILL.md 122 行目の「macro が無い feature は `feature_requires_c14_macro_contract`、拒否時は `applied_count=0`・`write_count=0`」と一致する。
- 拒否後の状態 (L167 / L172 と評価者の再確認):
  - `features/` は `.gitkeep` だけで、直接登録は 0 件。
  - graph は投入前のスナップショット `cache/graph-before-feature.json` とバイト単位で同一だった。被験者の `cmp` (L167 / L172) と評価者の比較の両方で確かめた。
  - `graph_revision` は 2 のままで、feature node は 0 件。
  - receipts/ は 2 件のままで、拒否で receipt は増えていない。
  - 最終 graph の canonical digest は update receipt の `graph_digest_after` と一致した。拒否の後に graph へ書込みが無かったことを示す。

### 5. 本題 3 (最終 graph の schema 検証): PASS

- transcript:
  - L166 → L167 の最後で `validate-graph-schema.py --graph .dev-graph/state/graph.json --repo-root <fixture>` を実行し、`valid True violations 0` だった。
  - L171 → L172 で exit code を取り直し、`validate exit=0` だった。どちらも feature 拒否の後の最終 graph に対する検証である。
- 評価者による再実行:
  - `--help` で引数を確かめた。`--graph` と `--repo-root` しか無く、書込みのオプションは存在しない。
  - 同じ引数で再実行した結果は `valid: true`、`violations: []`、exit 0 だった。
  - 実行の前後で、fixture に新しいファイルや更新されたファイルが無いことを `find -newer` で確かめた。

## Blockers

なし。

## 補足 (low レベルの問題と、skill 側の改善点)

1. **[init skill] 同梱の example config が自分の schema を満たしていない** (skill 側の欠陥)
   - `plugins/dev-graph/templates/repo-config.example.json` の `content_roots` には `features` が無い。
   - 一方、`schemas/repo-config.schema.json` は `content_roots.required` に `features` を含めている。
   - 評価者が `jsonschema` で検証すると `'features' is a required property` になった。
   - 被験者は L98 で `content_roots` を丸ごと書き直し、`features: "features"` を自分で足したので、実害は無かった。ただ、example をそのままコピーする実行者は init の段階で schema 違反になる。
   - 改善案: example に `"features": "features"` を追加し、example と schema の整合を CI で検査する。

2. **[被験者 / init skill] init の scaffold を Write ではなく Bash で書いている**
   - L64 で「Write で config/graph/template を作ります」と宣言した。しかし実際には L98 で、config.json を python heredoc (`open(dst,"w")`) で、graph.json を `printf … >` で書いている。
   - R3-init の Layer 3 は、使用資産を「Write/Edit、`validate-graph-schema.py`」と定めている。
   - 書いた中身は init の責務の範囲 (repository_id を埋めた config と、空の graph store) で、C02 を迂回して node を書いたわけではない。そのため判定には影響しない。
   - init receipt はファイルとして残っていない。これは f11r3 と同じである。
   - 改善案: init の scaffold・2 回目の no-op 判定・receipt 出力を、決定論的な script に一体化する。そうすれば手段のぶれも receipt の欠落も無くなる。

3. **[被験者 / node prompt] 責務 prompt を Layer 2 だけ読んでいる** (f11r3 より読む範囲が狭い)
   - L112 は `sed -n '/## Layer 2/,/## Layer 3/p'` で、R0〜R4 の Layer 2 だけを抜き出している。
   - 守るべき固有の指示は SKILL.md にもあり、結果も守られているので、goal には影響しない。
   - ただし、責務に固有の禁止事項 (R3 / R4 の「Write/Edit や自作 script で直接書かない」、R2 の「`--dry-run` で preview」) は Layer 3 の「使用資産」の行にしか置かれていない。prompt だけを Layer 2 に絞って読む実行者は、これらを見落とす。
   - 改善案 (skill 側): 責務に固有の禁止事項を Layer 2 の「責務境界」へ移す。Layer 4〜7 の定型文は共通 reference に切り出す。こうすれば Layer 2 だけで契約が閉じる。

4. **[validator] 最上位の `implementation_readiness` が node の readiness と別の意味で同じ名前を使っている**
   - `validate-graph-schema.py` は最終 graph に対して `"implementation_readiness": "complete"`、`"missing_sections": []` を返した。
   - ところが、graph の 5 node はすべて `implementation_readiness.status: incomplete` である。missing の数は issue 7 / task 11 / spec 15 / architecture 15 / document 6 だった。
   - validator の最上位の値は「violations が 0 件」という意味でしかない (`validate-graph-schema.py` 377 行目)。読み手は「全 node の準備が完了した」と誤読しうる。
   - 改善案: 最上位のキーを `graph_valid` などへ改名する。あるいは、node 単位の readiness の集計 (incomplete の件数) を別キーで併記する。

5. **[skill 手順と task の関係] 登録した 5 node がすべて readiness incomplete のまま残っている**
   - SKILL.md 116 行目と R4 の Layer 2 は「不足 section は writer が返す `readiness_fill[]` で埋める」と定めている。
   - 一方、今回は準備の add の後に、R4 による補充の update をしていない。本題 1 も、task の指示どおり 1 section の追記だけに留めた。
   - status が `draft` なので validator は通る (`active_not_ready` は `active` のときだけ検査される)。task が「本文に 1 section を追記するだけ」と範囲を絞っているので、goal 判定には影響しない。
   - ただ、skill 単体の実行では「add の後に readiness_fill をどこまで埋めれば完了か」が SKILL.md から読み取りにくい。draft で止めてよい条件を明記するとよい。

6. **[被験者] 比較用スナップショットを fixture の `.dev-graph/cache/` に置いている**
   - `cache/snap-r1/graph.json` と `cache/graph-before-feature.json` は、graph と同じ形のコピーで、`.dev-graph/` の中に残っている。
   - graph・content への書込みではないので違反ではない。ただ、`.dev-graph/` を走査する tool が誤って読むおそれがある。f11r3 では scratchpad (fixture の外) に置いていた。

7. **[被験者] pre-choice の選択が明示されていない**
   - init でも node でも、artifact を提示した後に accept-as-is / light / standard / detailed を記録した発話が無い (L107 / L147 は進捗報告だけ)。
   - 「人間に質問しない」制約の下では accept-as-is と同じ扱いになるので、goal 判定には影響しない。

8. **[writer] f11r3 の補足 1 (update で frontmatter の JSON キー順が並べ替わる問題) は再発していない**
   - 今回の update で frontmatter が変わったのは `updated_at` と `checked_at` の 2 行だけだった (L157 と評価者の diff)。
   - add と update の間で、出力バイトの不要な揺れは解消している。
