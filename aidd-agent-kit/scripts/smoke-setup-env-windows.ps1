[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$KitPath,
  [string]$TempRoot = [IO.Path]::GetTempPath()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Stop-AiddSetupSmoke {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Message
  )
  throw ('[AIDD-SETUP-SMOKE] phase={0} path="{1}" message={2}' -f `
    $Phase, $Path.Replace('"', "'"), $Message)
}

function Write-AiddAsciiBatch {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Content
  )
  $crlf = ($Content -replace "`r?`n", "`r`n")
  [IO.File]::WriteAllText($Path, $crlf, [Text.Encoding]::ASCII)
}

function Get-AiddMotwCount {
  param([Parameter(Mandatory = $true)][string]$Root)

  $count = 0
  foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -Force -File) {
    if ($null -ne (Get-Item -LiteralPath $file.FullName `
      -Stream 'Zone.Identifier' -ErrorAction SilentlyContinue)) {
      $count++
    }
  }
  return $count
}

function Invoke-AiddSetup {
  param(
    [Parameter(Mandatory = $true)][string]$BatchPath,
    [Parameter(Mandatory = $true)][hashtable]$Environment,
    [Parameter(Mandatory = $true)][int]$ExpectedExit
  )

  $startInfo = New-Object Diagnostics.ProcessStartInfo
  $startInfo.FileName = $env:ComSpec
  $startInfo.Arguments = ('/d /c call "{0}"' -f $BatchPath)
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $utf8 = New-Object Text.UTF8Encoding($false)
  $startInfo.StandardOutputEncoding = $utf8
  $startInfo.StandardErrorEncoding = $utf8
  foreach ($name in $Environment.Keys) {
    $startInfo.EnvironmentVariables[$name] = [string]$Environment[$name]
  }

  $process = New-Object Diagnostics.Process
  $process.StartInfo = $startInfo
  try {
    if (-not $process.Start()) {
      Stop-AiddSetupSmoke -Phase 'process' -Path $BatchPath `
        -Message 'cmd.exe did not start'
    }
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $exitCode = $process.ExitCode
  } finally {
    $process.Dispose()
  }

  $text = $stdout + $stderr
  Write-Host $text
  if ($exitCode -ne $ExpectedExit) {
    Stop-AiddSetupSmoke -Phase 'exit-code' -Path $BatchPath `
      -Message "expected $ExpectedExit but got $exitCode"
  }
  return $text
}

$sourceKit = [IO.Path]::GetFullPath($KitPath)
$runId = [Guid]::NewGuid().ToString('N').Substring(0, 6)
$japanese = -join @([char]0x65E5, [char]0x672C, [char]0x8A9E)
$fixtureRoot = Join-Path ([IO.Path]::GetFullPath($TempRoot)) `
  "AIDD Setup $japanese $runId"
$fixtureKit = Join-Path $fixtureRoot 'kit'
$nodeBin = Join-Path $fixtureRoot 'node bin'
$localAppData = Join-Path $fixtureRoot 'local app data'
$pnpmHome = Join-Path $localAppData 'pnpm'
$temp = Join-Path $fixtureRoot 'temp'
$setup = Join-Path $fixtureKit 'setup-env-windows.bat'
$node = Join-Path $nodeBin 'node.cmd'
$pnpm = Join-Path $pnpmHome 'pnpm.cmd'
$completed = $false

try {
  foreach ($path in @(
    (Join-Path $sourceKit 'setup-env-windows.bat'),
    (Join-Path $sourceKit 'NODE_MIN_MAJOR')
  )) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      Stop-AiddSetupSmoke -Phase 'fixture' -Path $path `
      -Message 'required source file missing'
    }
  }

  $minimumText = ([IO.File]::ReadAllText(
    (Join-Path $sourceKit 'NODE_MIN_MAJOR'))).Trim()
  $minimum = 0
  if (-not [int]::TryParse($minimumText, [ref]$minimum) -or $minimum -le 1) {
    Stop-AiddSetupSmoke -Phase 'fixture' `
      -Path (Join-Path $sourceKit 'NODE_MIN_MAJOR') `
      -Message 'minimum Node version must be an integer greater than one'
  }
  $belowMinimum = $minimum - 1

  foreach ($directory in @($fixtureKit, $nodeBin, $pnpmHome, $temp)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
  }
  Copy-Item -LiteralPath (Join-Path $sourceKit 'setup-env-windows.bat') `
    -Destination $setup
  Copy-Item -LiteralPath (Join-Path $sourceKit 'NODE_MIN_MAJOR') `
    -Destination (Join-Path $fixtureKit 'NODE_MIN_MAJOR')

  Write-AiddAsciiBatch -Path $pnpm -Content @'
