---
id: "P05-C12-01-visual-density-tests"
title: "test_visual_density.py を節単位ゲート契約 (W-DIAGRAM-FEW / E-IMAGE-ABSENT / level 正本) へ追従させる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/tests/validate-handout-config.py/test_visual_density.py"
acceptance_criterion: "pytest plugins/guide-doc-generator/tests/validate-handout-config.py/test_visual_density.py が exit0。かつ (a) W-DIAGRAM-FEW / E-IMAGE-ABSENT が main セクション単位の pointer (/sections/<i>/parts) で assert されている、(b) 総量比キー min_diagrams_per_main_sections への参照が 0 件、(c) level:'error' 宣言により W-DIAGRAM-FEW 単独で exit=1 になることを --strict 無しで assert する回帰が 1 本ある"
objective: "P05-C12-01 で W-DIAGRAM-FEW の判定単位を資料全体の総量比から main セクション単位へ移し、E-IMAGE-ABSENT を新設し、重大度を config/handout-visual-policy.json の level:'error' 正本へ従わせた。既存 test_visual_density.py は旧契約 (pointer=/diagrams・総量比 value/floor・W- 接頭辞は必ず warning) を assert しており 7 件 fail する。うち TestDiagramFew::test_ratio_comes_from_canon_not_script は正本から削除済みのキー min_diagrams_per_main_sections を参照しているため期待値の付け替えでは足りず、テスト意図そのものの再設計が要る。fixture 側も全 main セクションへ IMG を持たせる必要がある (E-IMAGE-ABSENT の発火は仕様どおり)。本 node の write_scope は scripts/validate-handout-config.py に閉じるため修正できない"
verify: "pytest plugins/guide-doc-generator/tests/validate-handout-config.py/test_visual_density.py が exit0。かつ (a) W-DIAGRAM-FEW / E-IMAGE-ABSENT が main セクション単位の pointer (/sections/<i>/parts) で assert されている、(b) 総量比キー min_diagrams_per_main_sections への参照が 0 件、(c) level:'error' 宣言により W-DIAGRAM-FEW 単独で exit=1 になることを --strict 無しで assert する回帰が 1 本ある"
depends_on: ["P05-C12-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-C12-01-visual-density-tests.md"]
consumes: []
---

# test_visual_density.py を節単位ゲート契約 (W-DIAGRAM-FEW / E-IMAGE-ABSENT / level 正本) へ追従させる

## 由来

build 実行中に `P05-C12-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P05-C12-01 で W-DIAGRAM-FEW の判定単位を資料全体の総量比から main セクション単位へ移し、E-IMAGE-ABSENT を新設し、重大度を config/handout-visual-policy.json の level:'error' 正本へ従わせた。既存 test_visual_density.py は旧契約 (pointer=/diagrams・総量比 value/floor・W- 接頭辞は必ず warning) を assert しており 7 件 fail する。うち TestDiagramFew::test_ratio_comes_from_canon_not_script は正本から削除済みのキー min_diagrams_per_main_sections を参照しているため期待値の付け替えでは足りず、テスト意図そのものの再設計が要る。fixture 側も全 main セクションへ IMG を持たせる必要がある (E-IMAGE-ABSENT の発火は仕様どおり)。本 node の write_scope は scripts/validate-handout-config.py に閉じるため修正できない

**発見時の証跡**: `plugins/guide-doc-generator/scripts/validate-handout-config.py`

## 作業

`plugins/guide-doc-generator/tests/validate-handout-config.py/test_visual_density.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-C12-01-visual-density-tests.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

pytest plugins/guide-doc-generator/tests/validate-handout-config.py/test_visual_density.py が exit0。かつ (a) W-DIAGRAM-FEW / E-IMAGE-ABSENT が main セクション単位の pointer (/sections/<i>/parts) で assert されている、(b) 総量比キー min_diagrams_per_main_sections への参照が 0 件、(c) level:'error' 宣言により W-DIAGRAM-FEW 単独で exit=1 になることを --strict 無しで assert する回帰が 1 本ある
