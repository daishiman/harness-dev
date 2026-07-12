# INSTALL_HOOKS — Hook 有効化手順書

## 目的

`plugins/skill-governance-hooks/scripts/hook-guard-rubric.py` および `hook-verify-evaluator-json.py`
を中心とする hook 群を、`.example` テンプレートから実発動可能な状態へ昇格させる
ための手動セットアップ手順を記述する。

対象 hook（`plugins/skill-governance-config/config/claude-settings-hooks.json.example` で定義済み）:

- **PreToolUse** (`Write|Edit`): `hook-guard-rubric.py`
- **FileChanged** (`SKILL.md`): `hook-validate-skill-md.py`
- **SubagentStop**: `hook-verify-evaluator-json.py`
- **TaskCreated**: `hook-check-file-ownership.py`
- **PreCompact**: `hook-handoff.py`
- **PostCompact**: `hook-post-compact.py`

## 重要な制約

**本手順書は自動実行しない**。`.claude/settings.json` および
`.claude/settings.local.json` は個人環境への影響が大きいため、必ずユーザー自身が
下記コマンドを手動実行すること。スキル / エージェントから直接これらのファイルを
書き換えてはならない。

## 前提

- `python3` (3.9+) が PATH 上にある。追加ライブラリは不要。
- カレントディレクトリは対象プロジェクトのルート

## 手順

### Step 1: 既存 `.claude/settings.json` のバックアップ

```bash
mkdir -p .claude
if [ -f .claude/settings.json ]; then
  cp .claude/settings.json ".claude/settings.json.bak.$(date +%Y%m%d-%H%M%S)"
fi
```

### Step 2: テンプレートを deep-merge

`plugins/skill-governance-config/config/claude-settings-hooks.json.example` の `hooks` キーを既存
設定にマージする。Python 標準ライブラリ `json` だけを使い、既存キー
（permissions / env など）は保持する。

```bash
TEMPLATE=plugins/skill-governance-config/config/claude-settings-hooks.json.example
TARGET=.claude/settings.json

# 既存が無ければ空オブジェクトから開始
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

python3 - "$TARGET" "$TEMPLATE" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
template = Path(sys.argv[2])
current = json.loads(target.read_text(encoding="utf-8"))
incoming = json.loads(template.read_text(encoding="utf-8"))

def deep_merge(base, update):
    result = dict(base)
    for key, value in update.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

merged = deep_merge(current, incoming)
target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

注意: `hooks.PreToolUse` 等の配列は上記手順では**置換**される。既存 hook を
温存したい場合は、配列を連結すること。例:

```bash
python3 - "$TARGET" "$TEMPLATE" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
template = Path(sys.argv[2])
current = json.loads(target.read_text(encoding="utf-8"))
incoming = json.loads(template.read_text(encoding="utf-8"))
merged = dict(current)
merged.update(incoming)
merged["hooks"] = dict(current.get("hooks", {}))
for hook_name, entries in incoming.get("hooks", {}).items():
    merged["hooks"][hook_name] = current.get("hooks", {}).get(hook_name, []) + entries
target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

### Step 3: hook スクリプトのパス確認

テンプレート内 `command` は `python3 scripts/hook-guard-rubric.py` のように
**カレントディレクトリからの相対パス**を前提とする。Claude Code 起動時の cwd が
harness ルートでない場合は、`scripts/` への絶対パスに書き換えること。

```bash
# 例: 絶対パスへの一括書き換え
ABS=$(pwd)/scripts
python3 - "$TARGET" "$ABS" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
abs_scripts = sys.argv[2].rstrip("/")
data = json.loads(target.read_text(encoding="utf-8"))
for event_entries in data.get("hooks", {}).values():
    for matcher in event_entries:
        for hook in matcher.get("hooks", []):
            command = hook.get("command", "")
            hook["command"] = command.replace("scripts/", abs_scripts + "/")
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

## 検証

### A) Claude Code 内から確認

```
/config
```

を実行し、`hooks` セクションに以下が表示されることを確認:

- PreToolUse: `hook-guard-rubric.py`
- FileChanged: `hook-validate-skill-md.py`
- SubagentStop: `hook-verify-evaluator-json.py`
- TaskCreated: `hook-check-file-ownership.py`

### B) JSON 構文チェック

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo "OK: valid JSON"
```

### C) 実発動確認

`plugins/harness-creator/skills/ref-skill-design-rubric/rubric.json` を Edit してみて、
PreToolUse hook が走り `hook-guard-rubric.py` のメッセージが出ることを確認。

## ロールバック

### 完全ロールバック（バックアップから復元）

```bash
LATEST_BAK=$(ls -t .claude/settings.json.bak.* 2>/dev/null | head -n1)
if [ -n "$LATEST_BAK" ]; then
  cp "$LATEST_BAK" .claude/settings.json
  echo "Restored from $LATEST_BAK"
else
  echo "No backup found; remove .claude/settings.json manually if needed"
fi
```

### 部分ロールバック（hooks キーだけ削除）

```bash
python3 - .claude/settings.json <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
data = json.loads(target.read_text(encoding="utf-8"))
data.pop("hooks", None)
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

### 個別 hook の無効化

`.claude/settings.json` を開き、対象 hook エントリ 1 件を削除するか、`command`
を `: # disabled` に書き換える。

## 参考

- `plugins/skill-governance-config/config/claude-settings-hooks.json.example` — 正本テンプレート
- `plugins/skill-governance-hooks/scripts/hook-*.py` — hook 実体
- `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` — rubric governance との関係
