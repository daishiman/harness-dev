# task-graph 契約 (第3の射影・producer=plugin-dev-planner 所有)

plan 成果物の 3 射影のうち第3。13 phase ファイル (人間可読ライフサイクル軸) と component-inventory.json
(機械 SSOT・実体軸) に加え、タスク単位の依存エッジ・成果物連結・並列実行可能性を型付けした
**task-graph** を導入する。本 skill (producer) が schema/導出/検証/ready-set 計算/graph_hash 算出を
所有し、L4 実行系 (consumer=harness-creator) はそれを消費するのみで再実装しない (SSOT)。

## 用語対応 (実行単位の 3 概念)
似た語が別階層を指すため冒頭で固定する:

| 用語 | 定義 |
|---|---|
| **node** (task node) | task-graph.json 上の**実行単位**。id/phase_ref/entity_ref/write_scope を持ち dispatch の主体になる |
| **task spec** | **実行仕様の宣言正本** (`task-specs/<task-id>.md` frontmatter)。objective/verify/acceptance_criteria/knowledge_refs を node ごとに宣言し、dispatch 対象 node が `task_spec_ref` で携帯する |
| **TaskExecutionEnvelope** | dispatch 直前に node + task spec + 単一 phase policy から `render-task-execution-envelope.py` が決定論合成する**合成済み実行契約 packet**。consumer は envelope を SubAgent prompt の唯一の入力として扱う |

## schema (schemas/・producer 所有 SSOT)
| schema | 役割 |
|---|---|
| task-graph.schema.json | nodes(id/title/phase_ref/entity_ref/state/write_scope) + edges(parent_of/depends_on/produces/consumes)。`blocks` は独立宣言禁止の派生ビューゆえ edge type に非列挙。canonical graph の state は pending seed 固定、runtime の pending/running/done/blocked は task-state.json のみが所有し、ready は computed-only とする |
| discovered-task.schema.json | build 中発見タスク (E4)。discovering_task_id/reason/discovered_at_artifact/proposed_node/change_level(additive\|structural)。provenance.route_id は optional additive |
| handoff-notes.schema.json | went_well/friction_points/downstream_watchouts。各 maxItems 3 / maxLength 200 の**単一正本** (task-state の handoff_notes が $ref する) |
| plan-ledger.schema.json | cycle 台帳 (cycle_id/status/plan_dir/summary + optional predecessor_cycle_id)。status=active/finished/superseded。predecessor_cycle_id は過去 cycle への immutable lineage (C19・実在参照/自己参照禁止/閉路禁止) |
| task-state.schema.json | runtime state (C16)。永続 state 4 値 (ready 除外)。graph_hash pin・running→lease 必須・blocked→blocked_reason(origin-failure\|propagated) 必須。node は additionalProperties:true (consumer の route_report/handoff_notes 拡張を許容) |
| task-execution-envelope.schema.json | dispatch 前に合成する SubAgent 実行契約 (C17)。task_id/execution_kind/objective/phase_policy_ref(単一)/component_route/acceptance_criteria/write_scope/injected_inputs/injected_notes($ref handoff-notes)/knowledge_refs/verify。title 単独・暗黙 route・13 phase 全文注入を構造で拒否 |

## edge 方向の意味論 (from/to の読み方)
edge の `from`/`to` は type ごとに意味が異なる。初見の誤読 (特に depends_on の向き) を防ぐため固定表とする:

| type | from | to | 読み方 |
|---|---|---|---|
| depends_on | 待つ側 task | 待たれる側 task | **from が to の done を待つ** (to が先行) |
| parent_of | 親 (phase 仮想ルート) | 子 task | from が親・to が子 |
| produces | producer task | artifact id | **from が to (artifact) を生産する** |
| consumes | artifact id | consumer task | **from (artifact) が to の入力として消費される** (実在検査対象) |

## write_scope の 2 用法
`write_scope` は並列衝突判定キーとして全 node 必須だが、node 種別で意味が異なる:

1. **entity 紐づき task node** = **排他書込パス** (component-inventory の build_target)。同一パスを持つ候補は
   ready-set で直列化される (単一 winner)。
2. **checkpoint node** (entity_ref=null の task・phase 仮想ルート) = **自 node id の擬似 scope**。実パスを
   書かないため node id を scope に流用し、定義上他 node と衝突しない (一意)。

