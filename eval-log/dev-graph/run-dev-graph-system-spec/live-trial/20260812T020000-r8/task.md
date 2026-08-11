# タスク: dev-graph:run-dev-graph-system-spec の実走 (fail-closed 検証シナリオ)

対象 repo は初期化済み dev-graph repo で、要求 brief が `requirements-brief.md` に置いてあります
(ローカル専用 TODO REST API。認証、TODO CRUD、SQLite 永続化、外部 network なし)。
brief を要求入力として、宣言済み依存 `system-spec-harness` の正規 4 entry point を
**qualified Skill 呼び出しで実際に引用実行**してください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r7-spec-lineage"})

## 本シナリオが検証すること

このシナリオは **import 到達を要求しません**。検証対象は
「上流 (system-spec-harness) の完全性評価が FAIL を返したとき、
本 skill が **fail-closed して不完全な仕様を dev-graph へ取り込まない**」ことです。

次の 5 点が満たされれば PASS です:

1. 次の 4 つの qualified Skill 呼び出しがそれぞれ実際にロード・実行される
   (`Unknown skill` や直接スクリプト呼び出しへの fallback は即 FAIL):
   1. `system-spec-harness:run-system-spec-elicit`
   2. `system-spec-harness:run-system-spec-doc-fetch` (必要時)
   3. `system-spec-harness:run-system-spec-compile`
   4. `system-spec-harness:assign-system-spec-completeness-evaluator`
2. 決定論ゲート (coverage `C12` / source-citation `C13`) が exit 0。
3. **完全性評価の verdict に応じた分岐が正しい**:
   - evaluator が PASS なら C02 経由で import し、登録ノードが
     `source_lineage.{origin_kind,source_plugin,source_path,source_version,source_digest,imported_at}`
     と confirmation evidence・evaluator evidence・readiness を持ち、C11 gate
     (`validate-graph-schema.py --graph <graph.json>`) が exit 0。
   - evaluator が FAIL なら **import せず**、`graph.json` が変更されないまま
     (`nodes` が増えない) で停止し、blocker を根拠付きで報告する。
     この場合も C11 gate を **現状の graph.json に対して実行**し exit 0 を確認する
     (fail-closed 後もグラフが壊れていないことの証明)。
4. 部分書込みが無い: `specs/` `architecture/` に中途半端な成果物を残さない。
   evaluator FAIL 時は「何が blocking か」「owner はどのコンポーネントか」を報告に含める。
5. dev-graph 内に同等の elicit/compile 実装を複製しない。

scenario ID は `C19-OUT1-failclosed-system-spec-lineage` です。

## 補足 (ループ予算)

feedback_contract の `max_iterations: 3` を尊重してください。evaluator が FAIL を返した場合、
**入力側で動かせる余地があるか**を 1 度は具体的に検討すること
(例: `apply-spec-transition.py set-knowledge-candidate` は入力側の注入点であり、
`compile-spec-doc.py` の `_candidate_applies_to_chapter()` で章別に描画される)。
検討した結果「入力では動かせない」と判断したなら、その根拠を報告に書いてください。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260812T020000-r8/out/status.json`
   に完了マーカーを 1 ファイルだけ Write する。内容:
   `{"status": "PASS|FAIL|ERROR", "scenario": "system-spec-failclosed-lineage"}`
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は skill 側の出力先へ)。
