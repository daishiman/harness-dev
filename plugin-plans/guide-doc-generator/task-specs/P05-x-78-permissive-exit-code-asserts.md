---
id: "P05-x-78-permissive-exit-code-asserts"
title: "assertIn(rc, (1,2)) 型の許容 assert を横断確認して契約を固定する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/tests/"
acceptance_criterion: "テスト名が特定の exit code を主張しているのにその code を固定していない assert が 0 件であること。exit code の主張は assertEqual で単一値へ固定されていること"
objective: "orange が P04-C22-01 で test_presentation_order_missing_from_config_is_exit2 が assertIn(res.returncode, (1, 2)) で exit 1 も通していたのを発見した (本ノードで assertEqual(2, rc) へ修正済み)。名前が is_exit2 なのに exit 1 を許す形はテストが緑でも 1=品質FAIL / 2=検査不能 という契約を固定していない。1 件見つかった以上、同型を tests/ 全体で探す価値がある"
verify: "テスト名が特定の exit code を主張しているのにその code を固定していない assert が 0 件であること。exit code の主張は assertEqual で単一値へ固定されていること"
depends_on: ["P04-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-78-permissive-exit-code-asserts.md"]
consumes: []
---

# assertIn(rc, (1,2)) 型の許容 assert を横断確認して契約を固定する

## 由来

build 実行中に `P04-C22-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: orange が P04-C22-01 で test_presentation_order_missing_from_config_is_exit2 が assertIn(res.returncode, (1, 2)) で exit 1 も通していたのを発見した (本ノードで assertEqual(2, rc) へ修正済み)。名前が is_exit2 なのに exit 1 を許す形はテストが緑でも 1=品質FAIL / 2=検査不能 という契約を固定していない。1 件見つかった以上、同型を tests/ 全体で探す価値がある

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/tests/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-78-permissive-exit-code-asserts.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

テスト名が特定の exit code を主張しているのにその code を固定していない assert が 0 件であること。exit code の主張は assertEqual で単一値へ固定されていること
