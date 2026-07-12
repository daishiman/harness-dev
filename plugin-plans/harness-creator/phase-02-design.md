---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (component 分解設計)

## 目的
checklist C1-C7 および追加差分指示 C10-C13 (冪等再開・実行排他/実行イベントログ/実行時停滞検出/task-graph 実行知見の knowledge 化) を buildable な component 群へ分解し、5 種 component_kind (skill/sub-agent/slash-command/hook/script) 全てを検討した上で component-inventory.json の `components[]` (8 件) と `plugin_level_surfaces` (8 面) を確定する。

## 背景
P01 で確定した consumer 責務 (並列 dispatch・state write-back・成果物注入・discovered-task emit・進捗集計・境界契約文書追記) を、単一責務 (SRP) を保ったまま最小の buildable 実体数へ落とし込む。前回サイクル (`plugin-plans/finish/harness-creator/`) の component 分解パターン (script は plugin-root hoist、Markdown 参照ファイル更新は plugin_level_surfaces として扱う) を踏襲する。

## 前提条件
- P01 の goal-spec 確認が完了している。

## ドメイン知識

### component 分解結果 (5 種検討証跡は component-inventory.json の `derivation` フィールドが正本)
| id | component_kind | name | depends_on | 責務 |
|---|---|---|---|---|
| C01 | script | dispatch-ready-set | [] | task-graph.json + task-state.json マージ → producer 側 compute-ready-set.py 呼び出し → dispatch batch 決定 |
| C02 | script | sync-task-state | [] | route build 完了時の task-state.json write-back (単一 writer) |
| C03 | script | inject-task-inputs | [] | produces/consumes 成果物・notes の dependent task 入力への有界注入 |
| C04 | script | emit-discovered-task | [] | build 中発見タスクの provenance 付き emit (E4 境界) |
| C05 | script | summarize-task-progress | [C02] | task-state.json + route-build-report 群からの進捗集計・実行時停滞検出 (C12)。C02 の resolve_build_dir() を import するため build 時コード再利用依存を持つ |
| C06 | slash-command | capability-build (UPDATE) | [C01, C02, C03, C04, C05, C07, C08] | task_graph_ref 検出時の並列 dispatch 経路追加 (allowed-tools へ Task 追加)・build 開始時に C07 を先行呼出・build 完了前に C08 で未処理 discovered-task/knowledge 化を確認 |
| C07 | script | manage-build-lease | [C02] | build 開始前安全性ゲート: build lock 排他 (C10-c)・孤児 lease 回収判断 (C10-b・実書込は C02 委譲)・graph_hash pin 検証 (C10-d) |
| C08 | script | record-task-graph-knowledge | [C02, C04, C05] | discovered-task inbox の未処理検出・task-events/stall/handoff_notes からの蒸留済み knowledge entry 生成・Loop A/Loop B への add_entry.py 経由記録 (C13) |

DAG は C01-C04 が相互 depends_on なし (並列 buildable)、C05 と C07 はいずれも C02 の内部関数を import/subprocess 再利用するため C02 に依存する (C05 は `resolve_build_dir()` を import、C07 は `reap_expired_lease()` を subprocess 経由で呼ぶ・いずれも build 時コード再利用依存であり実行時呼出順とは別軸)、C08 は C02 の task-events/task-state、C04 の discovered-task inbox、C05 の stall summary を読むため [C02,C04,C05] に依存する → C06 が C01-C05, C07, C08 の全 7 script に依存して統合する形 (非循環)。これは checklist C1 が要求する「相互独立タスクの並列 dispatch」と C13 が要求する「発見タスクを残したまま完了しない」を、component 分解そのものが体現する構造になっている。

