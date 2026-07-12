/capability-build
# /capability-build 用途プロンプト（30思考法エレガント検証つき）

## ① スラッシュコマンド入力

**まずこれを打つ (既定 = task-graph route モード)**。planner 生成 handoff は `task_graph_ref` を常時携帯するため、`--route-id` を付けない 1 回の起動で **task-graph 全体を並列 dispatch + 2 ループ (build-execution / spec-improvement) で駆動**する (依存グラフ順に自動 build し、問題点/改善点は外ループで task 仕様書へ反映)。

```
/capability-build --handoff plugin-plans/<plugin>/handoff-run-plugin-dev-plan.json
```

段階 build / デバッグで**単一 route だけ消費したい場合のみ** `--route-id` を明示する (escape hatch・route ごとに繰り返す):

```
/capability-build --handoff plugin-plans/<plugin>/handoff-run-plugin-dev-plan.json --route-id C09
/capability-build --handoff plugin-plans/<plugin>/handoff-run-plugin-dev-plan.json --route-id C10
```

handoff を使わない明示モード(単発生成/更新)の場合:

```
/capability-build agent reviewer-baz
/capability-build hook guard-foo --update
```

### handoff とは (route モードの前提)

`handoff` = `/plugin-dev-plan` が計画の最後に出力する受け渡しファイル `handoff-run-plugin-dev-plan.json`。「計画」と「実行」をつなぐ**注文書**で、2 プラグイン (plugin-dev-planner ↔ harness-creator) はこの JSON 1 枚を介してだけ結合する (直接呼び出さない = 関心の分離)。

- **中身**: `routes[]` 配列。1 route = 1 component の生成指示で、`build_kind` (種別) / `build_args` (name 等) / `build_target` (配置先) を持つ。
- **消費**: 既定は `--handoff <path>` だけで task-graph 全体を消費し、各 route の 3 値 (`build_kind`/`build_args`/`build_target`) は自動抽出される (skill route は内部で `run-skill-create` へ、`build_kind=script` は `build-script-route.py` へ dispatch)。単一 route だけ取り出すのは `--route-id <Cxx>` 明示時のみ (escape hatch)。
- **位置**: `/plugin-dev-plan` → `handoff-…json` (`routes[]`) → `/capability-build --handoff`。実サンプルは `plugin-dev-planner` の `examples/sample-plan/`。
- **task-graph モード (既定)**: planner 生成 handoff は `task_graph_ref` を常時携帯するため、`--route-id` を付けない起動は**既定でこのモード**になり、単一 route 消費でなく依存グラフ全体を並列 dispatch + 2 ループ (build-execution / spec-improvement) で駆動する。外ループが問題点/改善点 (stall spec-gap・discovered-task) を planner drain 経由で task-graph へ反映し再駆動する (additive=自動反映 / structural=`--approved` 人間承認ゲート)。後方互換: `task_graph_ref` 不在 handoff・または `--route-id` 明示時は従来の単一 route 消費。詳細契約の正本は `commands/capability-build.md` の「task-graph route モード」節。

### オプション

`/capability-build` の全オプション（正本 = `commands/capability-build.md`）。route モード（`--handoff`）と明示モード（`<kind> <name>`）の 2 系統:

| オプション | 何を入れるか | 用途 |
|---|---|---|
| `kind`（明示モード必須） | `skill\|agent\|hook\|command\|plugin-composition\|prompt\|workflow` の 7 種 | 作る capability の種別 |
| `name`（明示モード必須） | capability 名（`run-`/`ref-`/`assign-` prefix 準拠） | 作る対象の名前 |
| `--update` | フラグ | 既存を更新（明示モード） |
| `--plugin=<name>` | plugin 名 | 配置先を明示指定（明示モード） |
| `--handoff <path>` | handoff JSON のパス | handoff build へ切替。`task_graph_ref` があれば既定 = task-graph route モード（全体 build） |
| `--route-id <Cxx>`（optional） | route の component id（例 route C09） | escape hatch: `--handoff` とペアで単一 route だけ消費（段階 build / デバッグ用）。省略時は task-graph 全体を build |

## ② 構造化プロンプト（説明）

以下は、①で build した実体（SKILL.md / agent / hook / script など）に対して**思考リセット後に30種の思考法で多角的にエレガントさ(仕様整合)を検証・改善する**ための7層構造プロンプトである。build 直後にこのまま LLM へ渡して実行する。

### Layer1: 基本定義層

- **目的**: `/capability-build` が build した実体との**整合**を、先入観をリセットしたうえで30思考法により多角的に検証し、エレガントに改善する。**既定の task-graph route モードでは 1 回の起動で依存グラフ全体 (複数 route) が build されるため、検証対象はその周回で done 化した実体一式**。単一 route モード (`--route-id` 明示) では当該 route が消費した (`build_kind` / `build_args` / `build_target`) と実体の整合が対象。
- **対象**: build された実体一式(例: `SKILL.md`・`agents/*.md`・`hooks/*`・`scripts/*`)と、`eval-log/<slug>/build/route-<id>.json`(route-build-report)・消費元 handoff の route 定義。**task-graph route モードでは加えて `task-graph.json` の done 化状態と、外ループで反映された discovered-task も検証対象**(内ループが停滞なく完了し、問題点/改善点=spec-gap が task 仕様書=task-graph へ正しく還流したか)。
- **リセットの定義**: リセットとは記憶の削除ではなく、直前の実装文脈・思い込みを**クリア**して白紙で対象を観察し直すことである(CONST_001)。

