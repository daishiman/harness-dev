#!/usr/bin/env bash
# Shared, source-only helpers for resolving a selected Cloudflare Account.
# The complete Account ID stays in process memory and is never printed.

turnstile_require_user_api_token() {
  local token="${CLOUDFLARE_API_TOKEN:-}"
  case "$token" in
    '') return 2 ;;
    cfat_*|cfk_*) return 1 ;;
    *) return 0 ;;
  esac
}

turnstile_run_wrangler_whoami() {
  if [ -f pnpm-lock.yaml ] || [ -f pnpm-workspace.yaml ]; then
    pnpm exec wrangler whoami --json
  elif [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
    npx --no-install wrangler whoami --json
  elif [ -f yarn.lock ]; then
    yarn exec wrangler whoami --json
  elif command -v wrangler >/dev/null 2>&1; then
    wrangler whoami --json
  elif command -v pnpm >/dev/null 2>&1; then
    pnpm exec wrangler whoami --json
  elif command -v npm >/dev/null 2>&1; then
    npx --no-install wrangler whoami --json
  elif command -v yarn >/dev/null 2>&1; then
    yarn exec wrangler whoami --json
  else
    return 127
  fi
}

turnstile_resolve_account() {
  local selected_index="${1:-${CLOUDFLARE_ACCOUNT_INDEX:-}}"
  local whoami_json accounts_json account_count

  case "$selected_index" in
    ''|*[!0-9]*|0) return 2 ;;
  esac

  whoami_json=$(turnstile_run_wrangler_whoami 2>/dev/null) || return 3
  [ -n "$whoami_json" ] || return 3

  accounts_json=$(printf '%s' "$whoami_json" | (
    jq -c '.accounts' 2>/dev/null ||
    python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['accounts']))"
  )) || return 3
  account_count=$(printf '%s' "$accounts_json" | (
    jq 'length' 2>/dev/null ||
    python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
  )) || return 3
  [ "$selected_index" -le "$account_count" ] || return 2

  TURNSTILE_ACCOUNT_ID=$(printf '%s' "$accounts_json" | (
    jq -r --argjson index "$selected_index" '.[$index - 1].id' 2>/dev/null ||
    python3 -c "import sys,json; print(json.load(sys.stdin)[int(sys.argv[1])-1]['id'])" "$selected_index"
  )) || return 3
  [ -n "$TURNSTILE_ACCOUNT_ID" ] && [ "$TURNSTILE_ACCOUNT_ID" != "null" ]
}