### state_file パス確定 (open_questions[2] の最終解消)
`eval-log/<slug>/build/task-state.json` に確定する。根拠: producer 側 `handoff-run-plugin-dev-plan.json` の `open_issues[0]` が「task state ファイルは仮置きで `eval-log/<slug>/build/task-state.json` (route-build-report と同居) とし単一 writer は consumer 側」と既に記述しており (`aligned_with: goal-spec.json#checklist.C7`)、producer 側は既にこの前提で task-graph 設計を完了している。route-build-report (`eval-log/<slug>/build/route-<id>.json`, PR#70 契約) と同居させることで、C02/C05 が同一ディレクトリを read/write するだけで完結し新規ディレクトリ規約を持ち込まない。

task-graph.json (構造・producer SSOT・consumer からは read-only) と task-state.json (runtime state・consumer SSOT・単一 writer=C02) を分離する設計とする。producer 側 `derive-task-graph.py` は `node.state=pending` の初期値を書くのみで単一 writer 原則は破らない。C01 は両ファイルをマージした上で producer 側 `compute-ready-set.py` を cross-plugin subprocess として呼び出す (再実装しない)。

### 周回衝突排除 (build 成果物の cycle スコープ化・planner 側 goal-spec C13 の consumer 側含意)
planner 側 goal-spec C13 は plan_dir 自体を `plugin-plans/<slug>/<cycle-id>/` へ周回サブディレクトリ化する規約 (cycle-id 形式 YYYYMMDD-<concept-slug>・specfm.plan_output_dir() 拡張・plan-ledger.json 台帳) を追加する (本 plan 作成時点で C13 は goal-spec 上 `done:false`・未実装)。consumer 側 (本 plan) は plan_dir レイアウト規約自体を再実装せず、build 成果物側 (`eval-log/<slug>/build/` 配下の task-state.json・route-<id>.json) が同一 plugin の複数改善周回で衝突しないことだけを保証する。

設計判断 (契約整合の最終形・team-lead 再送指示によりシグネチャ確定): cycle-id の判定は plan_dir 側の文字列を一切解析せず、handoff top-level の `cycle_id: str | null` フィールド (producer 側追加・additive・null=flat) の値のみから導出する。C02 (sync-task-state.py) 内に `resolve_build_dir(target_plugin_slug: str, cycle_id: str | None) -> str` を定義する。関数内部で `f"eval-log/{target_plugin_slug}/build"` を組み立て、`cycle_id` が非 null ならその配下 (`.../<cycle_id>`) を返し、null なら組み立てた flat パスをそのまま返す。第一引数は handoff.target_plugin_slug、第二引数は handoff.cycle_id の値であり、いずれも handoff トップレベルのフィールド値をそのまま渡すのみで、それ以外の入力 (plan_dir・--plan-dir・--out-dir 等) は一切参照しない。dispatcher (C06) は handoff.cycle_id を解釈せず C01-C05/C07/C08 へ `--cycle-id` としてそのまま転送する。C05 (summarize-task-progress.py)・C07 (manage-build-lease.py)・C08 (record-task-graph-knowledge.py) はこの関数を import して再利用し独自実装しない (SSOT を C02 に一本化)。C13 未実装の間は全 handoff が cycle_id フィールド不在/null のため、resolve_build_dir() は後方互換パスのみが発動し続け破壊的変更は 0 である (詳細アルゴリズムは P05 に内包・open_issue GAP-CYCLE-SCOPE-PENDING で C13 実装後の実地検証を advisory として記録)。

`resolve_build_dir()` 自体の独立 7 個目の component への昇格は検討したが no-split threshold (第二消費者/machine-verifiable な独立面/280行超) をいずれも満たさない数行の純粋関数のため見送り、C02 内部関数への畳み込みとした (derivation フィールド参照)。

### 追加差分指示 (C10-C12) の component 化判断
team-lead から追加された goal-spec checklist C10 (冪等再開・実行排他)/C11 (実行イベントログ)/C12 (実行時停滞検出) を、単一責務原則で以下のように component へ落とし込む (根拠の全文は component-inventory.json `derivation` 参照)。
- **C10(a) 冪等 resume**: 新規 component 不要。C01 の `merge_state()` が producer 側 compute-ready-set.py のアルゴリズムと組み合わさって done ノードを ready-set 計算から自然に除外するため、追加の受入例のみを P04 へ足す。
- **C10(b) lease 回収判断 / C10(c) build lock 排他 / C10(d) graph_hash pin 検証**: 新規 7 個目の component `C07=manage-build-lease.py` として独立させる (3 者とも「build 開始前に一度だけ実行される安全性検査・build 単位の排他制御」という共通タイミング・共通不変条件を持ち、no-split threshold の独立検証基準を満たす)。実書込み (孤児 running → pending) は単一 writer 規約を守り C02 の `reap_expired_lease()` へ委譲、C07 自身は `.build.lock` 以外を書かない。
- **C11 実行イベントログ**: 新規 component 化せず C02 (sync-task-state.py) の拡張とする。writer が「state と同じ単一 writer (親 dispatcher)」という goal-spec の要求そのものが、既に単一 writer である C02 と同一責務・同一呼び出しタイミングであることを示しているため、別 script へ分離すると状態更新とイベント記録が同一トランザクションで完結しなくなるリスクを生む。
- **C12 実行時停滞検出**: 新規 component 化せず C05 (summarize-task-progress.py) の拡張とする。停滞判定 (ready-set=∅ ∧ 未完了>0 ∧ running=0) は進捗集計 (by_state 導出) の直後に同一データから導く追加ビューであり、独立の副作用や書込みスコープを持たないため no-split threshold の独立検証基準を満たさない。

### 実行排他の堅牢化 (安全機構が自ら競合を生まない設計)
C10 の lease/lock 機構は「回収・排他」という安全側の副作用を持つため、正当な build を誤って阻害しない堅牢化を design 段で明記する (詳細アルゴリズムは P05・受入例は P04)。
- **lease/lock heartbeat (renewal)**: lease 期限 (既定 3600s) を超える正当な長時間 build は、dispatcher (C06) が in-flight 実行中に C02 `--renew-lease` と C07 `--lock-action renew` を定期呼出しして `lease_expires_at`/lock `started_at` を延長する。これにより「1 時間超の正当 running が偽孤児として C07 に pending 回収され二重 dispatch される」事故を防ぐ (回収・steal は heartbeat が途絶した genuinely stale な状態のみに発火)。
- **lock 孤児化の steal 規約**: `.build.lock` を空ファイルではなく `{started_at, pid, host}` JSON とし、acquire 時に既存 lock が `now - started_at > lock_ttl_seconds` (既定 lease の 2 倍) または pid 非生存なら安全に steal する。dispatcher クラッシュ後の残留 lock による恒久 lockout (C10-a resume が自分の残した lock に締め出される問題) を防ぐ。人間の手動救済として `--lock-action force-release` を持つ。
- **blocked 伝播の書込担体**: route 失敗時、dispatcher は C02 `--to-state blocked --reason origin-failure` で起点を blocked にし、`--propagate-blocked --task-graph <path>` で下流閉包 (depends_on/consumes 逆引き) を `blocked --reason propagated` へ連鎖遷移させる (単一 writer=C02 を維持)。起点故障 (origin-failure) と伝播 (propagated) は第一級 field `blocked_reason` で区別する (state enum 追加は planner C16 所有・GAP-FAILED-STATE-VOCAB)。
- **graph_hash の周回再検証**: build 開始時の C07 pin 検証だけでなく、dispatch ループの各周回で C01 が pin 済み graph_hash と現 task-graph の再計算 hash を照合し不一致で fail-closed する (goal-spec C10-d 『実行中の混入拒否』の検証点を 1 回から周回ごとへ強化)。

### discovered-task 境界確定 (E3 相乗り vs E4 新設)
E4 新設に決定する。E3 (`emit-improvement-handoff.py`) は build 完了後の全体的な改善還流 (elegant-review/content-review/evaluator 後の findings、`improvement-handoff.schema.json` 消費) であるのに対し、discovered-task は build 進行中 (in-flight) の単一 route から生じる plan 未網羅タスクの発見 (`discovered-task.schema.json` 消費、producer 側 `accept-discovered-task.py` の二段受理) であり、時間軸 (post-build vs in-flight)・スキーマ・受理機構のいずれも異なるため、相乗りは SRP 違反と判断し独立境界 (C04・E4) とする。

### C13: 発見タスクと knowledge の接続
依存関係は双方向 writer ではなく「片方向 writer を周回でつなぐ」設計にする。planner は task-graph/plan の writer、harness-creator は task-state/task-events/discovered-task inbox/knowledge の writer であり、harness は graph を直接編集しない。新しい課題を見つけたら C04 が proposal を inbox に emit し、C08 が未処理 proposal の残存を完了ブロックとして検出する。planner の次回 `--mode update --discovered-inbox <inbox>` が accept-discovered-task.py の inbox ドレインで proposal を受理/却下/置換し、graph を更新した後に harness が更新済み graph を再消費する。

### 2 ループ構造 (内ループ=build 実行 / 外ループ=spec 改善・改善還流の中核設計)
本 consumer の実行を **2 つの入れ子ループ**として設計する。この 2 ループの結合が「タスク仕様書 (task-graph) を改善してから harness で再実行する」改善サイクルを機構化する (ユーザー要件: 外ループ+内ループの統合)。

- **内ループ (build-execution loop・C06 が所有)**: `dispatch-ready-set(C01) → 並列 build → sync-task-state(C02) write-back → inject-task-inputs(C03)` を `ready_batch` が空になるまで反復し、**現 task-graph を完了へ駆動する**。仕様は固定のまま実行だけを回すループ。
- **外ループ (spec-improvement loop・consumer↔producer 横断)**: 現 task-graph が不十分 (build 中に plan 未網羅タスク発見、または仕様不備由来の stall) なとき、`emit-discovered-task(C04) → record-task-graph-knowledge(C08) 完了ブロック → planner run-plugin-dev-plan --mode update --discovered-inbox でドレイン (task 仕様書=task-graph を改善) → 新 graph_hash → C07/C01 が再 pin → 内ループ再始動`。**仕様そのものを改善してから実行し直すループ**。

**2 ループの結合点 (両ループを縫合する 2 機構)**:
1. **完了ゲート = C08 (内→外の強制ハンドバック)**: 未処理 discovered-task が inbox に 1 件でも残る間、内ループは build を completed にできず、C06 が正確な planner 再起動コマンド (`run-plugin-dev-plan --mode update --discovered-inbox <inbox>`) と capability-build 再実行を実行可能なハンドバック指示として提示する。内ループの完了を外ループの決着まで機構的に遅延させる。
2. **再入トリガ = graph_hash (外→内の再始動・provenance-gated)**: planner のドレインで graph が変わると canonical `graph_hash` が変化する。C07 は build 開始時の pin 照合で新旧不一致を検知したとき、現 graph の hash が accepted discovered-task の `resulting_graph_hash` と一致する場合のみ正当な再入として pin を新 hash へ更新 (`sync-task-state.py --repin-graph-hash` 委譲・`graph_hash_pin:"repinned"`) し内ループを改善済み仕様で再始動する。どの accepted form とも一致しない graph 差替えは実行中の不正混入 (F10) として `mismatch` で fail-closed 拒否する。同一 `graph_hash` 機構に「不正改変の拒否」と「正当改善の受容」の両方を、provenance (`resulting_graph_hash`) を認可述語にして両立させる (安全と活性の止揚)。

**stall の外ループ合流 (トリガ一本化)**: `ready_batch` 空だが未完了残存の stall (C05 detect_stall) のうち、診断が「depends_on/consumes が graph 上に不在」等の**仕様不備**を示すものは、単なる build 失敗と区別して C04 が structural discovered-task として emit する。これにより「新タスク発見」と「stall による仕様不足」を discovered-task inbox という**単一ジョイント**へ合流させ、外ループのトリガを一本化する (blocked 伝播による純粋な build 失敗は外ループでなく人手救済へ回し、仕様不備 stall のみを外ループへ流す)。この合流判定は C06 orchestrator が C05 stall summary の diagnosis 種別を見て行う。

knowledge へ入れる情報は task-events の全量ではなく、(1) どの依存/成果物/blocked 起点で詰まったか、(2) どう解決したか、(3) 次回どの task/route で先に確認すべきか、の 3 点へ蒸留する。C08 は生成対象 harness の `knowledge/` (Loop A) と `plugins/harness-creator/knowledge/` (Loop B) の双方へ同じ必須6フィールド schema で記録し、次回 build-time/runtime の search_knowledge で参照できるようにする。source には task-events/discovered-task/route-build-report/stall summary の path + task_id 参照だけを持たせ、生ログを knowledge へ丸写ししない。

### C7 (境界契約文書追記) の扱い
独立 component 化せず `plugin_level_surfaces.references_config_assets` として扱う (前回サイクル踏襲・5 種 component_kind に Markdown 参照ファイルという種別は存在しないため)。追記実行は C04 の build 完了条件に含める。

## 成果物
- `component-inventory.json` (`considered_component_kinds` 全 5 種・`components[]` 8 件・`plugin_level_surfaces` 8 面・`derivation` narrative)。

## スコープ外
- 各 component の入出力詳細・アルゴリズム設計 (P05 の責務)。
- テストケースの具体的な fixture (P04 の責務)。

## 完了チェックリスト
- [ ] considered_component_kinds が 5 種全てを含む。
- [ ] components が 8 件 (C01-C08) で DAG が非循環。
- [ ] state_file パスが `eval-log/<slug>/build/task-state.json` に確定している。
- [ ] 周回衝突排除 (resolve_build_dir(target_plugin_slug, cycle_id)・handoff.cycle_id 有無 2 ケース・パス解析禁止) が C02 内部関数として確定している。
- [ ] discovered-task 境界が E4 新設として確定し根拠が明記されている。
- [ ] C10 (冪等再開・実行排他)/C11 (実行イベントログ)/C12 (実行時停滞検出) の component 化判断 (C07 新設・C02/C05 拡張) が根拠付きで確定している。
- [ ] C13 (未処理 discovered-task 完了ブロック + knowledge 化) の component 化判断 (C08 新設) と writer 方向が根拠付きで確定している。
- [ ] plugin_level_surfaces 8 面が required:true または required:false+omitted_reason で明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記表の通り 8 component・DAG 非循環・state_file パス・E4 境界・C10-C13 の component 化判断が具体的な id/パス/根拠で確定している。
- 満たさない例: 「並列 dispatch とタスク発見と冪等再開の機構を追加する」とだけ記され、component_kind・build_target・依存関係が未確定のまま P03 へ進む。

### 事前解決済み判断
- 分岐点: task-graph 導入の並列可能性を単一 script (統合) に畳み込むか C01-C05 の 5 script へ分離するか → 判断: 5 分離 (dispatch 判断/state 書込/注入/発見/集計は異なる不変条件を持ち、統合は SRP 違反かつ単一 writer 規約の境界を曖昧にするため)。

## 参照情報
- `plugin-plans/harness-creator/component-inventory.json`。
- `plugin-plans/plugin-dev-planner/handoff-run-plugin-dev-plan.json` (`open_issues[0]`)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/component-domain.md`。
- 後続 P03 (design-review) / P05 (implementation)。
