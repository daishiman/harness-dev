#!/bin/bash
# AIDDキットの編集元を、このリポジトリの実行時配置へ反映する管理者用スクリプト。
# Codex Skillは .agents/skills、custom agent TOMLは .codex/agents へ入る。

set -Ee

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd -P)

echo "AIDDキットをプロジェクトへ反映します: $PROJECT_ROOT"
echo "  Codex skills: $PROJECT_ROOT/.agents/skills"
echo "  Codex custom agents: $PROJECT_ROOT/.codex/agents"
echo ""

AIDD_TARGET_HOME="$PROJECT_ROOT" \
AIDD_CODEX_TARGET="$PROJECT_ROOT/.codex" \
bash "$SCRIPT_DIR/install-mac.command" "$@"

if [ -x "$SCRIPT_DIR/doctor-codex-layout.sh" ]; then
  echo ""
  if ! AIDD_PROJECT_ROOT="$PROJECT_ROOT" "$SCRIPT_DIR/doctor-codex-layout.sh"; then
    echo "[注意] projectへの反映は完了しましたが、user scopeとの衝突があります。"
    echo "       ファイルは自動削除していません。CODEX-PLACEMENT.mdに従って使うscopeを1つに決めてください。"
  fi
fi
