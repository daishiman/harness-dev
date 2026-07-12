---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計・TDD Red)

## 目的
C01/C02 の `feedback_contract.criteria` (IN1-IN16/OUT1-OUT3) を test-first で確定する。既存C2/C4/C13-C16に加え、C17 TaskExecutionEnvelope、C18 状態三層parity、C19 cross-cycle lineage/knowledgeの正常・異常fixtureを内包する。

## 背景
goal-spec の checklist は verify_by=script/test/human の 3 種を持つ。script/test 系は本 phase で具体的なテストケース (入力/期待出力) を確定し、P05 で最小実装設計を Green にする対象とする。human 系 (C8) は C02 の意味判定プロンプト手順として P05 で設計する。

## 前提条件
- P03 の design-review が PASS している。

## ドメイン知識

### C2 受入例 (task-graph 導出 → validator exit0)
derive-task-graph.py の新shape導出ルール: phase文書は共通policy、`task-specs/<task-id>.md`は1検証可能成果物の実行契約、component-inventory/handoff routeはbuilder写像として別々に読む。leafは`execution_kind`+`task_spec_ref`必須、component-buildだけが`route_ref`を持ち、`entity_ref`は分類専用。component依存は配下task集合の直積へ展開せず、上流componentのcompletion barrierまたは成果物の`produces/consumes` joinへ1回だけ写像する。

本 plan 自身の一部を入力とした受入例 (満たす例):
| id | phase_ref | execution_kind | route_ref | task_spec_ref | depends_on | produces | consumes |
|---|---|---|---|---|---|---|---|
| T1 | P02 | direct-task | null | task-specs/T1.md | [] | A1=component-inventory.json | [] |
| T2 | P05 | component-build | C01 | task-specs/T2.md | [T1] | A2=C01 route report | [A1] |
| B1 | P05 | phase-gate | null | null | [T2] | A3=C01 completion barrier | [A2] |
| T3 | P09 | component-build | C02 | task-specs/T3.md | [B1] | A4=C02 route report | [A3] |

この4 nodeではC02→C01のcomponent依存を`T3→B1`の1 edgeだけで表し、C01/C02配下taskの全組合せを結ばない。validatorはDAG非循環・orphan 0・producer一意・inventory矛盾0に加え、推移冗長edge 0、同一`(phase_ref,title,route_ref)`複製0、`depends_on_edges <= max(2 * executable_nodes, 1)`を確認してexit0とする。負例はC01に10 task、C02に10 taskを置き100本の直積edgeを作るfixtureで、同じ意味をbarrier 1本で表せるため`cartesian-component-dependency`としてexit1。`T3→T2`をB1と重ねて追加するfixtureも推移冗長としてexit1。

### C4 受入例 (ready-set 計算・4 ケース)
runtime stateは下表の`task-state.json` fixtureから読み、canonical graphのseed stateは全nodeでpending固定のままにする。上表のT1-T4に加え、write_scope衝突検証用のT5 (T1にのみdepends_on、T2と同一write_scope) を追加する。

| id | write_scope | depends_on | state |
|---|---|---|---|
| T1 | component-inventory.json | [] | done |
| T2 | scripts/derive-task-graph.py | [T1] | pending |
| T3 | prompts/R1-evaluate.md | [T1] | pending |
| T4 | handoff-run-plugin-dev-plan.json | [T2, T3] | pending |
| T5 | scripts/derive-task-graph.py (T2 と同一) | [T1] | pending |