## scripts (scripts/)
- **derive-task-graph.py**: 13 phase §5 チェックリスト項目 + inventory → task-graph.json を**決定論導出**。`canonicalize()` が唯一の正準 writer (nodes=id 昇順 / edges=(type,from,to) 昇順 / 固定 key 順)。`graph_hash(graph)="sha256:"+sha256(canonical_json)`。
  - **phase ライフサイクル順序 edge**: 「1 task 完了 → done 記述 → それが次 task の発火条件」という event 駆動チェーンを graph 構造で保証するため、component 依存 (inventory) とは別に phase 順序 depends_on を焼く: (1) phase marker (root) は自 phase の全 leaf に depends_on (marker done = phase 完了の集約点。parent_of と同じ marker→leaf 向きゆえ DAG 閉路を作らない)。(2) 各 phase の leaf は直前 phase marker に depends_on (前 phase の全 leaf done → marker ready→done → 次 phase leaf ready の直列チェーン)。これで後段 phase (final-review 等) が実装 phase 完了前に ready 化する順序逆転を封じる。compute-ready-set は readiness を depends_on のみで判定し parent_of を無視するため marker↔leaf の parent_of は readiness に干渉しない。
  - **接合が密な兄弟ペアの直列化 (couples_with)**: inventory の optional `couples_with: [<component id>]` (対称宣言) を、同一 phase 兄弟の直列化 depends_on へ機械展開する。`depends_on` (成果物ハード依存) とは別概念で、「成果物依存は無いが同時 build すると統合 finding が両方 build 後まで先送りされる密結合 (共有 contract を挟む producer↔consumer 等)」を宣言する。展開規則: (1) 既に component depends_on で順序付いたペアは skip (逆順追加による cycle 化を防ぐ)。(2) 向きは entity id 昇順で decisive に固定 (小 id を先発=prereq)。(3) phase 逆走は焼かない (異 phase ペアは phase 順序 edge が既に直列化するため無介入)。**`couples_with` は同一 phase 専用**であり、cross-phase ペアへの宣言は直列化 edge を焼かない **silent no-op** になる (derive は stderr へ advisory を出す)。異 phase の因果的な build 順序が必要なら `couples_with` でなく `depends_on` を使う (depends_on は (i) future-phase 検査で方向逆転を弾く保証を受けられるが couples_with は対称ゆえ受けられない)。直列化の機構は既存 depends_on を流用する (consumer=compute-ready-set が depends_on を直列化するため追加 edge type/機構が不要・生成ハーネスの checklist へも depends_on として伝播)。**過剰宣言しない**: 真に接合が密なペアのみ宣言し無関係兄弟の並列性を保つ (幅広 DAG の利点を殺さない)。
