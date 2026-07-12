---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
既存 presentation-slide-generator(v8.4.2)の全機能を xl-skills plugin へ抜け漏れなく移植し、共通コア + output_mode=slide/report の 2 モード + report 新規機能を持つビジュアル生成ハーネスを目的ドリブンに要件化して、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`slide-report-generator` を固定する。

## 背景
本プラグインは、単一 SKILL の巨大ハーネス(13 sub-agent / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 チェーン / 30種思考法評価 / A4印刷 / GASデプロイ)を plugin 化する構想から出発する。機能削減・平均回帰・オミットを禁じ、既存全資産が component か plugin-level surface に必ず対応することを要件の第一に据える。同一構想は常に同一 `PLAN_DIR` へ解決され(再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- 既存 presentation-slide-generator の実ソース(SKILL.md / agents / references / scripts / schemas / assets)が参照可能である。
- 移植元 root が存在する、または plan 同梱 `vendor-digest-manifest.json` (v8.4.2 byte 正本) で照合可能である(移植元不在環境では manifest 照合を代替とする)。
- 汎用の `run-goal-elicit`(harness-creator)で purpose/background/goal/checklist を抽出できる(再実装しない)。
- このフェーズは特定 component へ紐づかない(責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- output_mode = slide | report の 2 分岐。意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみモード別(purpose の中核語)。
- vendored Node engine = Node/CJS 製レンダリング/画像/印刷/検証エンジンを byte 維持で携行し Python 化しない不変原則(既存資産の毀損回避)。
- 抜け漏れ厳禁 = source-inventory §5 被覆チェックリストで既存全資産が component or surface へ対応することを保証する。
- その他の plan 全体用語(component_kind / 5 種 buildable / 2 軸直交等)は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json`(purpose/background/goal/checklist/constraints/handoff_targets)。
- target_plugin_slug=`slide-report-generator` と plan_dir=`plugin-plans/slide-report-generator` の確定値。
- `source-inventory.md`(既存全資産 → component/surface の R2 分解正本・被覆チェックリスト)。

## スコープ外
- component 分解・schema 設計(P02 へ委譲)。
- ヒアリング機構の再実装(`run-goal-elicit` を引用するのみ)。
- 実装・build(P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている(要件 C1-C8 の被覆が確認できる)。
- [ ] target_plugin_slug が ASCII kebab(`slide-report-generator`)で確定し以降のフェーズが参照できる。
- [ ] 既存全資産(13 agents / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 / 30種思考法 / A4印刷 / GAS)が移植対象として goal-spec に明記されている。
- [ ] `check-plugin-goal-spec.py` が exit0(R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `source-inventory.md`(R2 分解正本・被覆チェックリスト §5)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02(この goal-spec を component 分解の入力とする)。
