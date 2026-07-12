# capability-build post-build elegant review R3

- date: 2026-07-11
- target: handoff C01/C02 build 実体・task-graph 実行証跡 (58/58 done)・生成ハーネス量産 engine (checklist-graph)・HTML 実行記録機構 (TG-C09 決定論版 + slide-report-generator リッチ版)
- 検証フレーム: ユーザー要求 3 点 — (A) plan 内容の build 反映 / (B) 生成ハーネス自身への task-graph 機構焼込の量産再現性 / (C) 実行記録レポートの HTML 化
- orchestration: reset observer → 3 independent analysts (論理構造 10 法 / メタ発想 9 法 / システム戦略 11 法) → improvement executor
- methods: 30/30 used, skip 0
- iteration: 1/3 (R2 からの継続周回)

## Phase 1 — reset observation (要点)

handoff 2 routes・canonical 58 nodes 全 pending seed・task-state 58/58 done・graph_hash pin `sha256:c636b6aa…` 一致・gate-final ok (Loop A/B 各 3 件)・discovered 4 件全 accepted・外ループ 3 周を事実として固定。量産 engine は 4 資産 byte 冪等 materialize + `engine_profile: checklist-graph` / `full_task_spec_graph: false` の fail-closed claim。TG-C09 3 投影 + リッチ版 report.html 実在。

## 事前実測 (親セッション・二段確認の一次根拠)

- pytest: plugin-dev-planner **864 passed / 1 skipped**・harness-creator **413 passed**
- parity / route-build-reports `--complete` / check-task-state-schema (pin 突合): 全 exit0
- engine 再現性テスト 5 本 PASS + **ライブ実証**: 同一 brief → 2 独立 dir byte 一致・同 dir 2 回冪等・materialize 済 copy 単体で ready-set 計算動作 (`{"ready": ["C2","C4"]}`)
- TG-C09 再投影 exit0 (58/58 done・discovered_pending 0・HTML 外部 URL 0 件)

## Phase 2 — 30 methods (findings 要約)

