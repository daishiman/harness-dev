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
既存 plugin `ubm-goal-setting` (capability A=`run-ubm-goal-setting` / capability B=`run-ubm-knowledge-sync`) への改善構想 (YouTube 3経路取込・harness-creator 仕様適合・ナレッジ依存グラフ・harness-creator 成果物アクセス方式) を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` (artifact_class=existing-plugin-update) を確定させる。

## 背景
本計画は新規プラグインの構想でなく、稼働中の既存 2 capability を持つ plugin の改善計画である。新規構築とは異なり、要件化の段階から既存契約 (skill 名称/入出力契約/knowledge スキーマ) の非後退を制約として織り込まないと、後続の component 分解が既存動作を壊しうる。target_plugin_slug=`ubm-goal-setting` を既存実体に固定し、goal-spec.checklist C1-C11 を全フェーズ不変のアンカーとする。

## 前提条件
- 既存 plugin `plugins/ubm-goal-setting/` の実体 (2 skill / 5 agent / 2 command / knowledge/*.json) が Read で実査済み。
- `goal-spec.json` が purpose/background/goal/checklist (C1-C11)/constraints/open_questions/handoff_targets を持つ形で既に確定済み (本フェーズでの新規生成は不要・引用のみ)。
- 既存 2 capability の workflow-manifest.json / SKILL.md の契約 (phase 構成・gate・resourceIds) を後続フェーズが参照できる。

## ドメイン知識
- artifact_class=existing-plugin-update: 新規プラグイン生成でなく、既存プラグインへの additive 拡張であることを示す goal-spec の分類 (非後退制約の起点)。
- REQ1a/1b/1c: YouTube ナレッジ取込の 3 経路 (URL単発 / 北原孝彦のコンサルティングチャンネル全量バックフィル / 新着動画継続差分同期)。REQ2=harness-creator 仕様適合ギャップ解消、REQ3=ナレッジ依存グラフ、REQ4=harness-creator 成果物アクセス方式選定。
- source制約: 2アカウントを扱えるregistryとし、提示済み『北原孝彦のコンサルティング』をrequired-primary、未提示の第2sourceをpending-identificationにする。全量PASSはrequired-primaryのcontent coverage 100%であり、取得不能を分母から落とさない。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1-C11/constraints/open_questions/handoff_targets、既存・確定済み)。
- target_plugin_slug=`ubm-goal-setting` と artifact_class=existing-plugin-update の確定値。

## スコープ外
- component 分解・依存 DAG 設計 (P02 へ委譲)。
- 特定YouTube provider/scheduler製品の確定。provider-neutral I/O・fallback・quota/auth・cadence契約はP02で確定し、製品名だけlate-bindする。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、checklist C1-C11 が全て purpose/REQ 語彙から導出されている。
- [ ] target_plugin_slug=`ubm-goal-setting`・artifact_class=existing-plugin-update が確定し、以降のフェーズがそれを参照できる。
- [ ] 既存 capability A/B の契約 (skill 名称・出力契約・knowledge スキーマ) が非後退制約として constraints に明記されている (goal-spec C11)。

### 受入例
required-primary URL、第2source pending、全量/自動sync/graph/harness artifact要件がgoal-spec C1-C11へ現れる。

### 事前解決済み判断
第2source未提示でもprimary取込を停止しない。特定providerだけをlate-bindする。

## 参照情報
- `goal-spec.json` (checklist C1-C11・constraints・open_questions)。
- 既存 `plugins/ubm-goal-setting/skills/run-ubm-goal-setting/` / `run-ubm-knowledge-sync/` の workflow-manifest.json・SKILL.md。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
