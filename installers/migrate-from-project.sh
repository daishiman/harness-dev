#!/usr/bin/env bash
# migrate-from-project.sh
#
# 現プロジェクト内のメタskill実体を creator-kit/ 配下に移動し、
# .claude/skills/ 等にはsymlinkを張り直す。
#
# 用途: 既存プロジェクトを kit ベースに移行する (1回のみ実行)
#
# 使い方:
#   bash creator-kit/migrate-from-project.sh [--dry-run]

set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$KIT_DIR/.." && pwd)"
DRY="false"

[[ "${1:-}" == "--dry-run" ]] && DRY="true"

echo "==> Migrating project assets into kit"
echo "    project: $PROJECT_DIR"
echo "    kit:     $KIT_DIR"
echo "    dry-run: $DRY"

mkdir -p "$KIT_DIR/skills" "$KIT_DIR/scripts/adapters" "$KIT_DIR/scripts/secrets" "$KIT_DIR/scripts" "$KIT_DIR/config"

do_move() {
  local src="$1" dst="$2"
  if [[ ! -e "$src" ]]; then
    echo "    SKIP (not found): $src"
    return
  fi
  if [[ -e "$dst" ]]; then
    echo "    SKIP (kit already has): $dst"
    return
  fi
  if [[ "$DRY" == "true" ]]; then
    echo "    [dry-run] MOVE: $src -> $dst"
    echo "    [dry-run] LINK: $src -> $dst"
  else
    mv "$src" "$dst"
    ln -s "$dst" "$src"
    echo "    MOVED + LINKED: $src -> $dst"
  fi
}

# 移行対象skills (manifest.json から動的取得; bash 3.2 互換)
SKILLS=()
while IFS= read -r line; do SKILLS+=("$line"); done < <(python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for s in m.get('skills', []): print(s['name'])
" "$KIT_DIR/manifest.json")
for s in "${SKILLS[@]}"; do
  do_move "$PROJECT_DIR/.claude/skills/$s" "$KIT_DIR/skills/$s"
done

# scripts (adapters/secrets/lint/hooks)
for f in "$PROJECT_DIR/scripts/adapters/"*.py; do
  [[ -e "$f" ]] || continue
  do_move "$f" "$KIT_DIR/scripts/adapters/$(basename "$f")"
done
for f in "$PROJECT_DIR/scripts/secrets/"*; do
  [[ -e "$f" ]] || continue
  do_move "$f" "$KIT_DIR/scripts/secrets/$(basename "$f")"
done
for f in "$PROJECT_DIR/scripts/"*.py; do
  [[ -e "$f" ]] || continue
  case "$(basename "$f")" in
    lint-*|hook-*|validate-*) do_move "$f" "$KIT_DIR/scripts/$(basename "$f")";;
    *) echo "    KEEP (project-owned): $f";;
  esac
done
for f in "$PROJECT_DIR/.claude/skills/scripts/"*.py; do
  [[ -e "$f" ]] || continue
  case "$(basename "$f")" in
    lint-*|hook-*|validate-*) do_move "$f" "$KIT_DIR/scripts/$(basename "$f")";;
    *) echo "    KEEP (project-owned): $f";;
  esac
done

# config
for f in "$PROJECT_DIR/.claude/config/"*; do
  [[ -e "$f" ]] || continue
  do_move "$f" "$KIT_DIR/config/$(basename "$f")"
done
if [[ -e "$PROJECT_DIR/references/governance-params.json" ]]; then
  do_move "$PROJECT_DIR/references/governance-params.json" "$KIT_DIR/config/governance-params.json.example"
fi

echo ""
echo "==> Migration $( [[ \"$DRY\" == 'true' ]] && echo '(dry-run) ' )done."
echo "    Verify: ls -la .claude/skills/"
echo "    Commit: git add creator-kit && git commit -m 'migrate meta-skills to kit'"
