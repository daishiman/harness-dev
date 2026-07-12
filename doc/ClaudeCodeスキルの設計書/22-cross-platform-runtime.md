# 22. クロスプラットフォームランタイム

## 責務

このファイルは、Skill 群が **macOS / Linux / Windows のどれで実行されても同じ契約**を返すための実行基盤を定義する。
原則は次の 3 点。

1. **追加ライブラリ導入なし**で動く (`pip install` / `npm i` / `brew install` などを Skill が要求しない)。ただし Windows では Python 実行系そのものが無い場合があるため、PowerShell 経路またはユーザー確認フォールバックを必須にする。
2. **OS 差分は Skill 側で吸収**し、ユーザーには単一 interface を見せる
3. OS 判定に失敗したら **Claude がユーザーに OS を尋ねる**フォールバックを必ず持つ

この責務を背負う共有 Skill が `ref-cross-platform-runtime` であり、本ファイルはその仕様書である。

## OS 判定マトリクス

Skill 内で OS を識別する方法を次に固定する。判定キーが揃わない場合は「未判定」とみなし、後述のフォールバックへ落とす。

| OS      | shell 既定           | 判定コマンド            | 期待 stdout (前方一致) | python3 同梱 |
| ------- | -------------------- | ----------------------- | ---------------------- | ------------ |
| macOS   | zsh / bash           | `uname -s`              | `Darwin`               | あり (3.x)   |
| Linux   | bash                 | `uname -s`              | `Linux`                | あり         |
| Windows | PowerShell 5.1+      | `ver` または `$PSVersionTable.PSVersion` | `Microsoft Windows` を含む | なし (要インストール) |
| 未判定  | -                    | 上記いずれも失敗        | -                      | -            |

Skill 共通プリアンブル (14 章) で次の 1 行を `!` 注入する。

```markdown
!`uname -s 2>/dev/null || ver`
```

この出力を `<important if="os=...">` 分岐で本文側が読む。

## 許可 CLI ホワイトリスト (no-deps 原則)

Skill が呼び出してよい CLI は **OS 標準同梱 or Claude Code 標準同梱**に限る。
追加導入を要求する CLI を本文に書いてはならない。

| カテゴリ            | macOS                | Windows                  | 備考                                  |
| ------------------- | -------------------- | ------------------------ | ------------------------------------- |
| シェル              | `zsh` / `bash` / `sh`| `powershell` / `cmd`     | PowerShell は 5.1 を下限              |
| OS 情報             | `uname` / `sw_vers`  | `ver` / `systeminfo`     |                                       |
| ファイル操作        | `ls` / `cp` / `mv`   | `dir` / `copy` / `move`  | Skill は Python ラッパー経由を推奨    |
| バージョン管理      | `git`                | `git`                    | 双方とも標準扱い (Xcode CLT / Git for Windows) |
| Python (任意)       | `python3` (同梱)     | `python` (要 install)    | Win 不在時はフォールバック必須        |
| Claude Code 標準    | `gh` (任意)          | `gh` (任意)              | Skill 必須にしない                    |

禁止例:
- `jq`, `yq`, `rg`, `fd`, `bat` — 便利だが OS 標準ではない
- Python の `requests` / `pyyaml` 等 — 標準ライブラリ外
- Node.js / npm パッケージ全般

## macOS pristine state と creator-kit

creator-kit は「追加導入なしの macOS」で動くことを配布条件とする。macOS 側の最低前提は `/bin/bash` 3.2、`/usr/bin/python3`、`security`、`git` のみであり、`jq` / `yq` / `PyYAML` / `requests` を必要としてはならない。

この制約を保つため、機械処理する構成ファイルは JSON を正本とし、Python 標準ライブラリ `json` で読む。例外は Claude Code 仕様としての `SKILL.md` frontmatter と、GitHub Actions workflow (`.yml`) など外部仕様が要求するファイルに限定する。YAML という形式そのものを一般禁止するのではなく、実行時依存としての PyYAML と、Bash 内での ad hoc YAML 解析を禁止する。

言語選択の詳細は 28 章と `creator-kit/CONVENTIONS.md` に委譲する。要点は、Bash が install / uninstall / migrate などの lifecycle を担い、Python が lint / validation / adapter / secret helper などの structured logic を担う、という2層モデルである。

## OS 分岐パターン

### bash 版 (Mac / Linux)

```bash
OS_KIND="$(uname -s 2>/dev/null || echo unknown)"
case "$OS_KIND" in
  Darwin) echo "mac" ;;
  Linux)  echo "linux" ;;
  *)      echo "unknown" ;;
esac
```

### PowerShell 版 (Windows)

```powershell
$osKind = if ($IsWindows -or $env:OS -like '*Windows*') { 'windows' }
          elseif ($IsMacOS) { 'mac' }
          elseif ($IsLinux) { 'linux' }
          else { 'unknown' }
Write-Output $osKind
```

### Skill 本文での分岐 (推奨)

```markdown
## Runtime

!`uname -s 2>/dev/null || ver`

<important if="os=mac">
Mac の場合は `python3 scripts/build_skill.py` を呼ぶ。
</important>

<important if="os=windows">
Windows の場合は `powershell -File scripts\build_skill.ps1` を呼ぶ。
</important>

<important if="os=unknown">
OS 判定に失敗した。後述「OS 確認プロンプト」を起動する。
</important>
```

## フォールバック動線 (OS 未判定時)

