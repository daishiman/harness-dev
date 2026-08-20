---
name: run-slide-report-status
description: 生成中のslide deckまたはreportの現在phaseと次アクションをread-onlyで確認したいときに使う。
allowed-tools: Bash, Read
runtime_root_policy: host-skill-path
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
