---
name: run-intake-status
description: 進行中のskill intakeについてphase、5軸、visual、Notion公開状態を確認したいときに使う。
allowed-tools: Read, Glob
---

# run-intake-status

## Purpose & Output Contract

`output/<hint>/`をread-onlyで走査し、kickoff/profile/5軸/visual/Notion公開状態をMarkdown表で返す。

## Key Rules

- 引数があれば`output/<hint>/`だけ、なければ`output/*/`を対象にする。
- `intake.json`の5軸、`visuals/*.{svg,png}`、`notion-url.txt`、`notion-log.json.status`を観測する。
- 欠落は未完了として表示し、ファイルを生成・修復しない。
- JSON parse不能は対象名と原因を表示し、成功へ畳まない。

## ゴールシーク実行

対象を確定し、各証拠を読み、`hint | kickoff | profile | 5 axes | visuals | notion`列の表を返す。全対象を1行ずつ報告できたら完了する。

## 検証

- 集計値を実ファイル数と再照合する。
- 状態不明を`✓`へ推測変換しない。
