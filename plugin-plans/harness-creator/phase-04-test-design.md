---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計・TDD Red)

## 目的
C01-C08 それぞれの受入基準を test-first で確定し、未達状態 (Red) として明示する。checklist C1 (並列 dispatch 受入例 3 ケース)・C6 (後方互換)・C10-C13 (冪等再開/実行排他・実行イベントログ・実行時停滞検出・未処理 discovered-task 完了ブロック + knowledge 化) を、下流 builder AI が追加質問なしで実装着手できる具体度で本 phase 本文へ内包する。

## 背景
goal-spec の checklist は verify_by=script/test/human の 3 種を持つ。script/test 系は本 phase で具体的なテストケース (入力/期待出力) を確定し、P05 で最小実装設計を Green にする対象とする。human 系 (C8) は fork evaluator 側の意味判定手順として P05/P07 で設計する。

## 前提条件
- P03 の design-review が PASS している。

## ドメイン知識

### C1 受入例 (dispatch-ready-set.py・並列 dispatch 3 ケース)
共通 fixture task-graph (task-graph.json + task-state.json マージ後の論理ビュー):

| id | write_scope | depends_on | state |
|---|---|---|---|
| T1 | A | [] | done |
| T2 | B | [T1] | pending |
| T3 | C | [T1] | pending |
| T4 | D | [T2, T3] | pending |
| T5 | B (T2 と同一) | [T1] | pending |

3 テストケースと期待 dispatch batch (`dispatch-ready-set.py` 標準出力の `ready_batch`):
1. **直列チェーン**: T3/T5 を除外した T1(done)→T2(pending)→T4(pending, depends_on=[T2]) のみの単純チェーン。期待 `ready_batch = ["T2"]` (T4 は T2 未完了のため対象外・SubAgent 並列投入対象は 1 件のみで直列相当)。
2. **ダイヤモンド依存 (中間 2 タスク並列)**: T1(done)→{T2, T3} (write_scope B/C 非重複)→T4(depends_on=[T2, T3])。期待 `ready_batch = ["T2", "T3"]`・`conflicts = []` (write_scope 非重複のため同一 message 内で 2 SubAgent 並列 dispatch 可能)。
3. **write_scope 衝突 (直列化)**: T1(done)→{T2, T5} (両者 depends_on=[T1] のみ・write_scope 同一 B)。期待 `ready_batch = []`・`conflicts = [["T2", "T5"]]` (両者とも depends_on 条件のみでは ready 相当だが write_scope 重複のため自動並列対象から除外され、呼び出し元 capability-build へ直列化指示が返る。安全側 fail-closed のタイブレークとして「どちらか一方を選ぶ」非決定的選択は行わない)。

これら 3 ケースは `dispatch-ready-set.py` が producer 側 `compute-ready-set.py` を subprocess 呼び出しした結果をそのまま射影するテストであり、ready-set 計算アルゴリズム自体の単体テストは producer 側 (`plugin-plans/plugin-dev-planner/phase-04-test-design.md` の C4 受入例) が既に担う。本 phase のテストは「dispatch-ready-set.py が subprocess 結果を正しく薄く射影し、write_scope 衝突ペアを conflicts へ明示する」契約に閉じる (責務の二重テストを避ける)。

4. **冪等 resume (C10-a)**: T1(done)→T2(state=done・build 中断前に完了済み)→T4(depends_on=[T2], pending)。中断/再開後に同一 task-graph/task-state をそのまま再度渡す。期待 `ready_batch = ["T4"]` (T2 は既に done のため再 dispatch 対象に含まれず、`merge_state()` が done ノードをそのまま反映し producer 側 ready-set アルゴリズムが自然に除外する。再実行時に T2 が再度 running へ遷移する回帰が無いことを固定テストで示す)。
5. **周回 graph_hash 再検証 (C10-d・F10)**: task-state.json に pin 済み graph_hash が存在する状態で dispatch-ready-set.py を呼ぶ 2 ケースを固定する。(a) 現 task-graph.json の再計算 hash が pin と一致 → 期待 `graph_hash_pin = "verified"`・通常どおり `ready_batch` を出力し exit0。(b) dispatch ループ中に task-graph.json が改変され再計算 hash が pin と不一致 → 期待 `graph_hash_pin = "mismatch"`・exit1 (build 開始時 1 回の C07 pin 検証を素通りした実行中の graph 変更混入を、dispatch 周回ごとに fail-closed で拒否する)。pin 未設定 (cycle 初回) では `graph_hash_pin = null` で照合をスキップし正常動作する。

