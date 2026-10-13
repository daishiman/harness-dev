---
name: ubm-goal-setting
description: 1年目標・週報・月報・期報の目標設定・振り返り対話を手動起動したいときに使う。
argument-hint: "[yearly|weekly|monthly|quarterly]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
kind: command
version: 0.2.0
owner: harness-maintainers
---

# UBM 目標設定・振り返り

UBM（北原さん式ゴールセッティング）の目標設定（1年=1年 / 期報=3ヶ月 / 月報=1ヶ月 / 週報=1週間）をユーザーとの高速対話で作成・振り返りする入口コマンド。過去データの自動収集＋思考法を適用した最小ターン数のヒアリングで、トントン拍子に目標設定を完了する。

## 実行

`run-ubm-goal-setting` スキルを `Skill` ツールで起動し、その指示に従って実行する。

- 引数 `$ARGUMENTS` に `yearly` / `weekly` / `monthly` / `quarterly` が指定されていればその種別で開始する。
- 旧値 `bimonthly` が指定された場合も受理し、`quarterly` として開始する（後方互換の別名。正本は `run-ubm-goal-setting` の `references/data-contract.md` の `goal_type` と、`workflow-manifest.json` の Phase0 の gate）。
- 引数がなければスキルの Phase0（`AskUserQuestion`）で目標種別を確認する。

## 引数

- `yearly`: 1年目標（4層の最上位）を作成。正本は挑戦宣言（`05_Project/UBM/挑戦宣言/`）で、ここに置いた到達点を期報 → 月報 → 週報へ割っていく
- `weekly`: 1週間目標（週報）を作成
- `monthly`: 1ヶ月目標（月報）を作成
- `quarterly`: 3ヶ月目標（期報）を作成
- `bimonthly`: `quarterly` の後方互換の別名（旧・2ヶ月期報の呼び名。新規は `quarterly` を使う）
- 引数なし: Phase0 で選んでもらってから開始する。選択肢は 1=週報・2=月報・3=期報・4=1年目標・5=既存目標の見直し（`goal-reviewer` が既存の目標を見直すモード。新しい目標は作らない。引数では選べない）

4層の降ろし方（1年 → 3ヶ月 → 1ヶ月 → 1週間）と検証の引数は `run-ubm-goal-setting` の `SKILL.md` を正本とする。

## コミュニケーションスタイル（スキル側で強制）

対話の進め方は `run-ubm-goal-setting` が持ち、本コマンドには写さない。精神論の禁止と北原さんの原則の引用回数は同スキルの「守ること」、1ターンの問いの数は同スキルの `assets/interview-quick-templates.md` が正本。
