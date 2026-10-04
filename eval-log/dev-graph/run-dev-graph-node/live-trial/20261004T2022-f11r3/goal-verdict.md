# goal-verdict: dev-graph:run-dev-graph-node (20261004T2022-f11r3)

VERDICT: PASS

- `L<n>` は transcript.jsonl の 0 始まりの行番号を指す。
- out/status.json の自己申告 (`PASS`) と、最後の `DONE: PASS` は根拠にしていない。
- 前回 run (20261004T1945-f11r2, goal FAIL) の結論は引き継いでいない。transcript の全 tool_use 33 件 (Bash 24 / Write 6 / Skill 2 / Read 1) を走査し、fixture の実物を評価者が独立に再検証した。
- 被験者が使った writer は repo 側の `plugins/dev-graph/scripts/build-graph-node.py` である。評価者が `diff` で比べたところ、インストール済みの `~/.claude/plugins/cache/harness-local/dev-graph/0.1.12/scripts/build-graph-node.py` とバイト単位で同一だった。

## 結論

PASS。5 つの判定項目すべてを、transcript と fixture の実物で確認できた。

- graph と content は、init の正規経路と C02 単一 writer (`build-graph-node.py add|update`) だけで書かれている。
- 本題 1 (update の apply)、本題 2 (feature の拒否)、本題 3 (最終 graph の schema 検証) は、いずれも実際に実行されている。
- 結果は、receipt・graph・本文の digest で互いに突き合わせて矛盾がない。

前回 FAIL の原因は、writer の CLI が無く、被験者が自作 heredoc で代行したことだった。今回はその経路が 1 箇所も無い。

## 判定項目ごとの根拠

### 1. 経路の制約: PASS

#### graph / content / receipt を書いた経路

書込みを伴う操作を機械的に全件抽出した。Write / Edit 呼び出しと、Bash 内の `cp` / `mv` / `rm` / `mkdir` / リダイレクト / `open(...,'w')` / `os.replace` などが対象である。

| L | 操作 | 書込み先 | 判定 |
|---|---|---|---|
| L120 | Bash `mkdir -p` と、templates の欠落分だけ `cp` | 6 root、`.dev-graph/{state,cache,locks,templates}` | init の正規経路 (Execution contract 2・3、R4-template の使用資産 Read/Write) |
| L125 | Write | `.dev-graph/config.json` | init の正規経路 (R3-init Layer 3「使用資産: Write/Edit、validate-graph-schema.py」) |
| L127 | Write | `.dev-graph/state/graph.json` (`graph_revision: 0, nodes: []`) | 同上。init の初期 graph store の生成 |
| L163 | Bash `mkdir -p` | `.dev-graph/cache/inputs` | 入力置き場。graph/content ではない |
| L171 / L194 / L211 | Write | `.dev-graph/cache/inputs/{add-5kinds,update-issue-append,add-feature}.json` | writer への入力 JSON。SKILL.md は「`--input <repo 内 JSON>`」「skill は … 入力 JSON に整形するだけ」と定めている。graph・content・receipt ではない |
| L190 / L215 | Bash `cp` | 被験者の scratchpad (`/private/tmp/.../scratchpad/before/`, `graph-before-feature.json`) | 比較用スナップショット。fixture の外 |
| L225 | Write | `out/status.json` | 規定の完了マーカー |

- 上記以外の書込みはすべて writer が行った。
  - L178 `build-graph-node.py add`
  - L202 `build-graph-node.py update`
  - L215 `build-graph-node.py add` (feature 入力。拒否された)
- 自作 Python / heredoc は L137 と L206 の 2 本だけである。どちらも `json.load` / `jsonschema` / `diff` / `cmp` による読み取り専用の検証だった。
- Edit の呼び出しは 0 件だった。
- receipts/ の 2 ファイル (`node-r000001-add.json`, `node-r000002-update.json`) は、writer の実行結果 (L179, L203) の `receipt_path` と一致する。被験者が receipt を書いた形跡は無い。