4 テストケースと期待 ready-set:
1. **直列チェーン**: T5 を除外し T3 も未定義とした T1(done)→T2(pending)→T4(pending, depends_on=[T2]) のみの単純チェーンで検証。期待 ready-set = `{T2}` (T4 は T2 未完了のため対象外)。
2. **ダイヤモンド依存**: T1(done)→{T2, T3}(いずれも pending・write_scope 非重複)→T4(depends_on=[T2,T3])。期待 ready-set = `{T2, T3}` (両者 write_scope 非重複のため並列投入可能・T4 は未対象)。
3. **blocked 伝播**: ケース2 の T2.state を `blocked` に変更。期待 ready-set = `{T3}` (T2 は blocked のため pending への遷移を経ず ready-set から除外され、depends_on=[T2] を持つ T4 も T2 未完了のため対象外のまま。blocked は「未完了」より強い除外状態として扱われ、T2 自身の depends_on 充足有無に関わらず ready-set に入らない)。
4. **write_scope 衝突**: T1(done)→{T2, T5} (両者 depends_on=[T1] のみ・write_scope が同一)。期待 ready-set=`{T2}`、deferred=`{T5}`、conflicts=`[(T2,T5)]`。id昇順の決定論winnerだけをdispatchし、winner done後にdeferredを昇格する。両者除外はready=0の人為的deadlockを作るため不採用、非決定的選択も禁止する。
5. **done だが成果物欠落 (負例)**: T1(state=done・`produces` A1=component-inventory.json)→T2(state=pending・depends_on=[T1]・`consumes` A1)。T1.state=done であっても producer 成果物 A1 の解決パスがファイルシステム上に存在しない (異常終了・部分書込・route-build-report 未生成) 場合。期待 ready-set = `{}` (T2 は depends_on 条件 T1=done を充足するが、compute-ready-set.py の `os.path.exists` による consumes 成果物実在検査が A1 欠落を検出して T2 を除外する)。この負例は「producer state==done を成果物実在の代理述語にせず artifact 実パスを独立検査する」設計 (P05 の compute-ready-set.py 節) を固定し、done だが成果物欠落の異常状態を ready-set が誤って並列投入候補にしないことを保証する。

### C13 受入例 (plan-ledger.json 検証)
`plugin-plans/<slug>/plan-ledger.json` の満たす例:
```json
{
  "schema_version": "1.0",
  "entries": [
    {"cycle_id": "20260601-task-graph", "status": "finished", "plan_dir": "plugin-plans/plugin-dev-planner/20260601-task-graph", "summary": "task-graph 第3射影の初回導入サイクル"},
    {"cycle_id": "20260705-cycle-ledger", "status": "active", "plan_dir": "plugin-plans/plugin-dev-planner/20260705-cycle-ledger", "summary": "plan 出力ディレクトリ規約の導入サイクル"}
  ]
}
```
`check-plan-ledger.py` を実行すると: cycle_id が `CYCLE_ID_RE` (`^\d{8}-[a-z0-9-]+$`) に一致・各 status が `LEDGER_STATUSES` (active/finished/superseded) に属する・active status のエントリが 1 件のみであることが確認され、**exit0** となる。満たさない例: 2 件目の `status` を `"active"` のまま 1 件目にも `"status": "active"` を設定 (同時 active 重複) すると、`check-plan-ledger.py` は「同時 active 重複」を fail-closed で検出し exit1 となる。`plan_output_dir(name, out_dir=None, base=PLAN_OUTPUT_BASE, cycle_id=None)` は `cycle_id` 省略時に現行の `plugin-plans/<plan_slug(name)>` (flat 配置) を返し、`cycle_id` 指定時のみ `plugin-plans/<plan_slug(name)>/<cycle_id>` を返す (既存呼出元は無改修で現状動作を維持)。

### C14 受入例 (A/B比較・新旧shape非劣化)
同一構想「T2: derive-task-graph.py 設計確定」を旧shape/新shapeそれぞれで生成した fixture ペア:

**旧shape fixture** (13 phase 固定・phase-05-implementation.md §5 の 1 項目):
```
- [ ] derive-task-graph.py の決定論導出ルールを実装する。
```

**新shape fixture** (task-graph 駆動・task node):
```json
{"id": "T2", "title": "derive-task-graph.py 設計確定", "phase_ref": "P05", "entity_ref": "implementation", "execution_kind": "component-build", "route_ref": "C01", "task_spec_ref": "task-specs/T2.md",
 "depends_on": ["T1"], "produces": ["A2=derive-task-graph 設計節"], "consumes": ["A1"],
 "acceptance_criterion": "task spec 1件から実行可能leaf 1件を導出し、phase_ref policyとroute_ref=C01を明示joinする。component依存はcompletion barrier/artifact joinへ1回だけ写像され、C2上表と一致する"}
```

