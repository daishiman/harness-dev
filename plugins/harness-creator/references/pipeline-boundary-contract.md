# パイプライン境界契約 (E1/E2/E3/E4)

> skill-intake → plugin-dev-planner → harness-creator build → 改善 という量産パイプラインの
> 3 つの段境界における producer/consumer の機械契約・検証ゲート・provenance を単一箇所に集約する
> 参照正本。各段の**実行は分離**したまま (自動連鎖 orchestrator は設けない)、境界の *契約* だけを固める。
>
> **各段を実際に起動するコマンド/スキルの表記・実態・用途は `pipeline-command-reference.md` を参照** (本ファイルは契約、あちらは操作手順)。

## 用語

- **E1 (intake→goal-spec)**: skill-intake の `intake.json` を plugin-dev-planner が消費し goal-spec へ源泉反映する境界。
- **E2 (plan→build)**: plugin-dev-planner の `handoff-run-plugin-dev-plan.json` の `routes[]` を harness-creator の build 実行入口が消費する境界。
- **E3 (改善→plan)**: 改善成果物 (run-elegant-review 等) を `improvement-handoff.json` に正規化し、`run-plugin-dev-plan --mode update` が受理して plan へ還流する境界。
- **E4 (build中発見→planner提案・外ループ帰路)**: harness-creator が task-graph 実行中に発見した追加タスクを `discovered-task` proposal として inbox に出し、次回 `run-plugin-dev-plan --mode update --discovered-inbox <inbox>` が inbox を一括ドレインして受理/却下/置換し plan/task-graph へ反映する境界。これは **spec-improvement loop (外ループ)** の帰路であり、build 実行 (内ループ) を回す E2 と対になる。
- **provenance chain**: `intake.json → goal-spec(source_intake) → plan → build handoff → 改善成果物(source_improvement)` の 5 ノードと、それを読む次サイクル goal-spec の逆リンク追跡可能性。

## 識別子 namespace 凡例 (裸 Cxx 禁止)

`Cxx` 形式の component id は系統ごとに独立採番され同番号が異義衝突する (例: PB-C08=parity 検査 / TG-C08=完了ゲート / ENG-C08=graph-knowledge lint)。恒久 doc では**裸の `Cxx` 表記を禁止**し、必ず以下の接頭辞または文脈語で修飾する。

| 表記 | 系統 | 番号→実体の対応 | 番号正本 |
|---|---|---|---|
| `PB-Cxx` | パイプライン契約系 (本ファイルの境界表 C01..C11) | PB-C01=`run-plugin-dev-plan` R1 / PB-C02=`/plugin-dev-plan` / PB-C04=`check-intake-consumption.py` / PB-C05=`check-provenance-chain.py` / PB-C06=`run-skill-create` R1 (`brief_path`/`handoff` 消費) / PB-C07=`/capability-build` build 入口 / PB-C08=`check-route-component-parity.py` / PB-C09=`emit-improvement-handoff.py` / PB-C10=`plugin-dev-plan-improvement-reviewer` / PB-C11=`enforce-provenance-chain` hook | 本ファイル |
| `TG-Cxx` | task-graph 実行系 (harness-creator `scripts/` + dispatcher) | TG-C01=`dispatch-ready-set.py` / TG-C02=`sync-task-state.py` / TG-C03=`inject-task-inputs.py` / TG-C04=`emit-discovered-task.py` / TG-C05=`summarize-task-progress.py` / TG-C06=`/capability-build` の task-graph dispatcher 拡張 (command 本文・script ではない) / TG-C07=`manage-build-lease.py` / TG-C08=`record-task-graph-knowledge.py` / TG-C09=`project-task-status.py` (live 状態の plan dir 投影・観測性) | 本表が正本 (歴史的導出元: 当該周回の phase-05) |
| `ENG-Cxx` | 生成 harness 同梱 engine 系 (with-goal-seek `engine:task-graph` 変種) | ENG-C01=`ready-set-from-checklist.py` / ENG-C02=`self-reflect-append.py` / ENG-C06=`extract-capability-dependency-graph.py` / ENG-C07=`record-capability-graph-knowledge.py` / ENG-C08=`lint-capability-graph-knowledge.py` | `skills/run-build-skill/SKILL.md` |
| `route Cxx` / `component Cxx` | plan-local component id (各 plan の inventory 内番号) | 接頭辞は付けず、必ず「route C09」「component C12」のように文脈語を添える | 各 `plugin-plans/<slug>/component-inventory.json` |

