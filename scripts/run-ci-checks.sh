#!/usr/bin/env bash
# CI と同等の機械チェックをローカルで一括実行する。
# pre-push hook / 手動実行 (bash scripts/run-ci-checks.sh) の双方から呼ばれる SSOT。
# 内容の良し悪し (LLM 自由度領域) は判定対象外。構造・命名・SSOT・symlink drift のみ。
#
# 失敗したチェックを蓄積して全て表示するため、最初の失敗で抜けず continue する。
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAILED=()
PASSED=()
WARNED=()

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

# ── 構造・命名・frontmatter ──
run "lint-script-naming"                   python3 scripts/lint-script-naming.py
run "lint-skill-description (harness-creator)" python3 scripts/lint-skill-description.py
run "lint-dependency-direction (harness-creator)" python3 scripts/lint-dependency-direction.py --skills-dir plugins/harness-creator/skills
run "lint-dependency-direction (all)"      python3 scripts/lint-dependency-direction.py --skills-dir plugins
run "lint-external-refs"                   python3 scripts/lint-external-refs.py --skills-dir plugins/harness-creator/skills --allowed-prefix .claude/ --allowed-prefix eval-log/ --allowed-prefix references/ --allowed-prefix plugins/ --allowed-prefix scripts/ --allowed-prefix doc/ --fail-on-external

# ── SSOT / drift ──
run "lint-feedback-protocol --strict"      python3 scripts/lint-feedback-protocol.py --strict
run "lint-content-review (all)"            python3 scripts/lint-content-review.py --all
run "lint-live-trial-verdict (all)"        python3 scripts/lint-live-trial-verdict.py --all
run "lint-feedback-contract (all)"         python3 scripts/lint-feedback-contract.py --all
run "lint-vendored-ssot"                   python3 scripts/lint-vendored-ssot.py
run "lint-legacy-plugin-name"              python3 scripts/lint-legacy-plugin-name.py
run "lint-runtime-portability"             python3 scripts/lint-runtime-portability.py
run "check-scripts-drift"                  bash scripts/check-scripts-drift.sh
run "build-claude-symlinks --check"        python3 scripts/build-claude-symlinks.py --check
# ── discovery 派生台帳 parity (roster / llm-coverage が discovery と一致するか) ──
# governance-check.yml と対称。この2つが run-ci-checks 非包含だと改名/skill 変更時に
# pre-push を素通りして CI で初めて露見する (2026-07-02 harness-creator 改名で criteria
# roster STALE を CI が検出・pre-push 緑だった事故の恒久対策)。両生成器を書き込みなし
# モード (roster=引数なし / llm-coverage=--check) で走らせ stale を先行 fail-closed 検出。
run "criteria-roster-parity"               python3 tests/criteria/build_criteria_roster.py
run "llm-coverage-parity"                  python3 scripts/validate-llm-coverage.py --all --check
run "lint-ssot-duplication --strict"       python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py --plugin-dir plugins/harness-creator --strict
run "lint-goal-seek --self-test"           python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py --self-test
run "lint-goal-seek conformance"           python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py --skills-dir plugins/harness-creator/skills