#### 責務 prompt を出力の前に読んだか

- init:
  - L46 で `cat skills/run-dev-graph-init/prompts/*.md` を実行し、R1〜R5 を全文読んでいる。
  - init の出力 (L120〜L127) より前である。
- node:
  - L148 で R0〜R4 の Layer 2 (入力契約・出力契約・責務境界・受入条件) を読んでいる。
  - L158 で Layer 3 から出力指示までを読んでいる。
  - 最初の入力 JSON (L171) より前である。
  - R3 / R4 の Layer 3 にある「graph・content・receipt を Write/Edit や自作 script で直接書かない」も、このとき読んでいる。
  - 全文の `cat` ではない。Layer 1 は読んでおらず、grep で 3 行を除外している (補足 2)。ただし、読まなかった部分の中身は他の層と重複しているか、共通ポリシーである。出力を左右する契約はすべて読了しているので、違反とは扱わない。

#### その他の制約

- external mutation guard の preview は発行していない。
  - L229 と L233 で `build-external-intelligence-runtime.py` を呼んでいるが、これは mutation guard とは別物である。
  - 呼んだ理由は、セッション冒頭の UserPromptSubmit hook (L15) にある「At task end call operation=finish with capture=null」という指示である。
  - 結果は `invalid_request` (必須キー不足) で、何も記録されていない。
  - pending guard context による Bash の遮断も起きていない。
- out/ には `status.json` の 1 ファイルしか無い (評価者が `find` で確認)。
- 人間への質問は無い。AskUserQuestion は 0 件である。
  - init の pre-choice では、被験者自身が accept-as-is を選んで handoff している (L141)。

### 2. 準備: PASS

- L36 で `Skill dev-graph:run-dev-graph-init` を実行し、L142 で `Skill dev-graph:run-dev-graph-node` を実行している。
- init の検証 (L137 → L138):
  - repo-config schema の違反は 0 件だった。
  - `validate-graph-schema.py` は exit 0 だった。
  - C24 の `repository_id` は config と一致した。
  - 2 回目の init で予定されるテンプレートのコピーは 0 件、6 root はすべて揃っていた。
  - `.claude/` は存在しない (hook_source=plugin で、fallback は導入していない)。
- 5 kind の登録 (L178 → L179):
  - `status: applied`、`applied_count: 5`、`graph_revision 0 → 1`、`owner: C02/run-dev-graph-node`
  - receipt は `node-r000001-add.json`
  - 分類はどれも `decision: auto` で、confidence が 0.88〜0.92、margin が 0.75〜0.82 だった。いずれも閾値 (0.80 / 0.15) を満たす。
  - 事前に `--dry-run` も実行している (L175: `preview`、planned 5)。
- 実物の確認 (評価者):
  - `.dev-graph/state/graph.json` の 5 node は、issue / task / specification / architecture / document が各 1 件だった。
  - 5 node とも `tracker_binding: "none"` である。入力の `add-5kinds.json` も 5 件すべて `tracker_binding: "none"` だった。

### 3. 本題 1 (issue への section 追記の apply): PASS

- 入力 `update-issue-append.json` (L194) の中身:
  - `expected_graph_revision: 1`
  - `updates[0]` は `graph_node_id: issue-login-timeout` と `append_sections: {"調査メモ": …}` だけである。
- 実行 (L202 → L203):
  - `--dry-run` で `preview 1` を得てから、本実行している。
  - 結果は `status: applied`、`applied_count: 1`、`graph_revision 1 → 2`、`sections_appended: ["調査メモ"]`、`sections_replaced: []`、`node_fields_patched: []`、`unmanaged_body_preserved: true`。
  - receipt は `node-r000002-update.json`