## 境界ごとの producer / consumer / gate

| 境界 | producer | consumer | 検証ゲート | provenance |
|---|---|---|---|---|
| E1 | skill-intake `intake.json` (v2.0.0) | `run-plugin-dev-plan` R1 (PB-C01)・`/plugin-dev-plan --intake-json` (PB-C02) | `check-intake-consumption.py` (PB-C04・情報漏れ検出) | goal-spec `source_intake: {ref, schema_version}` |
| E2 | `handoff-run-plugin-dev-plan.json` の `routes[]` + `render-skill-brief.py` (brief 実体化の owner=`/capability-build` route preflight が inventory から射影) | `run-skill-create` R1 `brief_path`/`handoff` (PB-C06)・`/capability-build --handoff` (PB-C07・既定=task-graph route モードで `--handoff` 1 回によりグラフ全体を消費・`--route-id` は段階 build 用 escape hatch) | `check-route-component-parity.py` (PB-C08・routes↔inventory 1:1) | route ↔ inventory の 1:1 対応 |
| E3 | 改善成果物 → `emit-improvement-handoff.py` (PB-C09) → `improvement-handoff.json` | `run-plugin-dev-plan --mode update` `improvement_handoff` (PB-C01) | `check-provenance-chain.py` (PB-C05)・`enforce-provenance-chain` hook (PB-C11) | goal-spec `source_improvement: {ref, schema_version}` |
| E4 | harness-creator `/capability-build` task-graph 経路 → `emit-discovered-task.py` (TG-C04・`--change-level additive\|structural`) → `eval-log/<slug>/build[/<cycle-id>]/discovered-tasks/*.json` | planner 側 `accept-discovered-task.py --inbox` (一括ドレイン+status 書戻し) + `run-plugin-dev-plan --mode update --discovered-inbox` | `record-task-graph-knowledge.py` (TG-C08) の completion gate (未処理 proposal が残れば `completion_gate:blocked`+`handback_command` で completed 拒否) | discovered-task `{discovering_task_id, proposed_node, change_level, status, resulting_graph_hash, provenance.route_id}` |

## 契約スキーマ

- `improvement-handoff.json`: `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/schemas/improvement-handoff.schema.json` (schema_version / source{kind,ref} / target_plugin_slug / plan_dir / findings[] / provenance{source_intake, prev_goal_spec, origin_request{kind,ref}})。
- goal-spec provenance フィールド: `plugin-goal-spec.schema.json` の `source_intake` / `source_improvement` (任意・欠落は後方互換で WARN 受理)。

## 新規作成フロー一巡 (E1→E2)

1. `intake.json` と `next-action.json` を用意し `/plugin-dev-plan "<構想>" --intake-json <intake.json> --next-action-json <next-action.json>` を起動 (PB-C02→PB-C01)。
2. R1 が §0/§3 と `split_candidates[]` を反映し `source_intake` を記録、`check-intake-consumption.py --next-action ... --strict` で未反映 0 を確認 (PB-C04)。
3. plan 生成後、`handoff-run-plugin-dev-plan.json` を得る。
4. `/capability-build --handoff <handoff>` で消費する (PB-C07)。**既定=task-graph route モード** (planner 生成 handoff は `task_graph_ref` を常時携帯するため、`--handoff` 1 回でグラフ全体を 2 ループ駆動)。段階 build が必要なときのみ `--route-id <route component id>` を escape hatch として明示し単一 route を消費する。build 前に `check-route-component-parity.py` を preflight (PB-C08)。
5. `/capability-build` の route preflight が skill route の `build_args.brief_path` 未 materialize を検知したら `render-skill-brief.py --inventory <PLAN_DIR>/component-inventory.json --component <route-id> --out <PLAN_DIR>/<brief_path>` で射影し、skill route は `run-skill-create` が `brief_path` 経由で再ヒアリングなしに build (PB-C06)。

## 改善フロー一巡 (E3)