# ── completeness / frontmatter (harness-creator + prompt-creator) ──
run "lint-skill-tree (harness-creator)"      python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir plugins/harness-creator/skills
run "lint-skill-tree (prompt-creator)"     python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-completeness (harness-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir plugins/harness-creator/skills
run "validate-frontmatter --self-test"     python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --self-test
run "validate-frontmatter (harness-creator)" python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir plugins/harness-creator/skills
run "validate-frontmatter (prompt-creator)" python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-name (prompt-creator)"     python3 plugins/skill-governance-lint/scripts/lint-skill-name.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-description (prompt-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-description.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-completeness (prompt-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir plugins/prompt-creator/skills

# ── completeness / frontmatter (全 plugin 段階導入: SS-201) ──
# harness-creator / prompt-creator は上の strict 行が正。その他 plugin は
# 既存違反の棚卸しが済むまで run_soft (warning) で観測し breakage を避ける。
for skills_dir in plugins/*/skills; do
  [ -d "$skills_dir" ] || continue
  plugin="$(basename "$(dirname "$skills_dir")")"
  case "$plugin" in
    harness-creator|prompt-creator) continue ;;  # 上で strict 検査済み
  esac
  run_soft "lint-skill-tree ($plugin)"         python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir "$skills_dir"
  run_soft "lint-skill-completeness ($plugin)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir "$skills_dir"
  run_soft "validate-frontmatter ($plugin)"    python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir "$skills_dir"
done

# ── rubric 正本-派生照合 (elegant-review run-20260610-175852 で修復・配線) ──
# check-rubric-sync は 2026-05-24 に「チェックリスト化のみで実体未配線」のまま腐った前例があり、
# 配線漏れ自体が今回の根本原因 (SS-205/SS-213)。strict 配線で再発を機械遮断する。
run "check-rubric-sync (L0/L2 rubric drift)" python3 plugins/skill-governance-lint/scripts/check-rubric-sync.py
# LS-215: governance lint scripts 自身の削除済み root (creator-kit) 残存参照を fail-closed 検出
run "lint-stale-root-refs (governance scripts)" python3 plugins/skill-governance-lint/scripts/lint-path-canonical.py --scripts-dir plugins/skill-governance-lint/scripts
# rubric_refs 解決検査は registry/symlink 由来の既存違反棚卸しが済むまで soft 観測
run_soft "lint-rubric-refs-exist"          python3 plugins/skill-governance-lint/scripts/lint-rubric-refs-exist.py

# ── governance-lint 回帰テスト (MD-208/LS-211/LS-215 の挙動保証) ──
if python3 -c "import pytest" 2>/dev/null; then
  run "pytest (governance-lint regressions)" python3 -m pytest plugins/skill-governance-lint/tests/ -q
else
  echo "[Warn] pytest 不在のため governance-lint 回帰テストを skip (CI では harness-creator-kit-ci.yml が実行)"
fi

# ── knowledge loop ──
run "lint-knowledge-loop --self-test"      python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py --self-test
run "lint-knowledge-loop --store-only"     python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py plugins/harness-creator --store-only --strict

# ── manifest sanity (jq) ──
if command -v jq >/dev/null 2>&1; then
  run "marketplace.json plugins>=1" jq -e '.plugins | length >= 1' .claude-plugin/marketplace.json
  for manifest in plugins/*/.claude-plugin/plugin.json; do
    run "manifest:$manifest" jq -e '.name and .version and .description' "$manifest"
  done
else
  echo "[WARN] jq 未インストールにつき manifest 検証 skip"
fi

# ── marketplace ↔ plugins / bundles 双方向整合 (MK-001..003 / BD-001) ──
# 実体ディレクトリ起点で「全 plugin が marketplace.json + bundles.json 両方に登録」を
# fail-closed 検査する。配線漏れで腐ると登録漏れ (notion-gmail-send 未表示) を永久に
# 見逃す自己強化ループに陥るため hard 配線で再発を機械遮断する (F4/F5)。
run "validate-plugin-completeness (MK/BD)" python3 scripts/validate-plugin-completeness.py

# ── test discovery coverage (全 test が CI 実行で到達するか) ──
# elegant-review 2026-06-30 (LS-F1/SS-02/SS-05): tests/・plugins/ 以外 (scripts/・doc/・
# repo-root 直下) に置いた test は CI の探索 2 機構の境界外で無言未実行になりうる。
# 実 test 集合 ⊆ CI 到達集合 を fail-closed 検査し silent-skip を loud failure 化する。
run "lint-test-discovery-coverage"         python3 scripts/lint-test-discovery-coverage.py

# ── サマリ ──
echo
echo "========================================"
echo "PASS: ${#PASSED[@]} / WARN: ${#WARNED[@]} / FAIL: ${#FAILED[@]}"
echo "========================================"
if (( ${#WARNED[@]} > 0 )); then
  echo "Warned checks (段階導入中、STRICT_ALL_PLUGINS=1 で error 化):"
  for w in "${WARNED[@]}"; do echo "  - $w"; done
fi
if (( ${#FAILED[@]} > 0 )); then
  echo "Failed checks:"
  for f in "${FAILED[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "All CI-equivalent checks passed."
exit 0
