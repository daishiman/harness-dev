#!/usr/bin/env bash
# PKG-012: same-version no-op and different-version non-destructive sandbox upgrade.
set -euo pipefail

PLUGIN=""
PLUGINS_ROOT=""
SANDBOX_ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin) PLUGIN="$2"; shift 2 ;;
    --plugins-root) PLUGINS_ROOT="$2"; shift 2 ;;
    --sandbox-root) SANDBOX_ROOT="$2"; shift 2 ;;
    *) echo "error: unsupported argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$PLUGIN" ]] || { echo "error: --plugin is required" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARGS=(--plugin "$PLUGIN" --operation upgrade)
[[ -z "$PLUGINS_ROOT" ]] || ARGS+=(--plugins-root "$PLUGINS_ROOT")
[[ -z "$SANDBOX_ROOT" ]] || ARGS+=(--sandbox-root "$SANDBOX_ROOT")
exec python3 "$SCRIPT_DIR/sandbox-plugin-lifecycle.py" "${ARGS[@]}"
