# resolve-skill-dirs.ps1
# ----------------------
# resolve-skill-dirs.sh の PowerShell 等価実装。
# 設計書22「クロスプラットフォームランタイム」契約に基づき、
# Windows 経路の run-build-skill から `. .\plugins\skill-governance-automation\scripts\resolve-skill-dirs.ps1`
# で source 相当の dot-sourcing を行うことで $env:SKILL_DIR / $env:OUT_BASE を確立する。
#
# 確立する環境変数:
#   $env:SKILL_DIR   - run-build-skill 本体ディレクトリ
#   $env:OUT_BASE    - 出力先基底ディレクトリ
#
# 優先順序:
#   1. 既存 $env:CLAUDE_SKILL_DIR / $env:CLAUDE_SKILL_OUT_BASE があれば使用
#   2. plugins\harness-creator\skills\run-build-skill\ が存在すれば plugin 配置
#   3. .claude\skills\run-build-skill\ が存在すれば .claude 配置
#   4. $PSScriptRoot をフォールバック
#
# no-deps 原則準拠: PowerShell 5.1 標準のみ使用、追加モジュール不要。

$ErrorActionPreference = 'Stop'

if (-not $env:SKILL_DIR -or $env:SKILL_DIR -eq '') {
    if ($env:CLAUDE_SKILL_DIR -and $env:CLAUDE_SKILL_DIR -ne '') {
        $env:SKILL_DIR = $env:CLAUDE_SKILL_DIR
    } elseif (Test-Path 'plugins\harness-creator\skills\run-build-skill\scripts\render-frontmatter.py') {
        $env:SKILL_DIR = 'plugins\harness-creator\skills\run-build-skill'
    } elseif (Test-Path '.claude\skills\run-build-skill\scripts\render-frontmatter.py') {
        $env:SKILL_DIR = '.claude\skills\run-build-skill'
    } else {
        $env:SKILL_DIR = $PSScriptRoot
    }
}

if (-not $env:OUT_BASE -or $env:OUT_BASE -eq '') {
    if ($env:CLAUDE_SKILL_OUT_BASE -and $env:CLAUDE_SKILL_OUT_BASE -ne '') {
        $env:OUT_BASE = $env:CLAUDE_SKILL_OUT_BASE
    } elseif ($env:SKILL_DIR -like 'plugins\harness-creator*') {
        $env:OUT_BASE = 'plugins\harness-creator\skills'
    } else {
        $env:OUT_BASE = '.claude\skills'
    }
}

Write-Output "SKILL_DIR=$($env:SKILL_DIR)"
Write-Output "OUT_BASE=$($env:OUT_BASE)"
