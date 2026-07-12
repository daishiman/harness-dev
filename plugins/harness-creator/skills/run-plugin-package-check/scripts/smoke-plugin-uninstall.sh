#!/usr/bin/env bash
# PKG-011: uninstall 完全性
# 本実装は計画 stub。実際の uninstall flow は claude CLI 連携が必要なため、ここでは
# plugin 由来の symlink/settings/hook 痕跡候補のリストを返す。
set -euo pipefail

PLUGIN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin) PLUGIN="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# symlink 痕跡候補
SYMLINKS=$(find "$REPO_ROOT/.claude/skills" -maxdepth 1 -type l 2>/dev/null | while read -r ln; do
  target=$(readlink "$ln")
  if [[ "$target" == *"plugins/$PLUGIN/"* ]]; then
    echo "$ln"
  fi
done | wc -l | tr -d ' ')

cat <<EOF
{
  "pkg_id": "PKG-011",
  "status": "skip",
  "skip_reason": "uninstall smoke は claude CLI 連携実装後に有効化。現状は痕跡候補列挙のみ。",
  "last_run_at": "$NOW",
  "trace_candidates": {
    "claude_skills_symlinks": $SYMLINKS
  }
}
EOF
exit 0