### C07 受入例 (manage-build-lease.py・build 開始前安全性ゲート)
| ケース | 入力 | 期待 |
|---|---|---|
| lock 取得成功 | `--lock-action acquire`, `.build.lock` 不在 | exit0, `{lock: "acquired", ...}`, `.build.lock` が生成される |
| 二重起動検出 (排他・C10-c) | `--lock-action acquire`, `.build.lock` が既に存在 (他プロセス保持中) | exit1, `{lock: "already-held"}` (build 開始を拒否) |
| 孤児 lease 回収判断 (C10-b) | task-state.json に T2 (state=running, lease_expires_at=過去時刻) が存在 | exit0, `reaped_task_ids: ["T2"]` を返し、内部で `sync-task-state.py --task-id T2 --to-state pending --reap-lease` を subprocess 呼出しして実書込みを委譲する (本 script 自身は task-state.json を直接書かない) |
| graph_hash pin 一致検証 (C10-d) | task-state.json に既に pin 済み graph_hash が存在し、現 task-graph の再計算 hash と一致 | exit0, `{graph_hash_pin: "verified"}` |
| graph_hash pin 不一致検出 (C10-d・fail-closed) | task-state.json に pin 済み graph_hash が存在するが、build 中に task-graph.json が変更され再計算 hash と不一致 | exit1, `{graph_hash_pin: "mismatch"}` (実行中の graph 変更混入を拒否し build を停止させる) |
| graph_hash 初回 pin | task-state.json に graph_hash が未設定 (初回 build) | exit0, producer 側 `derive-task-graph.graph_hash()` の算出値を `sync-task-state.py --pin-graph-hash` 経由で書き込ませ `{graph_hash_pin: "pinned"}` を返す |
| 孤児 lock steal (C10-c・恒久 lockout 防止) | `--lock-action acquire`, `.build.lock` が存在するが中身 `started_at` が `lock_ttl_seconds` (既定 lease の 2 倍) より過去 (dispatcher クラッシュ残留) | exit0, `{lock: "stolen"}`・`.build.lock` を自分の `{started_at:now, pid, host}` で上書き再取得 (孤児 lock を安全に steal し build 再開を可能にする) |
| 生存 lock は steal されない | `--lock-action acquire`, `.build.lock` の `started_at` が `lock_ttl_seconds` 未超過 かつ pid 生存 | exit1, `{lock: "already-held"}` (稼働中 build を誤って乗っ取らない) |
| 手動解放 (force-release) | `--lock-action force-release`, `.build.lock` が存在 (状態不問) | exit0, `.build.lock` を無条件 unlink し `{lock: "released"}` (人間の救済手順) |
| lock heartbeat (renew) | `--lock-action renew`, 自身が保持中の `.build.lock` が存在 | exit0, `.build.lock` の `started_at` が `now` へ更新され `{lock: "renewed"}` |
| 長時間 running は回収されない (C10-b・F1 偽孤児防止) | task-state.json に T2 (state=running) が存在し、dispatcher が定期 `sync-task-state.py --task-id T2 --renew-lease` で `lease_expires_at` を将来へ延長し続けている | `find_expired_leases()` が T2 を返さず `reaped_task_ids: []` (heartbeat 更新中の正当な長時間 build を偽孤児として回収しない) |
| lock 解放 | `--lock-action release`, `.build.lock` が存在 | exit0, `.build.lock` が削除され `{lock: "released"}` |

### C11 受入例 (sync-task-state.py 拡張・実行イベントログ)
| ケース | 入力 | 期待 |
|---|---|---|
| state 遷移イベント追記 | `--task-id T2 --to-state running` | task-events.jsonl へ `{"ts":..., "type":"state_transition", "task_id":"T2", "from_state":"pending", "to_state":"running"}` の 1 行が追記される (append-only・既存行は変更されない) |
| dispatch 判断イベント追記 | `--event-extra '{"type":"ready_set_snapshot","ready_batch":["T2","T3"]}'` | task-events.jsonl へ dispatcher 由来のスナップショットがそのまま 1 行追記される (本 script は内容を解釈せず記録するのみ) |
| replay 整合検査 | task-events.jsonl を先頭から順に replay し各 task の終端 state を再構成する | 再構成結果が現在の task-state.json の各 task state と完全一致する (現在値と履歴の二層分離の整合性を固定テストで示す) |