- **validate-task-graph.py**: DAG 非循環 / orphan 0 / producer 一意 / inventory depends_on 実現性 / consumes producer 実在 / **couples_with 直列化実現 (j)** / 非正準拒否 (canonicalize 再適用と不一致)。(j) は宣言した couples_with が直列化 depends_on で実現され参照先が実在 component であることを検査 ((d) inventory depends_on 実現の鏡像)。既に depends_on 順序付きペアは (d) が担い対象外。
- **lint-sibling-coupling.py** (advisory・ハード 12 ゲート外): 未宣言の密結合な同一 phase 兄弟ペア候補を record-only 検出する安全網。derive は consumes edge を焼かずグラフから密結合を推論できないため、inventory のテキスト参照 (B の inputs/purpose が A の出力ファイル名を参照=producer→consumer データ流) を唯一の決定論シグナルにして、couples_with も depends_on も持たない兄弟ペアを候補提示する。判断は architect (宣言) に残し機構は候補を漏らさない。既定 exit0 (record-only)・`--strict` で候補>0 を exit1。
- **compute-ready-set.py**: depends_on 完了 + consumes 成果物実在 (`os.path.exists` で producer state==done の代理述語にせず独立検査) の ready-set を決定論計算。候補内 write_scope 衝突は「fail-closed 全除外」ではなく**決定論 tie-break (id 昇順) で単一 winner のみ ready・残りは deferred** として次周回へ持ち越す (直列化。winner done 化で scope が解放され deferred が昇格するため ready 0 件デッドロックを構造的に排除。非決定的タイブレークは禁止のまま)。deferred は winner との衝突ペアを `conflicts` に記録する。
- **accept-discovered-task.py**: additive は即時反映 (canonicalize)、structural は `--approved` 必須の二段受理。`--form` 単発受理に加え **`--inbox <dir>` で discovered-task inbox を一括ドレイン** (外ループ帰路 FC-6)。ドレインは filename 昇順で走査し additive を累積受理・各 form へ `status`(accepted/rejected)・`resulting_graph_hash` を書き戻す (structural 未承認は pending 据置)。**接合が密な既存兄弟との直列化 (外ループ追記の盲目並列防止)**: proposed_node の optional `couples_with` (既存兄弟の entity_ref id 群) が宣言されていれば、同一 phase の当該兄弟 node の**後**へ直列化 depends_on (from=新ノード to=兄弟) を張る。plan-time の derive は両兄弟未 build ゆえ id 昇順で対称直列化するのに対し、外ループの新タスクは既存兄弟が既に build 中/済ゆえ「新タスクは既存兄弟の後」が因果的に正しい (統合面を観測してから新規 build)。新ノードは leaf dependent ゆえ cycle を作らず additive のまま。consumer は `emit-discovered-task.py --node-couples-with <entity id>` で宣言する。
- **apply-handoff-notes.py**: 直接 depends_on/consumes 先行タスクへ有界伝播 + advisory/actionable 分類。
- **check-plan-ledger.py** / **migrate-plan-layout.py**: cycle 台帳検証 (同時 active 高々1) / flat→cycle-id 配置移行。
- **check-shape-non-regression.py**: 新旧 shape 非劣化 (受入基準携帯率 + byte一致再現性)。C14(b) 品質 genuine 判定は assign-plugin-plan-evaluator。
- **render-task-graph-mermaid.py**: canonical 順序で mermaid 導出 (byte一致・graph 外要素非描画)。
- **check-task-state-schema.py**: task-state schema 整合 + graph_hash pin 整合。
- **render-task-execution-envelope.py** (C17): dispatch 対象 node + 可変 task spec + 単一 phase policy から TaskExecutionEnvelope を決定論合成。`build_envelope(node, spec, graph, notes)` が title 単独/entity_ref 暗黙 route/component-build route 欠落/phase-gate dispatch/13 phase 全文注入を fail-closed 拒否し、schema 完全性を満たす envelope のみ返す。`task_spec_ref` と `--emit` は解決後も PLAN_DIR 内であることを必須とし、handoff が実在する場合は `route_ref` が `routes[].id` に実在するかも検査する。handoff 不在の従来単体利用は互換経路として維持する。consumer は envelope を SubAgent prompt の唯一の入力 packet として扱う。
- **project-task-status.py** (C18・parity 検査専用): `check_parity(graph, state)` が三層 parity (graph node 集合=state node 集合 / graph_hash pin 一致) を fail-closed 検証する。**投影ファイル (task-graph-status.json + task-progress.md + task-execution-report.html) は書かない** — projection writer は consumer (harness-creator TG-C09 `project-task-status.py`) が単一 writer (producer/consumer の二重 writer は出力 schema drift を招くため producer 側を検査専用へ縮退)。consumer HTML は status JSON と route reports/build-summary から自己完結・escape 済み・決定論的に生成し、Markdown は差分確認用として併存する。`--check-only` は後方互換 no-op。
- **check-cycle-knowledge.py** (C19): active cycle の task spec (task-specs/<id>.md frontmatter) の knowledge_refs (id/source_ref/freshness_checked_at/decision/reason) と external_inputs (path/hash) を有界検査し、`--predecessor-graph` 指定時は過去 cycle の node id が active graph へ混在していないか (過去 node の active DAG コピー禁止) を fail-closed 検証する。

## consumer 向け安定 CLI 契約 (FC-4/FC-5・破壊禁止)
consumer=harness-creator の L4 実行系は build 開始時の graph_hash pin を **read-only サブコマンドのみ**で取得する
(canonicalize()/graph_hash() を直接 import・subprocess 消費しない):