1. 改善成果物 (例 `run-elegant-review` の findings) を `emit-improvement-handoff.py` で `improvement-handoff.json` へ正規化 (PB-C09)。
2. 現 goal-spec に対し `check-intake-consumption.py` / `check-provenance-chain.py` を `--marker-dir <PLAN_DIR>` 付きで PASS させ、PB-C04/PB-C05 の pass marker (goal-spec digest pin) を作る。
3. `/plugin-dev-plan "<構想>" --mode update --out-dir <PLAN_DIR> --improvement-handoff <handoff>` を起動 → `enforce-provenance-chain` hook (PB-C11) が PreToolUse で marker の存在と digest 一致を確認 (欠落/stale なら exit2 block)。`--out-dir` が無くても hook は handoff の `plan_dir` を読んで検査する。
4. PB-C01 が `findings[]` を反映し `source_improvement` を記録、`check-provenance-chain.py` で断裂なしを確認 (PB-C05)。
5. `plugin-dev-plan-improvement-reviewer` (PB-C10) が改善成果物と再生成 plan の意味的整合を独立レビューし verdict を返す。

## task-graph 実行フロー一巡 (2 ループ = 内ループ build 実行 + 外ループ spec 改善)

task-graph は planner が作る計画構造であり、harness-creator は build 実行状態と知見だけを書く。両者を双方向 writer にしない。日々の build で新しい課題が見つかった場合も、harness が graph/phase/inventory/handoff を直接編集せず、proposal と knowledge を残し、次サイクルの planner update が graph を更新する。

実行は **2 つの入れ子ループ** (内=build-execution loop・TG-C06 所有 / 外=spec-improvement loop) で駆動する。dispatch 手順・stall 分岐・handback 提示などの**制御フロー正本は `commands/capability-build.md` の「task-graph route モード」節**であり、本ファイルはループ間契約の不変条件のみを定める:
- **単一 writer**: state write-back は dispatcher (TG-C06) が直列呼出しする `sync-task-state.py` (TG-C02) のみが行う (SubAgent は state を書かない)。
- **完了ゲート fail-closed**: `record-task-graph-knowledge.py` (TG-C08) が未処理 discovered-task 残存時に completed を機構的にブロックし、`handback_command` で外ループへ制御返却する。第2段=--task-state の blocked node 残存、第3段=graph の local required node 全件 done (P13 一括例外は禁止。schema-valid `runtime-evidence-ledger.json` が task id 単位で列挙した install/enable/trust/new-session/uninstall/PR の user-owned node だけを保留可)、第4段=C01 `sync-native-surfaces.py --check --json` の単一 desired-set gate とする。TG-C08 から旧 reflector/C02 を個別再実行せず、C01 child report に含まれる parity 結果を判定する。
- **provenance-gated repin**: 実行中の graph 差替えは accepted discovered-task の `resulting_graph_hash` と一致する場合のみ TG-C07→TG-C02 委譲で再 pin (`repinned`) し、不一致は不正混入 (F10) として `mismatch` で fail-closed 拒否する。

本節が単一 writer 規約を含むループ間不変条件の唯一の正本であり、他文書・script header の同旨記述は本節への参照 (要約) である。