### C2 受入例 (sync-task-state.py・状態遷移)
| ケース | 入力 | 期待 |
|---|---|---|
| 正常遷移 | `--task-id T2 --to-state running`, T2 現状態 pending | exit0, task-state.json の T2.state が running に更新, canonicalizer 経由で正準直列化 |
| 正常遷移 (完了) | `--task-id T2 --to-state done`, T2 現状態 running, route-report 存在 | exit0, T2.state が done に更新 |
| 不正遷移 (後退) | `--task-id T2 --to-state pending`, T2 現状態 done | exit1, task-state.json 無変更 (後退遷移を fail-closed で拒否) |
| route-report 欠落 | `--to-state done` だが `--route-report` が指す path が存在しない | exit1, task-state.json 無変更 |
| 周回衝突排除・handoff.cycle_id 無し (null・後方互換) | `--target-plugin-slug harness-creator --cycle-id` 省略 (handoff.cycle_id が null)、`--task-state` 省略 | `resolve_build_dir("harness-creator", None)` が `eval-log/harness-creator/build` を返す (既存 flat レイアウトのまま・path 変化なし) |
| 周回衝突排除・handoff.cycle_id 有り | `--target-plugin-slug harness-creator --cycle-id 20260710-task-graph-consumer` (handoff.cycle_id フィールドの明示値)、`--task-state` 省略 | `resolve_build_dir("harness-creator", "20260710-task-graph-consumer")` が `eval-log/harness-creator/build/20260710-task-graph-consumer` を返す (cycle_id は producer 側確定値をそのまま消費・新規生成・検証は行わない) |
| 負例: `--out-dir` 上書き plan (plan_dir のパス文字列が slug と異なっていても handoff.cycle_id が null なら flat 維持) | `--plan-dir plugin-plans/custom-location` (plan_dir 側は関数へ一切渡されない) だが handoff.cycle_id は null | `resolve_build_dir("harness-creator", None)` は `--plan-dir`/`--out-dir` の値を一切参照しないため `eval-log/harness-creator/build` のまま (plan_dir 文字列を cycle-id 相当として誤判定していたはずの回帰を防止する固定テスト) |
| lease 回収による特別遷移 (running→pending) | `--task-id T2 --to-state pending --reap-lease`, T2 現状態 running かつ lease_expires_at が現在時刻より過去 | exit0, T2.state が pending に更新され `lease_reaped` イベントに reason `"lease_expired"` が記録される (通常の ALLOWED_TRANSITIONS 経路とは別扱い) |
| 不正な reap (期限未到来) | `--reap-lease` 指定だが T2 の lease_expires_at が現在時刻より未来 | exit1, task-state.json 無変更 (期限未到来の running を pending へ回収させない) |
| lease heartbeat (renew・F1) | `--task-id T2 --renew-lease`, T2 現状態 running かつ lease_expires_at 未来 | exit0, T2.state は running のまま lease_expires_at が `now + lease_seconds` へ延長され `lease_renewed` イベントが task-events.jsonl へ追記される (state 遷移なし) |
| blocked 遷移の理由必須 (F9) | `--task-id T1 --to-state blocked` で `--reason` 省略 | exit1, task-state.json 無変更 (起点故障 origin-failure と伝播 propagated を区別するため reason を必須とする) |
| blocked 起点 + 下流伝播 (F3・propagate-blocked) | `--task-id T1 --to-state blocked --reason origin-failure --propagate-blocked --task-graph <path>` で T2/T3 が depends_on=[T1] | exit0, T1.state=blocked かつ blocked_reason=origin-failure・下流閉包 T2/T3 も state=blocked かつ blocked_reason=propagated へ連鎖遷移し、各遷移が task-events.jsonl へ追記される (単一 writer=C02 を維持) |
| route:task=1:N の covered_task_ids 照合 (F6) | `--task-id T2 --to-state done --route-report <path>` で route-report の `covered_task_ids=["T2","T3"]` | exit0, T2 が done へ遷移 (--task-id が covered_task_ids に含まれるため許可) |
| covered_task_ids 不整合 (F6・fail-closed) | `--task-id T9 --to-state done --route-report <path>` で route-report の `covered_task_ids=["T2","T3"]` (T9 を含まない) | exit1, task-state.json 無変更 (1 route が賄わない task を done 遷移させない) |

