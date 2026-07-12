#!/usr/bin/env bash
# Auto-generated rollback template for plugin: <PLUGIN>
# Pre-state snapshot id: <SNAPSHOT_ID>
# NOTE: This file is a TEMPLATE. Placeholders such as <PLUGIN>, <SNAPSHOT_ID>,
#       and <MOVED_PATHS> are replaced at generation time by
#       scripts/phase2/gen-rollback.py (本実装は Phase2-06)。
#       テンプレ自体は `bash -n` PASS を保つため、プレースホルダはコメント or
#       文字列内に閉じ込め、ループ変数経由で安全に展開する。

set -euo pipefail

PLUGIN="${PLUGIN:-skill-governance-adapters}"
SNAPSHOT_ID="${SNAPSHOT_ID:-phase2-06-20260520T073546Z}"
# MOVED_PATHS は gen-rollback.py が配列リテラルとして注入する
# 生成時の形: MOVED_PATHS=("creator-kit/...." "creator-kit/...." ...)
MOVED_PATHS=(creator-kit/scripts/adapters/dispatch.py creator-kit/scripts/adapters/resolve_route.py creator-kit/scripts/adapters/sink_http.py creator-kit/scripts/adapters/sink_local.py creator-kit/scripts/adapters/sink_notion.py creator-kit/scripts/adapters/sink_sheets.py creator-kit/scripts/adapters/sink_slack.py)
EVAL_DIR="eval-log/task/phase2-06/${PLUGIN}"

echo "[rollback] plugin=${PLUGIN} snapshot=${SNAPSHOT_ID}"

# Step 1: .claude/ 派生 (symlink) のうち plugin 由来のものを削除
#         build CLI が再生成するため、ここでは削除のみで良い。
find .claude/skills -lname "*plugins/${PLUGIN}/*" -delete 2>/dev/null || true
find .claude/agents -lname "*plugins/${PLUGIN}/*" -delete 2>/dev/null || true

# Step 2: plugins/<PLUGIN>/ を git restore
if git ls-files --error-unmatch "plugins/${PLUGIN}" >/dev/null 2>&1; then
  git restore --staged --worktree "plugins/${PLUGIN}/" 2>/dev/null || true
else
  rm -rf "plugins/${PLUGIN}"
fi

# Step 3: creator-kit/ 内の移動元 (MOVED_PATHS) を git restore
for path in "${MOVED_PATHS[@]}"; do
  if [ -n "${path}" ]; then
    git restore --staged --worktree "${path}" 2>/dev/null || true
  fi
done

# Step 4: settings.json を pre-state に戻す
if [ -f "${EVAL_DIR}/settings.before.json" ]; then
  cp "${EVAL_DIR}/settings.before.json" .claude/settings.json
else
  echo "[rollback][ERROR] missing snapshot: ${EVAL_DIR}/settings.before.json" >&2
  exit 1
fi

# Step 5: build CLI --check で整合確認
python3 scripts/build-claude-symlinks.py --check
python3 scripts/build-claude-settings.py --check

echo "[rollback] OK plugin=${PLUGIN}"