| 項目 | writer / owner | reader / consumer | 完了ゲート | 備考 |
|---|---|---|---|---|
| `task-graph.json` / phase / inventory / handoff | plugin-dev-planner | harness-creator `/capability-build` | planner 側 graph/schema/gate | harness は read-only。plan 直接 mutation 禁止 (例外は下行 TG-C09 の gitignore 済派生投影ビューと、`reports/` 行のリッチ版納品物の 2 write class のみ) |
| `task-state.json` / `task-events.jsonl` | harness-creator `sync-task-state.py` | `dispatch-ready-set.py` / `summarize-task-progress.py` / `record-task-graph-knowledge.py` | state schema + replay 整合 | state と event は同じ単一 writer。TG-C07 acquire は dispatch 前に TG-C02 `--initialize-from-graph` へ委譲し、graph 全 node を pending materialize (既存 state は保持、未知/重複は拒否) して sparse state を禁止 |
| discovered-task inbox | harness-creator `emit-discovered-task.py` | planner `accept-discovered-task.py` | 未処理 status があれば TG-C08 が completed 拒否 | status は `accepted` / `rejected` / `superseded` で解決済み |
| build 成果物の周回 scope | harness-creator `resolve_build_dir(target_plugin_slug, cycle_id)` | TG-C02/TG-C05/TG-C07/TG-C08 | `cycle_id` は handoff top-level だけを消費 | `plan_dir` のパス解析は禁止 |
| blocked 起点/伝播 | harness-creator `sync-task-state.py` | progress summary / knowledge distill | `blocked_reason` 必須 | `origin-failure` と `propagated` を state enum ではなく第一級 field で区別 |
| knowledge Loop A | generated harness の `knowledge/` | 生成後 harness の build/runtime | add_entry.py schema | 生ログ全文ではなく source_ref 付き要約のみ |
| knowledge Loop B | `plugins/harness-creator/knowledge/` | harness-creator の次回 build-time search | add_entry.py schema | 依存詰まり・成果物欠落・解決判断を再利用 |
| `.build.lock` (build 排他 lock) | harness-creator `manage-build-lease.py` (TG-C07) | TG-C07 自身 (steal/renew/release 判定) | owner token + lock TTL + pid 生存判定 | 中身は `{started_at, pid, host, owner_token}` JSON。acquire 出力 token をメモリ保持し renew/release で一致必須。runtime 生成物で git 追跡外 |
| `runtime-evidence-ledger.json` | dispatcher (TG-C06) | TG-C08 completion gate | `runtime-evidence-ledger.schema.json` + artifact SHA-256 + task-state graph_hash pin + UTC timestamp + gate/task mapping | ledger 所在 build dir 相対 artifact path のみ。local build/native parity/rollback 証跡必須。`not_applicable` は user が不要と明示した PR gate のみ |
| `route-*.json` (route-build-report) | route builder (`build-script-route.py` / `run-build-skill`) | `validate-route-build-reports.py` / TG-C02 (done 照合) / TG-C05 / TG-C08 | route-build-report 契約 (PR#70・additive のみ) | `covered_task_ids` は dispatcher (TG-C06) が node→route join から決定論導出して追記する |
| `plan-P*.json` (checklist-verification report) | harness-creator dispatcher (TG-C06) | TG-C02 (done 照合) / TG-C08 | `verified_by` + `covered_task_ids` 必須 | `entity_ref=null` ノードの plan-node-verification 証跡 |
| `task-graph-status.json` / `task-progress.md` / `task-execution-report.html` (live 状態・実行記録投影ビュー) | harness-creator `project-task-status.py` (TG-C09) | 人間 (plan dir 観測性) / 機械 (status JSON) | HTML は self-contained/escape/決定論テスト。最終 `build-summary.json` 保存後に再投影 | **read-only 派生ビュー**: task-graph.json(構造)+task-state.json(状態)+route reports/build-summary(証跡) を merge 投影するのみで SSOT を書かず graph_hash pin を温存する。HTML は slide-report-generator の report 原則を採用し進捗/フロー図/route 証跡/外ループを構造化表示する。3 ファイルとも gitignore 追跡外で追跡衝突しない (plan dir write 例外 class その1) |
| `plugin-plans/<slug>/reports/<run-id>/` (リッチ版実行記録レポート・任意) | slide-report-generator `run-slide-report-generate` (capability-build 手順 5 の委譲先) | 人間 (納品閲覧) | slide-report-generator 側の R3.5/RQ 検証 | **tracked 納品物** (毎回上書きしない point-in-time 記録・gitignore しない)。オンライン閲覧想定で web font 等の外部資産を許容する — 自己完結の正本は上行 TG-C09 決定論版。plan dir write 例外 class その2 |

handoff `routes[].status` は planner の計画時宣言のみであり、build 後も `planned` 据置が正 (実行状態の正本は task-state.json / route-build-report。parity 突合対象外)。この意味論は planner 側 `references/io-contract.md` の handoff 契約にも同旨を明記する (誤読が起きる成果物の近くに置く)。

### 実行時契約の既定値表 (正本)

| 契約値 | 既定 | owner | 根拠 |
|---|---|---|---|
| task lease | 3600s (`--lease-seconds`) | TG-C02 | 単一 route build の正常所要上限の見込み。超過する正当 build は heartbeat renew で表明する |
| lock TTL | 2×lease = 7200s (`--lock-ttl-seconds` 既定) | TG-C07 | lease 1 周期 + 回収猶予を包含し、lease 回収より先に lock が steal されない順序を保つ |
| heartbeat 周期 | ≤ lock TTL / 3 | dispatcher (TG-C06) | renew 1 回の一過性失敗を挟んでも TTL 失効前に次の renew が届き偽孤児化しない |
| knowledge max-entries | 3 (`--max-entries`) | TG-C08 | 周回あたりの knowledge 肥大を防ぎ bounded summary への蒸留を強制する (constraints #11) |

`record-task-graph-knowledge.py` は completion gate と knowledge 記録の owner だが、task-graph の owner ではない。未処理 discovered-task が残る限り completed を出さず、全 proposal が `accepted` / `rejected` / `superseded` のいずれかになった後で、task-events/stall summary/route-build-report handoff_notes から必要最小限の lesson を蒸留する。

### build lock の legacy migration / 管理者救済

owner token 導入前の `{started_at,pid,host}` lock は推測可能な pid/host だけでは所有権を証明できない。そのため TG-C07 は次の順序を固定する。

1. legacy lock が TTL 超過または同一 host の死 pid なら stale と判定し、compare-delete + O_EXCL 再取得で owner-token 形式へ自動移行する。
2. legacy lock が生存中なら `already-held` + `lock_format=legacy` で fail-closed にし、自動移行・renew・通常 release を禁止する。
3. owner の正常終了または TTL 失効を待てない緊急時だけ、人間の管理者が `manage-build-lease.py --lock-action force-release --admin ...` を実行する。dispatcher はこの導線を使用しない。
4. force-release も読取 snapshot と inode/content が一致する場合だけ compare-delete する。新 owner の lock が race で置換された場合は削除しない。

### task-state 損失時の再導出手順 (runbook)

`task-state.json` は eval-log 配下の ephemeral 成果物 (gitignore) であり、損失・破損は設計上起こりうる。復旧は次の決定論手順のみを正とし、**handoff `routes[].status` を実行状態として読まない** ("planned" 据置は計画時宣言 — 誤読して route を再 build すると `--mode update` の Edit 差分が二重適用され非冪等):
1. 同 build dir の `route-*.json` (route-build-report) と `plan-P*.json` (checklist-verification report) から各 node の done/blocked を再導出する (`covered_task_ids` が node→報告の決定論 join)。
2. 再導出した state の `graph_hash` を canonical `task-graph.json` の `derive-task-graph.graph_hash()` 算出値と突合して pin する。
3. `check-task-state-schema.py --task-state <path> --task-graph <canonical>` の exit0 で schema + pin を確認する。
4. producer 側 parity 検査 (planner `project-task-status.py`・C18) の exit0 で graph/state/projection の 3 面一致を確認して完了。部分損失 (node 集合不一致) は同検査が exit1 で捕捉するため、欠落 node のみ手順 1 から再導出する。

## 2 ループの actor 責務分離 (AI orchestrator / 決定論 script / 独立 SubAgent / 人間承認)

前節の表は artifact→writer/reader の**データ所有**を定める。本節は 2 ループの各ステップを**判断主体 (actor)** で切り分ける単一対照表であり、「どこを AI が判断し、どこを決定論 script が機械実行し、どこを人間が承認するか」を一望させる (保守者が層を取り違えないための正本)。原則: **活性 (何を並列に起動するか等の判断) は AI orchestrator、安全と決定性 (排他/pin/受理/state 遷移) は決定論 script、不可逆な仕様変更の承認は人間**。

| ループ | ステップ | actor (主体) | 担い手 | 備考 |
|---|---|---|---|---|
| 内 | build 開始ゲート (lock 排他 / graph node 初期化 / 孤児 lease 回収 / graph_hash pin) | 決定論 script | `manage-build-lease.py` (TG-C07) → `sync-task-state.py --initialize-from-graph` (TG-C02) | owner-token + O_EXCL・pid 生存判定・全 node materialize・producer hash 照合 |
| 内 | ready-set 計算 | 決定論 script | `dispatch-ready-set.py` (TG-C01) → producer `compute-ready-set.py` | depends_on 完了 + consumes 実在 + write_scope 非重複 |
| 内 | fan-out 判断 (どの ready を並列起動するか) | **AI orchestrator** | dispatcher=`/capability-build` (TG-C06) | TG-C01 の `ready_batch`/`conflicts` を入力に起動を決める |
| 内 | node→build 解決 (`entity_ref`→route 写像) | 決定論写像 | dispatcher (`entity_ref==route.component_id`) | 自然文 title 解釈に依存しない |
| 内 | route build 実行 | **独立 SubAgent** | `run-build-skill` / `run-skill-create` / `build-script-route.py` | 各 SubAgent 内は AI・state は書かない |
| 内 | 入力注入 (producer 成果物 / handoff_notes) | 決定論 script | `inject-task-inputs.py` (TG-C03) | 有界注入 |
| 内 | state write-back (done/blocked/lease) | 決定論 script (単一 writer) | `sync-task-state.py` (TG-C02) を dispatcher が直列呼出 | SubAgent は TG-C02 を呼ばない |
| 内 | heartbeat (lock/lease 延長) | 決定論 script | TG-C07 `renew` / TG-C02 `--renew-lease` | 偽孤児回収を防ぐ |
| 内 | 進捗集計 / 停滞判定 | 決定論 script | `summarize-task-progress.py` (TG-C05) | stall を kind 分類 |
| 内 | live 状態の plan dir 投影 (観測性) | 決定論 script | `project-task-status.py` (TG-C09) | task-graph.json+task-state.json を **read-only** merge 投影 (SSOT 不変・plan dir へ status JSON / progress md / execution-report HTML の 3 成果物・観測性断絶を解消) |
| 外 | 発見タスク emit | 決定論 script (引数の 2 つのみ AI) | `emit-discovered-task.py` (TG-C04) | stall 由来は TG-C05 構造化フィールドから機械導出・`--node-title`/`--reason` のみ AI 判断 |
| 外 | 完了ゲート (未処理 discovered-task 判定) | 決定論 script | `record-task-graph-knowledge.py` (TG-C08) | 未処理残存で completed を block |
| 外 | handback 提示 | 決定論 script 生成 → **AI が提示** | TG-C08 `handback_command`/`next_steps` | 文面は script が生成・ユーザーへ渡すのは AI |
| 外 | **structural 受理の承認** | **人間承認** | `--approved` フラグ | 不可逆な仕様変更の安全弁 (未承認は pending 据置) |
| 外 | planner drain (inbox 受理・task-graph 反映) | 決定論 script | producer `accept-discovered-task.py` | additive 自動 / structural は `--approved` 時のみ |
| 外 | graph_hash 再 pin (provenance-gated) | 決定論 script | TG-C07 → TG-C02 `--repin-graph-hash` | accepted form の `resulting_graph_hash` 一致時のみ |
| 外 | knowledge 蒸留 / 記録 (Loop A/B) | 決定論 script | TG-C08 | 完了ゲートと疎結合 (失敗は WARN) |
| 外 | 改善反映の意味的忠実性 verdict | **独立 SubAgent (fork)** | `plugin-dev-plan-improvement-reviewer` (PB-C10) | 機械緑を十分条件にしない意味層 |

## build 中発見の還流先決定表 (AI 裁量を排す)

build 実行中に発見した残件・欠陥・改善点を「どこへ還流するか」は、AI orchestrator の裁量に委ねると最小抵抗経路 (直接修正 / 放置) に流れ、外ループが実運用で bypass される。発見の種別から還流先を**機械的に決める**決定表を正本とする (どれにも当たらない場合のみ人間へエスカレーション):

| 発見の種別 | 還流先 | 担い手 | 例 |
|---|---|---|---|
| 自 plan の graph 不足 (spec-gap: depends_on/consumes 先が graph 上に不在等) | **E4 discovered-task** (`--change-level structural`) | `emit-discovered-task.py` (TG-C04) → planner drain | stall の `has_spec_gap==true` |
| 自 plan の未網羅タスク (additive: 新規 buildable component) | **E4 discovered-task** (`--change-level additive`) | 同上 (additive は自動反映) | build 中に判明した派生 component |
| 他 plugin の欠陥 (cross-plugin 依存・pin drift 等) | **E3 improvement-handoff** | `emit-improvement-handoff.py --source-kind manual` → 相手 plugin plan | upstream pin bump (`goal-seek-paradigm.md` sha 追随) |
| doc-only 軽微 (次 route が読めば足りる申し送り) | route-build-report の `handover` / `handoff_notes` | builder が report へ記録 | 命名ラベルの不精確など |
| build 中に已むを得ず out-of-band 修正した項目 | **knowledge Loop B 記録を必須**とする | `record-task-graph-knowledge.py` (TG-C08) の蒸留対象 | schema 未知キー拒否→additive 拡張の判断 |
| **post-build review の structural 発見** (elegant/content review が検出した能力境界・plan 設計変更級の残件) | **E3 improvement-handoff** | `emit-improvement-handoff.py --source-kind elegant-review` → 境界を所有する plan | full task-spec graph の生成ハーネス同梱 (with-task-graph-goalseek 境界変更) の承認判断 |

原則: **build-failure のみの stall (仕様は正しいが route 失敗) は emit せず人手救済**、**spec-gap を含む stall は structural emit して外ループへ合流**。post-build review の発見は build 内ループの外で生まれるため TG-C08 inbox 監視に乗らない — review 散文へ書くだけでは人間記憶依存になるため、structural 級は必ず E3 handoff として第一級成果物化する (review artifact は source_ref として紐づく)。out-of-band 修正を knowledge へ残さないと次周回で同じ調査をやり直すため、TG-C08 の完了ゲートは out-of-band 修正の Loop B 記録有無を報告する。

## 片方向 writer の逆説 (なぜ harness が task-graph を直接書かないか)

「harness が build 中に見つけた課題を直接 task-graph へ書けば外ループは不要では?」への答え (直書きで壊れる点を 1 箇所に列挙する):
1. **canonical serializer の二重化ドリフト**: 正準 writer は producer `derive-task-graph.canonicalize()` 一本。harness が別経路で書くと nodes/edges の正準順序・graph_hash 算出が二実装に分岐し、pin 照合が沈黙破綻する。
2. **structural 二段受理のバイパス**: 直書きは既存エッジ張替え/component 追加 (structural) の `--approved` 人間承認を素通りさせ、不可逆変更の安全弁を殺す。
3. **provenance chain の断裂**: TG-C07 の再 pin 認可は planner drain が accepted form へ焼く `resulting_graph_hash` に依存する。harness 直書きにはこの provenance が無く、「正当な改善」と「実行中の不正混入 (F10)」を区別できなくなる。
4. **同時書込 race**: planner `--mode update` と harness build が同一 `task-graph.json` を同時に書くと lost-update が起きる。片方向 writer (producer のみ書く・consumer は emit のみ) がこの race を構造的に排除する。

ゆえに consumer は emit と state/knowledge の書込に閉じ、graph 本体の更新は producer の次 `--mode update` 周回に一方向で委ねる。これが 2 ループ設計 (内=実行 / 外=仕様改善) を分ける根拠である。

## 利用者フィードバックの人間ブリッジ (E3 の起点辺)

`run-skill-feedback` が収集し Notion 改善要望 DB に溜めた利用者要望を E3 (改善→plan) の起点へ繋ぐ辺は、**機械の自動 read-back ではなく人間工程**として定義する。この辺を契約に明記することで、パイプラインの feedback 面を漏れなく (MECE) 被覆する。

- **意図的分離の記録**: Notion 改善要望 DB は**人間可視の優先度台帳**であり provenance chain のノードではない (chain 5 ノードに Notion を含まない)。機械が改善要望 DB を直接 query して plan 再生成を自動発火する経路は、goal-spec 制約6 (Notion は BYO config 依存で fail-open になりやすい) と片方向依存原則により**意図的に採らない**。read-back 辺の不在は設計漏れではなく設計判断である。
- **橋渡し手順 (正本)**: `feedback-to-improvement-runbook.md`。Stage 2 (トリアージ: rollup+優先度で人間が着手要望を選ぶ) → Stage 3 (`emit-improvement-handoff --source-kind manual --source-ref <notion url> --origin-request-ref <notion url>`) → Stage 4 (`/plugin-dev-plan --mode update --out-dir <PLAN_DIR> --improvement-handoff <handoff>`) → Stage 6 (対応ステータス→完了 を人手更新)。
- **起点追跡**: improvement-handoff の `provenance.origin_request {kind, ref}` に起点 Notion 要望ページを記録し、要望→改善→クローズの帰路を追跡可能にする。
- **in-place 改善との棲み分け**: `/skill-improve <capability-path>` は `run-elegant-review` を起動して対象を in-place パッチする**別系統**であり、Notion / rollup を読まず、`--mode update` の plan 再生成にも到達しない (plan-backed plugin では plan ドリフトに注意)。Notion 起点の改善は必ず本ブリッジ (source-kind=manual) を経ること。

## 二層分離 (機械層 / 意味層)

- 機械層: PB-C04 (反映 signal 重複)・PB-C05 (provenance 構造連続性)・PB-C08 (routes↔inventory parity)・PB-C11 (marker digest pin) が exit code で fail-closed 判定する。
- 意味層: PB-C10 (改善反映の意味的忠実性) が独立 context で verdict を返す。「機械緑」を反映の十分条件にせず、意味の正否は fork reviewer に委ねる。
