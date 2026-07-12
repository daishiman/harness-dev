#!/usr/bin/env bash
# harness-creator 正本 → skill-intake 同梱 (vendored) を再同期する。
# skill-intake は単独 install でコアフローが自己完結動作する要件のため notion_config.py を
# 実体同梱する。正本 (harness-creator) を変更したら本スクリプトで vendored を更新し、
# scripts/lint-intake-vendored-ssot.py の byte 一致検証を通すこと。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sync_one() {
  local canonical="$ROOT/$1"
  local vendored="$ROOT/$2"
  if [ ! -f "$canonical" ]; then
    echo "ERROR: canonical 不在: $1" >&2
    exit 1
  fi
  # symlink に回帰していたら実体へ置換 (単独 install で壊れる回帰を解消)。
  if [ -L "$vendored" ]; then
    unlink "$vendored"
  fi
  cp "$canonical" "$vendored"
  echo "synced: $2 <- $1"
}

sync_one "plugins/harness-creator/scripts/notion_config.py" "plugins/skill-intake/scripts/notion_config.py"

echo "done. 検証: python3 scripts/lint-intake-vendored-ssot.py"
