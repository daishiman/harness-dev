---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装・TDD Green)

## 目的
P04 のテストケースを green にする最小実装設計を、C01 (run-plugin-dev-plan) の新規ファイル群と既存ファイルへの Edit 差分、C02 (assign-plugin-plan-evaluator) の既存プロンプト/schema への Edit 差分として確定する。本 phase は計画 (L3) であり実コードは書かないが、後段 build (L4・run-skill-create の Edit/新規ファイル mode) が従う実装設計をプローズで確定する。

## 背景
task-graphに関する既存C1-C16へ、C17 task execution envelope、C18状態三層parity、C19 cycle lineage/knowledgeをEdit差分で追加する。buildable componentはC01/C02のまま増やさない。

## 前提条件
- P04 のテストケース設計 (C2/C4 の受入例) が確定している。

## ドメイン知識

- **C1 実装設計 (新規)**: `schemas/task-graph.schema.json` を新設する。トップレベル `{"schema_version": "1.0", "nodes": [...], "edges": [...]}`。`nodes[]` の各要素は `{"id": str, "title": str, "phase_ref": "P01".."P13", "entity_ref": str|null, "state": "pending", "write_scope": str}` とし、canonical graph の `state` は後方互換 seed=`pending` に固定する。runtime の `pending|running|done|blocked` は C16 `task-state.json` のみが所有し、`ready` は compute-ready-set.py が都度導出する computed-only 出力で、いずれのSSOTにも永続化しない。task-graph.json 上で `done` 等へ直接更新することは validate-task-graph.py が拒否する。`edges[]` は `parent_of` / `depends_on` (consumer task→producer task) / `produces` (producer task→artifact) / `consumes` (artifact→consumer task) を持ち、schema の `additionalProperties:false` で `blocks` 独立宣言を禁止する。

- **C2/C11 実装設計 (新規)**: `derive(plan_dir)` はshape markerで分岐する。`fixed-13-phase`はbootstrap互換として現行射影を保持するが、`task-graph-derived`は13 phaseをpolicyとして読み、`task-specs/*.md` 1件から実行可能leaf 1件を導出する。leafは`execution_kind`/`task_spec_ref`必須、component-buildだけが`route_ref`必須、phase rootは非dispatch `phase-gate`、`entity_ref`は分類専用。component依存は配下task集合の直積へ展開せずcomponent completion barrierまたはproduces/consumes artifact joinへ1回だけ写像する。`canonicalize()`はschema_version/nodes/edgesのkey順とid/edge順を固定し、唯一のwriterとしてbyte一致を保証する。`--print-graph-hash`は既存graphを変更しないread-only安定CLIとする。

- **C2/C3/C11 実装設計 (新規)**: `validate(graph, inventory, handoff)` は(a)DAG非循環、(b)orphan 0、(c)producer一意、(d)route_refとinventory/handoff依存の向き/parity、(e)consumes producer実在、(f)canonical一致、(g)component依存のtask集合直積0、(h)推移冗長depends_on 0、(i)同一`(phase_ref,title,route_ref)`複製0、(j)`depends_on_edges <= max(2 * executable_nodes, 1)`を検査する。barrier/artifact joinで同じ意味を疎に表せる直積・冗長edgeはfail-closedで拒否し、violations空のみexit0とする。

- **C4 実装設計 (整合修正)**: 候補はblocked除外→depends_on/consumes充足で算出する。write_scope衝突群はid昇順の単一winnerだけをreadyに残し、他をdeferredとしてconflictsへ記録する。両方除外するとready=0の人為的deadlockになるため禁止する。producer doneだけを成果物実在の代理にせず`os.path.exists`を独立検査する。

- **C5 実装設計 (新規)**: `schemas/discovered-task.schema.json` を新設する。正準formは`discovering_task_id/reason/discovered_at_artifact/proposed_task_spec/change_level/provenance.route_id`を持つ。`accept-discovered-task.py`はinboxを受理してtask specへのEdit候補を作り、pin済みgraphを直接変更しない。additiveは安全な外ループ境界で自動採用し、structural (既存edge張替え/component追加) は`--approved`無しでfail-closed拒否する。採用後はplanner単一writerがtask specsから新graph revision/hashを再導出し、旧revision/hash/evidenceをimmutable保持したまま`predecessor_revision`で結ぶ。consumer inbox→次外ループR1→spec Edit→新revision→再dispatchの帰路を固定する。

