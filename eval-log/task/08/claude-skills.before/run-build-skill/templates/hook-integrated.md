---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *)]
kind: {{kind}}
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal") }}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly") }}
role_suffix: {{role_suffix}}
# === Hook 統合スキル ===
# 本 skill は Hook と組で運用される。スキル本文は Hook の存在と結果解釈を明示する。
# 設計書10章: 自然言語の禁則ではなく Hook + permissions.deny の二段防御で守る。
#
# 必須 hook (settings.json に登録):
#   PreToolUse:    scripts/hook-{{name}}-guard.py     (静的 deny を補強)
#   PostToolUse:   scripts/hook-{{name}}-validate.py  (副作用後の検査)
#   SubagentStop:  scripts/hook-{{name}}-verify.py    (evaluator JSON 契約)  [evaluator pair時]
#
# 必須 permissions.deny (settings.json):
#   {{deny_rules_list}}
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Hook Integration Map

| Hook Event | Script | 役割 | exit code 意味 |
|---|---|---|---|
| PreToolUse | hook-{{name}}-guard.py | 文脈次第の危険操作を block | 2=block, 0=pass |
| PostToolUse | hook-{{name}}-validate.py | 副作用後の整合性検査 | 警告のみ (exit 0固定) |
| {{additional_hook_event}} | {{additional_hook_script}} | {{additional_hook_role}} | {{additional_hook_exit}} |

### Hook 競合解決順序（設計書10章§7.2）
1. `permissions.deny` match → 即 BLOCK（hook 評価せず）
2. `PreToolUse` hook 登録順に評価 → 最初の deny/exit 2 で確定
3. `permissions.allow` / ask 判定
4. tool 実行 → `PostToolUse` hook（副作用後検査）

## Boundary
{{boundary}}

## Key Rules
- 自然言語で「○○してはいけない」と書いて済ませない。**決定論で守れる境界は Hook に移す**
- `permissions.deny` は access control の最終防衛線。Hook 無効化時も deny は効く
- 同イベントに複数 hook を登録しない（登録順依存で読み取り困難になる）
- PostToolUse で「禁止表現」をしない（副作用が出た後の block は意味がない）

## Steps

### Step 1: 静的禁止の宣言（permissions.deny）
`settings.json` に以下を追加（既存の deny を上書きしないこと）:
```json
{
  "permissions": {
    "deny": [{{deny_rules_list}}]
  }
}
```

### Step 2: Hook スクリプトの配線
```bash
# scripts/ に hook 実装を配置
ls scripts/hook-{{name}}-guard.py scripts/hook-{{name}}-validate.py
# settings.json の hooks セクションに matcher 付きで登録
```

### Step 3: 動作検証
```bash
# Hook が想定通り block するか dry-run
echo '{"tool":"Write","tool_input":{"file_path":"<禁止対象>"}}' \
  | python3 scripts/hook-{{name}}-guard.py
# exit 2 が返ればOK
```

## Gotchas
- **Hook で access 制御だけ書く**: `permissions.deny` を併用しないと hook 設定ミス時に素通り。設計書10章 §7.5 アンチパターン①
- **PostToolUse で禁止表現**: 副作用後の block は不可。`PreToolUse` + `permissions.deny` で前段で止める
- **`disableAllHooks` 想定外**: settings で hooks 無効化されても安全側に倒れるよう、`permissions.deny` を必ず一段目に置く

## Additional Resources
- 設計書 10章 §7 — Hook 競合解決の意思決定フロー
- `creator-kit/config/claude-settings-hooks.json.example` — 公式 hook 配線例
{{additional_resources}}