### C3 受入例 (inject-task-inputs.py・成果物注入)
| ケース | 入力 | 期待 |
|---|---|---|
| 正常注入 | dependent=T4, producer T2/T3 とも state=done かつ各 artifact_path が実在 | exit0, `injected_inputs` に T2/T3 の build_target が列挙 |
| producer 未完了 | dependent=T4, T2.state=pending | exit1, `{rejected: true, blocking_producer_task_id: "T2"}` |
| producer done だが成果物欠落 (F5・state==done 代理述語に依存しない) | dependent=T4, T2.state=done だが T2 の build_target (artifact_path) が実在しない | exit1, `{rejected: true, blocking_producer_task_id: "T2", missing_artifact: <path>}` (done state と成果物実在の乖離を fail-closed 検出) |
| notes 有界性違反 (F8・上限は schema 由来) | notes 件数が handoff-notes.schema.json の maxItems を超過 (`--max-notes` 省略時は schema 値を既定として使用し consumer 側で数値を再定義しない) | exit1, 有界性違反理由を明示 |

### C4 受入例 (emit-discovered-task.py・E4 境界)
| ケース | 入力 | 期待 |
|---|---|---|
| 正常 emit | `--discovering-task-id T2 --proposed-node '{"id":"T-new",...}' --change-level additive` (task-graph 上に T2 が実在) | exit0, producer discovered-task.schema.json 正準準拠の discovered-task.json (schema_version/discovering_task_id/reason/discovered_at_artifact/proposed_node/change_level/provenance) を inbox 定位置へ出力 |
| source 不在 | `--discovering-task-id T99` (task-graph 上に不在) | exit1 |
| E3/E4 分離確認 | emit-discovered-task.py の出力を `improvement-handoff.schema.json` で検証 | 不一致 (discovered-task.schema.json のみで検証可能なこと。E3 の emit-improvement-handoff.py の出力と混同されないことを固定テストで示す) |

