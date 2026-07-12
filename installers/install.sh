#!/usr/bin/env bash
# install.sh — harness-creator-kit を現在のプロジェクトに展開する
#
# 使い方:
#   bash installers/install.sh [--mode symlink|copy] [--force]
#
# 動作:
#   1. manifest.json を読む (stdlib json のみ。PyYAML 不要)
#   2. .claude/skills/, .claude/config/, scripts/ に必要なディレクトリを作成
#   3. kit内skill/script/configを target にsymlink (or copy)
#   4. 既存と衝突したら conflict_policy に従う

set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(pwd)"
MODE="symlink"
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2;;
    --force) FORCE="true"; shift;;
    --help|-h)
      echo "Usage: bash installers/install.sh [--mode symlink|copy] [--force]"
      exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

echo "==> harness-creator-kit installer"
echo "    kit dir:     $KIT_DIR"
echo "    project dir: $PROJECT_DIR"
echo "    mode:        $MODE"
echo ""

# --- prerequisites ---
if [[ "$KIT_DIR" == "$PROJECT_DIR/creator-kit" ]] || [[ "$KIT_DIR" == "$PROJECT_DIR"* ]]; then
  echo "    detected: kit is inside this project (in-tree)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 required (mac同梱 / linux同梱 / windowsはpython.org公式installer)" >&2
  exit 1
fi

# --- OS判定 (doc/22 cross-platform-runtime 準拠) ---
OS_KIND_RAW="$(uname -s 2>/dev/null || echo unknown)"
case "$OS_KIND_RAW" in
  Darwin)            OS_KIND="mac" ;;
  Linux)             OS_KIND="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS_KIND="windows" ;;
  *)                 OS_KIND="unknown" ;;
esac

# manifest.json 宣言サポートOSとの突き合わせ
SUPPORTED_OS_JSON="$(KIT_MANIFEST="$KIT_DIR/manifest.json" python3 -c "
import json
import os
m=json.load(open(os.environ['KIT_MANIFEST']))
print(','.join(m.get('requirements',{}).get('os',[])))
")"

if [[ "$OS_KIND" == "unknown" ]]; then
  cat >&2 <<MSG
ERROR: OS判定に失敗しました。次のいずれかでお答えください。
  1. macOS
  2. Linux
  3. Windows (PowerShell 5.1+ の場合は install.ps1 を使用してください)

判定に成功するまで install を中断します。
MSG
  exit 2
fi

if [[ ",${SUPPORTED_OS_JSON}," != *",${OS_KIND},"* ]]; then
  cat >&2 <<MSG
ERROR: 検出 OS '${OS_KIND}' は manifest.json の requirements.os=[${SUPPORTED_OS_JSON}] に含まれていません。
       silent failure を避けるため install を中断します。
       Windows をフルサポートで使う場合は: powershell -File installers/install.ps1
MSG
  exit 3
fi

echo "    OS:          ${OS_KIND} (supported: ${SUPPORTED_OS_JSON})"

# Keychain は mac でのみ secrets/ ディレクトリを完全展開する。
# linux/windows では keychain_helper が OS 分岐側のフォールバックで動く。
SKIP_SECRETS_DIR="false"
if [[ "$OS_KIND" != "mac" ]]; then
  if ! command -v security >/dev/null 2>&1; then
    echo "    NOTE: 'security' CLI 不在 → keychain_helper はフォールバック動線で起動 (env/XDG/file fallback)"
  fi
fi

# --- directories ---
mkdir -p \
  "$PROJECT_DIR/.claude/skills" \
  "$PROJECT_DIR/.claude/agents" \
  "$PROJECT_DIR/.claude/config" \
  "$PROJECT_DIR/.claude/logs" \
  "$PROJECT_DIR/scripts/adapters" \
  "$PROJECT_DIR/scripts/secrets" \
  "$PROJECT_DIR/scripts"

# --- helpers ---
link_or_copy() {
  local src="$1" dst="$2" item_mode="${3:-$MODE}"
  if [[ ! -e "$src" ]]; then
    echo "    SKIP (missing in kit): $src"
    return
  fi
  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ "$FORCE" == "true" ]]; then
      rm -rf "$dst"
    else
      echo "    SKIP (exists): $dst"
      return
    fi
  fi
  mkdir -p "$(dirname "$dst")"
  if [[ "$item_mode" == "symlink" ]]; then
    ln -s "$src" "$dst"
    echo "    LINK: $dst -> $src"
  else
    cp -R "$src" "$dst"
    echo "    COPY: $src -> $dst"
  fi
}

