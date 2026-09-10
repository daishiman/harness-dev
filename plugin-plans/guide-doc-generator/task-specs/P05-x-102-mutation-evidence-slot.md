---
id: "P05-x-102-mutation-evidence-slot"
title: "route-build-report schema に変異証跡 (mutation evidence) の格納枠を新設する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/skills/run-build-skill/schemas/route-build-report.schema.json"
acceptance_criterion: "route-build-report.schema.json に変異証跡を構造化して置ける枠 (例: mutation_evidence[] で command / exit_code / passed / failed / mutation (何をどう壊したか) / baseline_matches (復元後の baseline 一致) を保持) が存在し、status=success の report で exit_code!=0 の item を持てること。validate-route-build-reports.py がその枠を検証し、かつ従来どおり test_evidence[] へは非ゼロ exit を置けないままであること。eval-log/guide-doc-generator/build/route-C10.json の evidence[] にある変異証跡 A/B/C が数値を落とさず新枠へ移せること"
objective: "route-build-report schema に変異注入の赤を格納する場所が無い。test_evidence[] は additionalProperties=false かつ『成果物がゲートを通ること』だけを表す形で、status=success の report に exit_code!=0 / failed>0 の item を置くと validator が矛盾として弾く。ところが『検査が空ゲートでないこと』を示せるのは変異注入の赤だけで、緑の記録は 1 件もそれを示せない (実測: C10 で config から hook_scan_budget を削除すると exit 1 / failures 104 / errors 2、無変異の複製では exit 0 / 203 OK)。結果、成功証跡と変異証跡が同じ配列を共有できず、空ゲートでないことの証明が report の一級市民になっていない。C10 では已むを得ず evidence[] へ自由文字列として退避したが、これは構造化されず機械検証もできない。C10 固有ではなく本 cycle の全 route に効く。"
verify: "route-build-report.schema.json に変異証跡を構造化して置ける枠 (例: mutation_evidence[] で command / exit_code / passed / failed / mutation (何をどう壊したか) / baseline_matches (復元後の baseline 一致) を保持) が存在し、status=success の report で exit_code!=0 の item を持てること。validate-route-build-reports.py がその枠を検証し、かつ従来どおり test_evidence[] へは非ゼロ exit を置けないままであること。eval-log/guide-doc-generator/build/route-C10.json の evidence[] にある変異証跡 A/B/C が数値を落とさず新枠へ移せること"
depends_on: ["P05-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-102-mutation-evidence-slot.md"]
consumes: []
---

# route-build-report schema に変異証跡 (mutation evidence) の格納枠を新設する

## 由来

build 実行中に `P05-C10-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: route-build-report schema に変異注入の赤を格納する場所が無い。test_evidence[] は additionalProperties=false かつ『成果物がゲートを通ること』だけを表す形で、status=success の report に exit_code!=0 / failed>0 の item を置くと validator が矛盾として弾く。ところが『検査が空ゲートでないこと』を示せるのは変異注入の赤だけで、緑の記録は 1 件もそれを示せない (実測: C10 で config から hook_scan_budget を削除すると exit 1 / failures 104 / errors 2、無変異の複製では exit 0 / 203 OK)。結果、成功証跡と変異証跡が同じ配列を共有できず、空ゲートでないことの証明が report の一級市民になっていない。C10 では已むを得ず evidence[] へ自由文字列として退避したが、これは構造化されず機械検証もできない。C10 固有ではなく本 cycle の全 route に効く。

**発見時の証跡**: `eval-log/guide-doc-generator/build/route-C10.json`

## 作業

`plugins/harness-creator/skills/run-build-skill/schemas/route-build-report.schema.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-102-mutation-evidence-slot.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

route-build-report.schema.json に変異証跡を構造化して置ける枠 (例: mutation_evidence[] で command / exit_code / passed / failed / mutation (何をどう壊したか) / baseline_matches (復元後の baseline 一致) を保持) が存在し、status=success の report で exit_code!=0 の item を持てること。validate-route-build-reports.py がその枠を検証し、かつ従来どおり test_evidence[] へは非ゼロ exit を置けないままであること。eval-log/guide-doc-generator/build/route-C10.json の evidence[] にある変異証跡 A/B/C が数値を落とさず新枠へ移せること
