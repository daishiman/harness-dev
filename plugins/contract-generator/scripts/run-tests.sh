#!/usr/bin/env bash
# Contract generator plugin self-test entry.
# WHY: lint-plugin-manifest.py を CI/pre-commit から直接呼ぶと引数知識が外部に
#      漏れて Loop B (改善の改善) が切れる。本スクリプトに 6 段検査
#      (manifest lint / lib AST parse / check_intermediate dry-run / import smoke /
#       config SSOT lint / template scan)を集約し、CI 側は entry を 1 行知れば済む状態にする。
# Called by CI/pre-commit. POSIX-ish bash (mac/linux). No pip deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/6] plugin.json manifest lint"
python3 scripts/lint-plugin-manifest.py --plugin-root "$ROOT"

echo "[2/6] lib AST parse"
for f in lib/*.py; do
  # WHY: AST parse は import 副作用なしで構文崩壊を最短検出できる
  python3 -c "import ast,sys; ast.parse(open('$f',encoding='utf-8').read())"
done

echo "[3/6] check_intermediate dry-run (no eval-log required)"
# WHY: eval-log が空でも skill 名引数を受理することを確認 (--eval-log-dir で隔離)
# --allow-missing で eval-log 不在を warning に降格 (exit 0)。set -e 下でも握り潰さず厳格運用。
python3 lib/check_intermediate.py run-contract-generate --eval-log-dir /tmp --allow-missing

echo "[4/6] feedback_loop import smoke"
PYTHONPATH=lib python3 -c "import feedback_loop, check_intermediate, engine, goal_seek_log; print('OK')"

echo "[5/6] config SSOT lint (設定の文書/コード整合)"
# WHY: 設定の事実(置き場所/優先順位/ファイル名/段数)が複数文書に複製される構造は
#      1 箇所の変更で残りがずれる。表現層の整合を機械検証しドリフトを再発防止する。
python3 scripts/lint-config-ssot.py --plugin-root "$ROOT"

# 正本=~/.config/contract-generator/google-config.json(XDG準拠)。後方互換として
# XDG 配下の旧ドット名・cwd 直下/親の .google-config.json も発火条件に含める。
CG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator"
if [[ -n "${GOOGLE_CONFIG_PATH:-}" \
      || -f "$CG_CONFIG_DIR/google-config.json" \
      || -f "$CG_CONFIG_DIR/.google-config.json" \
      || -f .google-config.json \
      || -f ../../.google-config.json ]]; then
  echo "[6/6] template mapping scan (Drive-backed; requires google-config.json + Keychain)"
  python3 lib/scan_template.py --type individual >/tmp/contract-generator-scan-individual.log
  python3 lib/scan_template.py --type corporate >/tmp/contract-generator-scan-corporate.log
  tail -n 6 /tmp/contract-generator-scan-individual.log
  tail -n 6 /tmp/contract-generator-scan-corporate.log
else
  echo "[6/6] template mapping scan skipped (google-config.json not found)"
fi

echo "All contract-generator checks passed."
