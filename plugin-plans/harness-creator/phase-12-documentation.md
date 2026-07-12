---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
task-graph consumer 機構 (並列 dispatch/state write-back/成果物注入/discovered-task emit/進捗集計/完了前 discovered-task gate/knowledge 化) の利用者向けドキュメント (中学生説明 Part1 概念 + Part2 技術) を確定し、反映先と install 手順への影響有無を明示する。

## 背景
本サイクルは既存プラグインの内部拡張であり、entry_points (skills/agents/commands) の追加・削除を伴わない (C06 は既存 capability-build の allowed-tools 拡張のみ) ため、install 手順自体への変更はない。ドキュメントは task-graph 消費という新概念の説明に限定される。

## 前提条件
- P11 の evidence 設計が完了している。

## ドメイン知識
- Part1 (概念): 「/capability-build は今まで作業手順書 (route) を 1 列に並べて順番に処理していたが、今回、地図 (task-graph) を読んで『同時に進めても大丈夫な作業』を見つけ、並行して複数の作業員 (SubAgent) へ同時に頼めるようになった。ただし同じファイルを触る作業同士は衝突するので、その場合は今まで通り順番を守る」という説明。
- Part2 (技術): task-graph.json (producer SSOT・読み取り専用) + task-state.json (consumer SSOT・単一 writer) の分離、ready-set 計算の subprocess 委譲、状態遷移の禁止方向 (done からの後退禁止)、produces→consumes 注入の fail-closed 拒否、discovered-task の E4 境界 (E3 と別スキーマ・別受理経路)、build 成果物の周回衝突排除 (`resolve_build_dir(target_plugin_slug, cycle_id)` [C02] が handoff top-level の `cycle_id` フィールド [producer 側追加・additive・null=flat] の値をそのまま消費するのみで plan_dir のパス解析は行わない・cycle_id フィールド不在/null の既存 handoff は既存 flat パスのまま後方互換)、冪等再開・実行排他 (C10・build lease/孤児 lease 回収/graph_hash pin 検証を C07=manage-build-lease.py が担う)、実行イベントログ (C11・task-events.jsonl・writer=C02 単一)、実行時停滞検出 (C12・C05 拡張の detect_stall())、完了前 discovered-task gate と Loop A/Loop B knowledge 化 (C13・C08=record-task-graph-knowledge.py)。
- 反映先: 本サイクルの変更点は既存 `references/pipeline-boundary-contract.md` への追記 (C7) に集約する。新規 reference ファイルは作らない (producer 側計画が既に `task-graph-contract.md` を新設予定であり、consumer 側で同種の schema/アルゴリズム説明を重複して持たないため。既存ファイルへの追記は「境界」節に限定する)。
- install 手順: entry_points 変更なしのため既存 README/setup 手順は不変。

## 成果物
- `references/pipeline-boundary-contract.md` への追記方針 (新セクション「task-graph 境界 (E4 含む)」・E1/E2/E3 と同じ表形式)。表の行構成: producer/consumer 境界・task-state.json 単一 writer・discovered-task (E4) 境界・build 成果物の周回衝突排除 (`resolve_build_dir(target_plugin_slug, cycle_id)` が handoff.cycle_id フィールドのみを消費し plan_dir のパス解析は行わない)・実行時契約 3 点の所有区分 (schema=producer C16/実行=consumer C01・C07・C02・C05)・C13 completion/knowledge gate (C08 が未処理 discovered-task を block し、Loop A/Loop B へ bounded summary を記録) の 6 行。

## スコープ外
- README/setup 手順の実編集 (entry_points 変更を伴わないため本 plan では不要)。
- producer 側 `task-graph-contract.md` の新設・編集 (producer 側 plan の責務)。

## 完了チェックリスト
- [ ] Part1/Part2 の 2 タスク雛形が task-graph consumer 機構に即して具体化されている。
- [ ] 反映先 (pipeline-boundary-contract.md への追記であり新規 reference ファイルではないこと) が明示されている。
- [ ] install 手順への影響有無 (無し) が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: Part1 の説明文が「地図」「作業員」という具体的比喩で並列 dispatch の役割を説明し、Part2 が task-graph.json/task-state.json の分離・ready-set 計算委譲・状態遷移禁止方向・produces/consumes 注入・E4 境界・周回衝突排除・冪等再開実行排他 (C10)・実行イベントログ (C11)・実行時停滞検出 (C12)・完了前 discovered-task gate と knowledge 化 (C13) の 10 点を具体的に列挙する。
- 満たさない例: 「ドキュメントを更新する」とだけ記され、対象ファイルや説明内容が未確定である。

### 事前解決済み判断
- 分岐点: consumer 側の説明を新規 reference ファイルへ分離するか、既存 `pipeline-boundary-contract.md` の追記に留めるか → 判断: 追記に留める (C7 の goal-spec 要求が「pipeline-boundary-contract.md へ追記する」と明示しており、かつ producer 側が別途 task-graph 自体の schema/アルゴリズム説明を新設 reference で担うため、consumer 側で重複した説明ファイルを持たない)。

## 参照情報
- P11 (evidence)。
- `plugins/harness-creator/references/pipeline-boundary-contract.md`。
- 後続 P13 (release)。