### C5 受入例 (summarize-task-progress.py・進捗集計)
| ケース | 入力 | 期待 |
|---|---|---|
| 混在 state | task-state.json = {T1:done, T2:running, T3:pending, T4:blocked} | `{total:4, by_state:{done:1,running:1,pending:1,blocked:1}, completion_rate:0.25, blocked_tasks:["T4"]}` |
| additive 読取確認 | route-build-report (PR#70 契約) に既存フィールドのみの fixture を与える | 既存フィールドを変更せず読み取りのみで完走 (exit0) |
| 周回衝突排除 (C2 と同一導出) | `--target-plugin-slug harness-creator --cycle-id 20260710-task-graph-consumer`, `--build-dir` 省略 | C02 の `resolve_build_dir(target_plugin_slug, cycle_id)` を import した結果 `eval-log/harness-creator/build/20260710-task-graph-consumer` 配下の route-*.json のみを集計対象にする (C2 と同一の handoff.cycle_id 消費結果を再現し独自導出を持たない) |
| 停滞検出 (C12)・deadlock | task-state.json = {T1:done, T2:blocked, T3:blocked}, `--ready-batch '[]'` (dispatcher が C01 の直近出力を転送), `--task-graph` に T2 の depends_on=[T4] (T4 が task-graph 上に不在) | `stall: {stalled: true, diagnosis: ["T2 は depends_on T4 が task-graph 上に不在のため blocked", ...]}` |
| 停滞検出 (C12)・producer 失敗による下流全 blocked (DAG 妥当) | task-state.json = {T1:blocked (route 失敗), T2:blocked, T3:blocked} (T2/T3 は depends_on=[T1]・DAG 自体は非循環で妥当), `--ready-batch '[]'` | `stall: {stalled: true, diagnosis: ["T1 (route 失敗) が blocked のため下流 T2/T3 が伝播 blocked"]}` (DAG 構造は正常でも実行時停滞が起きる例として固定) |
| 停滞なし (running が存在) | task-state.json = {T1:done, T2:running, T3:pending}, `--ready-batch '[]'` | `stall: null` (running が 1 件でもあれば停滞と判定しない) |

### C13 受入例 (record-task-graph-knowledge.py・完了ブロック + knowledge 化)
| ケース | 入力 | 期待 |
|---|---|---|
| 未処理 discovered-task が残る | `<build_dir>/discovered-tasks/D1.json` が status 欠落または `pending` | exit1, `completion_gate="blocked"`, `pending_discovered_tasks=["D1"]`。capability-build は completed にせず planner `--mode update` へ差し戻す |
| 処理済み discovered-task のみ | inbox 内が `accepted` / `rejected` / `superseded` のいずれか | exit0, `completion_gate="pass"`。accepted は planner が graph 更新済み、rejected/superseded は人間または planner が不要判断済みとして扱う |
| Loop A/Loop B への knowledge 追記 | task-events.jsonl + stall summary + route-build-report の handoff_notes から、依存詰まりと解決策が 1 件ずつ抽出される | `add_entry.py --dir <target knowledge>` と `add_entry.py --dir plugins/harness-creator/knowledge` が呼ばれ、各 entry が id/title/intent/background/keywords/source の必須6フィールドを満たす |
| 情報量の有界化 | task-events.jsonl が巨大 (1000行以上) | knowledge entry は `source_ref` と 1-3 件の distilled lesson のみを持ち、生ログ全文・推移的な全 notes を複製しない |

### C6 受入例 (capability-build・後方互換)
| ケース | 入力 | 期待 |
|---|---|---|
| task_graph_ref 有り | handoff に `task_graph_ref` フィールドが存在 | C01 (dispatch-ready-set.py) 経路へ分岐し並列 dispatch を試みる |
| task_graph_ref 無し | 従来の handoff (`task_graph_ref` フィールド不在) | 従来 top-sort 直列モードのまま既存ゲート (core 5 scripts) を維持し、新規 C01-C05/C07/C08 分岐に一切触れない (後方互換固定) |

## 成果物
- feedback_contract 相当の受入基準は非 skill component (script/slash-command) のため criteria ブロックを持たないが、上記 C1-C8・C10-C13 の受入例テーブル・fixture が test-first の正本として本 phase 本文に確定済み。

## スコープ外
- 実装コード自体 (P05 で設計プローズとして確定し、L4 build で実コード化)。

## 完了チェックリスト
- [ ] C1 の 3 テストケース (直列チェーン/ダイヤモンド/write_scope衝突) + 冪等 resume 1 ケース (C10-a) が期待 `ready_batch`/`conflicts` 付きで内包されている。
- [ ] C2-C5, C07, C08 の受入例テーブルが各 component の component-inventory.json 記載の exit_codes と一致する。
- [ ] C2/C5 の周回衝突排除 (`resolve_build_dir(target_plugin_slug, cycle_id)`) が handoff.cycle_id 有り/無し (後方互換) の両ケース + `--out-dir` 上書き plan の負例 (plan_dir 非参照確認) を具体的な期待 build_dir 付きで内包している。
- [ ] C6 の後方互換テストケース (task_graph_ref 有無の分岐) が具体的に内包されている。
- [ ] C10 (冪等 resume/孤児 lease 回収/build lock 排他/graph_hash pin 不一致) の 4 ケースが具体的な期待挙動付きで内包されている。
- [ ] 実行排他の堅牢化 (F1 lease/lock heartbeat renewal で長時間 running が偽孤児回収されない負例・F2 孤児 lock steal / 生存 lock 非 steal / force-release・F10 dispatch 周回ごとの graph_hash 再検証 mismatch 拒否) が具体的な期待挙動付きで内包されている。
- [ ] blocked 伝播 (F3 propagate-blocked による下流連鎖遷移・F9 origin-failure/propagated の reason 区別) と route:task=1:N の covered_task_ids 照合 (F6) の受入例が内包されている。
- [ ] 成果物実在検査 (F5 producer done だが artifact 欠落の fail-closed 負例) と notes 上限の schema 由来化 (F8) が受入例に反映されている。
- [ ] C11 (実行イベントログの追記・replay 整合検査) が具体的なイベント形式付きで内包されている。
- [ ] C12 (deadlock/starvation 検出・原因診断・DAG 妥当でも起きる実行時停滞) が具体的な診断出力付きで内包されている。
- [ ] C13 (未処理 discovered-task 完了ブロック・Loop A/Loop B knowledge 追記・情報量有界化) が具体的な入出力付きで内包されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記の C1-C7 テーブルの通り、具体的な task id・write_scope・depends_on・期待 dispatch batch/state/exit code/lease/graph_hash/イベントログ/停滞診断が数値・文字列・JSON で確定している。
- 満たさない例: 「並列 dispatch と後方互換と冪等再開のテストケースを用意する」とだけ記され、具体的な期待値が未確定のまま P05 へ進む。

### 事前解決済み判断
- 分岐点: C1 の ready-set 計算アルゴリズム自体の単体テストを本 plan (consumer 側) でも複製するか → 判断: 複製しない (producer 側 phase-04 が C4 受入例として既に担っており、本 plan は dispatch-ready-set.py の射影契約 [subprocess 結果の正しい受け渡し + conflicts 明示] のみをテスト対象にする。constraints #1 の SSOT 遵守を test 設計レベルでも徹底する)。

## 参照情報
- `plugin-plans/harness-creator/component-inventory.json` (C01-C08)。
- `plugin-plans/plugin-dev-planner/phase-04-test-design.md` (C4 受入例・compute-ready-set.py 自体のテスト正本、C16 の task-state.schema.json 受入例)。
- P02 (design)。
- 後続 P05 (implementation)。