判定コマンドが両方失敗、もしくは想定外文字列が返った場合、Claude は自走を停止し
**必ず**ユーザーへ問い合わせる。文面例:

> お使いの OS を判定できませんでした。次のいずれかでお答えください。
> 1. macOS
> 2. Windows
> 3. Linux
>
> 回答に応じて、以降の Skill は対応する分岐 (`os=mac` / `os=windows` / `os=linux`) で実行します。

回答後の挙動:

- ユーザー回答を `OS_KIND_USER_DECLARED` として **その会話のみ**保持する
- 長期記憶やプロジェクト設定には書き込まない (ユーザーが別 PC に切り替える可能性がある)
- 同会話内で再度判定が必要になったら、まず CLI 判定 → 失敗時のみ宣言値を採用

## 実装例: Python 3 標準ライブラリで SKILL.md を生成

**目的**: Mac/Win で同一スクリプトが動き、依存ゼロで SKILL.md (YAML frontmatter + 本文) を吐く最小例。

```python
#!/usr/bin/env python3
# scripts/build_skill.py
# Python 3.8+ 標準ライブラリのみ。Mac は同梱、Windows は python.org 公式 installer で導入。

import argparse
import os
import platform
import sys
import textwrap
from pathlib import Path

def detect_os() -> str:
    s = platform.system().lower()
    if s == "darwin":
        return "mac"
    if s == "windows":
        return "windows"
    if s == "linux":
        return "linux"
    return "unknown"

def render(name: str, description: str, os_kind: str) -> str:
    body = textwrap.dedent(f"""\
        ---
        name: {name}
        description: {description}
        ---

        # {name}

        Detected OS: {os_kind}

        ## Steps

        1. ...
        """)
    return body

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--out", default="SKILL.md")
    args = p.parse_args()

    os_kind = detect_os()
    if os_kind == "unknown":
        print("ERROR: OS detection failed. Ask the user.", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(args.name, args.description, os_kind), encoding="utf-8")
    print(f"wrote: {out_path} (os={os_kind})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**import モジュール (すべて Python 3 標準ライブラリ)**:

- `argparse` — CLI 引数解析
- `os` — 環境変数 / パス
- `platform` — OS 判定 (`platform.system()`)
- `sys` — 終了コード / stderr
- `textwrap` — テンプレ整形
- `pathlib.Path` — クロスプラットフォーム パス操作

pip 不要・追加 install 不要で完結する。

## PowerShell 5.1 ラッパー例 (Python 不在 Windows 用)

Windows に `python` が無い環境向けフォールバック。PowerShell 5.1 は Windows 10 以降に標準同梱。

```powershell
# scripts/build_skill.ps1
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Name,
  [Parameter(Mandatory=$true)][string]$Description,
  [string]$Out = "SKILL.md"
)

$osKind = if ($env:OS -like '*Windows*') { 'windows' } else { 'unknown' }
if ($osKind -eq 'unknown') {
  Write-Error "OS detection failed. Ask the user."
  exit 2
}

$outDir = Split-Path -Parent $Out
if ($outDir -and -not (Test-Path $outDir)) {
  New-Item -ItemType Directory -Path $outDir | Out-Null
}

$body = @"
---
name: $Name
description: $Description
---

# $Name

Detected OS: $osKind

## Steps

1. ...
"@

Set-Content -Path $Out -Value $body -Encoding UTF8
Write-Output "wrote: $Out (os=$osKind)"
```

## OS 確認プロンプト Skill 例 (辞書型)

OS 判定が外せない Skill 群が共通で参照する辞書型 Skill。

```markdown
---
name: ref-cross-platform-runtime
description: Cross-platform runtime contract（契約） for Mac/Windows. Use when a Skill needs to branch on host OS or when OS detection failed.
kind: ref                       # 列挙値: ref|run|wrap|assign|delegate （atomic は旧仕様、使用禁止）
disable-model-invocation: false
owner: team-platform
hierarchy_level: L0
---

# Cross-platform runtime

## Detect OS

```!
uname -s 2>/dev/null || ver
```

- `Darwin*`        -> os=mac
- `Linux*`         -> os=linux
- `Microsoft Windows*` -> os=windows
- それ以外         -> os=unknown

## If os=unknown

次の問いをユーザーへ投げる。回答が得られるまで後続処理を停止する。

> お使いの OS はどれですか？
> 1. macOS
> 2. Windows
> 3. Linux

回答を `OS_KIND_USER_DECLARED` として会話スコープのみで保持する。
長期記憶・設定ファイルには書き込まない。

## No-deps 原則

- Python は標準ライブラリのみ使用する
- 追加 CLI (`jq` / `rg` 等) を要求しない
- 不在 CLI を呼ぶ前に必ず存在チェック (`command -v` / `Get-Command`)

## Output contract（契約）

呼び出し元 Skill へ次を返す:

- `os`: mac | windows | linux | unknown
- `shell`: bash | powershell
- `python_available`: true | false
- `fallback_used`: true | false
```

## 設計チェック

- [ ] Skill が呼ぶ CLI は OS 標準同梱だけで構成されている
- [ ] OS 分岐は `<important if="os=...">` で表現されている
- [ ] OS 判定失敗時にユーザーへ問い合わせる文面がある
- [ ] Python を使う場合、import が標準ライブラリのみ
- [ ] PowerShell 版があり Windows で `python` 不在でも動く
- [ ] パス区切りは hardcode せず `pathlib` / `Join-Path` を使う
- [ ] 長期記憶に OS 情報を焼き込んでいない
