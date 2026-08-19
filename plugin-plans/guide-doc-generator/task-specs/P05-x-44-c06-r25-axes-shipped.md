---
id: "P05-x-44-c06-r25-axes-shipped"
title: "R25 意味軸 4 種を agents/handout-readability-reviewer.md へ反映する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/agents/"
acceptance_criterion: "出荷 md が 10 軸を持ち AC8-AC10 が緑になる"
objective: "P03-x-02 で C06 brief の axis を 6 種から 10 種へ拡張し opening-order / visual-fit / card-granularity / nav-scannability を新設、procedure 14->18・AC 7->10 とした。出荷 md は 6 軸のままで、R25 の 9 要求 (冒頭のゴール先頭・図解と本文の噛み合い・カード粒度・nav ラベルの拾いやすさ) を判定する担当が出荷物には依然不在。同ファイルの dangling references 3 箇所と :155 の C18 誤帰属 (P05-x-37) と同時に直すのが効率的"
verify: "出荷 md が 10 軸を持ち AC8-AC10 が緑になる"
depends_on: ["P03-x-02"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-44-c06-r25-axes-shipped.md"]
consumes: []
---

# R25 意味軸 4 種を agents/handout-readability-reviewer.md へ反映する

## 由来

build 実行中に `P03-x-02` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P03-x-02 で C06 brief の axis を 6 種から 10 種へ拡張し opening-order / visual-fit / card-granularity / nav-scannability を新設、procedure 14->18・AC 7->10 とした。出荷 md は 6 軸のままで、R25 の 9 要求 (冒頭のゴール先頭・図解と本文の噛み合い・カード粒度・nav ラベルの拾いやすさ) を判定する担当が出荷物には依然不在。同ファイルの dangling references 3 箇所と :155 の C18 誤帰属 (P05-x-37) と同時に直すのが効率的

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/`

## 作業

`plugins/guide-doc-generator/agents/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-44-c06-r25-axes-shipped.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

出荷 md が 10 軸を持ち AC8-AC10 が緑になる