# --- parse manifest.json (stdlib only, no PyYAML) ---
MANIFEST_PATH="$KIT_DIR/manifest.json"
if [[ ! -e "$MANIFEST_PATH" ]]; then
  echo "ERROR: $MANIFEST_PATH not found" >&2; exit 1
fi

# --- install skills ---
echo "==> Installing skills"
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for s in m.get('skills', []): print(s['name'])
" "$MANIFEST_PATH" | while read -r skill_name; do
  link_or_copy "$KIT_DIR/skills/$skill_name" "$PROJECT_DIR/.claude/skills/$skill_name"
done

# --- install agents ---
echo "==> Installing agents"
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for a in m.get('agents', []):
    source = a.get('source') or ('agents/' + a['name'] + '.md')
    target = a.get('path') or ('.claude/agents/' + a['name'] + '.md')
    mode = a.get('mode', 'symlink')
    print(source + '\t' + target + '\t' + mode)
" "$MANIFEST_PATH" | while IFS="$(printf '\t')" read -r source target item_mode; do
  link_or_copy "$KIT_DIR/$source" "$PROJECT_DIR/$target" "$item_mode"
done

# --- install scripts ---
echo "==> Installing scripts/adapters"
for f in "$KIT_DIR/scripts/adapters/"*.py; do
  [[ -e "$f" ]] || continue
  link_or_copy "$f" "$PROJECT_DIR/scripts/adapters/$(basename "$f")"
done

echo "==> Installing scripts/secrets"
for f in "$KIT_DIR/scripts/secrets/"*; do
  [[ -e "$f" ]] || continue
  link_or_copy "$f" "$PROJECT_DIR/scripts/secrets/$(basename "$f")"
done

echo "==> Installing scripts/migrate"
mkdir -p "$PROJECT_DIR/scripts/migrate"
for f in "$KIT_DIR/scripts/migrate/"*.py; do
  [[ -e "$f" ]] || continue
  link_or_copy "$f" "$PROJECT_DIR/scripts/migrate/$(basename "$f")"
done

echo "==> Installing scripts/lint+hooks"
for f in "$KIT_DIR/scripts/"*.py; do
  [[ -e "$f" ]] || continue
  link_or_copy "$f" "$PROJECT_DIR/scripts/$(basename "$f")"
done

# --- install config ---
echo "==> Installing config"
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for c in m.get('config', []):
    print(c['source'] + '\t' + c['target'] + '\t' + c.get('mode', 'symlink'))
" "$MANIFEST_PATH" | while IFS="$(printf '\t')" read -r source target item_mode; do
  link_or_copy "$KIT_DIR/$source" "$PROJECT_DIR/$target" "$item_mode"
done

echo ""
echo "==> Post-install checks"

# output-routing.json の正本配備チェック (設計書31)
ROUTING_EXAMPLE="$PROJECT_DIR/.claude/config/output-routing.json.example"
ROUTING_REAL="$PROJECT_DIR/.claude/config/output-routing.json"
if [[ -e "$ROUTING_EXAMPLE" && ! -e "$ROUTING_REAL" ]]; then
  cat >&2 <<MSG
WARN: output-routing.json が未配備です (設計書31 §5.1)。
      adapter dispatch を実運用するには、以下を実施してください:
        cp "$ROUTING_EXAMPLE" "$ROUTING_REAL"
        # database_id / webhook URL / keychain:service/account を編集
      未配備時、ref-output-routing は defaults.adapter (local) にフォールバックします。
MSG
fi

# rubric-registry.json の L1 整合性チェック (設計書29)
REGISTRY="$PROJECT_DIR/.claude/config/rubric-registry.json"
if [[ -e "$REGISTRY" ]]; then
  python3 - <<'PY' "$REGISTRY" "$PROJECT_DIR" || true
import json, os, sys
registry_path, project_root = sys.argv[1], sys.argv[2]
with open(registry_path) as f:
    reg = json.load(f)
missing = []
for r in reg.get("rubrics", []):
    p = os.path.join(project_root, r["rubric"])
    if not os.path.exists(p):
        missing.append((r["domain"], r["rubric"]))
if missing:
    print("WARN: rubric-registry.json に未配置の L1 rubric があります:", file=sys.stderr)
    for d, p in missing:
        print(f"      domain={d}  path={p}", file=sys.stderr)
PY
fi

echo ""
echo "==> Done."
echo "    Run: ls -la .claude/skills/  # to verify symlinks"
echo "    Next: copy .claude/config/output-routing.json.example to output-routing.json and customize"
echo "    Next: review .claude/config/rubric-registry.json for L1 domain rubrics (設計書29)"
