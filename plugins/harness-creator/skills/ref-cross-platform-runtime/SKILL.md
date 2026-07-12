---
name: ref-cross-platform-runtime
description: 他Skillが host OS で分岐するとき、OS判定に失敗したときに読む。
effect: none
disable-model-invocation: false
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
owner: team-platform
since: 2026-05-19
version: 0.1.0
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/22-cross-platform-runtime.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L0
responsibility_refs: [prompts/R1-search-summarize.md]
---

# ref-cross-platform-runtime

## Purpose & Output Contract
Python 標準ライブラリを実行基盤の正本とし、Mac / Linux / Windows / unknown を横串で扱うための共通契約を提供する。
本 ref を import した skill は次の dict を呼び出し元へ返せる:

```json
{
  "os": "mac|linux|windows|unknown",
  "python_cmd": "python3|python|unknown",
  "python_available": true,
  "fallback_used": false
}
```

## Boundary
- **責務**: OS 判定動線・フォールバック文面・no-deps 原則の宣言
- **非責務**: 個別 secret 取得（→ `scripts/cross_platform_secret.py` に委譲）

## Key Rules
1. 実行は Python 標準ライブラリを既定にする。生成・検証・adapter・hook は `.py` を正本とし、`.js` / `.sh` を新規生成しない。
2. Node.js / npm / npx / yarn / pnpm を必須化しない。既存の Node 前提が見つかった場合は Python stdlib に置換する。
3. Bash は Claude/Codex 側の tool 名として `python3 ...` を起動する場合だけ許容する。成果物として shell script を配布しない。
4. OS 判定は Python の `platform` / `shutil.which` を優先する。判定不能または Python 不在なら自走せずユーザーへ問い合わせる。
5. ユーザー宣言値は **会話スコープのみ** に保持。長期記憶へ焼き込まない。
6. 追加導入を要求する CLI を呼ばない（jq, yq, rg, node, npm, requests, PyYAML 禁止）。

## Steps
参照用。手順なし。本文を import する skill 側が以下を組み込むこと。

### Runtime 判定 (skill 本文に貼る雛形)
```python
import platform
import shutil

system = platform.system().lower()
os_kind = {"darwin": "mac", "linux": "linux", "windows": "windows"}.get(system, "unknown")
python_cmd = shutil.which("python3") or shutil.which("python") or "unknown"
python_available = python_cmd != "unknown"
```

### unknown フォールバックプロンプト
```text
Python 実行環境または OS を判定できませんでした。次を教えてください。
  1. OS: macOS / Linux / Windows
  2. Python 起動コマンド: python3 / python / 未インストール
回答に応じて、以降は os=mac|linux|windows、python_cmd=python3|python で分岐します。
```

## Gotchas
- macOS 向けでも `bash` 前提の `.sh` を配布しない。Python から `pathlib`, `shutil`, `subprocess` を使う。
- WSL は `platform.system() == "Linux"` として扱う（ユーザーに確認しない）。
- Windows では PowerShell 固有構文を本文に直書きせず、Python 実装に閉じる。

## Additional Resources
- `references/os-matrix.md` — OS × Python × 判定マトリクス
- `references/forbidden-clis.md` — no-deps 原則で禁止される CLI 一覧
- 設計書 22 章 — クロスプラットフォームランタイム正本
- `plugins/skill-governance-automation/scripts/cross_platform_secret.py` — secret OS 分岐実装例
