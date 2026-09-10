---
id: "P05-x-127-tg-c08-knowledge-on-blocked"
title: "TG-C08 の knowledge 記録を completion_gate=blocked 経路でも実行する (疎結合の逆方向)"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/scripts/"
acceptance_criterion: "未処理 discovered-task が残る状態で TG-C08 を --target-knowledge-dir 配線ありで実行したとき、completion_gate=blocked を保ちつつ出力に knowledge_record_status が現れ、knowledge へ実際に entry が追記されることを実測で示す。あわせて capability-build SKILL 本文と script header コメントのどちらを正本とするかを決め、他方を追従させる。"
objective: "capability-build SKILL は『stall/中断で build を終える場合も TG-C08 を knowledge 記録目的で必ず呼ぶ (completed 宣言の有無と独立)』『完了ゲート(制御)と knowledge 記録(ベストエフォート)を疎結合化している』と規定する。しかし record-task-graph-knowledge.py の実装では、未処理 discovered-task 検出時に :1161-1178 で early return し、knowledge 蒸留・add_entry 呼出しは :1348 以降すなわち completion_gate=ok 経路にしか存在しない。本 cycle で実測: --target-knowledge-dir plugins/guide-doc-generator/knowledge と --summary-json を正しく配線して実行したが、出力キーは completion_gate / inbox_absent / pending_discovered_tasks / needs_approval / handback_command / next_steps の 6 つのみで knowledge_record_status が存在せず、Loop A / Loop B いずれの knowledge へも 1 件も追記されていない。疎結合は片方向 (knowledge 失敗が完了を block しない) しか実装されておらず、逆方向 (完了が blocked でも knowledge は記録される) が実装されていない。結果として『stall 時こそ最も蒸留価値が高い知見 (依存詰まり・blocked 伝播起点・再試行で解消した判断)』が、まさに stall している時に限って記録されない。SKILL 側 :28 の header コメントは『ok 時: 記録サマリ』と書いており実装と一致するため、正本が SKILL 本文と script header の 2 つに割れている点も併せて裁定を要する。本 cycle の『指示された手順がその目的を果たせない経路にいる』型 (F-P05C04-01 の面 5 到達不能と同族) の実例。"
verify: "未処理 discovered-task が残る状態で TG-C08 を --target-knowledge-dir 配線ありで実行したとき、completion_gate=blocked を保ちつつ出力に knowledge_record_status が現れ、knowledge へ実際に entry が追記されることを実測で示す。あわせて capability-build SKILL 本文と script header コメントのどちらを正本とするかを決め、他方を追従させる。"
depends_on: ["P05-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-127-tg-c08-knowledge-on-blocked.md"]
consumes: []
---

# TG-C08 の knowledge 記録を completion_gate=blocked 経路でも実行する (疎結合の逆方向)

## 由来

build 実行中に `P05-C10-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: capability-build SKILL は『stall/中断で build を終える場合も TG-C08 を knowledge 記録目的で必ず呼ぶ (completed 宣言の有無と独立)』『完了ゲート(制御)と knowledge 記録(ベストエフォート)を疎結合化している』と規定する。しかし record-task-graph-knowledge.py の実装では、未処理 discovered-task 検出時に :1161-1178 で early return し、knowledge 蒸留・add_entry 呼出しは :1348 以降すなわち completion_gate=ok 経路にしか存在しない。本 cycle で実測: --target-knowledge-dir plugins/guide-doc-generator/knowledge と --summary-json を正しく配線して実行したが、出力キーは completion_gate / inbox_absent / pending_discovered_tasks / needs_approval / handback_command / next_steps の 6 つのみで knowledge_record_status が存在せず、Loop A / Loop B いずれの knowledge へも 1 件も追記されていない。疎結合は片方向 (knowledge 失敗が完了を block しない) しか実装されておらず、逆方向 (完了が blocked でも knowledge は記録される) が実装されていない。結果として『stall 時こそ最も蒸留価値が高い知見 (依存詰まり・blocked 伝播起点・再試行で解消した判断)』が、まさに stall している時に限って記録されない。SKILL 側 :28 の header コメントは『ok 時: 記録サマリ』と書いており実装と一致するため、正本が SKILL 本文と script header の 2 つに割れている点も併せて裁定を要する。本 cycle の『指示された手順がその目的を果たせない経路にいる』型 (F-P05C04-01 の面 5 到達不能と同族) の実例。

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/build-summary.json`

## 作業

`plugins/harness-creator/scripts/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-127-tg-c08-knowledge-on-blocked.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

未処理 discovered-task が残る状態で TG-C08 を --target-knowledge-dir 配線ありで実行したとき、completion_gate=blocked を保ちつつ出力に knowledge_record_status が現れ、knowledge へ実際に entry が追記されることを実測で示す。あわせて capability-build SKILL 本文と script header コメントのどちらを正本とするかを決め、他方を追従させる。