```
derive-task-graph.py --print-graph-hash <task-graph.json>
  argv:   --print-graph-hash <path>
  stdout: sha256:<64hex>\n
  exit:   0=成功 / 1=graph 不正で hash 算出不能 / 2=引数不足・IO エラー
```

`compute-ready-set.py` も consumer が subprocess 消費する (固定パス起動・stdout schema):

```
compute-ready-set.py <plan_dir> [--repo-root <path>]
  argv:   <plan_dir> 位置引数 (固定・<plan_dir>/task-graph.json を読む) + optional --repo-root
  stdout: {"ready_set":[id,...],"conflicts":[[id,id],...]} JSON (ready_set は sorted 決定論)
  exit:   0=OK (ready 空でも正常) / 1=読込不能 / 2=usage error
```

`render-task-execution-envelope.py` も consumer が dispatch 直前に subprocess 消費する (C17):

```
render-task-execution-envelope.py <plan_dir> --task-id <id> [--notes <handoff-notes.json>] [--emit <out.json>]
  argv:   <plan_dir> 位置引数 + --task-id (dispatch 対象 leaf node id) + optional --notes/--emit
  stdout: envelope JSON (--emit 未指定時) もしくは violations 列挙
  exit:   0=OK (envelope 合成成功) / 1=violation (title 単独/暗黙 route/route 欠落・不在/PLAN_DIR 外参照/phase-gate dispatch/13 phase 全文注入の合成拒否) / 2=usage/IO error・node 不在
```

**掲載基準: consumer が subprocess 消費する producer CLI は全て本節へ掲載する** (未掲載 CLI の subprocess 消費は契約外・掲載時に argv/stdout/exit 形状を固定する)。

consumes 成果物実在検査における**相対パス write_scope の解決基点は `--repo-root` (未指定時 cwd)**。
consumer は起動 cwd への依存 (cwd anchoring) を避けるため `--repo-root` に repo root を明示指定して
呼び出す (絶対パス write_scope は `--repo-root` の影響を受けない)。これらの
argv 形状 / stdout schema / exit codes を破壊すると consumer が沈黙破綻するため安定契約として固定する
(optional flag の追加は additive・既定挙動不変で許容)。

## 所有 / 書込分離 (C12/C16 と同型)
- **schema・graph_hash 算出規約・pin 検査ロジック**の所有 = producer (本 skill)。
- **task-state.json への実書込** (state 遷移・lease 更新・blocked_reason 記録・graph_hash pin) = consumer (harness-creator) が**単独 writer**。
- consumer は `blocked_reason` を第一級 schema field へ直接書き込む (notes.reason や advisory handoff_notes に混ぜない・状態理由と advisory を分離)。
- discovered-task の反映は producer が次の `--mode update` 周回で graph を更新する一方向 writer 契約 (consumer は emit のみ・graph 本体を直接編集しない)。

## 内ループ / 外ループ (2 ループ構造・改善還流)

task-graph の実行は 2 つの入れ子ループで駆動する。producer=本 skill は**外ループの改善器**、consumer=harness-creator は**内ループの実行器**を所有し、両者は 2 つの機構的ジョイントで縫合される。

- **内ループ (build-execution loop・consumer 所有)**: ready-set 計算 → 並列 dispatch → state write-back → 成果物注入を `ready_batch` が空になるまで反復し、現 task-graph を完了へ駆動する。1 周=1 dispatch batch。
- **外ループ (spec-improvement loop・producer↔consumer 横断)**: 現 task-graph が不十分 (build 中に plan 未網羅タスクを発見) なとき、consumer が discovered-task を emit → 完了ゲートで block → **producer が `--mode update --discovered-inbox` でドレインし task-graph を改善** → 新 `graph_hash` → consumer が改善済 graph を再消費。1 周=1 spec 改善。

**2 つのジョイント (両ループの結合点)**:
1. **完了ゲート = C08 (consumer)**: 未処理 discovered-task (status が accepted/rejected/superseded 以外) が inbox に 1 件でも残る間、consumer は build を completed にできない。これが内ループの完了を外ループの決着まで強制的に遅延させる縫合点。
2. **再入トリガ = graph_hash (provenance-gated)**: producer のドレインで graph が変わると canonical `graph_hash` が変化し、ドレインは accepted form の `resulting_graph_hash` に最終 graph_hash を焼く。consumer の pin 検証 (C07) は不一致検知時、現 graph の hash が accepted form の `resulting_graph_hash` と一致する場合のみ正当な再入として pin を再設定 (`repinned`)、一致しない差替えは不正混入として `mismatch` 拒否する。`resulting_graph_hash` を認可述語にして「不正改変の拒否」と「正当改善の受容」を両立させる。