(a) 精度比較: 旧shapeの完了チェックリスト1項目は暗黙でも1受入単位として扱うためlegacy基準線は1/1=100%とする。新shapeは暗黙性を許さず、全実行可能leafが非空かつ二値判定可能な`acceptance_criterion`と1件以上の成果物を持つ場合だけ携帯済みと数える。満たす例: T2が1/1=100%で基準線と同等以上。満たさない例: `acceptance_criterion`欠落、成果物欠落、検証不能語だけのcriterionはいずれも0/1となりexit1。平均値で欠落nodeを隠さず全leaf 100%を要求する。
(c) 再現性比較: 満たす例: 同一 goal-spec/component-inventory.json を入力に `derive-task-graph.py` を 2 回連続実行し、出力 task-graph.json が byte 一致 (ノード集合 {T1,T2,T3,T4}・エッジ集合が両実行で完全同一) することを検証する。満たさない例: 2 回目の実行で dict 反復順序に依存した非決定的な key 順が出力に混入し 1 バイトでも異なれば `check-shape-non-regression.py` は再現性軸で exit1。
(b) 品質比較 (C02 genuine 判定・script では計測不可のため参考記載): fork evaluator が上記 2 fixture を A/B 比較し、新shape fixture の `acceptance_criterion` が「derive-task-graph.py の出力が具体的にどのテーブルと一致すべきか」という下流 builder AI の追加質問を要さない事前解決済み判断を内包しているか、旧shape fixture の抽象記述と比べ実効性が劣化していないかを genuine 判定する (plan-findings.json の bucket `shape-ab-comparison` へ計上)。満たす例 (劣化なしと判定): 上記新shape fixture の criterion「task spec 1件から実行可能leaf 1件を導出し、phase_ref policyとroute_ref=C01を明示joinする。component依存はcompletion barrier/artifact joinへ1回だけ写像され、C2上表と一致する」は、期待する出力構造 (leaf 件数・join対象 phase_ref/route_ref・依存の写像回数・突合先=C2上表) を事前解決済みで内包するため、下流 builder が「何を何本、どのテーブルへ突き合わせて作るか」を追加質問せず実装でき、旧shape の抽象1行と比べ実効性は劣化なしと genuine 判定される (この場合 shape_marker=`task-graph-derived` を採用可)。満たさない例 (劣化ありと判定→fallback): 新shape fixture の criterion を「タスクグラフを適切に導出する」等の抽象語のみに差し替えると、下流 builder が「適切とは何か・何をどこへ突合するか」を必ず追加質問することになり、旧shape の暗黙記述から実効性が劣化する (criterion が在るのに判断を内包しない分、事前解決済みと誤認させて悪化する)。この場合 C02 は劣化ありと genuine 判定し、shape_marker は `task-graph-derived` を採らず `fixed-13-phase` へ fallback する。

**block/fallback**: (a)(c) いずれかが exit1、または (b) で C02 が劣化ありと genuine 判定した場合、shape_marker は `task-graph-derived` を採用せず `fixed-13-phase` へ fallback する (C10⇔C14 相互参照)。

