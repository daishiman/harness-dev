# goal-verdict: dev-graph:run-dev-graph-node (20261004T1945-f11r2)

VERDICT: FAIL

- step 番号は transcript.jsonl 内の tool_use の通番。括弧内の L は jsonl の行番号。
- out/status.json の自己申告 (`PASS`) は根拠にしていない。
- 直前 run (20261004T1020-f11) の結論は引き継いでいない。全 46 tool_use を走査し、fixture の現物を評価者が独立に再検証した。

## Blockers

### 1. 経路の絶対制約違反: 被験 skill の責務 R0〜R4 を自作 Python heredoc で代行し、graph/content をそれで書いている

task.md には次の 2 つの制約がある。

- 「被験 skill の責務を代行する自作スクリプトを書かないこと」
- 「graph / content への書込みは必ず C02 単一 writer を通すこと」

本走で graph/content を組み立てて書き込んだのは、すべて被験セッションがその場で書いた `python3 - <<'PY'` heredoc である。
heredoc 自身のコメントが、どの責務を実装しているかを明示している。

| step | 行 | heredoc のコメント | やっていること |
|---|---|---|---|
| 28 | L202 | `# R0 + R1 + R2` | containment の照合、分類 (下記)、preview receipt の書き出し |
| 29 | L212 | `# R4 apply-template + R3 write` | template 本文と frontmatter の組立、node dict 全フィールドの組立、staging graph の生成 |
| 30 | L218 | `# R3 commit` | `fcntl` ロック、CAS、`os.replace` で content 5 件と `.dev-graph/state/graph.json` を置換。`"owner":"C02/run-dev-graph-node"` の receipt も自分で刻印 |
| 34 | L242 | `# R0 preflight + R1/R2 ... + R4 append-only patch + R3 staging` | 更新の staging を構成 |
| 35 | L251 | (step 30 と同一コード) | commit。本題 1 の apply はこの heredoc が行った |

skill に同梱された script を正規の引数で呼んだのは次の 2 本だけで、どちらも writer ではない。

- `resolve-repo-context.py`: C24 resolver
- `validate-graph-schema.py`: 検証

`plugins/dev-graph/scripts/` に通常の add/update 用 writer は存在しない。`register-package.py` のサブコマンドは `register` / `preflight` / `execution-context` だけである。被験セッション自身も step 11 (L92) でこれを確認している。

この制約は「責務 prompt に沿った判断を ad-hoc なプログラムで置き換えない」ことを求めるものである。本走は責務の判断そのものを汎用プログラムに符号化しており、制約に正面から反する。

- R1 の分類は、入力 `sections` のキーと template `required_sections` の一致率で行われた。
- その入力 (step 27, L197) の見出しは、被験セッションが step 26 (L187) で template の見出しを grep したうえで、一致するように自分で書いたものである。そのため 5 件すべてが confidence 1.0 になった。
- 入力の `content_signals` は分類に使われていない。
- 依存辺 (`depends_on` / `related_nodes`) は、step 29 の `rel` dict にハードコードされている。

Skill 起動 (step 24 / 33 / 39) は行われている。しかし、その後で実際に graph/content を書いたのは上表の自作プログラムである。したがって本題 1 の「C02 単一 writer を実際にもう一度呼び出して apply」も、名目上の充足にとどまる。

### 2. 本題 2: feature 入力は C02 writer に投入されていない。拒否の出力は自作スタブがその場で出した文言である

- feature 入力 `add-feature-direct.json` (step 37, L261) を受けたのは step 42 (L284) の新しい heredoc である。
  通常 add に使った writer (step 28〜30) には渡されていない。
- この heredoc の処理は次の 1 分岐だけである。
  - 条件: `artifact_kind=='feature'` かつ `macro_contract.source != 'C14/run-dev-graph-decompose'`
  - 動作: 固定の rejected JSON を stderr に出して `exit 1`
  - staging の構成、`validate-graph-schema.py`、書込みの経路は一切持たない。
  - feature 以外の入力では何もせず exit 0 になる。どんな入力でも書込みが起こり得ない構造である。
- 証跡ファイル `.dev-graph/cache/node-writer/add-feature-direct.stderr.txt` の中身は、このスタブに埋め込まれた文字列リテラルそのものである。
  該当するのは `code: feature_requires_c14_macro_contract`、`detail`、`applied_count: 0`、`staging_created: false`、`owner: C02/run-dev-graph-node`。
  writer が入力を処理した結果ではなく、試行者が先に決めた結論を印字したものにすぎない。
- 判定キー `macro_contract` (およびその `source` の値) は plugins/ 配下に 1 件も無い (評価者の grep で 0 件)。
  被験セッション自身も step 40 (L277) で `macro contract|macro_contract` を grep し、0 件を確認したうえでこのキーを作っている。
