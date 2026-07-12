# install.ps1 — harness-creator-kit を Windows 環境に展開する
#
# 使い方:
#   powershell -ExecutionPolicy Bypass -File installers/install.ps1 [-Mode symlink|copy] [-Force]
#
# 動作 (doc/22 cross-platform-runtime 準拠):
#   1. OS判定 (Windows のみ許可、それ以外は停止しユーザーへ確認)
#   2. python / git の存在確認 (no-deps 原則: PyYAML 等の追加ライブラリは要求しない)
#   3. manifest.json を python の json で読む
#   4. symlink (要管理者権限) または copy で展開
#   5. keychain_helper は不在のため cross_platform_secret.py (Windows file fallback) を case 別に配置

[CmdletBinding()]
param(
  [ValidateSet("symlink", "copy")]
  [string]$Mode = "copy",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$KitDir = Split-Path -Parent $PSCommandPath
$ProjectDir = (Get-Location).Path

Write-Host "==> harness-creator-kit installer (Windows)"
Write-Host "    kit dir:     $KitDir"
Write-Host "    project dir: $ProjectDir"
Write-Host "    mode:        $Mode"
Write-Host ""

# --- OS判定 ---
$osKind = if ($IsWindows -or $env:OS -like '*Windows*') { 'windows' }
          elseif ($IsMacOS) { 'mac' }
          elseif ($IsLinux) { 'linux' }
          else { 'unknown' }

if ($osKind -ne 'windows') {
    Write-Error "ERROR: install.ps1 は Windows 専用です。検出 OS: $osKind。`n  mac/linux の場合は install.sh を使ってください。"
    exit 2
}

# --- prerequisites ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "ERROR: python (>=3.9) が必要です。https://www.python.org/ からインストールしてください。"
    exit 1
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Error "ERROR: git が必要です。https://git-scm.com/ からインストールしてください。"
    exit 1
}

# --- manifest 突き合わせ ---
$manifestPath = Join-Path $KitDir "manifest.json"
if (-not (Test-Path $manifestPath)) {
    Write-Error "ERROR: $manifestPath not found"
    exit 1
}

$supportedOs = & $python.Path -c "import json; m=json.load(open(r'$manifestPath')); print(','.join(m['requirements']['os']))"
if (",$supportedOs," -notlike "*,$osKind,*") {
    Write-Error "ERROR: '$osKind' は manifest の requirements.os=[$supportedOs] に含まれていません。"
    exit 3
}
Write-Host "    OS:          $osKind (supported: $supportedOs)"

# --- directories ---
$dirs = @(".claude/skills", ".claude/agents", ".claude/config",
          "scripts/adapters", "scripts/secrets", "scripts", "scripts/migrate")
foreach ($d in $dirs) {
    $full = Join-Path $ProjectDir $d
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
}

# --- helper ---
function Link-Or-Copy($src, $dst, $itemMode) {
    if (-not (Test-Path $src)) {
        Write-Host "    SKIP (missing in kit): $src"
        return
    }
    if (Test-Path $dst) {
        if ($Force) {
            Remove-Item -Path $dst -Recurse -Force
        } else {
            Write-Host "    SKIP (exists): $dst"
            return
        }
    }
    $parent = Split-Path -Parent $dst
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if ($itemMode -eq "symlink") {
        try {
            New-Item -ItemType SymbolicLink -Path $dst -Target $src -ErrorAction Stop | Out-Null
            Write-Host "    LINK: $dst -> $src"
        } catch {
            Write-Host "    LINK failed (権限不足の可能性) → fallback to copy: $dst"
            Copy-Item -Path $src -Destination $dst -Recurse -Force
        }
    } else {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
        Write-Host "    COPY: $src -> $dst"
    }
}

# --- install skills ---
Write-Host "==> Installing skills"
$skills = & $python.Path -c "import json; m=json.load(open(r'$manifestPath')); [print(s['name']) for s in m.get('skills',[])]"
foreach ($skill_name in $skills) {
    $src = Join-Path $KitDir "skills/$skill_name"
    $dst = Join-Path $ProjectDir ".claude/skills/$skill_name"
    Link-Or-Copy $src $dst $Mode
}

# --- install agents ---
Write-Host "==> Installing agents"
$agentLines = & $python.Path -c @"
import json
m=json.load(open(r'$manifestPath'))
for a in m.get('agents',[]):
    print(a.get('source', 'agents/'+a['name']+'.md') + '|' + a.get('path', '.claude/agents/'+a['name']+'.md') + '|' + a.get('mode','symlink'))
"@
foreach ($line in $agentLines) {
    $parts = $line -split '\|'
    $src = Join-Path $KitDir $parts[0]
    $dst = Join-Path $ProjectDir $parts[1]
    Link-Or-Copy $src $dst $parts[2]
}

# --- install scripts (Windows では keychain_helper をスキップ) ---
Write-Host "==> Installing scripts/adapters"
Get-ChildItem -Path (Join-Path $KitDir "scripts/adapters") -Filter "*.py" | ForEach-Object {
    Link-Or-Copy $_.FullName (Join-Path $ProjectDir "scripts/adapters/$($_.Name)") $Mode
}

Write-Host "==> Installing scripts/lint+hooks"
Get-ChildItem -Path (Join-Path $KitDir "scripts") -Filter "*.py" | ForEach-Object {
    Link-Or-Copy $_.FullName (Join-Path $ProjectDir "scripts/$($_.Name)") $Mode
}

Write-Host "==> Installing scripts/migrate"
Get-ChildItem -Path (Join-Path $KitDir "scripts/migrate") -Filter "*.py" | ForEach-Object {
    Link-Or-Copy $_.FullName (Join-Path $ProjectDir "scripts/migrate/$($_.Name)") $Mode
}

# secrets/ は keychain_helper.py を除外し、cross_platform_secret.py を主導
Write-Host "==> Installing scripts/cross_platform_secret.py (Windows経路はfile fallback)"
Link-Or-Copy (Join-Path $KitDir "scripts/cross_platform_secret.py") (Join-Path $ProjectDir "scripts/cross_platform_secret.py") $Mode

# --- install config ---
Write-Host "==> Installing config"
$configLines = & $python.Path -c @"
import json
m=json.load(open(r'$manifestPath'))
for c in m.get('config',[]):
    print(c['source']+'|'+c['target']+'|'+c.get('mode','symlink'))
"@
foreach ($line in $configLines) {
    $parts = $line -split '\|'
    $src = Join-Path $KitDir $parts[0]
    $dst = Join-Path $ProjectDir $parts[1]
    Link-Or-Copy $src $dst $parts[2]
}

Write-Host ""
Write-Host "==> Done."
Write-Host "    Probe: python -m scripts.cross_platform_secret --probe"
