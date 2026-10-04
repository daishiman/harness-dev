#!/bin/bash
# Codexのuser/projectスコープ重複と誤配置を、削除せず診断する。

set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
PROJECT_ROOT=${AIDD_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd -P)}
USER_ROOT=${AIDD_USER_HOME:-$HOME}
USER_CODEX_ROOT=${AIDD_USER_CODEX_HOME:-${CODEX_HOME:-$USER_ROOT/.codex}}
STRICT=0

case "${1:-}" in
  "") ;;
  --strict) STRICT=1 ;;
  *) echo "使い方: $0 [--strict]" >&2; exit 2 ;;
esac

warnings=0
errors=0

diagnose_pair() {
  kind="$1"
  name="$2"
  left_scope="$3"
  left_file="$4"
  right_scope="$5"
  right_file="$6"
  [ -f "$left_file" ] && [ -f "$right_file" ] || return 0

  if cmp -s "$left_file" "$right_file"; then
    echo "[WARN:SAME] $kind '$name' が${left_scope}/${right_scope}の両方にあります。同名定義は統合されません。"
    warnings=$((warnings + 1))
    [ "$STRICT" -eq 0 ] || errors=$((errors + 1))
  else
    echo "[WARN:DIFF] $kind '$name' が${left_scope}/${right_scope}で異なります。このrepositoryではproject scopeを正本として扱います。"
    warnings=$((warnings + 1))
    [ "$STRICT" -eq 0 ] || errors=$((errors + 1))
  fi
}

diagnose_external_pair() {
  kind="$1"
  name="$2"
  project_file="$3"
  external_file="$4"
  [ -f "$project_file" ] && [ -f "$external_file" ] || return 0

  if cmp -s "$project_file" "$external_file"; then
    detail="SAME"
  else
    detail="DIFF"
  fi
  echo "[WARN:$detail] $kind '$name' がproject .agentsとuser CODEX_HOMEの両方にあります。後者はAIDD管理外ですが、catalogで同名になる可能性があります。"
  warnings=$((warnings + 1))
  [ "$STRICT" -eq 0 ] || errors=$((errors + 1))
}

for source_dir in "$SCRIPT_DIR"/skills/*/ "$SCRIPT_DIR"/codex/workflow-skills/*/; do
  [ -d "$source_dir" ] || continue
  name=$(basename "$source_dir")
  diagnose_pair \
    "Skill" "$name" \
    "project .agents" \
    "$PROJECT_ROOT/.agents/skills/$name/SKILL.md" \
    "user .agents" \
    "$USER_ROOT/.agents/skills/$name/SKILL.md"
  diagnose_external_pair \
    "Skill" "$name" \
    "$PROJECT_ROOT/.agents/skills/$name/SKILL.md" \
    "$USER_CODEX_ROOT/skills/$name/SKILL.md"
done
diagnose_pair \
  "Skill" "app-orchestrator" \
  "project .agents" \
  "$PROJECT_ROOT/.agents/skills/app-orchestrator/SKILL.md" \
  "user .agents" \
  "$USER_ROOT/.agents/skills/app-orchestrator/SKILL.md"
diagnose_external_pair \
  "Skill" "app-orchestrator" \
  "$PROJECT_ROOT/.agents/skills/app-orchestrator/SKILL.md" \
  "$USER_CODEX_ROOT/skills/app-orchestrator/SKILL.md"

for source in "$SCRIPT_DIR"/codex/agents/*.toml; do
  [ -f "$source" ] || continue
  name=$(basename "$source")
  diagnose_pair \
    "custom agent" "$name" \
    "project .codex" \
    "$PROJECT_ROOT/.codex/agents/$name" \
    "user .codex" \
    "$USER_CODEX_ROOT/agents/$name"
done

if [ -e "$PROJECT_ROOT/.codex/skills" ]; then
  echo "[NG] project scopeのAIDD Skillは .codex/skills へ配置しません: $PROJECT_ROOT/.codex/skills"
  errors=$((errors + 1))
fi

echo ""
echo "AIDDのこのrepositoryでの正本: project scope"
echo "  Skill: $PROJECT_ROOT/.agents/skills"
echo "  custom agent: $PROJECT_ROOT/.codex/agents"
echo "  Codex組込installer等のpersonal領域: $USER_CODEX_ROOT/skills (AIDDは書き込まない)"
echo "  診断: warnings=$warnings / errors=$errors"
echo "  自動削除は行っていません。"

[ "$errors" -eq 0 ] || exit 1
