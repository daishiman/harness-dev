#!/usr/bin/env bash
# Compatibility entrypoint. The publish pipeline passes an explicit successful
# receipt and hint; this script is intentionally not wired to generic Bash.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../scripts/post_publish_notify.py" "$@"