- apply の発生 (評価者が実物で突合):
  - receipts/ に `node-r000002-update.json` が実在する。中身は `operation: update`、`graph_revision_before 1 / after 2`。
  - 最終 graph の `graph_revision` は 2。
  - 最終 graph の canonical digest を writer の `_canonical_digest` と同じ方法 (sort_keys / 区切り詰め) で計算すると `sha256:9247a101…` になった。update receipt の `graph_digest_after` と一致する。
- id と path は不変である。
  - receipt の `sha256_before` (`72789f40…`) は、add receipt の issue の `sha256_after` と一致する。
  - 現在の `issues/login-timeout.md` の sha256 (`f367b8f8…`) は、update receipt の `sha256_after` と一致する。
  - graph でも本文の frontmatter でも、`graph_node_id: issue-login-timeout` と `file_path: issues/login-timeout.md` のままである。
  - L207 の被験者自身の比較でも、変化したフィールドは `implementation_readiness` と `updated_at` だけだった。
- 本文は全置換されていない。
  - L207 の diff を見ると、本文で変わったのは末尾の `## 調査メモ` と本文 1 段落の追加 (96a97,100) だけである。
  - 既存の見出し (概要 / 背景と問題 / 現在の挙動 / 期待する挙動) とテンプレート由来の section は、評価者が見た実物 `issues/login-timeout.md` に残っている。
  - frontmatter では `updated_at` / `implementation_readiness.checked_at` 以外に、JSON 値 5 行でキー順だけが変わっている。意味は同じなので本文の全置換には当たらないが、writer 側の改善点として補足 1 に記す。
- 他 4 kind は無変更である。
  - 本文: 現在の sha256 が、add receipt の `sha256_after` と 4 件とも一致した (task `4484e517…`、spec `9b222536…`、architecture `93ddd4d5…`、doc `59e93b88…`)。
  - graph node: `updated_at` は 4 件とも add 時刻 (`11:24:31.185448Z`) のままである。L207 の比較でも 4 node とも `unchanged` だった。

### 4. 本題 2 (feature 入力の writer 投入と拒否): PASS

- 入力 `add-feature.json` (L211) の中身:
  - `artifact_kind: "feature"` を含む通常の add 入力である。
  - C14 package 用のキー (`parent_feature` / `feature_package_id` / `phase_ref`) は含まない。
  - `expected_graph_revision` は 2。
- 投入 (L215): 通常の add と同じ `build-graph-node.py add` に、実際に渡している。
- エラー出力そのもの (L221):

  ```json
  {
    "applied_count": 0,
    "code": "feature_requires_c14_macro_contract",
    "error": "feature nodes enter features/ only through the C14 macro contract (run-dev-graph-decompose); ordinary add/update cannot create or edit them",
    "findings": [],
    "status": "rejected",
    "valid": false,
    "write_count": 0
  }
  exit=1
  ```

  前回と違い、これは writer 本体が入力を処理して返した結果である。拒否は `build-graph-node.py` の入口にあり、SKILL.md の「`feature` は writer の入口で `feature_requires_c14_macro_contract` として拒否し、… `applied_count=0`・`write_count=0` を返す」と一致する。
- 拒否後の状態 (L221 と評価者の再確認):
  - `features/` は 0 件 (評価者が `ls -A` で確認)。
  - graph は投入前のスナップショットとバイト単位で同一 (`cmp`)。`graph_revision` は 2 のままで、feature node は 0 件。
  - receipts/ は 2 件のままで、拒否で receipt は増えていない。
  - 最終 graph の canonical digest は、update receipt の `graph_digest_after` と一致した。拒否の後に graph へ書込みが無かったことを示す。

### 5. 本題 3 (最終 graph の schema 検証): PASS