- **C6 実装設計 (Edit拡張)**: `check-build-handoff.py`の`_check_task_graph_ref`は`task_graph_ref{path,schema_version,revision,graph_hash}`を検証する。route対応は`entity_ref`で推測せず、`execution_kind=component-build`かつ`route_ref`を持つproducer task集合と`handoff.routes[].id`を1:1照合する。direct-task/phase-gateにroute_refがある場合、component-buildにroute_ref/task_spec_refが無い場合、route未対応/重複をviolationにする。bootstrap fixed shapeだけはshape markerでlegacy entity_ref joinを限定許可し、C17 build後に削除可能な互換分岐として検査する。handoffのcycle_idはgoal-specとparityし、consumerはpath末尾解析を禁止する。

- **C10 実装設計 (Edit拡張)**: `verify-index-topsort.py` へ `_shape_marker(index_frontmatter: dict) -> str` を新設する (`index_frontmatter.get("shape_marker", "fixed-13-phase")` で既定値付き取得。未知の値は `fixed-13-phase` にフォールバックする fail-soft 設計)。`main()` で `_shape_marker()` が `"fixed-13-phase"` を返す場合 (本 plan を含む既存の全 plan がこの既定値に該当) は既存の 13 ファイル固定検証ロジックを完全に不変のまま実行する。`"task-graph-derived"` を返す場合のみ、期待ファイル集合を `task-graph.json` の `phase_ref` の unique 集合から動的算出する分岐を追加する (本分岐は将来の plan 向け機能であり、本 plan 自身の検証では通過しない)。`specfm.py` へ `SHAPE_MARKERS = ("fixed-13-phase", "task-graph-derived")` を定数追加する。**C10⇔C14 相互参照**: `_shape_marker()` が `"task-graph-derived"` を返して良いのは `check-shape-non-regression.py` (C14 (a)(c)) が exit0 かつ C02 の A/B 比較 genuine 判定 (C14 (b)) が非劣化と判定した場合のみを前提条件とし、いずれか一方でも劣化が検出された場合は shape 解放を block し `"fixed-13-phase"` へ fallback する (平均回帰禁止)。

- **C12 実装設計 (新規)**: `schemas/handoff-notes.schema.json` を新設する。`{"went_well": [str, ...], "friction_points": [str, ...], "downstream_watchouts": [str, ...]}` の各配列に `maxItems: 3` と各要素文字列に `maxLength: 200` を schema で機械強制する。`scripts/apply-handoff-notes.py` に `propagate(notes: dict, graph: dict, task_id: str) -> dict` を新設する。伝播範囲は `graph` 上で `task_id` へ直接 `depends_on`/`consumes` している先行 task の notes のみに限定し (推移的な全履歴注入は行わない)、`classify(note_text: str) -> "advisory"|"actionable"` を新設し、`discovered-task` 相当の具体的な次アクション記述 (「〜を追加する」「〜を修正する」等の動詞句で終わる文) を検出した場合は `actionable` (accept-discovered-task.py への起票候補) とし、状態や所感の記述に留まる場合は `advisory` (notes に留める) とする簡易ヒューリスティックを実装する。