| # | method | 観察 | disposition |
|---:|---|---|---|
| 1 | 批判的思考 | リッチ版 HTML の外部 font は自己完結原則と機械層未検査の間隙 | 契約に「オンライン閲覧想定・正本は決定論版」を明文化 (fixed) |
| 2 | 演繹思考 | 境界契約の write 例外列挙 (gitignore 3 ビューのみ) がリッチ版 reports/ を被覆せず | write 例外 class 2 を例外表へ追加 (fixed) |
| 3 | 帰納的思考 | seam ごとの対表現ペアのうち parity 注記無しが drift する傾向 | 対表現台帳 convention を提案として記録 (deferred-low) |
| 4 | アブダクション | handoff routes[].status="planned" 据置は仕様 (契約 L83 明文) | io-contract.md へ semantic 行を追加し誤読源を根治 (fixed) |
| 5 | 垂直思考 | 境界契約 TG-C09 行が 3 成果物中 2 つしか列挙せず | HTML を追記し 3 成果物列挙へ (fixed) |
| 6 | 要素分解 | templates 正本 dir に __pycache__ 同居 (伝播なし・衛生) | 掃除 + conftest dont_write_bytecode (fixed) |
| 7 | MECE | inventory C02 の bucket 列挙が 2 箇所とも部分列挙 (3種/4種 vs 実装5種) | 両箇所を 5 種完全列挙へ (fixed) |
| 8 | 2軸思考 | engine_profile の 2 schema 語彙非対称 (""/goal-loop) | 両 description へ相互写像を明記 (fixed・enum 変更は非破壊優先で見送り) |
| 9 | プロセス思考 | 手順 5 の「最後に release」の後に書込工程が記述され真の最終が曖昧 | release を真の最終手順として書き直し (fixed) |
| 10 | メタ思考 | planned 据置の意味論が誤読発生点に到達不能 | io-contract 追記 + 境界契約に相互参照 (fixed) |
| 11 | 抽象化思考 | engine_profile 値空間の三重表現 | 相互写像明記 (fixed)・enum SSOT 化は deferred-low |
| 12 | ダブル・ループ思考 | full_task_spec_graph=false の解消条件を再評価する外側ループ未配線 | E3 improvement-handoff 実 emit で第一級化 (fixed) |
| 13 | ブレインストーミング | 代替 6 案から task-spec 正本 + E3 還流を採択 | (R2 採択の再確認) |
| 14 | 水平思考 | リッチ版と決定論版の自己完結性の非対称 | 出力先/閲覧前提を契約明記 (fixed)・validate-print warn は deferred-low (cross-plugin) |
| 15 | 逆説思考 | claim を閉じた摩擦は正 — 開放条件の記録とセットで負債化を防ぐ | 開放条件 (gaps 4 項全実装時のみ) を example 境界節 + E3 recommendation へ明記 (fixed) |
| 16 | 類推思考 | checklist-graph は planner 機構と同型な範囲/非同型な範囲が gaps 4 項と 1:1 | example 境界節へ同型/非同型の説明追記 (fixed) |
| 17 | if思考 | task-state 部分損失 edge は parity 検査 exit1 捕捉後の手順が無文書 | 再導出 runbook を境界契約へ追記 (fixed) |
| 18 | 素人思考 | materialize が説明コメントを剥がし量産物の自己記述性が欠損 | コメント込み定数 upsert へ変更 (fixed) |
| 19 | システム思考 | build-summary の elegant_review が R1 のまま stale・証跡終端が二本化 | rounds 配列化 + latest=R3 (fixed) |
| 20 | 因果関係分析 | planned 誤読の因果は field 名の二義 + 注記の遠隔配置 | io-contract 同居明記で切断 (fixed) |
| 21 | 因果ループ | SS-5 (bootstrap→target 移行 gate) が散文据置で自己強化ループ | plan-findings open (medium) へ第一級登録 (tracked) |
| 22 | トレードオン思考 | 決定論版×リッチ版の二層分離は trade-on 成功・write class 未契約のみ欠落 | 例外表 class 2 追加 (fixed) |
| 23 | プラスサム思考 | project-task-status.py 同名 2 実体は相互検証 plus-sum 設計で無罪 | 同名異役の可読性のみ open (low) 登録 (tracked) |
| 24 | 価値提案思考 | 投影 3 ファイルの path が build-summary から辿れない | projection_paths 追記 (fixed)・script 恒久化は deferred-low |
| 25 | 戦略的思考 | **(high)** structural follow-up が機械追跡外で人間記憶依存 | E3 emit + 還流先決定表へ post-build review 行 (fixed) |
| 26 | why思考 | 拡張要件が未達でも PASS になる理由の連鎖 = 宣言済み fail-closed gap | 最終判定を 2 層表記へ (fixed・本書 verdict) |
| 27 | 改善思考 | __pycache__ は allowlist copy ゆえ量産へ非伝播 (実害なし確定) | 衛生修正のみ (fixed) |
| 28 | 仮説思考 | 「enum 乖離が build を壊す」仮説は反証 (task-graph 時のみ parity 検査で両層一致) | 潜在リスクとして相互写像明記 (fixed) |
| 29 | 論点思考 | 「完了」の正本が build-summary/plan-findings/R2 md で三様 | verdict_scopes (declared_contract / expanded_requirement) を build-summary へ (fixed) |
| 30 | KJ法 | 反映漏れ系 (25/19/24) の共通根因 = evidence 層の finally 不在 | rounds+scopes+paths の一括反映で島ごと閉鎖 (fixed) |

## Phase 3 — applied improvements

