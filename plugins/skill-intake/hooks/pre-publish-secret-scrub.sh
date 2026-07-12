#!/usr/bin/env bash
# pre-publish-secret-scrub.sh
#
# Notion 公開前に intake 成果物にトークン/シークレットが混入していないかを走査する。
# 発火ゲート (pre-publish-schema-validate.py の TARGET_COMMANDS と同型):
#   stdin (PreToolUse JSON) の tool_input.command が publish 経路
#   (intake_publish_pipeline.py / publish_notion_page.py) を含むときのみ走査し、
#   非該当コマンドは即 exit 0 (無関係な Bash / 他 plugin セッションを誤遮断しない)。
#   stdin 不在 / JSON parse 失敗時は安全側 (従来動作 = 走査実行) に倒す。
# 検知パターン:
#   - Notion PAT       : ntn_[A-Za-z0-9]{40,}
#   - Notion Integration : secret_[A-Za-z0-9]{40,}
#   - 汎用 Bearer       : Bearer\s+[A-Za-z0-9_\-\.]{20,}
#   - .env 形式         : (NOTION|API|TOKEN|SECRET)_[A-Z_]*=[A-Za-z0-9_\-]+
#
# 配線: ~/.claude/settings.json または .claude/settings.json に以下を追加:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Bash",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "$CLAUDE_PLUGIN_ROOT/hooks/pre-publish-secret-scrub.sh"
#           }
#         ]
#       }
#     ]
#   }
# }
#
# 終了コード:
#   0 = clean (公開許可)
#   2 = secret detected (公開停止 — Claude Code が自動でブロック)
set -euo pipefail

# --- publish gate: tool_input.command が publish 経路のときのみ走査する ---
# stdin 不在 (tty) / JSON parse 失敗 / python3 不在は安全側 (従来動作 = 走査実行) に倒す。
gate="scan"
if [[ ! -t 0 ]]; then
  gate="$(python3 -c '
import json, sys

try:
    payload = json.loads(sys.stdin.read())
    command = payload.get("tool_input", {}).get("command", "")
except Exception:
    print("scan")  # parse 失敗 = 安全側で走査続行 (fail-closed)
    raise SystemExit(0)

if not isinstance(command, str):
    print("scan")  # 構造異常 payload = 安全側で走査続行 (fail-closed)
    raise SystemExit(0)

TARGET_COMMANDS = ("intake_publish_pipeline.py", "publish_notion_page.py")
print("scan" if any(t in command for t in TARGET_COMMANDS) else "skip")
' 2>/dev/null)" || gate="scan"
fi
if [[ "$gate" == "skip" ]]; then
  exit 0  # publish 非関連コマンドは走査せず素通し (誤遮断防止)
fi

TARGET_DIRS=(
  "output"
)

PATTERNS=(
  'ntn_[A-Za-z0-9]{40,}'
  'secret_[A-Za-z0-9]{40,}'
  'Bearer[[:space:]]+[A-Za-z0-9_\-\.]{20,}'
  '(NOTION|API|TOKEN|SECRET)_[A-Z_]*=[A-Za-z0-9_\-]{16,}'
)

found=0
for dir in "${TARGET_DIRS[@]}"; do
  [[ -d "$dir" ]] || continue
  for pattern in "${PATTERNS[@]}"; do
    if grep -REn --include='*.json' --include='*.md' --include='*.txt' "$pattern" "$dir" 2>/dev/null; then
      echo "FAIL: secret-like pattern detected in $dir matching: $pattern" >&2
      found=1
    fi
  done
done

if [[ $found -ne 0 ]]; then
  cat >&2 <<EOF
[skill-intake] PRE-PUBLISH SECRET SCRUB FAILED.
公開を停止しました。検知された行を修正してから再実行してください。
詳細: plugins/skill-intake/references/keychain-setup.md
EOF
  exit 2
fi

exit 0
