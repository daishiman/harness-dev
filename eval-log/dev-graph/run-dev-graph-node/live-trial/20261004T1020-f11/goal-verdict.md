# goal-verdict: dev-graph:run-dev-graph-node (20261004T1020-f11)

VERDICT: FAIL

step 番号は transcript.jsonl 内の tool_use 通番 (括弧内 L は jsonl の行番号)。
out/status.json の自己申告 (`PASS`) は根拠にしていない。

## Blockers

### 1. 本題 2: feature 入力が C02 単一 writer に投入されていない (拒否は自作スタブの出力)

- step 27 (L200) で `eval-log/inputs/03-add-feature-direct.json` を受けたのは、その場で書かれた python heredoc である。
  中身は次の 2 分岐だけで、staging への node 構成、`validate-graph-schema.py`、atomic replace の経路を持たない。
  - (a) `kind == 'feature' and not a.get('c14_macro_contract')` なら rejected JSON を出して `SystemExit`
  - (b) それ以外なら `SystemExit('unexpected non-feature artifact in this input')`

  どの入力でも書込みが起こらない構造であり、本題 1 の add に使った writer (step 22) とも別のプログラムである。
- そのため `eval-log/evidence/feature-add.stderr` の `{"status":"rejected", ..., "applied_count":0}` は、
  試行者が期待する結論を先に埋め込んだスタブの出力にすぎない。
  「被験 skill の C02 writer が feature を C14 で fail-closed する」ことの証跡にはならない。
  task.md が退けた「投入せずに `features/` が空であることを確認するだけ」と実質的に同じである。
- 判定キー `c14_macro_contract` は plugins/ 配下に 1 件も存在しない (評価者の grep で 0 件)。試行者が作った語である。
  plugin の scripts にも C14 provenance を検査する gate は無い (`validate-graph-schema.py` に該当する検査なし)。
- 先例 gm4 は feature node を実際に staging txn へ構成し、validator まで通したうえで R1-classify の契約に基づいて rollback している。
  本走はそこまで到達していない。

### 2. 経路の絶対制約「被験 skill の責務を代行する自作スクリプトを書かない」の違反

- step 22 (L168, add)、step 24 (L183, update)、step 27 (L200) は、責務 R0〜R4 を 1 本の自作 Python に符号化して実行している。
  - R0: C24 receipt の照合
  - R1: 分類
  - R2: 自動確定
  - R4: template の組立
  - R3: lock / staging / validate / `os.replace` / receipt
- 被験 skill には通常の add/update 用の script が無い。L64 の発話で、試行者自身が
  「no dedicated script exists for normal add/update — the skill itself (via its R-prompts) is the C02 writer」と認識している。
  それにもかかわらず、責務 prompt に沿って判断すべき工程を ad-hoc なプログラムで置き換えた。
- 特に R1-classify (「成果物内容から ... confidence、reason ... を推定する」) は内容を推定していない。
  - 入力の `kind_hint` をそのまま kind として採用している。
  - confidence は定数 0.95、第二候補は `others[0]` 固定で 0.05、margin は 0.90 で埋めている。
  - R2 の閾値判定 (`>=0.80` かつ margin `>=0.15`) は、この定数に対して常に真になる assert である。
- 評価者が現物を確認した結果、現 graph の 5 node はすべて `classification_confidence=0.95` で、
  第二候補は 0.05 (issue node は task、それ以外は issue に固定) だった。
- `classification_reason` の「本文節構成が template と一致」も、推定の結果ではなく文字列テンプレートである。
- 分類 preview は write の前に提示されておらず、commit 後の receipt にだけ現れる。
- 先例 gm4 は「python heredoc は検証専用で graph/content を書いていない」ことを適合の根拠にしていた。
  本走では heredoc そのものが graph/content の writer であり、分類器でもある。

## 現物で確認できた事実 (blocker を打ち消すものではない)

### 準備

- step 3 (L37) で `Skill dev-graph:run-dev-graph-init` を、step 16 (L122) で `Skill dev-graph:run-dev-graph-node` を実際に起動している。
- `.dev-graph/state/receipts/c02-rev0001-add.json` の内容は base 0 → rev 1、`applied_count=5`。
  その `graph_digest=16364a21…` は、評価者が計算した `eval-log/evidence/graph-rev1.json` の sha256 と一致する。
- 5 kind (issue / task / specification / architecture / document) が各 1 node あり、全 node が `tracker_binding=none`。

### 本題 1 (結果としては満たす)

- step 24 で apply に到達している。receipt `c02-rev0002-update.json` は base 1 → 2、`applied_count=1`。
  その `graph_digest=95d6479d…` は現 `.dev-graph/state/graph.json` の sha256 と一致する。
- 評価者が `eval-log/evidence/issue-rev1.md` と `issues/login-session-timeout.md` を diff した。
  rev1 側の sha256 `4298af0f…` は step 23 の記録と一致する。
  差分は `updated_at` の 1 行と、末尾に追加された `## 追加調査メモ` の 4 行だけである。
  `#` 見出し行は 10 → 11 で、本文の全置換は起きていない。
- 評価者が rev1 snapshot と現 graph を比較した。
  - node id の集合は同一。
  - issue node は `updated_at` だけが変わり、`graph_node_id` と `file_path` は不変。
  - 他の 4 kind は node フィールドの差分が 0 で、content の sha256 も一致 (`shasum -c` で OK)。

### 本題 2 (現状のみ)

- 現 graph は rev 2 のまま (snapshot `graph-rev2.json` と bit 一致)。feature node は 0、`features/` には `.gitkeep` しかない。
- ただし blocker 1 のとおり、投入先は書込みができないスタブだった。この状態は拒否が有効に働いたことを示さない。

### 本題 3

- 評価者が独立に実行した結果は次のとおり。

  ```
  python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>
  ```

  → `valid:true / violations:[] / implementation_readiness:complete`、exit 0。

### その他の制約

- external mutation guard の preview は発行されていない。transcript 中の該当語は、system context にある既存の git status 行、task.md の引用、SKILL.md 本文だけである。
- out/ には status.json の 1 ファイルしかない。
- 独立 auditor/verifier は task.md で要求されていない。SKILL.md の Agent fork は post-choice 節にあり、pre-choice では subagent が禁止されている。
  したがって本走では適用外で、Agent の呼び出しが 0 件であることは違反としない。
- tool error は 0 件。実走 model は claude-opus-5-5 だけだった。

## 手続き上の逸脱 (単独では FAIL の根拠にしない。先例 gm4 と同じ基準)

- 責務 prompt は、step 17 (L126) の `sed -n '/## Layer 2/,/## Layer 3/p'` で各 R*.md の Layer 2 (77 行中約 19 行) が読まれただけである。
  以後、prompts を読む呼び出しは無い。
  - 未読のまま残った部分: Layer 3 (R3 の使用資産)、Layer 5 の checklist、Layer 6 (前段 receipt/digest と後段 input digest の一致、stale handoff の拒否)。
  - 実際に、責務ごとの receipt/digest の受け渡しは作られていない (R0〜R4 が 1 本の script に畳まれている)。
- receipt の `user_choice: "accept-as-is (autonomous trial)"` は、現物を提示する前に script の中で固定値として書かれている。