- **C13 実装設計 (Edit拡張 + 新規)**: `specfm.py` の `plan_output_dir(name: str, out_dir: str | None = None, base: str = PLAN_OUTPUT_BASE)` に `cycle_id: str | None = None` を追加する。`cycle_id is None` の場合は既存の戻り値 (`<base>/<plan_slug(name)>`) を完全不変で返し (既存呼び出し元は無改修)、`cycle_id` 指定時のみ `<base>/<plan_slug(name)>/<cycle_id>` を返す。`specfm.py` へ `CYCLE_ID_RE = re.compile(r"^\d{8}-[a-z0-9-]+$")` と `LEDGER_STATUSES = ("active", "finished", "superseded")` を定数追加する。`schemas/plan-ledger.schema.json` を新設する。`{"schema_version": str, "entries": [{"cycle_id": str, "status": enum(LEDGER_STATUSES), "plan_dir": str, "summary": str}]}`。`scripts/check-plan-ledger.py` に `validate_ledger(ledger: dict) -> list[str]` を新設する。検査項目: (a) 各 `entries[].cycle_id` が `CYCLE_ID_RE` に一致、(b) 各 `entries[].status` が `LEDGER_STATUSES` の値域内、(c) `plan_dir`/`summary` が非空文字列、(d) `status == "active"` のエントリが台帳全体で高々 1 件 (2 件以上は fail-closed で violation とし非決定的な自動解決は行わない)。`main()` は `<plugin-plans>/<slug>/plan-ledger.json` を読み `validate_ledger()` の結果が空なら exit0、非空なら列挙し exit1。`scripts/migrate-plan-layout.py` に `migrate(old_plan_dir: Path, slug: str, cycle_id: str, status: str = "active") -> dict` を新設する。既存 flat 配置の `plugin-plans/<slug>/` 配下ファイルを `plugin-plans/<slug>/<cycle_id>/` へ移動し (git mv 相当)、`plugin-plans/<slug>/plan-ledger.json` が存在しなければ新規作成、存在すれば新規 entry を追記する (追記後は `validate_ledger()` を内部で再実行し fail-closed 検証してから書き込む)。既存 `plugin-plans/finish/<slug>/` 配下の完了 plan は本 migrate の対象外とし、別途 `status: "finished"` の entry として台帳に追加登録するのみに留める (finish/ ディレクトリ自体の物理移動は行わない・破壊的操作を避ける)。

- **C14 実装設計 (新規)**: `scripts/check-shape-non-regression.py` に 3 関数を新設する。(a) `acceptance_attachment_rate(nodes: list[dict], criterion_key: str = "acceptance_criterion") -> float`: task-graph.json の `nodes[]` のうち `criterion_key` に非空文字列を持つ (かつ「検証可能な成果物」を指す=`produces` エッジを 1 件以上持つ) node の割合を返す。`legacy_baseline_rate(phase_files: list[Path]) -> float`: derive-task-graph.py と同一の Markdown パーサで各 phase の `## 完了チェックリスト` 項目を走査し、旧shape の基準線として全項目に対する割合 1.0 (§5 項目は定義上すべてが受入基準を兼ねる) を返す定数関数とする。(b) `check_reproducibility(plan_dir: Path) -> list[str]`: `derive-task-graph.py` を同一入力に対し 2 回連続実行し、出力 `task-graph.json` の byte 列 (`canonicalize()` 適用後) が一致するかを比較し、加えて生成される仕様ファイル集合 (ファイル名の集合) とその node 集合 (id の集合) が両実行で一致するかを比較し、不一致を violations として返す。(c) `main()`: `acceptance_attachment_rate()` が `legacy_baseline_rate()` を下回る場合、または `check_reproducibility()` が非空の場合、violations を stdout へ列挙し exit1 とし (`--recommend-fallback` フラグ指定時は shape_marker 推奨値 `fixed-13-phase` を追加出力する)、いずれも満たす場合は exit0 とする。(d) C14(b) の genuine 判定は本スクリプトの責務外であり、C02 の R1-evaluate.md 側で新旧 fixture の A/B 比較として実施し、`plan-findings.json` の bucket `shape-ab-comparison` へ計上する (本スクリプトは (a)(c) のみを扱う)。

