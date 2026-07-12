#!/usr/bin/env bash
# git hooks を .githooks/ に切り替える。各 clone で 1 回実行すれば pre-push が有効化される。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git config core.hooksPath .githooks
chmod +x .githooks/* scripts/run-ci-checks.sh 2>/dev/null || true
echo "[install-git-hooks] core.hooksPath=.githooks 設定完了"
echo "[install-git-hooks] 有効 hooks:"
ls -1 .githooks