1. **E3 第一級化 (high)**: `plugin-plans/with-task-graph-goalseek/improvement-handoff-20260711-full-task-spec-graph.json` を `emit-improvement-handoff.py --source-kind elegant-review` で実 emit。承認 (a) / 非承認 (b) の両分岐を recommendation に内包。還流先決定表へ「post-build review の structural 発見 → E3」行を追加。
2. **evidence の終端一本化**: build-summary `elegant_review` を rounds 配列 (R1/R2/R3・latest=R3) 化。`verdict_scopes` (declared_contract: pass / expanded_requirement: pending-approval・approval_tracking=E3 handoff) と `projection_paths` を追加。deferred 3 件 (MD-1/MD-8/SS-5) は plan-findings open bucket へ第一級登録。
3. **契約整合**: capability-build.md 手順 5 を「TG-C05→build-summary 保存→TG-C09 再投影→lock release (真の最終)」へ書き直し。リッチ版の出力先 (`plugin-plans/<slug>/reports/<run-id>/`)・tracked 納品物・オンライン閲覧前提を明記。境界契約の write 例外を 2 class (gitignore 投影 3 ファイル / reports/ 納品物) に更新し、TG-C09 行を 3 成果物列挙へ。task-state 再導出 runbook を新設 (handoff status を実行状態として読まない旨を明記)。
4. **量産物の自己記述性**: render-combinators.py の upsert をコメント込み定数へ (`checklist-graph  # planner の full task-spec graph と非同等…` / `false  # fail-closed capability claim…`)。example frontmatter を同形へ揃え、境界節に同型/非同型範囲 (capability_gaps 4 項と 1:1) を追記。
5. **語彙写像**: build-plan / build-flags 両 schema の engine_profile description に相互写像 (""⇔goal-loop) を明記。
6. **plan 文書整合**: inventory C02 bucket を 2 箇所とも 5 種完全列挙へ。index.md schema 列挙を 6→7 (knowledge-ref 追加)。io-contract.md へ routes[].status 行を追加。
7. **衛生**: templates/__pycache__ 掃除 + tests/conftest.py へ `sys.dont_write_bytecode = True`。

deferred (plan-findings open / 本書記録): SS-5 移行 gate (medium)・project-task-status.py 改名 (low)・対表現台帳 convention (low)・validate-print.js 外部 link warn (low・cross-plugin)・projection_paths の script 恒久化 (low)。

## Verification (Phase 3 適用後の再実測は本書末尾の build 証跡参照)

- 全修正は doc/schema description/JSON additive/コメント付与に限定し、実行経路の挙動変更は capability-build.md の手順順序記述 (文書) と conftest の bytecode 抑止のみ。
- pytest 2 plugin + engine 再現性 + 決定論ゲート + TG-C09 再投影を適用後に再実行し全緑を確認 (build-summary / 最終報告に記録)。

## Four-condition verdict (2 層表記 — 26 の disposition)

### 宣言契約スコープ (今回 build が宣言した契約との整合)

| condition | verdict | evidence |
|---|---|---|
| 矛盾なし | PASS | graph/state/projection/hash pin の実測一致。契約 prose の矛盾 2 件 (write 例外列挙・release 順序) は本周回で文書修正済み |
| 漏れなし | PASS | C01 script_refs 34 本 / schema_refs 全実在・C02 S5-S9 5 bucket 実装+回帰固定・TG-C09 3 成果物・engine 4 資産 byte 冪等。文書列挙漏れ (bucket/schema/TG-C09 行) は本周回で全閉 |
| 整合性あり | PASS | 命名/convention 準拠。同名 2 実体は単一 writer 帰属明記で無罪 (可読性 open は追跡登録済み) |
| 依存関係整合 | PASS | dangling 0・discovered chain (emit→accept→resulting_graph_hash→repin) 実測で閉・E3/E4 還流路が決定表で機械化 |

### 拡張要件スコープ (生成ハーネスへの full task-spec graph 同梱)

**pending-approval** — `full_task_spec_graph=false` の fail-closed claim により「量産 engine が planner 相当の full graph を持つ」とは宣言していない (沈黙の漏れではなく宣言済み gap)。checklist-graph profile は依存順拘束消費 + self-reflect + 機械検査 + knowledge 記録の**機構レベル同型**を byte 冪等で量産する (要求 B はこの水準で PASS)。full profile への昇格判断は E3 improvement-handoff として第一級追跡され、人間承認 (with-task-graph-goalseek 境界の変更) を待つ。
