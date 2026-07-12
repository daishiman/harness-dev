#!/usr/bin/env bash
# PKG-010: install smoke
# Install UX Contract（36章 §Install UX Contract）の必須事象3群・禁止事象4群を擬似検証。
# 実環境への副作用を避けるため --dry-run 既定。
set -euo pipefail

PLUGIN=""
DRY_RUN=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin) PLUGIN="$2"; shift 2 ;;
    --no-dry-run) DRY_RUN=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) shift ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
PLUGIN_DIR="$REPO_ROOT/plugins/$PLUGIN"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: plugin not found: $PLUGIN_DIR" >&2
  exit 2
fi

# Install UX Contract: 必須事象 1-1 (skills/* が列挙可能)
SKILLS_COUNT=$(find "$PLUGIN_DIR/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
# 必須事象 1-2 (agents/* が参照可能)
AGENTS_COUNT=$(find "$PLUGIN_DIR/agents" -maxdepth 1 -mindepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
# 必須事象 1-3 (hooks 反映)
HOOKS_COUNT=$(find "$PLUGIN_DIR/hooks" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')
# 必須事象 1-4 (scripts 実行可能)
SCRIPTS_NON_EXEC=$(find "$PLUGIN_DIR/scripts" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' \) ! -perm -u+x 2>/dev/null | wc -l | tr -d ' ')
# 禁止事象 1 (plugin 外参照)
EXTERNAL_REFS=$(grep -rlE '\.\./\.\./scripts/|\.\./\.\./adapters/|\.\./\.\./\.claude/config/' "$PLUGIN_DIR" 2>/dev/null | wc -l | tr -d ' ')

STATUS="pass"
FINDINGS=()

if [[ "$SCRIPTS_NON_EXEC" -gt 0 ]]; then
  STATUS="fail"
  FINDINGS+=("\"非実行可能 script が ${SCRIPTS_NON_EXEC} 件 (Install UX Contract 必須事象 1-4 違反)\"")
fi
if [[ "$EXTERNAL_REFS" -gt 0 ]]; then
  STATUS="fail"
  FINDINGS+=("\"plugin 外参照が ${EXTERNAL_REFS} 件 (禁止事象 1 違反)\"")
fi

FINDINGS_JSON=$(IFS=,; echo "${FINDINGS[*]:-}")

cat <<EOF
{
  "pkg_id": "PKG-010",
  "status": "$STATUS",
  "last_run_at": "$NOW",
  "dry_run": $DRY_RUN,
  "counts": {
    "skills": $SKILLS_COUNT,
    "agents": $AGENTS_COUNT,
    "hooks": $HOOKS_COUNT,
    "scripts_non_executable": $SCRIPTS_NON_EXEC,
    "external_refs": $EXTERNAL_REFS
  },
  "findings": [$FINDINGS_JSON]
}
EOF

[[ "$STATUS" == "pass" ]] && exit 0 || exit 1
