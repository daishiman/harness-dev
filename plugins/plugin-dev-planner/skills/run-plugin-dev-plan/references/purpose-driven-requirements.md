---
name: purpose-driven-requirements
description: 固定手順でなく目的ドリブンで動かすための要件定義(goal-spec/ゴールシーク/中間成果物アンカー/収束閾値/feedbackループ/TDD対応)を読む。R1 と横断パラダイムの正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 目的ドリブン駆動開発の要件定義 (§13)

> 本スキルは固定手順でなく**目的ドリブン**で動く。以下を P1 + 横断パラダイムとして要件化する。正本の数値/形式は harness-creator-spec-reflection.md の D1-D6 を参照。

1. **要件定義 = goal-spec 固定**: `run-goal-elicit` が曖昧構想から `purpose/background/goal/checklist` を `<PLAN_DIR>/goal-spec.json` に固める。`PLAN_DIR` は既定 `plugin-plans/<plugin-slug>/` (可視・永続の tracked deliverable) で、`target_plugin_slug` とともに goal-spec へ固定する。checklist 各項目は `{id:^C[0-9]+$, criterion, done, verify_by ∈ {reasoning,script,lint,test,human}}`。追加質問せず仮定は constraints/open_questions に明示。

2. **固定手順禁止**: 「## ゴールシーク実行」4 ブロック (ゴール=観測可能完了形 1 文 / 目的背景 Why / 完了チェックリスト=二値 / ループ) + 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復・既定 5 周)。AI 最尤ゴール推定。

3. **中間成果物アンカー**: 各周回末に `<PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl` へ 5 要素 (`original_goal`=不変・SHA256 照合 / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` ∈ {initial,aligned,compressing,stagnant,widening,oscillating}) を追記。次周回 Step2 は前 merged_directive + original_goal を必須入力。改竄検知で停止。

4. **収束閾値**: `convergence-policy.json` (all_conditions_score_min=0.85 / delta_max_ratio=0.20 / 収束 Δ<0.10 / max_iterations=3 / loop_bounds: goal_seek_inner=5・content_review_inner=3・outer=3)。

5. **feedback ループ**: Stop hook `decision:block` で評価差し戻し起動・proposer≠approver・量産先に run-skill-feedback 実体配備。

6. **TDD 対応づけ**: Red→Green = 「未達チェックリスト項目 → goal-seek ループで埋める → 検証 exit0/PASS」。

## 仕様駆動開発 (SDD) の三本柱 (本スキルへの写像)

タスク仕様書は**仕様駆動開発**の正本である — 仕様が先・実装は従、という向きを植え付ける 3 要素を要件化する:

1. **仕様=正本 (spec-first)**: 要件の正本は `goal-spec.json` の checklist、仕様書 (index + 13 phase) はその被覆、実装 (L4 build) は仕様書の被覆。実装との乖離が出たら**仕様を先に更新**してから build へ戻す (逆流=実装に合わせた仕様の黙認改変は禁止)。大前提として、規律の中身は harness-creator 仕様の引用で構成する (`harness-creator-spec-reflection.md` マトリクス+`upstream-pins.json`・独自流儀の発明禁止)。
2. **要件トレーサビリティ (RTM)**: 全要件 id が index の `## 完了チェックリスト` / `## 受入確認` へ引用されること (要件 orphan=silent drop の封鎖) を `check-requirements-coverage.py` が fail-closed 機械検査する。detect-unassigned の component orphan 検査と対 (要件→計画 / 実体→計画 の双方向被覆)。
3. **受入基準の宣言型記述 (EARS 推奨・非強制指針)**: checklist の criterion と phase 完了チェックリスト項目は、可能なら EARS 形 —「<状態/イベント> のとき、<対象> は <観測可能な結果> を満たす」(例:「同一台帳を二回同期したとき、二周目の追加/更新が 0 件である」) — で書く。トリガと観測結果を一文に固定すると verify_by の機械判定に写しやすい。床は二値判定可能性まで (EARS 形自体は機械強制しない=Goodhart 回避)。

## 本スキルへの適用

- R1 (R1-elicit-goal.md) が構想から goal-spec を確定する (目的ドリブン要件定義)。
- 本スキル自身の `## ゴールシーク実行` も上記 4 ブロック + 6 ステップで構成し、`### ゴールシーク配線` に中間成果物アンカー (`intermediate.jsonl`/`original_goal`/`merged_directive_for_next`) を配線する。
- 量産する各 inventory component (と対応 phase ファイル) にも、上記 1-6 を「生成プラグインが満たすべき設計」として焼き込む (D1-D6 の焼き先)。
- R3 は index `## 基本定義` に仕様駆動の大前提 (harness-creator 仕様基点・spec-first・要件正本=goal-spec) を宣言し、goal-spec checklist の全 id を `## 完了チェックリスト` / `## 受入確認` で引用する (RTM ゲートが機械強制)。
