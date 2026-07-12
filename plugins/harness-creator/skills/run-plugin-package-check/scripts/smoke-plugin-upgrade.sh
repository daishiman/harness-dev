#!/usr/bin/env bash
# PKG-012: upgrade 冪等性
# 同一 version の plugin.json hash が変わらないことを確認する stub 実装。
set -euo pipefail

PLUGIN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin) PLUGIN="$2"; shift 2 ;;
    *) shift ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
PJ="$REPO_ROOT/plugins/$PLUGIN/.claude-plugin/plugin.json"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

STATUS="skip"
SKIP_REASON="upgrade smoke は claude CLI 連携実装後に有効化。現状は plugin.json hash 安定性確認のみ。"
HASH="null"

if [[ -f "$PJ" ]]; then
  HASH=$(python3 -c "import hashlib,sys; print('\"'+hashlib.sha256(open('$PJ','rb').read()).hexdigest()[:16]+'\"')")
fi

cat <<EOF
{
  "pkg_id": "PKG-012",
  "status": "$STATUS",
  "skip_reason": "$SKIP_REASON",
  "last_run_at": "$NOW",
  "plugin_json_hash_prefix": $HASH
}
EOF
exit 0
