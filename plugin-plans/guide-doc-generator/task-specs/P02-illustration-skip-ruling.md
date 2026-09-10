---
id: "P02-illustration-skip-ruling"
title: "挿絵 skipped と per-section 必須要件の関係を裁定する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json"
acceptance_criterion: "status=skipped の IMG が E-IMAGE-ABSENT の充足に数えられるか否かが 1 箇所で明文化され、C01/C07/C12 の 3 brief がその裁定を参照していること"
objective: "挿絵取得失敗時の fail-soft (status=skipped) と R25/REQ-3『図解と画像を毎セクション必須』が衝突し、skipped を含む稿を完了と呼べるかが未裁定"
verify: "status=skipped の IMG が E-IMAGE-ABSENT の充足に数えられるか否かが 1 箇所で明文化され、C01/C07/C12 の 3 brief がその裁定を参照していること"
depends_on: ["P02-C07-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-illustration-skip-ruling.md"]
consumes: []
---

# 挿絵 skipped と per-section 必須要件の関係を裁定する

## 由来

build 実行中に `P02-C07-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 挿絵取得失敗時の fail-soft (status=skipped) と R25/REQ-3『図解と画像を毎セクション必須』が衝突し、skipped を含む稿を完了と呼べるかが未裁定

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C07-01.json`

## 作業

`plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-illustration-skip-ruling.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

status=skipped の IMG が E-IMAGE-ABSENT の充足に数えられるか否かが 1 箇所で明文化され、C01/C07/C12 の 3 brief がその裁定を参照していること