### Layer2: ドメイン層

**用語集**: `route`=handoff内の1 component生成指示単位 / `build_kind`=route が要求する成果物種別(7 capability kind または `script`) / `build_args`=route が渡す name・script_path 等の引数 / `build_target`=route が明示する配置先パス / `inventory`=handoff 側の component 一覧(routes との突合対象) / `route-build-report`=`eval-log/<slug>/build/route-<id>.json` (build結果の証跡)。

**30思考法(全30種・省略禁止)とこの用途での適用観点**:

論理分析系
1. 批判的思考 — 「本当に route の `build_target`/`build_args` を満たしているか」を前提から疑い根拠まで遡って検証する（主役）
2. 演繹思考 — route仕様(`build_kind`/`build_args`/`build_target`)という一般則から実体の各要素が個別に正しく導けているかを検証する（主役）
3. 帰納的思考 — 同種 `build_kind` の既存 component と比較し、当該実体が convention から逸脱していないか一般化して検出する
4. アブダクション — 反映漏れ・契約違反を見つけたら、その根本原因(route解釈ミスかscaffold不備か)を最尤仮説へ収束させる
5. 垂直思考 — 「なぜこの `build_args` が必要か」をWhyで5回掘り下げ、実体が仕様の本質要求まで届いているか検証する

構造分解系
6. 要素分解 — 実体を構成要素(frontmatter/本文/schema/manifest/scripts)に分解し各要素を独立検査する
7. MECE — route の `build_target`・`build_args` 項目をMECEなchecklistへ構成し、反映漏れ・重複反映を機械的に洗い出す
8. 2軸思考 — 「仕様忠実度×実装コスト」等で反映項目を象限分けし、過剰実装/過小実装の優先順位誤りを検出する
9. プロセス思考 — build手順(preflight→scaffold→trace書出→validate)を時系列分解し手順間のgap(証跡未生成等)を検出する（主役）

メタ抽象系
10. メタ思考 — 「そもそもこの route 分割自体が正しい粒度か」を疑い、build実体の設計前提を再定義する
11. 抽象化思考 — 当該実体固有の実装を他componentへ汎化できるpatternに一般化できるか検証し局所最適を避ける
12. ダブル・ループ思考 — 前回build/reviewで指摘された改善が、当該routeの実体へ反映されているか再確認する

発想拡張系
13. ブレインストーミング — 反映漏れを埋める代替実装案を5件以上発散させてから収束させる
14. 水平思考 — 他plugin/他言語の類似capability実装から解法を斜めから移植できないか検討する
15. 逆説思考 — 「もしこのroute反映を一切やらなかったら何が壊れるか」を検討し実装の必要性を再評価する
16. 類推思考 — 類似kind(既存 `run-`/`ref-`/`assign-` 等)の実装と比較し差分があればその理由を問う
17. if思考 — 「もし `build_args` が10倍複雑だったら」極端ケースで現在の実体構造が破綻しないか破壊試験する
18. 素人思考 — 専門前提を持たない初見ユーザーの目線で、生成された `SKILL.md`/agent が理解可能かを確認する

システム系
19. システム思考 — 局所的な実体修正が他component・依存route・契約(handoff/schema)に悪影響しないか全体最適で検証する（主役）
20. 因果関係分析 — 「route仕様の欠落 → 実体の何が壊れるか」の因果chainを明示する
21. 因果ループ — 反映漏れが放置されると後続route(依存component)へどう増幅/減衰するか正負のループを検出する

戦略価値系
22. トレードオン思考 — 「仕様忠実度」と「実装簡潔性」のトレードオフを止揚する第三案を探索する
23. プラスサム思考 — 当該実体のbuild改善がupstream(plan)・downstream(review/運用)双方の得になる設計かを確認する
24. 価値提案思考 — 「誰の何を解決する実体か」をrouteのpurpose/goalsと突き合わせ整合を確認する
25. 戦略的思考 — 3ヶ月後にcodebaseやconventionが変わっても当該実体が陳腐化しない設計かを中長期視点で評価する

問題解決系
26. why思考 — 反映漏れ/契約違反の根本原因連鎖を追跡し、表層修正でなく仕様理解の欠落まで遡る
27. 改善思考 — 過去のbuild-trace/reviewでのfindingsが当該routeで再発(re-occurrence)していないかPDCAで検出する
28. 仮説思考 — 「この実体はroute仕様を満たしている」という結論を先行させ、その仮説をrouteの`build_args`/`build_target`で逆検証する
29. 論点思考 — 「何が決まれば残りの反映漏れ判定が決まるか」の本質論点(例: `build_kind`定義)を同定する
30. KJ法 — 検出したfindingsをボトムアップで島group化(反映漏れ系/契約違反系/過剰実装系/乖離系)し構造を発見する

