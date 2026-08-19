---
id: "P05-x-03-dir-name-format"
title: "config/handout-output.json へ dir_name_format を追加する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/config/handout-output.json"
acceptance_criterion: "config/handout-output.json が dir_name_format キーを持ち、値が {date} と {slug} の 2 プレースホルダのみを含む文字列 (現行裁定値 '{date}_{slug}') であること。script 側ソースに同等の書式リテラルが 0 件であること"
objective: "config/handout-output.json に dir_name_format キーが存在しない (dispatcher 実測: トップキーは _meta / version / default_out_dir / size_limits の 4 件のみ)。inventory C19 purpose・improvement/output-naming-decision.json・修正後の script-brief-C19.json のいずれもが『script へ書式を焼かず config から読む』と定めており、このまま build すると初回実行が exit2 になる。加えて出荷済みの route-handout-output.py:433 と validate-handout-config.py:334 の derive_slug が R25 前の旧書式のままで、実出力が REQ-6 の 4 変更点すべてに違反している"
verify: "config/handout-output.json が dir_name_format キーを持ち、値が {date} と {slug} の 2 プレースホルダのみを含む文字列 (現行裁定値 '{date}_{slug}') であること。script 側ソースに同等の書式リテラルが 0 件であること"
depends_on: ["P02-C19-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-03-dir-name-format.md"]
consumes: []
---

# config/handout-output.json へ dir_name_format を追加する

## 由来

build 実行中に `P02-C19-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: config/handout-output.json に dir_name_format キーが存在しない (dispatcher 実測: トップキーは _meta / version / default_out_dir / size_limits の 4 件のみ)。inventory C19 purpose・improvement/output-naming-decision.json・修正後の script-brief-C19.json のいずれもが『script へ書式を焼かず config から読む』と定めており、このまま build すると初回実行が exit2 になる。加えて出荷済みの route-handout-output.py:433 と validate-handout-config.py:334 の derive_slug が R25 前の旧書式のままで、実出力が REQ-6 の 4 変更点すべてに違反している

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C19-01.json`

## 作業

`plugins/guide-doc-generator/config/handout-output.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-03-dir-name-format.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

config/handout-output.json が dir_name_format キーを持ち、値が {date} と {slug} の 2 プレースホルダのみを含む文字列 (現行裁定値 '{date}_{slug}') であること。script 側ソースに同等の書式リテラルが 0 件であること
