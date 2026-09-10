---
id: "P05-x-79-required-config-keys-test-net-narrower-than-impl"
title: "必須フィールドのテスト網を実装の定数から導出する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/tests/verify-handout-narrative.py/"
acceptance_criterion: "TestArgvAndExit2 の必須フィールド系テストが REQUIRED_CONFIG_KEYS から導出され、定数へ要素を足すとテストが自動的に増えること。手書き列挙が残っていないこと"
objective: "test_cli_contract.py の TestArgvAndExit2 は必須フィールド 4 件 (purpose / background / goal / sections) を個別にテストするが、実装の REQUIRED_CONFIG_KEYS は 5 要素で presentation_order の兄弟テストだけが無い。テストが実装の定数から導出されず手書き列挙のため、必須フィールドが増えても網が追随しない。orange が検出"
verify: "TestArgvAndExit2 の必須フィールド系テストが REQUIRED_CONFIG_KEYS から導出され、定数へ要素を足すとテストが自動的に増えること。手書き列挙が残っていないこと"
depends_on: ["P04-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-79-required-config-keys-test-net-narrower-than-impl.md"]
consumes: []
---

# 必須フィールドのテスト網を実装の定数から導出する

## 由来

build 実行中に `P04-C22-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: test_cli_contract.py の TestArgvAndExit2 は必須フィールド 4 件 (purpose / background / goal / sections) を個別にテストするが、実装の REQUIRED_CONFIG_KEYS は 5 要素で presentation_order の兄弟テストだけが無い。テストが実装の定数から導出されず手書き列挙のため、必須フィールドが増えても網が追随しない。orange が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/tests/verify-handout-narrative.py/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-79-required-config-keys-test-net-narrower-than-impl.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

TestArgvAndExit2 の必須フィールド系テストが REQUIRED_CONFIG_KEYS から導出され、定数へ要素を足すとテストが自動的に増えること。手書き列挙が残っていないこと
