VERDICT: FAIL
BLOCKERS:
- 準備段階の graph 書込みが C02 単一 writer の実装本体 (`plugins/dev-graph/scripts/register-package.py`) を経由していない。実行者は自作の `c02-apply.py` (scratchpad, transcript #403) で node レコード・template 投影・fcntl ロック・atomic replace・registration receipt 生成を代行しており、`register-package.py` は読んだだけで一度も実行されていない (transcript 内の該当 Bash は #64/#337/#345 の閲覧のみ)。run-dev-graph-node の SKILL.md は「`register-package` verb はこの gate の実装本体 `../../scripts/register-package.py` に委譲する」「単一 writer は `register-package.py` が fcntl ロックと receipt の `os.link` 一回性で保証し、skill 側は入力整形と結果提示に留める」と明記しており、これは責務の代行に当たる。task.md の経路絶対制約 (手書き JSON の graph 組み立て禁止 / 違反時 trial 無効) にも該当する。
- 上記の結果、被験 skill の `criteria:OUT1` が照合先とする registration receipt (`.dev-graph/state/receipts/lt-feature-001-registration.json`) は C02 が発行したものではなく実行者の自作スクリプトの出力である。receipt の形式自体は `package-registration-receipt.schema.json` の required/properties を過不足なく満たすが、値 (`applied_count=13`, `source_digest`) の出所が正規 writer ではないため、OUT1 の証跡連鎖を正規経路として裏取りできない。

## 実行者の自己申告 FAIL 理由について

実行者が挙げた唯一の理由「生成 HTML に applied_count / source_digest が表示されていない」は、SKILL.md の宣言に照らして**正当な未達ではない**。

- `criteria:OUT1` の文言は「…X/Y が表示され、registration receipt の `applied_count/expected_count` と `source_digest` **が表示内容に一致する**」であり、digest を HTML 上に表示せよとは書いていない。要求は表示内容との整合であって表示そのものではない。
- 完了チェックリストの live trial 項目も「SVG と feature X/Y progress が表示される」までで、digest 表示は要求していない。
- Gotchas も「browser 表示だけで PASS にせず、receipt count と input/output digest も**照合する**」であり、照合 (検証行為) の要求である。

したがってこの理由単独では FAIL にならない。FAIL 判定の根拠は上記 BLOCKERS のみである。

## 独立に裏取りした事項 (いずれも被験 skill 側は問題なし)

対象: `eval-log/dev-graph/live-trial-fixtures/gm4-render/.dev-graph/render/index.html` (10,629 bytes)

- **外部 resource 参照 0 件**: `http(s)://` / cdn / unpkg / jsdelivr の出現 0 件。`<script>` は 2 個ともインライン (`type="application/json"` の graph-data と inline JS)。外部 `<link>`, `<img>`, `<iframe>` なし。CSS も `<style>` にインライン。
- **inline SVG での feature/task/edge 描画**: 単一 `<svg viewBox="0 0 1000 1160">` 内に `<g class="edges">` の `<path>` 12 本と、node 15 個 (architecture 1 / feature 1 / task 13) の `<g class="node">` を確認。feature ノードのバッジは `active · feature · 5/13`。
- **X/13 と graph 実値の一致**: graph.json 上で `parent_feature == "LT-FEATURE-001"` の node は 13 件、status 内訳は done 5 / active 1 / draft 7。HTML の `5/13` は実数と一致し、手入力値ではなく `parent_feature` 由来の集約である (`render-graph-html.py` を独立実行した receipt の `feature_progress.by_feature["LT-FEATURE-001"] = {done:5, total:13}` と一致)。registration receipt の `expected_count=applied_count=13` とも一致。
- **source_digest の対応**: registration receipt の `graph_digest_after` は `sha256:5a4c6465…86be2`、実ファイル `.dev-graph/state/graph.json` の sha256 も `5a4c6465…86be2` で一致。renderer receipt の `input_sha256` も同値。よって描画対象は登録後 graph と同一で、登録以降 graph は改変されていない (render は read-only を守っている)。
- **決定論**: 同一 graph に対し `render-graph-html.py` を独立に 2 回実行し、両出力の sha256 が `b90e15381bc2f85e289366c1bc991698c79aa4c4cefc9c7401975cca50016cee` で一致。さらに fixture 内の実成果物 `index.html` の sha256 も同値で、被験 skill の出力が再現された。
- **renderer receipt の counts 整合**: `nodes=15` / `edges=12` は graph の node 数 15、`depends_on` 総数 12 と一致。
- **被験 skill 自体の経路**: render 段階は plugin 同梱の `render-graph-html.py` を直接呼んでおり (transcript #437)、被験 skill の責務を代行する自作実装は使われていない。
