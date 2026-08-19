---
id: "P05-C23-01-section-key-surface-tests"
title: "resolve-handout-preset のテストを image_role 込みのキー面へ追従させる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/tests/resolve-handout-preset.py/"
acceptance_criterion: "pytest plugins/guide-doc-generator/tests/resolve-handout-preset.py/test_r20_invariants.py が exit0。かつ (a) キー面の期待値をテストへ書き写さず script の SECTION_ENTRY_KEYS から実測して突き合わせる、(b) image_role 欠落が E-PRESET-IMAGE-ROLE-MISSING で、列挙外が E-PRESET-IMAGE-ROLE-UNKNOWN で落ちることの回帰が各 1 本ある、(c) 既存の dir_token 2 件の赤 (DT-1 裁定待ち) を緑化しない"
objective: "P05-C23-01 で section_order[] のキー面へ image_role を必須追加し、E-PRESET-IMAGE-ROLE-MISSING / E-PRESET-IMAGE-ROLE-UNKNOWN を fail-closed で新設した。test_r20_invariants.py::PresetKeySurfaceTest::test_section_entry_keys_are_fixed は 5 キーの固定集合をテスト側へ書き写しているため落ちる。write_scope が scripts/resolve-handout-preset.py に閉じるため本 node では直せない。なお同 test file が期待値を書き写している構造そのものが 2 つ目の正本になっており、script 側 SECTION_ENTRY_KEYS からの実測へ寄せるのが望ましい"
verify: "pytest plugins/guide-doc-generator/tests/resolve-handout-preset.py/test_r20_invariants.py が exit0。かつ (a) キー面の期待値をテストへ書き写さず script の SECTION_ENTRY_KEYS から実測して突き合わせる、(b) image_role 欠落が E-PRESET-IMAGE-ROLE-MISSING で、列挙外が E-PRESET-IMAGE-ROLE-UNKNOWN で落ちることの回帰が各 1 本ある、(c) 既存の dir_token 2 件の赤 (DT-1 裁定待ち) を緑化しない"
depends_on: ["P05-C23-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-C23-01-section-key-surface-tests.md"]
consumes: []
---

# resolve-handout-preset のテストを image_role 込みのキー面へ追従させる

## 由来

build 実行中に `P05-C23-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P05-C23-01 で section_order[] のキー面へ image_role を必須追加し、E-PRESET-IMAGE-ROLE-MISSING / E-PRESET-IMAGE-ROLE-UNKNOWN を fail-closed で新設した。test_r20_invariants.py::PresetKeySurfaceTest::test_section_entry_keys_are_fixed は 5 キーの固定集合をテスト側へ書き写しているため落ちる。write_scope が scripts/resolve-handout-preset.py に閉じるため本 node では直せない。なお同 test file が期待値を書き写している構造そのものが 2 つ目の正本になっており、script 側 SECTION_ENTRY_KEYS からの実測へ寄せるのが望ましい

**発見時の証跡**: `plugins/guide-doc-generator/scripts/resolve-handout-preset.py`

## 作業

`plugins/guide-doc-generator/tests/resolve-handout-preset.py/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-C23-01-section-key-surface-tests.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

pytest plugins/guide-doc-generator/tests/resolve-handout-preset.py/test_r20_invariants.py が exit0。かつ (a) キー面の期待値をテストへ書き写さず script の SECTION_ENTRY_KEYS から実測して突き合わせる、(b) image_role 欠落が E-PRESET-IMAGE-ROLE-MISSING で、列挙外が E-PRESET-IMAGE-ROLE-UNKNOWN で落ちることの回帰が各 1 本ある、(c) 既存の dir_token 2 件の赤 (DT-1 裁定待ち) を緑化しない
