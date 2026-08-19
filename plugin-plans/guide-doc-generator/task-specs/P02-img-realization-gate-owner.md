---
id: "P02-img-realization-gate-owner"
title: "宣言された IMG に実体が無い状態を捕まえる機械ゲートの担い手を決める"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json"
acceptance_criterion: "レンダリング後の HTML に対する『IMG 宣言に対応する img 実体の存在』検査の担当 component が 1 つ決まり、その component の brief に検査コードと fail 条件が書かれていること。担い手を置かない裁定を採る場合は、E-IMAGE-ABSENT の緑が実体を保証しないことを利用者向け提示のどこで必ず伝えるかが明記されていること"
objective: "CR-IMG-SKIP-COUNT の known_gap: レンダリング後の HTML に対して『IMG 部品が宣言されているのに img 実体が無い』を機械判定するゲートが存在しない。E-IMAGE-ABSENT は構成データ段の宣言しか数えられず (時系列上 skip を観測できない)、実体の欠落を捕まえるのは C07 の提示規約だけで、これは人間への申告であって機械の関門ではない。C07 を経由しない経路では宣言と実体の乖離が黙って通る"
verify: "レンダリング後の HTML に対する『IMG 宣言に対応する img 実体の存在』検査の担当 component が 1 つ決まり、その component の brief に検査コードと fail 条件が書かれていること。担い手を置かない裁定を採る場合は、E-IMAGE-ABSENT の緑が実体を保証しないことを利用者向け提示のどこで必ず伝えるかが明記されていること"
depends_on: ["P02-illustration-skip-ruling"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-img-realization-gate-owner.md"]
consumes: []
---

# 宣言された IMG に実体が無い状態を捕まえる機械ゲートの担い手を決める

## 由来

build 実行中に `P02-illustration-skip-ruling` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: CR-IMG-SKIP-COUNT の known_gap: レンダリング後の HTML に対して『IMG 部品が宣言されているのに img 実体が無い』を機械判定するゲートが存在しない。E-IMAGE-ABSENT は構成データ段の宣言しか数えられず (時系列上 skip を観測できない)、実体の欠落を捕まえるのは C07 の提示規約だけで、これは人間への申告であって機械の関門ではない。C07 を経由しない経路では宣言と実体の乖離が黙って通る

**発見時の証跡**: `plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json`

## 作業

`plugin-plans/guide-doc-generator/improvement/visual-per-section-decision.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-img-realization-gate-owner.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

レンダリング後の HTML に対する『IMG 宣言に対応する img 実体の存在』検査の担当 component が 1 つ決まり、その component の brief に検査コードと fail 条件が書かれていること。担い手を置かない裁定を採る場合は、E-IMAGE-ABSENT の緑が実体を保証しないことを利用者向け提示のどこで必ず伝えるかが明記されていること
