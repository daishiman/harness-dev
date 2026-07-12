---
name: ref-cross-platform-runtime
description: 他Skillが host OS で分岐するとき、OS判定に失敗したときに読む。
disable-model-invocation: false
user-invocable: false
kind: ref
owner: team-platform
since: 2026-05-19
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/22-cross-platform-runtime.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L0
---

# ref-cross-platform-runtime

## Purpose & Output Contract
Mac / Linux / Windows / unknown を横串で扱うための共通契約を提供する。
本 ref を import した skill は次の dict を呼び出し元へ返せる:

```json
{
  "os": "mac|linux|windows|unknown",
  "shell": "bash|powershell",
  "python_available": true,
  "fallback_used": false
}
```

## Boundary
- **責務**: OS 判定動線・フォールバック文面・no-deps 原則の宣言
- **非責務**: 個別 secret 取得（→ `scripts/cross_platform_secret.py` に委譲）

## Key Rules
1. 判定キー: `uname -s` または `ver`。両方失敗 → unknown
2. unknown のとき自走しない。**必ず** ユーザーへ問い合わせる（後述プロンプト）
3. ユーザー宣言値は **会話スコープのみ** に保持。長期記憶へ焼き込まない
4. 追加導入を要求する CLI を呼ばない（jq, yq, rg, requests, PyYAML 禁止）

## Steps
参照用。手順なし。本文を import する skill 側が以下を組み込むこと。

### OS判定 (skill 本文に貼る雛形)
```bash
OS_KIND="$(uname -s 2>/dev/null || echo unknown)"
case "$OS_KIND" in
  Darwin) os=mac ;;
  Linux)  os=linux ;;
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  *) os=unknown ;;
esac
```

### unknown フォールバックプロンプト
```text
お使いの OS を判定できませんでした。次のいずれかでお答えください。
  1. macOS
  2. Linux
  3. Windows
回答に応じて、以降は os=mac / os=linux / os=windows で分岐します。
```

## Gotchas
- `uname` が無い純 Windows コマンドプロンプトでは `ver` を使う
- WSL は uname=Linux で返るので Linux 経路で扱う（user に確認しない）
- PowerShell では `$IsWindows / $IsMacOS / $IsLinux` 自動変数を使う

## Additional Resources
- `references/os-matrix.md` — OS × shell × python × 判定コマンドの表
- `references/forbidden-clis.md` — no-deps 原則で禁止される CLI 一覧
- 設計書 22 章 — クロスプラットフォームランタイム正本
- `creator-kit/scripts/cross_platform_secret.py` — secret OS 分岐実装例