- transcript: L215 の最後で `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を実行し、結果は `valid: true`、`violations: []`、`validate exit=0` だった (L221)。これは feature 拒否の後の最終 graph に対する検証である。
- 評価者による再実行:
  - `--help` で引数を確かめた。`--graph` と `--repo-root` しか無く、書込みのオプションは存在しない。
  - 同じ引数で再実行した結果は `valid: true`、`violations: []`、exit 0 だった。

## Blockers

なし。

## 補足 (low レベルの問題と、skill 側の改善点)

1. **[writer] update の初回に、frontmatter の JSON 値のキー順が並べ替わる** (cosmetic な差分ノイズ)
   - 該当箇所: `build-graph-node.py` の `_frontmatter()` (L340 付近) は `json.dumps(node[key], ensure_ascii=False)` を `sort_keys` なしで呼んでいる。
   - 原因:
     - add は、メモリ上で組み立てた node dict (挿入順) から frontmatter を作る。
     - graph.json は `_common.py` が `sort_keys=True` で保存する。
     - update は、その graph から読んだ dict (ソート済み) で frontmatter を作り直す。
   - 結果: 最初の update で、追記と関係のない frontmatter 5 行 (`confirmation_evidence`, `source_lineage`, `classification_candidates`, `github_publication`, `completion_evidence`) がバイト単位で書き換わった (L207 の diff)。
   - 意味は同じで、2 回目以降の update では再発しない。ただし「連続更新後も frontmatter/path 整合」(OUT1) のレビューや git diff の読みやすさを損なう。
   - 改善案: `_frontmatter()` に `sort_keys=True` を加え、add と update の出力バイトを揃える。

2. **[被験者] 責務 prompt の部分読み**
   - node prompt の Layer 1 (不変目的と成功条件のメタ規則) を読んでいない。
   - grep で除外した 3 行は「ユーザー提示は日本語」「secret を埋め込まない」と、出力指示の 1 行である。
   - 読まなかった内容の多くは、Layer 5.2 の目的など他の層と重複している。そのため結果への影響は無い。
   - ただ、除外した「ユーザー提示は日本語」に反して、途中の進捗報告の一部が英語だった (L76 / L109 / L147 / L205 など)。
   - 改善案 (skill 側): prompt の Layer 4〜7 はほぼ全責務で同じ定型文である。冗長なので、被験者が sed や grep で拾い読みする動機になっている。共通部分を 1 つの共有 reference へ切り出し、各 R*.md には責務に固有の層だけを置けば、「全文を読む」コストが下がる。

3. **[init skill] init receipt が永続化されていない**
   - R3-init の出力契約は「immutable init receipt」を求め、SKILL.md も「Receipt は `repository_id`, repo-relative roots, created/preserved/migration_preview, hook_source, schema_result を含む」としている。
   - 今回、被験者は L141 の会話テキストで結果を要約しただけで、receipt ファイルは作られていない。
   - init には専用 script が無く、エージェントが Write で scaffold する設計である (R3-init の Layer 3)。そのため receipt の形も保存先も実行者任せになっている。
   - 改善案: node 側の writer と同じように、init にも決定論的な script を用意し、scaffold・2 回目の no-op 判定・receipt 出力を一体で持たせる。

4. **[init skill] graph の保存先の記述が食い違っている**
   - init の SKILL.md は、出力を `.dev-graph/{config.json,graph.json,...}` と書いている。
   - 一方、`templates/repo-config.example.json` と writer が実際に使う path は `.dev-graph/state/graph.json` である。
   - 今回、被験者は config に従って state/ 側に置いたので実害は無い。ただ、SKILL.md だけを読む実行者は迷う。

5. **[被験者] Skill の起動引数にプレースホルダが残っている**
   - L142 の `Skill dev-graph:run-dev-graph-node` の args は、task.md の例の `--input <入力ファイル>` そのままだった。
   - その後の writer 呼び出しはすべて実在する入力 path で行われているので、判定には影響しない。

6. **[被験者] node の pre-choice 選択が明示されていない**
   - node skill の pre-choice (artifact を提示 → accept-as-is / light / standard / detailed を記録) について、node 側で選択を明示的に記録した発話が無い。
   - init 側は L141 で accept-as-is を明示している。
   - task の「人間に質問しない」制約の下では accept-as-is と同じ扱いになるので、goal 判定には影響しない。