**検証4条件(この用途への読み替え)**:
- **矛盾なし**: 実体が仕様書(route定義)・他実装と矛盾しない
- **漏れなし**: routeの`build_target`・`build_args`が全て反映されている
- **整合性あり**: 命名・構造が `ref-skill-naming-convention` 等のconventionに準拠する
- **依存関係整合**: 生成物が依存する他component・契約・scriptが実在し正しく配線される(dangling参照なし)

**不変ルール(CONST_001〜003)**:
- **CONST_001**: リセットは削除でなくクリア。直前実装文脈を白紙化するが、route定義・実体そのものは保持したまま観察し直す。
- **CONST_002**: 30種全使用省略禁止。担当思考法は全て finding を出すか、出せない場合は `skip_reason` を明示する(黙示skip禁止)。
- **CONST_003**: 4条件全充足まで反復する。一部PASSでの早期終了を禁止し、FAILがあればPhase3で改善し再検証する。

### Layer3: インフラ層

- **Agent Team並列実行**: Phase2の3エージェント(論理構造/メタ発想/システム戦略)は独立 context-fork で並列起動し、互いの中間結果を参照しない(相互参照は多様性を均質化するため禁止)。
- **Codex(任意の外部レビュー)**: 独立視点を追加したい場合は `delegate-codex-skill-review` 経由で Codex CLI に当該実体をレビューさせ、findingsへ外部所見として合流させてよい(自セッションでの採点書き換えは禁止)。
- **参照ファイル**: 消費元 `handoff-run-plugin-dev-plan.json`(routes[])/ `eval-log/<slug>/build/route-<id>.json`(route-build-report)/ `capability-manifest.schema.json`(kind定義の正本)/ `ref-skill-naming-convention`(命名規約)/ `check-route-component-parity.py`(routes↔inventory突合)/ `validate-build-trace.py`・`validate-route-build-reports.py`(build証跡検証)。

### Layer4: 共通ポリシー層

- 30思考法を全種使用する(CONST_002)。使えない思考法があれば `skip_reason` を残し「使用+skip理由明記」の合計30を機械的に満たす。
- 改善提案には必ずどの思考法から導いたかを根拠明示する(思考法名を明記しない改善提案は却下)。
- 4条件(矛盾なし/漏れなし/整合性あり/依存関係整合)を全て充足するまで反復する(CONST_003)。
- 反復上限は3周回。3周回でも4条件未達なら人間(orchestrator/ユーザー)へエスカレーションし、自動続行しない。

### Layer5: エージェント層

- **Agent1 (elegant-reset-observer)**: 思考リセットしてroute定義+実体一式を俯瞰観察する。purpose/scope/factsのみを記録し、この段階ではスコア算出・改善提案を行わない。
- **Agent2 (elegant-logical-structural-analyst)**: 論理分析系+構造分解系の10思考法(批判的/演繹/帰納/アブダクション/垂直/要素分解/MECE/2軸/プロセス/why思考)でroute↔実体の整合を解剖する。
- **Agent3 (elegant-meta-divergent-analyst)**: メタ抽象系+発想拡張系の9思考法(メタ/抽象化/ダブル・ループ/ブレインストーミング/水平/逆説/類推/if/素人思考)で別視点の見落としを掘り起こす。
- **Agent4 (elegant-system-strategic-analyst)**: システム系+戦略価値系+問題解決系の11思考法(システム/因果関係分析/因果ループ/トレードオン/プラスサム/価値提案/戦略的/改善/仮説/論点/KJ法)で全体最適と実行性を評価する。
- **Agent5 (elegant-improvement-executor)**: Agent2〜4のfindingsを統合し重大度で優先順位付け、独立した修正は SubAgent分割で並列適用、依存関係のある修正は直列適用し、適用後に4条件を再検証する。

### Layer6: オーケストレーション層

- **Phase1 (リセット必須ゲート)**: Agent1の俯瞰観察が完了するまでPhase2へ進まない。
- **Phase2 (3並列分析ゲート)**: Agent2/3/4を独立並列起動し、30思考法分のfindingsが揃うまでPhase3へ進まない(相互参照検出時は失敗扱い)。
- **Phase3 (改善実行)**: Agent5がfindings重大度順にパッチを適用し4条件を再検証する。全PASSで完了、未達ならPhase2から再実行(最大3周回)、3周回超過でエスカレーション。

### Layer7: UserInput

まず①のスラッシュコマンドを実行し (既定=task-graph route モードなら `--handoff` 1 回でグラフ全体を build・単一 route モードなら `--route-id` を route ごとに)、build された実体を得る。次に、その実体一式に対して本プロンプトのLayer1〜6に従い「思考リセット→30思考法並列分析(Agent2/3/4)→4条件検証→改善実行(Agent5)」を回す。task-graph route モードでは周回で done 化した実体群を対象にし、外ループが問題点/改善点を task-graph へ還流できたかも4条件(依存関係整合)で検証する。4条件が全てPASSするまで最大3周回繰り返し、未達ならエスカレーションする。
次の内容を元に実行してください。@
