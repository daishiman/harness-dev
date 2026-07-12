#!/usr/bin/env bash
# uninstall.sh — kit由来のsymlinkを外す (実体ファイルは削除しない)
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(pwd)"

echo "==> Removing kit symlinks from $PROJECT_DIR"

remove_if_symlink_to_kit() {
  local path="$1"
  if [[ -L "$path" ]]; then
    target="$(readlink "$path")"
    case "$target" in
      *creator-kit/*)
        rm "$path"
        echo "    REMOVED: $path"
        ;;
      *)
        echo "    KEEP (not kit-owned): $path -> $target"
        ;;
    esac
  fi
}

# skills (stdlib only, no PyYAML)
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for s in m.get('skills', []): print(s['name'])
" "$KIT_DIR/manifest.json" | while read -r skill_name; do
  remove_if_symlink_to_kit "$PROJECT_DIR/.claude/skills/$skill_name"
done

# scripts
for f in "$PROJECT_DIR/scripts/adapters/"* "$PROJECT_DIR/scripts/secrets/"* "$PROJECT_DIR/scripts/"*; do
  [[ -e "$f" || -L "$f" ]] || continue
  remove_if_symlink_to_kit "$f"
done

# config
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
for c in m.get('config', []): print(c['target'])
" "$KIT_DIR/manifest.json" | while read -r target; do
  remove_if_symlink_to_kit "$PROJECT_DIR/$target"
done

echo "==> Done. Project-owned files preserved."
