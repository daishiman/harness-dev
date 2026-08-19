---
id: "P02-c07-img-skip-ruling-ref"
title: "C07 の fail-soft 規約から CR-IMG-SKIP-COUNT を参照させる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/command-brief-C07.json"
acceptance_criterion: "command-brief-C07.json の挿絵 skip の fail-soft 規約が improvement/visual-per-section-decision.json#decision.skipped_image_counting (CR-IMG-SKIP-COUNT) を名指しで参照し、E-IMAGE-ABSENT の緑を『各セクションに画像がある』の証明として読まない旨を裁定の複製ではなく参照として持つこと"
objective: "CR-IMG-SKIP-COUNT を improvement/visual-per-section-decision.json#decision.skipped_image_counting へ明文化したが、AC が求める『C01/C07/C12 の 3 brief がその裁定を参照している』のうち command-brief-C07.json は visual-per-section-decision.json への参照が 0 件で、E-IMAGE-ABSENT の語も持たない。C07 は skip を含む稿を完了として提示しない fail-soft 規約を持つが、それが本裁定の受け皿であることが C07 側からは辿れない。write_scope が decision ファイルのため本ノードでは直せない"
verify: "command-brief-C07.json の挿絵 skip の fail-soft 規約が improvement/visual-per-section-decision.json#decision.skipped_image_counting (CR-IMG-SKIP-COUNT) を名指しで参照し、E-IMAGE-ABSENT の緑を『各セクションに画像がある』の証明として読まない旨を裁定の複製ではなく参照として持つこと"
depends_on: ["P02-illustration-skip-ruling"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c07-img-skip-ruling-ref.md"]
consumes: []
---

# C07 の fail-soft 規約から CR-IMG-SKIP-COUNT を参照させる

## 由来

build 実行中に `P02-illustration-skip-ruling` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: CR-IMG-SKIP-COUNT を improvement/visual-per-section-decision.json#decision.skipped_image_counting へ明文化したが、AC が求める『C01/C07/C12 の 3 brief がその裁定を参照している』のうち command-brief-C07.json は visual-per-section-decision.json への参照が 0 件で、E-IMAGE-ABSENT の語も持たない。C07 は skip を含む稿を完了として提示しない fail-soft 規約を持つが、それが本裁定の受け皿であることが C07 側からは辿れない。write_scope が decision ファイルのため本ノードでは直せない

**発見時の証跡**: `plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/command-brief-C07.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c07-img-skip-ruling-ref.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

command-brief-C07.json の挿絵 skip の fail-soft 規約が improvement/visual-per-section-decision.json#decision.skipped_image_counting (CR-IMG-SKIP-COUNT) を名指しで参照し、E-IMAGE-ABSENT の緑を『各セクションに画像がある』の証明として読まない旨を裁定の複製ではなく参照として持つこと