- **C15 実装設計 (新規)**: `scripts/render-task-graph-mermaid.py` に `render_mermaid(graph: dict, task_state: dict | None = None) -> str` を新設する。`graph["nodes"]`/`graph["edges"]` を (derive-task-graph.py の `canonicalize()` と同一の) canonical 順序のまま走査し、`graph TD` ヘッダ + 永続 4 state 分の `classDef` (pending/running/done/blocked の色分け) + 各 node の `id["title"]:::state` 宣言 + エッジ 4 型の線種 (`parent_of`=`-->` 細実線 / `depends_on`=`==>` 太実線 / `produces`=`-.->` 破線 / `consumes`=`--o` 円形終端) をこの順で文字列連結する。`critical_path(graph: dict) -> list[str]`: `depends_on` エッジのみを辺とする DAG 上の最長路を動的計画法で計算し (tie は経路上の先頭 node id の辞書順最小を採用)、該当エッジを `linkStyle` 追記で強調する。**クリティカルパス定義の正本 (harness C5 対向)**: クリティカルパス = `depends_on` エッジのみを辺とする最長依存鎖 (純トポロジ導出・エッジ重み/所要見積は持たない) と定義する。harness-creator C5 の『クリティカルパス上の未完了タスク』集計はこの producer 側 `critical_path()` 定義を正本として参照し、consumer 側で独自の重み付け最長路を再定義しない (task-graph schema はエッジ重み field を持たず純トポロジで足りる)。`main()` は `<plan_dir>/task-graph.json` を読み `render_mermaid()` の出力を `<plan_dir>/task-graph.mmd` へ書き込む (同一入力からの再実行は走査順序が canonical のため byte 一致)。**optional `--task-state <path>` (FC-7/M4)**: 指定時は `task-state.json` の node state を graph node へマージして `classDef` 色を live 反映し、未指定時は全 node を pending 相当で描画する (後方互換)。byte 一致テストは `(graph, state)` 入力ペア単位で評価する。node/edge の描画要素は `graph` の `id`/`title`/`type` フィールド (と任意の `task_state` の node state) のみから機械的に導出し、renderer 側で新規テキスト・装飾ラベルを合成しない (graph 外要素非描画の原則)。
- **C16 実装設計 (新規)**: `schemas/task-state.schema.json` を新設する。`{"schema_version": str, "graph_hash": str (パターン `^sha256:[0-9a-f]{64}$`), "nodes": [{"id": str, "state": enum, "started_at": str|null (format: date-time), "lease_expires_at": str|null (format: date-time), "blocked_reason": "origin-failure"|"propagated" (state==blocked のとき必須・他 state では省略)}]}`。**永続 state 値域は `pending|running|done|blocked` の 4 値** (`TASK_NODE_STATES` から computed-only の `ready` を除いた永続サブセット・harness 側 `ALLOWED_TRANSITIONS` と整合)。check-task-state-schema.py は永続 state に `ready` が現れた場合を fail-closed で拒否する。**lease 時刻の format 制約**: `started_at`/`lease_expires_at` は JSON Schema `format: "date-time"` (RFC3339/ISO8601・UTC "Z" 接尾) を制約として焼き、時刻表現を決定論化して producer/consumer 間の parity を維持する。`state == "running"` の node は `started_at`/`lease_expires_at` の両方が非 null であることを要求する (lease 未設定の running は孤児判別不能のため violation)。**blocked_reason の条件付き必須 (第一級 field・GAP-FAILED-STATE-VOCAB 解消)**: `state == "blocked"` の node は `blocked_reason ∈ {origin-failure, propagated}` を持つことを (running→lease と同型の if/then 条件付き必須で) 要求する — 欠落または値域外は violation、非 blocked state での付与も violation とする。`origin-failure` = route 自体が失敗した起点タスク、`propagated` = 上流 blocked による下流連鎖 blocked を表し、両者が state enum 上は同一値 `blocked` に潰れて C12 停滞診断が起点を特定できない問題 (harness GAP-FAILED-STATE-VOCAB) を、伝播閉包を辿って起点 route を特定可能にすることで解消する。これは consumer=harness-creator が blocked 遷移時に consumer 運用フィールド `notes.reason` へ暫定記録していた区別 (F9) を、producer 所有の第一級 schema field へ昇格した対応関係であり (cross_plan_request の正式解決先)、昇格後は所有=producer/書込=consumer を保ったまま consumer が第一級 `blocked_reason` field へ直接書き込む (`notes.reason` や advisory `handoff_notes` には記録しない・状態理由と advisory を混ぜない)。state enum への `failed` 追加 (代替案 a) は harness `ALLOWED_TRANSITIONS`・両 plan の永続 4 値域宣言・既存受入例へ波及し破壊的なため採らず、state 値域は 4 値のまま不変・本 field は additive とする。**consumer additive 拡張の許容 (schema parity・pipeline-blocking 回避)**: node オブジェクトは `additionalProperties: true` とし、consumer (harness-creator L4) が運用フィールド (`route_report`/`handoff_notes`) を additive に付与しても producer schema 検査が fail-closed で全 build を開始時停止させない (producer 所有の必須キーは `id`/`state`/`started_at`/`lease_expires_at` + `state==blocked` 時の `blocked_reason` に限定し、これらの型/値域のみを strict 検査する)。**状態 field と advisory の分離 (H1/M1)**: 状態理由 (blocked_reason・lease 回収) は第一級 state field 側に置き、advisory 引継知見は平坦 `notes` list 袋 (**廃止**) ではなく node の別フィールド `handoff_notes` (object 形状 `{went_well:[], friction_points:[], downstream_watchouts:[]}`) に分離して両者を同じ袋に混ぜない。`handoff_notes` の件数/文字数上限 (各 maxItems 3 / maxLength 200) は C12 の `handoff-notes.schema.json` が単一正本であり、task-state schema は node の `handoff_notes` を `$ref` で束縛し consumer は再定義しない (二重定義 drift を防ぐ・旧 平坦 `notes` を `$ref` 束縛していた曖昧さを解消)。blocked_reason・lease 理由は `handoff_notes` の ≤3 予算を食わせないため advisory 側へ混入させない。`derive-task-graph.py` へ `graph_hash(graph: dict) -> str` を追加する (`"sha256:" + hashlib.sha256(canonicalize(graph) の json.dumps 出力).hexdigest()`。C11 の canonical bytes から導出するため canonicalizer の単一 writer 原則をそのまま継承する)。この `graph_hash()` の戻り値が read-only サブコマンド `--print-graph-hash <path>` (FC-4) の stdout 出力実体であり、consumer は当該 CLI 経由でのみ pin 用 hash を取得する (canonicalize()/graph_hash() の直接 import・subprocess 消費はしない・FC-5)。`scripts/check-task-state-schema.py` に `validate_task_state(state: dict) -> list[str]` (schema 整合 + lease 整合 + blocked_reason 整合 (state==blocked のとき blocked_reason が値域内で存在するか・非 blocked での付与がないか) の検査) と `check_graph_hash_pin(state: dict, graph_path: Path) -> list[str]` (`derive-task-graph.graph_hash()` を `graph_path` 上で再計算し `state["graph_hash"]` と不一致なら violation とする pin 検査。discovered-task 受理等で graph が変わり hash 未更新のまま state が古い場合を fail-closed 検出し、反映は次周回のみとする constraints を機械強制する) を新設する。`main()` は両検査を実行し violations が空なら exit0、非空なら列挙し exit1。**所有/書込分離 (C12 と同型)**: schema 定義・pin 検査ロジックの所有は producer (C01) だが、`task-state.json` への実書込 (state 遷移・lease 更新) は consumer (harness-creator 側 L4 実行系) が単独 writer として担う (本 component は schema と検査 script のみを提供し、state ファイル自体を書かない)。
- **C17 実装設計 (TaskExecutionEnvelope)**: task-graph leaf nodeへ`execution_kind`と`task_spec_ref`を必須化し、`component-build`だけは`route_ref`も必須化する。`entity_ref`は分類/traceability専用でbuilder選択に使わず、phase rootは`phase-gate`の非dispatch集約点とする。plannerが`task-specs/<task-id>.md`を決定論生成し、`task-execution-envelope.schema.json`とrendererがnode/task spec/`phase_ref`で指定した単一phase policy/明示route/acceptance/write_scope/先行artifact/handoff notes/knowledge refs/verifyを合成する。title単独、entity_ref暗黙route、task_spec_ref不在、P01..P13全文注入をexit1で拒否する。consumerはrenderer出力をSubAgent promptの唯一の入力packetとして扱う。
- **C18 実装設計 (状態三層)**: canonical graphはseed state=pendingを含む構造SSOTとして同一revision内で不変。consumer単一writerがtask-stateとtask-eventsを更新し、project-task-status相当のprojectionがplan dirへstatus JSON/Markdown/自己完結HTMLを再生成する。HTMLはslide-report-generatorのreport原則 (読み物・1項目1ビジュアル・印刷対応) を採用しつつ、runtime再現性のため外部plugin呼出しを必須にせず標準ライブラリだけで決定論描画する。route reports/build-summaryを読み、進捗ドーナツ、仕様→graph→dispatch→evidenceの図解、phase別状態、成果物/証跡/逸脱、外ループ、正本リンクをescapeして表示する。discovered-task採用時は外ループ境界でtask specsをEditして新graph revision/hashへrepinし、旧revisionを上書きしない。parity検査はgraph node集合=state node集合=projection node集合、revision中graph hash不変、projection state=task-stateを強制する。
- **C19 実装設計 (cross-cycle knowledge)**: plan-ledger entryへoptional`predecessor_cycle_id`を追加し閉路/不存在を拒否する。task specの`knowledge_refs`はid/source_ref/freshness_checked_at/decision(adopted|rejected)+reasonを持ち、`external_inputs`は過去artifactのpath/hashを明示する。過去nodeをactive graphへコピーすること、source_ref無し、全文spec/推移的notes注入を拒否する。
- **C8/C14(b) 判定ステップ実装設計 (C02・`prompts/R1-evaluate.md` Edit 拡張)**: 既存 4 条件 (C1-C4) 判定に続く判定ステップ節を追加する。**C8 タスク粒度**: 各 task node に対し [Q1]「この node は 1 つの検証可能成果物 (produces エッジ 1 件以上) に対応し下流 builder が追加質問なしで着手できる粒度か」[Q2]「粒度が粗すぎ (複数の独立成果物を 1 node に束ねる) / 細かすぎ (成果物を持たない中間メモ node) ないか」を genuine 判定する。**C8 エッジ4型意味論**: [Q3]「`parent_of` を順序依存として誤用 (階層を depends_on の代用にする) していないか」[Q4]「`blocks` の独立宣言や `produces`/`consumes` のパス不整合がないか」を判定する。**C14(b) 新旧shape A/B比較**: [Q5]「同一構想の新shape task node の `acceptance_criterion` が旧shape §5 項目より下流 builder AI の追加質問を減らす事前解決済み判断を内包しているか (実効性の非劣化)」を判定する。**harness consumer plan 評価 (C8 対向)**: [Q6]「consumer 側 (harness-creator L4) の dispatch/state write-back/成果物注入/discovered-task emit が producer 契約 (安定 CLI 契約・graph_hash 照合・所有/書込分離) を逸脱していないか」を判定する。**bucket 記録形式**: 各判定を `plan-findings.json` の `findings[]` へ `{"bucket": "task-graph-semantics"|"shape-ab-comparison"|"task-graph-consumer", "severity": "high"|"medium"|"low"|"info", "node_ref": <task id or component id>, "verdict": "genuine PASS"|"genuine FAIL", "rationale": str}` 形式で追記する (既存 conditions C1-C4 の `additionalProperties:false`/required 構造は不変)。`references/plan-rubric.json` の `semantic_checks` へ上記 bucket 対応エントリを additive 追加する (deterministic_gates/conditions は不変)。
- **後方互換の担保 (C7/C9)**: C6/C10 いずれも新規ヘルパー・分岐はデフォルト値 (`task_graph_ref` 未設定時は検査自体をスキップ、`shape_marker` 未設定時は `fixed-13-phase` 既定) で無効化されるため、task-graph を持たない既存 plan (`plugin-plans/finish/` 配下含む) や既存呼び出し元の挙動は変化しない。C1-C5/C11/C12 は完全新規ファイルのため既存コードへの影響が無い。C13 の `plan_output_dir()` 拡張も `cycle_id` 省略時は既存戻り値を完全不変で返すため、既存の全呼び出し元 (derive-task-graph.py 含む) は無改修で動作する。C14 の `check-shape-non-regression.py` も完全新規ファイルであり、`shape_marker` が既定値 `fixed-13-phase` のまま (本 plan 自身含む既存の全 plan) の場合は非劣化ゲート自体が発火対象外 (task-graph-derived への遷移判断がそもそも発生しない) となる。C15/C16 も完全新規ファイル (`render-task-graph-mermaid.py`/`check-task-state-schema.py`/`task-state.schema.json`) かつ既存呼び出し元を持たないため、既存コード・既存ゲートへの影響は無い。

