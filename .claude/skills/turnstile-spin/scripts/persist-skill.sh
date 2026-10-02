#!/usr/bin/env bash
# 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。
# Persists the canonical Spin skill bundle (SKILL.md + scripts/ + references/)
# from cloudflare/skills to an unmanaged repository. Repositories whose
# AGENTS.md declares runtime locations as generated must update their authoring
# source and run their sync workflow instead.
#
# Args:
#   --path <path>   SKILL.md destination, e.g. .claude/skills/turnstile-spin/SKILL.md
#                   or .agents/skills/turnstile-spin/SKILL.md.
#                   The bundle is extracted into the parent directory of <path>,
#                   so scripts land beside SKILL.md in the selected client bundle.
#
# Outputs JSON. Exit 0 if the bundle was written, 1 on failure.
#   ok:    {"status":"ok","path":"<path>","bundle_root":"<dir>","scripts":[<list>]}
#   fail:  {"status":"error","reason":"<reason>"}

set -uo pipefail

PATH_ARG=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --path) PATH_ARG="$2"; shift 2 ;;
    *) echo "persist-skill: unknown arg $1" >&2; exit 2 ;;
  esac
done

: "${PATH_ARG:?--path required}"

TARGET_DIR=$(dirname "$PATH_ARG")

# Find the closest repository guidance before writing anything. AIDD-managed
# runtime paths are generated artifacts; fetching upstream content into them
# would bypass the authoring source, manifest, and verification contract.
case "$TARGET_DIR" in
  /*) SEARCH_DIR="$TARGET_DIR" ;;
  *) SEARCH_DIR="$PWD/$TARGET_DIR" ;;
esac
while [ ! -e "$SEARCH_DIR" ] && [ "$SEARCH_DIR" != "/" ]; do
  SEARCH_DIR=$(dirname "$SEARCH_DIR")
done

GUIDANCE=""
CURRENT="$SEARCH_DIR"
while [ -n "$CURRENT" ] && [ "$CURRENT" != "/" ]; do
  CANDIDATE=""
  if [ -f "$CURRENT/AGENTS.override.md" ]; then
    CANDIDATE="$CURRENT/AGENTS.override.md"
  elif [ -f "$CURRENT/AGENTS.md" ]; then
    CANDIDATE="$CURRENT/AGENTS.md"
  fi
  if [ -n "$CANDIDATE" ] && \
     grep -Eq 'aidd-agent-kit/skills|管理対象の実配置|authoring path' "$CANDIDATE"; then
    GUIDANCE="$CANDIDATE"
    break
  fi
  CURRENT=$(dirname "$CURRENT")
done

if [ -n "$GUIDANCE" ]; then
  echo "persist-skill: refusing to write a managed runtime path: $TARGET_DIR" >&2
  echo "persist-skill: update the authoring path declared by $GUIDANCE, then run sync and verify." >&2
  echo "{\"status\":\"error\",\"reason\":\"managed_runtime\",\"guidance\":\"$GUIDANCE\"}"
  exit 1
fi

mkdir -p "$TARGET_DIR"

# Install the canonical bundle from cloudflare/skills via degit. This writes
# SKILL.md, scripts/, references/, templates/, tests/ into $TARGET_DIR.
run_degit() {
  if [ -f pnpm-lock.yaml ] || [ -f pnpm-workspace.yaml ]; then
    pnpm dlx degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  elif [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
    npx --yes degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  elif [ -f yarn.lock ]; then
    yarn dlx degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  elif command -v pnpm >/dev/null 2>&1; then
    pnpm dlx degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  elif command -v npm >/dev/null 2>&1; then
    npx --yes degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  elif command -v yarn >/dev/null 2>&1; then
    yarn dlx degit cloudflare/skills/skills/turnstile-spin "$TARGET_DIR"
  else
    return 127
  fi
}

if ! run_degit >/dev/null 2>&1; then
  echo "persist-skill: degit failed; cannot fetch cloudflare/skills/skills/turnstile-spin." >&2
  echo "persist-skill: ensure the repository package manager can reach github.com and try again, or install manually." >&2
  echo "{\"status\":\"error\",\"reason\":\"degit_failed\"}"
  exit 1
fi

if [ ! -f "$TARGET_DIR/SKILL.md" ]; then
  echo "persist-skill: bundle extracted but SKILL.md is missing at $TARGET_DIR/SKILL.md." >&2
  echo "{\"status\":\"error\",\"reason\":\"skill_missing\"}"
  exit 1
fi

# Make scripts executable so the agent can invoke them directly.
if [ -d "$TARGET_DIR/scripts" ]; then
  chmod +x "$TARGET_DIR/scripts"/*.sh 2>/dev/null || true
fi

scripts_list=$(
  for script_path in "$TARGET_DIR"/scripts/*; do
    [ -f "$script_path" ] || continue
    script_name=${script_path##*/}
    printf '"%s"\n' "$script_name"
  done | paste -sd, -
)
echo "persist-skill: wrote bundle to $TARGET_DIR" >&2
echo "{\"status\":\"ok\",\"path\":\"$PATH_ARG\",\"bundle_root\":\"$TARGET_DIR\",\"scripts\":[$scripts_list]}"
exit 0