一巡: consumer emit → consumer block(C08) → **producer drain(`--discovered-inbox`)** → consumer 再消費。stall (ready_batch 空だが未完了残存) のうち仕様不備由来のものは consumer が structural discovered-task として emit し、この単一ジョイントへ合流させる (外ループのトリガを discovered-task inbox に一本化)。

## cycle_id 携帯 (C13)
handoff トップレベル `cycle_id: str|None` (additive・null=flat 後方互換)。consumer はレイアウト判断に
必要な cycle-id を本フィールドから読み、plan_dir パス末尾解析は禁止 (二重実装防止)。goal-spec↔handoff の
cycle_id parity は check-build-handoff.py が検証する。

## execution_kind / TaskExecutionEnvelope (C17)
task-graph leaf node は `execution_kind` を携帯する (target shape・optional additive で fixed-13-phase は非携帯後方互換):

| execution_kind | route_ref | task_spec_ref | dispatch | 意味 |
|---|---|---|---|---|
| component-build | **必須** (明示 route id) | 必須 | する | component を build する route。entity_ref からの暗黙 route 推測は禁止 |
| direct-task | null | 必須 | する | route を持たない実行タスク |
| phase-gate | null | null 可 | **しない** | phase 完了の非 dispatch 集約点 |

- `entity_ref` は**分類/traceability 専用**であり builder 選択には使わない。component-build の route は必ず明示 `route_ref` で宣言する (暗黙 route を fail-closed 拒否)。
- **可変 task spec** `task-specs/<task-id>.md` は node ごとの実行契約を frontmatter で宣言する (objective/verify/acceptance_criteria/knowledge_refs)。dispatch 対象 leaf は `task_spec_ref` で結ぶ。
- `render-task-execution-envelope.py` が node + task spec + `phase_ref` の指す**単一 phase policy** から envelope を合成する。envelope は `task_id/execution_kind/objective/phase_policy_ref/component_route/acceptance_criteria/write_scope/injected_inputs/injected_notes/knowledge_refs/verify` を持ち、P01..P13 全文は埋め込まない (`phase_policy_ref` は単一 P0N 参照)。**title 単独 prompt・entity_ref 暗黙 route・task_spec_ref 不在/PLAN_DIR 外・component-build の route 欠落/handoff 上不在・--emit の PLAN_DIR 外・phase-gate dispatch・13 phase 全文注入**を exit1 で拒否する。handoff 自体が不在の従来単体利用は、route 実在検査を行わない後方互換経路とする。
- check-build-handoff.py の route↔producer 対応は、fixed-13-phase の produces 経路 (entity_ref) に加え component-build node の明示 `route_ref` を additive 合算し、どちらかで対応が取れれば充足とする (後方互換)。

### bootstrap→target 移行 gate (l・GAP-BOOTSTRAP-TARGET-SHAPE-001)
`execution_kind`/`route_ref`/`task_spec_ref` は schema 上 optional additive で、fixed-13-phase bootstrap は
これらを一切携帯せず `entity_ref` から route を暗黙推測する legacy join だった。GAP-BOOTSTRAP-TARGET-SHAPE-001 は
「C01 build 完了後の新規 plan から明示 route_ref parity を必須化し、legacy join は shape marker でだけ後方互換許可する」
と宣言していたが、optional の常態化で C17 が風化する (target shape へ一部だけ移行した中途半端 graph を誰も止めない)。
validate-task-graph.py `(l) _check_migration_gate` がこの移行を機械層で強制する (`_check_target_shape` (k) の
task-graph-derived 限定とは別の **marker 非依存 additive 層**)。

- **発火条件** (どちらか成立で発火): (a) target shape 採用宣言 = `execution_kind` を携帯する node が 1 つでも存在する
  (shape_marker に依らず発火)。(b) `shape_marker=task-graph-derived` (dispatchable node に `execution_kind` 必須という shape 宣言)。
