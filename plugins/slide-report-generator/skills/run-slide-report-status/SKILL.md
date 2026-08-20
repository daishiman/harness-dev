---
name: run-slide-report-status
description: 生成中のslide deckまたはreportの現在phaseを確認したいとき、中断後の次アクションをread-onlyで特定したいときに使う。
kind: run
prefix: run
version: 0.1.0
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: false
argument-hint: "[output-dir?]"
effect: conversation-output
owner: harness maintainers
since: 2026-08-20
last-audited: 2026-08-20
output_language: ja
runtime_root_policy: host-skill-path
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 明示されたproject directoryへworkflow managerのcheck nextとoutput mode preflightをread-onlyで実行し全exit codeを保持している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: deck report両modeの現在phase 欠落artifact 次actionを推測せず報告しplugin runtime欠落を自動復元していない
      verify_by: evaluator
---

# run-slide-report-status

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

対象project directoryをplugin同梱workflow managerで検査し、現在phase、検証結果、次アクションを返す。

## Key Rules

- 対象path未指定時は推測せず確認する。
- plugin資産は`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`から解決する。
- 対象projectへ書き込まず、`--check --next`だけを実行する。
- validator非0を成功へ畳まない。

## ゴールシーク実行

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/vendor/scripts/workflow-manager.js" "<project-dir>" --check --next
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-output-mode.py" --preflight
```

stdout/stderrとexit codeから現在phase、欠落artifact、次アクションを要約する。

## 検証

- deck/report両modeを同じworkflow managerで判定する。
- plugin-local runtime欠落は復元せずremediationとして報告する。
