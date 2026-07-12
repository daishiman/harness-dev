---
name: ubm-goal-setting
description: 週報・月報・期報の目標設定・振り返り対話を手動起動したいときに使う。
argument-hint: "[weekly|monthly|bimonthly]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
kind: command
version: 0.1.0
owner: harness-maintainers
---

# UBM 目標設定・振り返り

UBM（北原さん式ゴールセッティング）の目標設定（週報=1週間 / 月報=1ヶ月 / 期報=2ヶ月）をユーザーとの高速対話で作成・振り返りする入口コマンド。過去データの自動収集＋思考法を適用した最小ターン数のヒアリングで、トントン拍子に目標設定を完了する。

## 実行

`run-ubm-goal-setting` スキルを Skill ツールで起動し、その指示に従って実行する。

- 引数 `$ARGUMENTS` に `weekly` / `monthly` / `bimonthly` が指定されていればその種別で開始する。
- 引数がなければスキルの Phase0（AskUserQuestion）で目標種別を確認する。

## 引数

- `weekly`: 1週間目標（週報）を作成
- `monthly`: 1ヶ月目標（月報）を作成
- `bimonthly`: 2ヶ月目標（期報）を作成
- 引数なし: どの目標を設定するかヒアリングして開始

## コミュニケーションスタイル（スキル側で強制）

- 歩み寄りながら、愛情ある厳しさで本質を突く。
- 「頑張る」「意識する」は許さず、具体的な行動（誰に・何を・いつまで・何件）に落とし込む。
- 1ターン1〜3問でテンポよく進める。北原さんの原則は1対話1〜2回まで引用する。