## 成果物
- C1: `schemas/task-graph.schema.json` の設計 (node/edge 型制約・`blocks` 非列挙)。
- C2/C3/C11: `derive-task-graph.py`/`validate-task-graph.py` の関数シグネチャ・アルゴリズム設計。
- C4: `compute-ready-set.py` の `ready_set()` アルゴリズム設計。
- C5: `discovered-task.schema.json`/`accept-discovered-task.py` の二段受理設計。
- C6: `check-build-handoff.py` への `_check_task_graph_ref` 追加設計。
- C10: `verify-index-topsort.py` への `_shape_marker` 分岐設計 + `specfm.SHAPE_MARKERS` 追加設計 (C14 非劣化ゲート PASS を採用前提とする相互参照込み)。
- C12: `handoff-notes.schema.json`/`apply-handoff-notes.py` の有界伝播・advisory/actionable 分類設計。
- C13: `plan_output_dir()` の `cycle_id` 引数拡張 + `plan-ledger.schema.json`/`check-plan-ledger.py`/`migrate-plan-layout.py` の設計。
- C14: `check-shape-non-regression.py` の `acceptance_attachment_rate()`/`legacy_baseline_rate()`/`check_reproducibility()` アルゴリズム設計 + block/fallback 判定ロジック。
- C15: `render-task-graph-mermaid.py` の `render_mermaid()`/`critical_path()` アルゴリズム設計 (canonical順序走査による byte一致 + graph外要素非描画)。
- C16: `task-state.schema.json` の設計 (永続 state 4 値域 (ready 除外)/graph_hash/lease の `format: date-time`/`state==blocked` 時の `blocked_reason` 第一級 field (origin-failure|propagated・条件付き必須・harness notes.reason 暫定区別の昇格先・GAP-FAILED-STATE-VOCAB 解消)/node `additionalProperties:true` による consumer additive (route_report/handoff_notes・平坦 notes 廃止) 拡張許容/handoff_notes 上限は C12 schema `$ref` 参照) + `derive-task-graph.graph_hash()` + `--print-graph-hash <path>` サブコマンド (FC-4) + `check-task-state-schema.py` の `validate_task_state()` (永続 ready 拒否 + blocked_reason 整合含む)/`check_graph_hash_pin()` 設計 (所有=C01・書込=consumer の分離込み)。
- C17: task-specs導出・task_spec_ref・TaskExecutionEnvelope schema/renderer/parity検査。
- C18: graph/state/projection parity + task-events append-only契約。
- C19: plan-ledger lineage + knowledge_refs/external_inputs検査。
- C8/C14(b): `prompts/R1-evaluate.md` への判定ステップ節 (Q1-Q6 質問項目) + `plan-findings.json` の bucket 記録形式 (task-graph-semantics/shape-ab-comparison/task-graph-consumer) + `plan-rubric.json` `semantic_checks` additive 追加設計 (C02・conditions 不変)。

