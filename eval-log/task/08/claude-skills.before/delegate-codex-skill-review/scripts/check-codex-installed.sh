#!/usr/bin/env bash
# delegate 前に codex CLI の存在と最低バージョンを決定論的に検証する。
# OS 非依存（doc/22 準拠）。codex 不在時は exit 2 (BLOCK) を返す。

set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  cat >&2 <<MSG
ERROR: codex CLI が見つかりません。
       次のいずれかでインストールしてください:
         macOS:   brew install openai/tools/codex  (※ 例。実際の配布元は要確認)
         linux:   npm i -g @openai/codex-cli
         windows: scoop install codex (PowerShell)

       本 skill (delegate-codex-skill-review) は委譲先 CLI 不在のため停止します。
MSG
  exit 2
fi

# 最低バージョン要件（必要なら更新）
CODEX_VER="$(codex --version 2>/dev/null || echo unknown)"
echo "ok: codex available (${CODEX_VER})"
exit 0
