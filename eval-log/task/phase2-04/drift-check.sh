#!/usr/bin/env bash
# drift-check.sh
# 用途: Phase 全体 (cross-plugin) の最終確認に使用する drift 検証。
#       per-plugin 単位の局所 --check は rollback.template.sh Step 5 が担当し、
#       本スクリプトは plugins/ 配下 worktree も含めた横断 invariant を扱う。
# 凍結 CLI (scripts/build-claude-symlinks.py / build-claude-settings.py) の
# `--check --json` 出力に対して invariant を検査する。
set -euo pipefail

out_dir="${1:?usage: drift-check.sh <eval-log-output-dir>}"
mkdir -p "$out_dir"

python3 scripts/build-claude-symlinks.py --check --json > "$out_dir/drift-symlink.json"
python3 scripts/build-claude-settings.py --check --json > "$out_dir/drift-settings.json"

# symlink drift: conflict == 0 かつ noop 以外の plan が無い
jq -e '.summary.conflict == 0 and ([.plan[] | select(.action != "noop")] | length == 0)' \
  "$out_dir/drift-symlink.json" > /dev/null

# settings drift: conflicts なし かつ invariant 検査が 12 件以上
jq -e '(.conflicts | length) == 0 and (.invariants_checked | length) >= 12' \
  "$out_dir/drift-settings.json" > /dev/null

echo "drift OK"