### C15 受入例 (byte一致 render + graph 外要素非描画)
C15専用の4 node fixture (T1=done, T2/T3/T4=pending) を入力に `render-task-graph-mermaid.py` を実行すると、node id・エッジ種別を C11 の canonical 順序 (安定 key 順) のまま走査し、以下の mermaid を決定論生成する:
```
graph TD
    classDef pending fill:#eee
    classDef running fill:#bbf
    classDef done fill:#bfb
    classDef blocked fill:#fbb
    T1["C01/C02 component-inventory 確定"]:::done
    T2["derive-task-graph.py 設計確定"]:::pending
    T3["R1-evaluate.md C8判定ステップ設計確定"]:::pending
    T4["handoff task_graph_ref 検証設計確定"]:::pending
    T1 --> T2
    T1 --> T3
    T2 ==> T4
    T3 ==> T4
```
線種区別: `parent_of`=細実線矢印 (`-->`)、`depends_on`=太実線矢印 (`==>`)、`produces`=破線矢印 (`-.->`)、`consumes`=円形終端 (`--o`) の 4 種を個別に割り当てる (本例は depends_on のみのため `-->`/`==>` の 2 種が出現)。クリティカルパス強調: `depends_on` のみを辺とする最長路 (T1→T2→T4 と T1→T3→T4 はいずれも長さ 2 で tie。tie 時は node id の辞書順で先行する経路 T1→T2→T4 を採用) を `linkStyle` で太線・強調色に上書きする。

満たす例 (byte一致): 同一 task-graph.json に対し `render-task-graph-mermaid.py` を 2 回連続実行した出力が byte 一致する (node/edge の走査順が C11 canonical 順序に固定されているため非決定的な dict 反復順の混入がない)。
満たさない例 (graph 外要素非描画): 出力 mermaid からノード id 集合を抽出し、入力 graph の `nodes[].id` 集合と set 一致することを検証する。renderer が graph に存在しない装飾ノード・ラベル文言 (node.title 以外の独自解釈テキスト) を追加すると、抽出集合が graph の id 集合と不一致になり検査は fail-closed で検出する。

### C16 受入例 (task-state schema 整合 + graph_hash pin 整合)
`task-state.schema.json` 準拠の満たす例:
```json
{
  "schema_version": "1.0",
  "graph_hash": "sha256:3f9a...",
  "nodes": [
    {"id": "T1", "state": "done"},
    {"id": "T2", "state": "running", "started_at": "2026-07-05T10:00:00Z", "lease_expires_at": "2026-07-05T10:30:00Z"}
  ]
}
```
1. **schema 整合 (満たす例/満たさない例)**: 満たす例=上記 fixture (schema_version が文字列・graph_hash が `sha256:` 接頭+16進文字列・各 node.state が `TASK_NODE_STATES` 値域内・`state:"running"` の node が `started_at`/`lease_expires_at` を両方携帯) を `check-task-state-schema.py` に通すと exit0。満たさない例=`state:"running"` の T2 から `started_at` を欠落させると、lease 不整合 (孤児 running を機械判別できない) として fail-closed で検出し exit1。
2. **graph_hash pin 整合 (満たす例/満たさない例)**: 満たす例=`task-state.json.graph_hash` が現在の `task-graph.json` の canonical bytes から C11 のロジックで再計算した hash と一致する場合 exit0。満たさない例=discovered-task 受理で task-graph.json にノードが追加された後も `task-state.json.graph_hash` が更新されないまま残ると、再計算 hash との不一致を `check-task-state-schema.py` の pin 検査が fail-closed で検出し exit1 (反映は次周回のみという constraints を機械強制する)。

### C17 受入例 (task spec → TaskExecutionEnvelope)
- 満たす例: leaf `T2` が `execution_kind=component-build`、`route_ref=C01`、`task_spec_ref=task-specs/T2.md` を持ち、renderer出力に `task_id/objective/phase_policy_ref=P05/component_route=C01/acceptance_criteria/write_scope/injected_inputs/injected_notes/knowledge_refs/verify` が揃う場合、validatorはenvelope完全性を確認してexit0。P01..P13全文は埋め込まない。direct-taskはroute_ref無し、phase rootはphase-gateでdispatch対象外。
- 満たさない例: `execution_kind`/`task_spec_ref`欠落、component-buildの`route_ref`欠落、`entity_ref`だけからrouteを推測、titleだけのprompt、13 phase全文連結のいずれかをvalidatorがexit1で拒否する。