- **非発火 (後方互換)**: `shape_marker=fixed-13-phase` かつ `execution_kind` 全不在 (現行 bootstrap plan)。
  `entity_ref` を持つ legacy node が多数あっても `execution_kind` が皆無なら発火しない。既存 6 bootstrap plan
  (plugin-dev-planner / harness-creator / mf-kessai-invoice-check{,-fidelity,-matching-rootcause} / with-task-graph-goalseek)
  はこの経路で移行 gate 非発火 = 追加 violation 0 (exit code 不変) を test_validate_task_graph.py が固定する。
- **要求 (発火時)**:
  - **(l1) 部分携帯 fail-closed**: `entity_ref` 非 null の全 node が `execution_kind` を携帯すること。一部 component node
    だけ target shape へ移行し他が legacy のまま残る「一番危険な中途半端 shape」を exit1 で拒否する。
  - **(l2) 明示 route_ref parity**: `execution_kind==component-build` の全 node が非空 `route_ref` を携帯すること
    (`entity_ref` からの暗黙 route 推測を禁止)。`direct-task`/`phase-gate` の `route_ref=null` は上表通りで (l2) の対象外
    ((k) が task-graph-derived shape の phase-gate/leaf 詳細を担う)。GAP 文言の「明示 route_ref parity」は route が発生する
    component-build node に scope する形で (l2) が実現する (schema の direct-task=route_ref null 意味論と両立)。

## 三層状態モデルと task-events (C18)
状態は 3 層に分離し、各層の writer/不変性を固定する:

| 層 | ファイル | 役割 | writer | 不変性 |
|---|---|---|---|---|
| 構造 | task-graph.json | canonical graph (構造 SSOT) | producer (derive) | **revision 内不変** (bytes/hash 固定) |
| 状態 | task-state.json | runtime state (遷移) | consumer 単独 | 遷移で更新 |
| 観測 | task-graph-status.json + task-progress.md + task-execution-report.html | 機械JSON + 差分確認Markdown + 構造化HTML実行記録の派生投影 | consumer (harness-creator TG-C09 project-task-status.py) が単一 writer / parity 検査=producer (本 skill scripts/project-task-status.py・検査専用) | state から純導出。最終HTMLは build-summary 保存後に再投影し完了ゲート/外ループ/route証跡を含む |

- **task-events.jsonl** は append-only のイベントログ (単一 writer=親 dispatcher)。state 遷移の履歴を追記のみで記録し、過去行を書き換えない (監査可能性)。1 行 = 1 イベント (JSON)。
- **三層 parity** (producer `project-task-status.check_parity`・検査専用): `--task-graph` / `--task-state` / `--status-json` の実配置を入力し、graph node 集合 = state node 集合 = projection node 集合、revision 内 graph_hash 不変、projection各state/summary = task-state を実比較する。graph node.state を直接 done へ書き換えた fixture は schema/validator と graph_hash pin の双方で fail-closed 拒否される (状態更新は task-state だけを触る)。
- discovered-task 採用時は旧 revision/hash/完了 evidence を immutable 保持したまま**新 graph revision/hash へ repin** する (旧 revision 上書き禁止)。

## cross-cycle lineage / knowledge (C19)
完了 cycle を immutable provenance として保持し、過去 node を active DAG へ混在させず、蒸留 knowledge と明示 artifact だけを有界再利用する:

- **plan-ledger** entry の optional `predecessor_cycle_id` が finished/superseded な過去 cycle への lineage を結ぶ。check-plan-ledger.py が実在参照/自己参照禁止/predecessor 連鎖の閉路禁止を検証する。
- **task spec の knowledge_refs** は `{id, source_ref, freshness_checked_at, decision(adopted|rejected), reason}` を持ち、**external_inputs** は過去 artifact の `{path, hash}` を明示する。source_ref 無し・freshness 未確認・decision 値域外は fail-closed 拒否 (check-cycle-knowledge.py)。
- **過去 node の active graph コピーは禁止**: check-cycle-knowledge.py `--predecessor-graph` が predecessor cycle の node id と active graph の node id の重複を検出して拒否する。再利用は source_ref 付き蒸留 knowledge + 明示 artifact のみ (全文 spec/推移的 notes の再注入は禁止)。
