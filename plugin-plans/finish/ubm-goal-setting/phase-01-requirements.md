---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
本 phase は greenfield な新規要件抽出でなく、既存資産の移植 (port) を前提とした要件の棚卸しである。「北原さん式ゴールセッティングの目標設定・振り返り対話とナレッジ差分同期を1 pluginへ移植する」構想を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`ubm-goal-setting` を固定し、移植元 (`~/dev/dev/ObsidianMemo/.claude/` 配下) が読み取り専用ソースでありフォーク・複製禁止であるという制約を `goal-spec.json` の constraints へ明示する。

## 背景
UBM (北原さん式ゴールセッティング) は現状 `~/dev/dev/ObsidianMemo/.claude/` 配下で量産規律の外側で個別資産として運用されている (slash-command 2 本・511 行の中核 skill・sub-agent 11 本・shell script 3 本・reference 8 本・asset 5 本・knowledge JSON 群)。単語置換ではなく目的ドリブンで要件化しないと後続の component 分解 (capability A=目標設定対話 / capability B=ナレッジ同期) が破綻するため、全 13 フェーズが参照する不変の goal-spec を最初に固定する必要がある。同一構想は常に同一 `PLAN_DIR` へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- プラグイン構想 1 件 (「北原さん式ゴールセッティングの目標設定・振り返り対話とナレッジ差分同期を1 pluginへ移植する」) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- 移植元 (`~/dev/dev/ObsidianMemo/.claude/` 配下) が読み取り専用ソースとして参照可能であり、フォーク・複製禁止の制約を共有している。

## ドメイン知識
- 移植 (port) ≠ 新規要件抽出: 既存資産の実棚卸しが要件化の中心作業であり、動作を発明しない。
- 移植元の確定: `.claude/commands/ai/ubm-goal-setting.md` / `.claude/commands/ai/ubm-knowledge-sync.md` が参照する `.claude/skills/ubm-goal-setting/` を移植源とする (同階層に併存する `skills/goal-setting/` は別資産であり移植対象外)。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- その他の plan 全体用語 (component_kind/data-tier 3 層等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist/constraints/handoff_targets/open_questions)。
- target_plugin_slug と plan_dir の確定値。

## スコープ外
- component 分解・5 種 component_kind への写像 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点 (checklist C1-C7) が purpose 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`ubm-goal-setting`) で確定し以降のフェーズがそれを参照できる。
- [ ] 移植元資産 (slash-command 2 本・中核 skill・sub-agent 11 本・shell script 3 本・reference 8 本・asset 5 本・knowledge JSON 群) の実棚卸しと、抽出/参照のみで移植しフォーク・複製しないという制約が明文化されている。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- 移植元: `.claude/commands/ai/ubm-goal-setting.md` / `.claude/commands/ai/ubm-knowledge-sync.md` / `.claude/skills/ubm-goal-setting/`。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
