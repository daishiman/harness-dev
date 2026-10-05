#!/usr/bin/env bash
# CI と同等の機械チェックをローカルで一括実行する。
# pre-push hook / 手動実行 (bash scripts/run-ci-checks.sh) の双方から呼ばれる。
# 内容の良し悪し (LLM 自由度領域) は判定対象外。構造・命名・SSOT・symlink drift のみ。
#
# CI の段の正本は .github/workflows/*.yml。本 script は段を手で写さず、
# scripts/extract-ci-workflow-steps.py が pull_request で起動する workflow から書き出した段を
# そのまま実行する。手写しの一覧は workflow とずれる (PR #83: validate-plugin-packages.py の
# PKG-007 をローカルが持たず、push 後の CI で初めて落ちた)。
#
# 環境変数:
#   CI_CHECKS_SKIP_JOBS="plugin-tests"  指定した job id の段を飛ばす (空白区切り)。飛ばした段は
#                                       サマリの Skipped に出る。CI と同じ範囲ではなくなるので、
#                                       push 前の最終確認では使わない。
#   STRICT_ALL_PLUGINS=1                段階導入中のローカル追加検査を error にする。
#
# 失敗したチェックを蓄積して全て表示するため、最初の失敗で抜けず continue する。
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAILED=()
PASSED=()
WARNED=()
SKIPPED=()

# SS-201 段階導入: 新規拡張 plugin の既存違反は warning 止まり。
# STRICT_ALL_PLUGINS=1 で error 化 (将来の既定化を見据えた opt-in)。
STRICT_ALL_PLUGINS="${STRICT_ALL_PLUGINS:-0}"

run() {
  local label="$1"; shift
  if "$@"; then
    PASSED+=("$label")
  else
    FAILED+=("$label")
  fi
}

# 段階導入用: 失敗しても STRICT_ALL_PLUGINS=1 でない限り warning 扱い
run_soft() {
  local label="$1"; shift
  if "$@"; then
    PASSED+=("$label")
  elif [ "$STRICT_ALL_PLUGINS" = "1" ]; then
    FAILED+=("$label")
  else
    echo "[WARN] $label failed (段階導入中: STRICT_ALL_PLUGINS=1 で error 化)" >&2
    WARNED+=("$label")
  fi
}

# ── CI workflow の段 (正本: pull_request で起動する .github/workflows/*.yml) ──
# if 条件や GitHub 式 (${{ }}) に依存する段はローカルで評価できないので、理由付きで
# Skipped に出す (黙って捨てない)。pip install の行は環境を書き換えないよう除く。
STEP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/run-ci-checks.XXXXXX")"
trap 'rm -rf "$STEP_DIR"' EXIT
if python3 scripts/extract-ci-workflow-steps.py --out-dir "$STEP_DIR" --skip-jobs "${CI_CHECKS_SKIP_JOBS:-}"; then
  for step in "$STEP_DIR"/*.sh; do
    [ -f "$step" ] || continue
    label="$(sed -n '1s/^# label: //p' "$step")"
    mode="$(sed -n '2s/^# mode: //p' "$step")"
    echo "## $label"
    if [ "$mode" = "soft" ]; then
      run_soft "$label" bash "$step"
    else
      run "$label" bash "$step"
    fi
  done
  while IFS="$(printf '\t')" read -r label reason; do
    [ -n "$label" ] && SKIPPED+=("$label: $reason")
  done < "$STEP_DIR/skipped.tsv"
else
  FAILED+=("extract-ci-workflow-steps (CI の段を書き出せない)")
fi

# ── ローカル追加検査 (CI に無いもの) ──
run "lint-skill-tree (prompt-creator)"     python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir plugins/prompt-creator/skills
# native surface は scope 付きの gate で見る (無条件の build-claude-symlinks.py --check は使わない)
run "native-surfaces --check"              python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --check
# CI は --self-test だけ。被覆率が下がっていないかはローカルで ratchet する
run "harness-coverage-ratchet"             python3 scripts/validate-harness-coverage.py --ratchet

# completeness / frontmatter (全 plugin 段階導入: SS-201)
# harness-creator / prompt-creator は CI の strict 段が正。その他 plugin は
# 既存違反の棚卸しが済むまで run_soft (warning) で観測し breakage を避ける。
for skills_dir in plugins/*/skills; do
  [ -d "$skills_dir" ] || continue
  plugin="$(basename "$(dirname "$skills_dir")")"
  case "$plugin" in
    harness-creator|prompt-creator) continue ;;  # CI の strict 段で検査済み
  esac
  run_soft "lint-skill-tree ($plugin)"         python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir "$skills_dir"
  run_soft "lint-skill-completeness ($plugin)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir "$skills_dir"
  run_soft "validate-frontmatter ($plugin)"    python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir "$skills_dir"
done

# rubric_refs 解決検査は registry/symlink 由来の既存違反棚卸しが済むまで soft 観測
run_soft "lint-rubric-refs-exist"          python3 plugins/skill-governance-lint/scripts/lint-rubric-refs-exist.py

# ── サマリ ──
echo
echo "========================================"
echo "PASS: ${#PASSED[@]} / WARN: ${#WARNED[@]} / SKIP: ${#SKIPPED[@]} / FAIL: ${#FAILED[@]}"
echo "========================================"
if (( ${#WARNED[@]} > 0 )); then
  echo "Warned checks (段階導入中、STRICT_ALL_PLUGINS=1 で error 化):"
  for w in "${WARNED[@]}"; do echo "  - $w"; done
fi
if (( ${#SKIPPED[@]} > 0 )); then
  echo "Skipped CI steps (ローカルで評価できない、または CI_CHECKS_SKIP_JOBS で除外):"
  for s in "${SKIPPED[@]}"; do echo "  - $s"; done
fi
if (( ${#FAILED[@]} > 0 )); then
  echo "Failed checks:"
  for f in "${FAILED[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "All CI-equivalent checks passed."
exit 0