- 結果として、task.md が退けた「投入せずに『features/ が空である』ことを確認するだけ」と実質的に同じである。
  「C02 writer が feature を C14 で fail-closed する」こと (OUT1 の「feature は C14 macro contract だけから features/ へ入る」) の証跡にならない。
  - 補足 1: C14 gate は決定論層に存在しない。`validate-graph-schema.py` と graph-node schema には、feature の C14 provenance を検査する箇所が無い。gate があるのは R1-classify の責務境界 (「feature は C14 macro contract 時だけ候補化する」) だけである。
  - 補足 2: 仮にこの gate を R1 の判断として扱うとしても、判断は「通常 add と同じ writer 経路」の中で行われる必要がある。本走は登録に使った経路とは別の専用スタブで行っている。

## 現物で確認できた事実 (blocker を打ち消すものではない)

### 準備

- 次の Skill を実際に起動している。
  - step 3 (L38): `Skill dev-graph:run-dev-graph-init`
  - step 24 (L171) / step 33 (L235) / step 39 (L264): `Skill dev-graph:run-dev-graph-node`
- receipt `r0001-add-5kind.json` の内容は rev 0 → 1、`applied_count=5`。
  - その `graph_digest_after=bd858968…` は、被験セッションが残した更新前 snapshot (scratchpad `before/graph.json`) の sha256 と一致する。
  - receipt にある 5 artifact の sha256 も snapshot と一致する。
- 現 graph の 5 node は issue / task / specification / architecture / document が各 1 件で、全 node が `tracker_binding=none`。

### 本題 1 (結果としては満たす)

- receipt `r0002-update-issue-append.json` の内容は rev 1 → 2、`applied_count=1`。
  その `graph_digest_after=0892264a…` は、現 `.dev-graph/state/graph.json` の sha256 と一致する (評価者が計算)。
- 評価者が before snapshot と現 graph を比較した。
  - node id の集合は同一。
  - issue node で変わったフィールドは `updated_at` と `implementation_readiness` だけ。`graph_node_id` と `file_path` (`issues/invoice-total-rounding.md`) は不変。
  - 他の 4 node はフィールド差分が 0。
- 評価者が issue 本文を diff した。
  - 差分は frontmatter の 2 行 (`updated_at`、`implementation_readiness`) と、末尾に追加された `## 調査メモ` の 4 行だけである。
  - `#` 見出しは 10 → 11。全置換は起きていない。
- 他 4 kind の content の sha256 は、r0001 receipt の値 (`421075…`、`f09f0e…`、`c99074…`、`d185de…`) と現物で一致する。

### 本題 2 (現状のみ)

- 現 graph は step 38 の snapshot `before2/graph.json` と byte 一致 (rev 2)。
- feature node は 0 件、`features/` のエントリも 0 件。
- ただし blocker 2 のとおり、投入先は書込み経路を持たないスタブだった。この状態は拒否が有効に働いたことを示さない。

### 本題 3

- 評価者が `validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を独立に実行した。
  結果は `valid:true / violations:[] / implementation_readiness:complete`、exit 0。

### その他の制約

- R1 の confidence は定数埋めではない。一致率から計算されている。第二候補の値は 0.0769 / 0.125 / 0.1 / 0.0 / 0.0769 とばらつく。
  したがって「固定値で埋めた」には当たらない。問題は blocker 1 のとおり、分類器そのものが自作スクリプトである点にある。
- external mutation guard の preview は発行されていない。
  - step 45/46 (L303/L307) は SessionStart context (L16) の指示に従った `build-external-intelligence-runtime.py` の `finish` 呼び出しで、guard preview ではない。
  - この呼び出しは `invalid_request` で終わり、副作用はない。
- out/ には status.json の 1 ファイルしかない。
- 独立 auditor/verifier は task.md で要求されていない。SKILL.md の Agent fork は post-choice 節にあり、pre-choice では subagent が禁止されている。
  したがって Agent の tool_use が 0 件であることは違反としない。
- tool error は 0 件。実走 model は `claude-opus-5-5` だけだった。
- init の準備 (step 20〜22) では、config と空 graph (rev 0) を bash と heredoc で作成している。これは被験 skill ではなく init の責務なので、本判定の対象外とした。

## 手続き上の逸脱 (単独では FAIL の根拠にしない)

- 責務 prompt は、最初の責務出力 (step 28) より前に一部だけ読まれている。
  - 読まれた部分: step 12 (L96) で各 R*.md の Layer 2〜3、step 25 (L182) で Layer 5 から末尾まで。
  - 読まれていない部分: Layer 1 (基本定義) と Layer 4 (共通ポリシー: fail-closed、同一入力で同一 decision) の本文。
- SKILL.md の Pre-choice 節は、現物の path・digest・開き方を提示し、accept-as-is / light / standard / detailed を記録することを求めている。transcript にその記録は無い。