### C18 受入例 (構造・状態・観測の三層parity)
- 満たす例: pending→running→doneの遷移前後で`task-graph.json`のbytes/hashが一致し、`task-state.json`と`task-events.jsonl`だけが更新される場合、parity検査は三層分離を確認してexit0。projection再生成後の`task-graph-status.json`/`task-progress.md`/`task-execution-report.html`はT2=doneを示す。HTMLは同一入力の2回生成がbyte一致し、外部URL/script不在、HTML escape、inline SVG図解、印刷CSS、route evidence/build-summary完了ゲートの反映を機械検証する。
- 満たさない例: graph node.stateを直接doneへ変更したfixtureはcanonical/hash gateがexit1で拒否する。discovered-task採用時は旧revision/hash/完了evidenceを不変保持し、task spec Edit後に新revision/hashを発行してlineageを記録できる場合だけexit0。旧revision/hash/完了evidenceを保持せず上書きした、または旧hashを据え置いたfixtureはexit1で拒否する。

### C19 受入例 (cross-cycle lineage/knowledge)
- 満たす例: finished cycle Aとactive cycle Bを`predecessor_cycle_id`で結び、Bのtask specが関連する`knowledge_refs[{id,source_ref,freshness_checked_at,decision}]`だけを持ち、Aのnode idがBのactive graphに0件である場合、lineage/knowledge検査はexit0。
- 満たさない例: source_ref無し、freshness未確認、全文spec/全notes注入、旧nodeのactive graphコピーのいずれかが混入すればexit1で拒否する。MF決済インボイスチェックの次改善では過去知見を候補検索し、採用/不採用理由を記録する。

## 成果物
- feedback_contract.criteria IN1-IN16 / OUT1-OUT3 の確定。
- 上記 C2/C4/C13/C14/C15/C16 の受入例テーブル・fixture (本 phase 本文が正本)。

## スコープ外
- 実装コード (P05 で設計プローズとして確定し、L4 build で実コード化)。

## 完了チェックリスト
- [ ] C2 の受入例 (満たす例/満たさない例) が具体的な node/edge データで内包されている。
- [ ] C4 の 4 テストケース (直列チェーン/ダイヤモンド/blocked伝播/write_scope衝突) + 「done だが成果物欠落」負例 (os.path.exists による consumes 成果物実在検査) が期待 ready-set 付きで内包されている。
- [ ] IN1-IN16/OUT1-OUT3 が component-inventory.json の C01.feedback_contract.criteria と一致する。
- [ ] C13 の plan-ledger.json fixture (満たす例/満たさない例) と `plan_output_dir()` の cycle_id 省略時後方互換動作が具体的に内包されている。
- [ ] C14 の A/B比較受入例 (旧shape fixture/新shape fixture) が (a)精度携帯率・(b)品質genuine判定・(c)再現性byte一致の3軸それぞれで満たす例/満たさない例付きで内包され、block/fallback 条件が明記されている。
- [ ] C15 の byte一致 render 例と graph 外要素非描画検査 (node id 集合の set 一致) が満たす例/満たさない例付きで内包されている。
- [ ] C16 の task-state schema 整合例と graph_hash pin 整合例 (満たす例/満たさない例) が具体的な fixture 付きで内包されている。
- [ ] C17-C19の正常/異常fixtureと期待exitが内包されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記の C2/C4/C13/C14/C15/C16 テーブル・fixture の通り、具体的な node id・write_scope・depends_on・期待 ready-set・cycle_id・status・acceptance_criterion 携帯率・graph_hash・lease フィールドが数値/文字列で確定している。
- 満たさない例: 「ready-set 計算のテストケースを複数用意する」とだけ記され、具体的な期待値が未確定のまま P05 へ進む。

### 事前解決済み判断
- 分岐点: write_scope衝突時に両者除外するか決定論winnerを選ぶか → 判断: id昇順winnerを1件ready、残りをdeferred。両者除外によるready=0 deadlockを避けつつ再現性を保つ。

## 参照情報
- `plugin-plans/plugin-dev-planner/component-inventory.json` (C01.feedback_contract.criteria)。
- P02 (design)。
- 後続 P05 (implementation)。