@echo off
if "%~1"=="--version" (
  echo 9.15.0
  exit /b 0
)
rem The old-Node case must stay old without using the network.
exit /b 1
'@

  $system32 = Join-Path $env:SystemRoot 'System32'
  $windowsPowerShell = Join-Path $system32 'WindowsPowerShell\v1.0'
  $isolatedPath = @($nodeBin, $system32, $windowsPowerShell) -join ';'
  $environment = @{
    'AIDD_NONINTERACTIVE' = '1'
    'LOCALAPPDATA' = $localAppData
    'PATH' = $isolatedPath
    'TEMP' = $temp
    'TMP' = $temp
    # setup-env の状態stampが実利用者の profile へ漏れないよう、
    # fixture専用の user scope を与える。
    'USERPROFILE' = (Join-Path $fixtureRoot 'user profile')
  }

  # Minimum Node + CLI none: precheck, FullLanguage and Unblock-File run through
  # the real batch entry point. Mark the actual fixture immediately before running.
  $minimumNodeBatch = @'
@echo off
if "%~1"=="--version" echo v{0}.0.0& exit /b 0
exit /b 1
'@ -f $minimum
  Write-AiddAsciiBatch -Path $node -Content $minimumNodeBatch
  foreach ($file in Get-ChildItem -LiteralPath $fixtureKit `
    -Recurse -Force -File) {
    Set-Content -LiteralPath $file.FullName -Stream 'Zone.Identifier' `
      -Value "[ZoneTransfer]`r`nZoneId=3"
  }
  $markedBefore = Get-AiddMotwCount -Root $fixtureKit
  if ($markedBefore -le 0) {
    Stop-AiddSetupSmoke -Phase 'minimum-before' -Path $fixtureKit `
      -Message 'Zone.Identifier fixture was not created'
  }

  $minimumOutput = Invoke-AiddSetup -BatchPath $setup `
    -Environment $environment -ExpectedExit 0
  foreach ($required in @(
    '一部の連携は未設定',
    'Claude Code (claude)',
    'OpenAI Codex (codex)'
  )) {
    if (-not $minimumOutput.Contains($required)) {
      Stop-AiddSetupSmoke -Phase 'minimum-output' -Path $setup `
        -Message "required output missing: $required"
    }
  }
  if ($minimumOutput.Contains('完全に完了')) {
    Stop-AiddSetupSmoke -Phase 'minimum-output' -Path $setup `
      -Message 'CLI-none path reported complete'
  }
  $stateStamp = Join-Path $environment['USERPROFILE'] `
    '.claude\aidd-agent-kit.setup-env'
  if (-not (Test-Path -LiteralPath $stateStamp -PathType Leaf)) {
    Stop-AiddSetupSmoke -Phase 'minimum-state' -Path $stateStamp `
      -Message 'setup state stamp missing'
  }
  $stateText = [IO.File]::ReadAllText($stateStamp)
  if ($stateText -notmatch '(?m)^schema=2\r?$' -or
      $stateText -notmatch '(?m)^state=attempted\r?$' -or
      $stateText -match '(?i)token|secret|account[_ -]?id') {
    Stop-AiddSetupSmoke -Phase 'minimum-state' -Path $stateStamp `
      -Message 'attempted state or no-secret contract failed'
  }
  $markedAfter = Get-AiddMotwCount -Root $fixtureKit
  if ($markedAfter -ne 0) {
    Stop-AiddSetupSmoke -Phase 'minimum-after' -Path $fixtureKit `
      -Message "Unblock-File left $markedAfter marked files"
  }

  # One major below the minimum: pnpm env is invoked but the fixture intentionally
  # cannot update, so the batch must fail and show the executable path still active.
  $belowMinimumNodeBatch = @'
@echo off
if "%~1"=="--version" echo v{0}.9.0& exit /b 0
exit /b 1
'@ -f $belowMinimum
  Write-AiddAsciiBatch -Path $node -Content $belowMinimumNodeBatch
  $belowMinimumOutput = Invoke-AiddSetup -BatchPath $setup `
    -Environment $environment -ExpectedExit 1
  foreach ($required in @(
    ('v{0} 以上' -f $minimum),
    '使用中の Node.js',
    $node
  )) {
    if (-not $belowMinimumOutput.Contains($required)) {
      Stop-AiddSetupSmoke -Phase 'below-minimum-output' -Path $setup `
        -Message "required output missing: $required"
    }
  }
  $failedStateText = [IO.File]::ReadAllText($stateStamp)
  if ($failedStateText -notmatch '(?m)^state=failed\r?$') {
    Stop-AiddSetupSmoke -Phase 'below-minimum-state' -Path $stateStamp `
      -Message 'failed setup did not replace the previous state'
  }

  $completed = $true
  Write-Host ('[AIDD-SETUP-SMOKE] phase=complete path="{0}"' -f $fixtureRoot)
} finally {
  if ($completed -and (Test-Path -LiteralPath $fixtureRoot)) {
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
  } elseif (-not $completed) {
    Write-Host ('[AIDD-SETUP-SMOKE] phase=failed path="{0}"' -f $fixtureRoot)
  }
}
