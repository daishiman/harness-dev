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
「タスク台帳を Notion DB へ冪等同期する」という構想を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`notion-task-sync` を固定し、Notion を中核とする外部依存 (MCP/API・冪等性・破壊防止) の制約を開示する。

## 背景
このプラグインは手作業によるタスク台帳→Notion 転記を自動化する構想から出発する。単語置換ではなく目的ドリブンで要件化しないと後続の component 分解が破綻するため、全 12 フェーズが参照する不変の goal-spec を最初に固定する必要がある。同一構想は常に同一 `PLAN_DIR` へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- 冪等同期 = 同一台帳で二回実行しても二回目の追加/更新が 0 件になる性質 (本 plan の purpose 中核語)。
- タスク台帳がデータの正本で、Notion DB はその写像 (逆方向の書き戻しは扱わない)。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- その他の plan 全体用語 (component_kind/冪等キー等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist/constraints/handoff_targets)。
- target_plugin_slug と plan_dir の確定値。

## スコープ外
- component 分解・DB スキーマ設計 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`notion-task-sync`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