## スコープ外
- 実 `plugins/plugin-dev-planner/` への実コード反映 (L4 build・本 plan の対象外)。
- `/capability-build` による並列 dispatch の実行本体 (本 plan の責務は schema/導出/検証/ready-set 計算/handoff 契約の設計まで)。

## 完了チェックリスト
- [ ] C01 run-plugin-dev-plan update routeがC1-C19の実装設計を1つのbuildとして適用し、全受入条件と後方互換を満たす。

この1 route taskが束ねる確認内訳:
- C1-C3/C11: schema、疎な導出、artifact join、canonical/validator。
- C4-C6: ready-set、revision境界のdiscovered-task、route_ref handoff parity。
- C7/C10/C14: 後方互換、shape解放、非劣化fallback。
- C12/C13/C15/C16: notes、cycle ledger、可視化、task-state schema/hash pin。
- C17-C19: TaskExecutionEnvelope、graph/state/projection、cycle knowledge。
- C8/C14(b): C02 evaluatorが使うgenuine判定契約。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C1-C19 全てについて、新規/拡張対象ファイル名・関数名・検出ロジックが具体的に記述されている。
- 満たさない例: 「task-graph の検証ロジックを実装する」のように対象ファイルや関数名が特定されないまま実装設計が完了扱いになっている。

### 事前解決済み判断
- 分岐点: canonicalizer (derive-task-graph.py) と lint (validate-task-graph.py の非正準拒否) を同一ファイルにするか別ファイルにするか → 判断: 別ファイル (derive は「書く」責務・validate は「検証する」責務で読み書き分離を保ち、canonicalize() のロジックは derive-task-graph.py 側に置いて validate-task-graph.py からは同一ロジックを再適用し比較するのみに留める。これにより単一 writer の原則 (constraints) を保ったまま検証と生成の責務を分離する)。

## 参照情報
- `phase-04-test-design.md`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-build-handoff.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/verify-index-topsort.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py`。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/prompts/R1-evaluate.md` / `references/plan-rubric.json`。
- 後続 P06 (test-run)。
