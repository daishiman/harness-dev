---
# Hook Skeleton (kind: hook)
#
# CapabilityManifest schema: definitions/kindHook
# Claude Code Hooks 仕様 (settings.json / plugin.json hooks) に準拠。
# 用途: PreToolUse / PostToolUse / SubagentStop 等で発火するスクリプトの宣言。
#
# 設計書 10章: 自然言語の禁則ではなく Hook + permissions.deny の二段防御で守る。
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}    hook 名 (kebab-case, 例: hook-file-ownership-guard)
#   {{OWNER}}              governance 担当
#   {{EVENT}}              PreToolUse|PostToolUse|UserPromptSubmit|Stop|
#                          SessionEnd|SubagentStop|PreCompact|Notification
#   {{MATCHER_TOOL}}       対象ツール名 (Edit|Write|Bash 等)
#   {{MATCHER_PATH_GLOB}}  対象ファイル glob (任意)
#   {{MATCHER_ARG_RE}}     Bash の場合 cmd 正規表現 (任意)
#   {{COMMAND}}            plugin.json hook runtime のスクリプトパス ($CLAUDE_PLUGIN_ROOT 利用可)。
#                          導入者向け README / 手動実行例には裸 $CLAUDE_PLUGIN_ROOT を出さない。
#   {{TIMEOUT_MS}}         100..60000 (default 5000)
#   {{EXIT_CODE_POLICY}}   non-blocking|blocking-on-nonzero|blocking-on-2
#   {{SIDE_EFFECT_SCOPE}}  read-only|lessons-write|git-write|external
---
name: {{CAPABILITY_NAME}}
description: {{WHEN_FIRES_SUMMARY}}
kind: hook
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
event: {{EVENT}}
matcher:
  tool: {{MATCHER_TOOL}}
  path_glob: {{MATCHER_PATH_GLOB}}
  argument_pattern: {{MATCHER_ARG_RE}}
command: {{COMMAND}}
timeout_ms: {{TIMEOUT_MS}}
exit_code_policy: {{EXIT_CODE_POLICY}}
side_effect_scope: {{SIDE_EFFECT_SCOPE}}
contract:
  intent: {{HOOK_INTENT}}
  interface:
    stdin: {{STDIN_SCHEMA_REF}}
    exit_codes:
      "0": pass
      "2": block (PreToolUse でのみ block 効果)
      other: warning / error (event により異なる)
  invariant:
    - PostToolUse で副作用後の block を試みない (意味がない)
    - permissions.deny を併用する (hook 単独で access control に頼らない)
    - 同イベントに重複登録しない (登録順依存で読み取り困難)
    - hook script は import-time に plugin root 外へ fail-closed 依存しない
    - hook script 内部の資産解決は `__file__` / plugin-relative を優先し、env 不在時も fail-soft にする
    - `scripts/lint-runtime-portability.py` を通す
---

# {{CAPABILITY_NAME}}

## When-fires
- event: `{{EVENT}}`
- matcher: tool=`{{MATCHER_TOOL}}` path=`{{MATCHER_PATH_GLOB}}` arg=`{{MATCHER_ARG_RE}}`
- 発火条件詳細: {{WHEN_FIRES_DETAIL}}

## Side-effect
- スコープ: `{{SIDE_EFFECT_SCOPE}}`
- 書き込み先: {{WRITE_TARGET}}
- 冪等性: {{IDEMPOTENT_NOTE}}

## Failure-handling
- timeout ({{TIMEOUT_MS}} ms 超過): {{TIMEOUT_BEHAVIOR}}
- exit code != 0:
  - policy=`{{EXIT_CODE_POLICY}}` に従う
  - block の場合 stderr に理由を出力して exit 2
  - warning の場合 stderr に出力して exit 0
- stdin parse error: exit 1, stderr に "invalid input"

## Registration Example
`settings.json` または `plugin.json` の `hooks` セクションに追記:
```json
{
  "hooks": {
    "{{EVENT}}": [
      {
        "matcher": "{{MATCHER_TOOL}}",
        "hooks": [
          { "type": "command", "command": "{{COMMAND}}", "timeout": {{TIMEOUT_MS}} }
        ]
      }
    ]
  }
}
```

## Companion permissions.deny
本 hook は二段防御の動的側。`permissions.deny` に静的禁止を必ず併記:
```json
{ "permissions": { "deny": [{{DENY_RULES_LIST}}] } }
```
