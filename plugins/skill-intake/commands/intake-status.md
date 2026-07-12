---
name: intake-status
description: 進行中ヒアリングの状況を表示 — 各 phase の完了状況・残り 5 軸・図解枚数を一覧化
argument-hint: "[<skill-name-hint>]"
---

# /intake-status

`output/<hint>/` ディレクトリを走査して、ヒアリングのどの phase まで進んでいるかを表で表示する。引数省略時は `output/` 直下を全件サマリ。

## 振る舞い

1. `output/$ARGUMENTS/` (または `output/*/`) の各ディレクトリで以下を集計:
   - `intake.json` の 5 軸充足度 (`output_destination` / `info_source` / `share_target` / `true_problem` / `knowledge_assets` の有無)
   - `visuals/*.svg` + `visuals/*.png` 枚数
   - `notion-url.txt` の有無
   - `notion-log.json.status` (success / partial / failed / 未公開)
2. Markdown 表で表示。

## 出力例

```
| hint                | kickoff | profile | 5 axes | visuals | notion |
|---------------------|---------|---------|--------|---------|--------|
| google-forms-gen    | ✓       | ✓       | 5/5    | 12+8    | ✓      |
| daily-report-gen    | ✓       | ✓       | 4/5    | 6+4     | 未公開 |
```
