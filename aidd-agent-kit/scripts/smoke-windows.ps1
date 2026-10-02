[CmdletBinding()]
param(
  # 既定値をここで計算してはいけない。param の既定式は「その引数を使うか
  # どうか」に関係なく束縛時に必ず評価される。CI は -KitPath を渡すので
  # RepoRoot は一度も使わないのに、その計算の失敗だけでスクリプトが
  # 起動前に落ちていた。必要になった場所で解決する。
  [string]$RepoRoot = '',
  [string]$TempRoot = [IO.Path]::GetTempPath(),
  # 検査したいキットの場所。既定はリポジトリの中身だが、CI からは
  # 配布 ZIP を展開した場所を渡す。利用者が実際に手にするのは ZIP の中身で
  # あって、リポジトリのチェックアウトではないため。
  [string]$KitPath = '',
  # CI では実行対象の fixture 自体に Mark of the Web を付け、
  # インストーラーの通常経路が実際に全件解除することを確かめる。
  [switch]$AssertMotwRecovery
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$script:CurrentPhase = 'bootstrap'
$script:CurrentCategory = 'script'
$script:CurrentPath = $PSCommandPath

function Write-AiddPhase {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Category,
    [Parameter(Mandatory = $true)][string]$Path
  )

  $script:CurrentPhase = $Phase
  $script:CurrentCategory = $Category
  $script:CurrentPath = $Path
  $safePath = $Path.Replace("`r", '').Replace("`n", '').Replace('"', "'")
  Write-Host ('[AIDD-SMOKE] phase={0} category={1} path="{2}"' -f `
    $Phase, $Category, $safePath)
}

function Stop-AiddSmoke {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Category,
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ExitCode,
    [Parameter(Mandatory = $true)][string]$Message
  )

  $safePath = $Path.Replace("`r", '').Replace("`n", '').Replace('"', "'")
  throw ('[AIDD-SMOKE] phase={0} category={1} path="{2}" exit={3} message={4}' -f `
    $Phase, $Category, $safePath, $ExitCode, $Message)
}

function Invoke-AiddProcess {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Category,
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$ArgumentLine,
    [int[]]$ExpectedExitCodes = @(0)
  )

  Write-AiddPhase -Phase $Phase -Category $Category -Path $Path
  $process = $null
  try {
    # Windows PowerShell 5.1 converts redirected native stderr into ErrorRecord
    # objects. Capture both streams through Process instead so a successful
    # cmd.exe run cannot become a terminating PowerShell error.
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = $ArgumentLine
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $utf8 = New-Object Text.UTF8Encoding($false)
    $startInfo.StandardOutputEncoding = $utf8
    $startInfo.StandardErrorEncoding = $utf8

    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
      throw 'process did not start'
    }
    $standardOutput = $process.StandardOutput.ReadToEnd()
    $standardError = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $exitCode = $process.ExitCode
  } catch {
    Stop-AiddSmoke -Phase $Phase -Category $Category -Path $Path `
      -ExitCode 'not-started' -Message 'process could not be started'
  } finally {
    if ($null -ne $process) {
      $process.Dispose()
    }
  }

  $output = New-Object 'System.Collections.Generic.List[string]'
  foreach ($stream in @($standardOutput, $standardError)) {
    foreach ($line in ($stream -split '\r?\n')) {
      if ($line.Length -gt 0) {
        $output.Add($line)
        Write-Host $line
      }
    }
  }
  if ($ExpectedExitCodes -notcontains $exitCode) {
    Stop-AiddSmoke -Phase $Phase -Category $Category -Path $Path `
      -ExitCode ([string]$exitCode) -Message 'unexpected process exit'
  }

  return $output
}

function Invoke-AiddBatch {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Category,
    [Parameter(Mandatory = $true)][string]$BatchPath
  )

  return (Invoke-AiddProcess -Phase $Phase -Category $Category `
    -Path $BatchPath -Executable $env:ComSpec `
    -ArgumentLine ('/d /c call "{0}"' -f $BatchPath))
}

function Get-AiddHomeSnapshot {
  param([Parameter(Mandatory = $true)][string]$UserProfile)

  $records = New-Object 'System.Collections.Generic.List[string]'
  foreach ($root in @(
    (Join-Path $UserProfile '.claude\skills'),
    (Join-Path $UserProfile '.claude\agents'),
    (Join-Path $UserProfile '.claude\commands'),
    (Join-Path $UserProfile '.claude\aidd-agent-kit.manifest'),
    (Join-Path $UserProfile '.claude\aidd-agent-kit.version'),
    (Join-Path $UserProfile '.agents\skills'),
    (Join-Path $UserProfile '.codex\agents'),
    (Join-Path $UserProfile '.codex\prompts'),
    (Join-Path $UserProfile '.codex\aidd-agent-kit.manifest'),
    (Join-Path $UserProfile '.codex\aidd-agent-kit.version')
  )) {
    if (-not (Test-Path -LiteralPath $root)) {
      $records.Add("MISSING|$root")
      continue
    }

    $rootItem = Get-Item -LiteralPath $root -Force
    if (-not $rootItem.PSIsContainer) {
      $hash = (Get-FileHash -LiteralPath $root -Algorithm SHA256).Hash
      $records.Add("F|$root|$hash")
      continue
    }

    $records.Add("D|$root")
    foreach ($item in Get-ChildItem -LiteralPath $root -Recurse -Force |
      Sort-Object -Property FullName) {
      if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        $records.Add("L|$($item.FullName)")
      } elseif ($item.PSIsContainer) {
        $records.Add("D|$($item.FullName)")
      } else {
        $hash = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
        $records.Add("F|$($item.FullName)|$hash")
      }
    }
  }
  return $records
}

function Get-AiddBackupCount {
  param([Parameter(Mandatory = $true)][string]$TargetHome)

  $count = 0
  foreach ($root in @(
    (Join-Path $TargetHome '.claude'),
    (Join-Path $TargetHome '.codex')
  )) {
    if (Test-Path -LiteralPath $root -PathType Container) {
      $count += @(Get-ChildItem -LiteralPath $root -Directory `
        -Filter 'backup-*').Count
    }
  }
  return $count
}

function Assert-AiddNoOp {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Category,
    [Parameter(Mandatory = $true)][string]$BatchPath,
    [Parameter(Mandatory = $true)][string]$TargetHome
  )

  $backupCountBefore = Get-AiddBackupCount -TargetHome $TargetHome
  $output = @(Invoke-AiddBatch -Phase $Phase -Category $Category `
    -BatchPath $BatchPath)
  # The batch installer emits [OK] only for the verified no-op path. Keep this
  # source ASCII-only because Windows PowerShell 5.1 reads BOM-less scripts by
  # using the active ANSI code page.
  if (-not (($output -join "`n").Contains('[OK]'))) {
    Stop-AiddSmoke -Phase $Phase -Category 'no-op-contract' -Path $BatchPath `
      -ExitCode '0' -Message 'no-op marker missing'
  }

  $backupCountAfter = Get-AiddBackupCount -TargetHome $TargetHome
  if ($backupCountAfter -ne $backupCountBefore) {
    Stop-AiddSmoke -Phase $Phase -Category 'backup-contract' -Path $TargetHome `
      -ExitCode 'contract' -Message 'backup count changed during no-op'
  }
}

function Assert-AiddFile {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Path
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Stop-AiddSmoke -Phase $Phase -Category 'artifact' -Path $Path `
      -ExitCode 'contract' -Message 'required file missing'
  }
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

function Restore-AiddEnvironment {
  param([Parameter(Mandatory = $true)][hashtable]$Original)

  foreach ($name in $Original.Keys) {
    $value = $Original[$name]
    if ($null -eq $value) {
      Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    } else {
      [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
  }
}

$temp = [IO.Path]::GetFullPath($TempRoot)

# 検査対象の決め方:
#   -KitPath があればそれ。無ければリポジトリの中の aidd-agent-kit。
# リポジトリ位置の解決は、KitPath が無いときだけ行う。
# $PSScriptRoot は起動のされ方 (dot-source, -Command "& {...}",
# スクリプトブロック経由) によっては空になる。空のまま Split-Path へ
# 渡すと、原因の分からない束縛エラーで止まるので、順に候補を試し、
# 全部だめなら何が起きたのかを名指しして落とす。
if ([string]::IsNullOrWhiteSpace($KitPath)) {
  # $MyInvocation はスクリプトブロックの中では「そのブロック自身」を指す。
  # 候補集めを & { } で包むと、この行だけ常に空になる。ここは素の
  # スクリプト直下 (if はスコープを作らない) なので、そのまま書く。
  $scriptFile = $PSCommandPath
  if ([string]::IsNullOrWhiteSpace($scriptFile)) {
    $scriptFile = $MyInvocation.MyCommand.Path
  }
  $scriptDir = $PSScriptRoot
  if ([string]::IsNullOrWhiteSpace($scriptDir) -and
      -not [string]::IsNullOrWhiteSpace($scriptFile)) {
    $scriptDir = Split-Path -Parent $scriptFile
  }
  if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
      throw ('スクリプトの位置を特定できません。-KitPath ' +
             'でキットの場所を明示してください。')
    }
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
  }
  $repo = [IO.Path]::GetFullPath($RepoRoot)
  $sourceKit = Join-Path $repo 'aidd-agent-kit'
} else {
  $sourceKit = [IO.Path]::GetFullPath($KitPath)
}
if (-not (Test-Path -LiteralPath $sourceKit -PathType Container)) {
  throw ('検査対象のキットが見つかりません: ' + $sourceKit)
}
Write-Host ('[AIDD-SMOKE] kit="{0}"' -f $sourceKit)
$realUserProfile = $env:USERPROFILE
$originalEnvironment = @{}
foreach ($name in @('AIDD_TARGET_HOME', 'AIDD_CODEX_TARGET', 'AIDD_NONINTERACTIVE')) {
  $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$runId = [Guid]::NewGuid().ToString('N').Substring(0, 6)
$japanese = -join @([char]0x65E5, [char]0x672C, [char]0x8A9E)
$fixtureRoot = Join-Path $temp "AIDD User $japanese $runId"
$fixtureKit = Join-Path $fixtureRoot 'kit\aidd-agent-kit'
$targetHome = Join-Path $fixtureRoot 'target home'
$projectRoot = Join-Path $temp "AIDD Project $japanese $runId"
$fixtureRoots = @($fixtureRoot, $projectRoot)
$completed = $false

try {
  Write-AiddPhase -Phase 'fixture-setup' -Category 'copy-kit' -Path $fixtureRoot
  Assert-AiddFile -Phase 'fixture-setup' -Path `
    (Join-Path $sourceKit 'install-windows.bat')
  New-Item -ItemType Directory -Path (Split-Path -Parent $fixtureKit) `
    -Force | Out-Null
  Copy-Item -LiteralPath $sourceKit -Destination $fixtureKit -Recurse

  $agentToml = Join-Path $fixtureKit 'codex\agents\app-orchestrator.toml'
  Assert-AiddFile -Phase 'fixture-setup' -Path $agentToml
  $toml = [IO.File]::ReadAllText($agentToml)
  $marker = 'developer_instructions = """'
  if (-not $toml.Contains($marker)) {
    Stop-AiddSmoke -Phase 'fixture-setup' -Category 'toml-fixture' `
      -Path $agentToml -ExitCode 'contract' -Message 'fixture marker missing'
  }

  $optionalConfig = @(
    'model = "gpt-5.6-luna"',
    'model_reasoning_effort = "low"',
    'sandbox_mode = "read-only"'
  ) -join "`n"
  $toml = $toml.Replace($marker, "$optionalConfig`n$marker")
  $optionalTables = @(
    '',
    '[mcp_servers.fixture]',
    'command = "cmd"',
    '',
    '[[skills.config]]',
    'path = ".agents/skills/fixture"',
    'enabled = true'
  ) -join "`n"
  $toml = $toml + "`n" + $optionalTables + "`n"
  [IO.File]::WriteAllText(
    $agentToml,
    $toml,
    (New-Object Text.UTF8Encoding($false))
  )

  $preflight = Join-Path $fixtureKit 'scripts\preflight-windows.ps1'
  Assert-AiddFile -Phase 'preflight-positive' -Path $preflight
  $preflightArgumentLine = (
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass ' +
    '-File "{0}" -KitRoot "{1}" -LegacyPrompts "0"' -f `
      $preflight, $fixtureKit
  )
  $positiveOutput = @(Invoke-AiddProcess -Phase 'preflight-positive' `
    -Category 'preflight-direct' -Path $preflight -Executable 'powershell.exe' `
    -ArgumentLine $preflightArgumentLine)
  if ($positiveOutput.Count -ne 0) {
    Stop-AiddSmoke -Phase 'preflight-positive' -Category 'preflight-contract' `
      -Path $preflight -ExitCode '0' -Message 'successful preflight emitted output'
  }

  $tomlBytes = [IO.File]::ReadAllBytes($agentToml)
  try {
    $namePattern = New-Object Text.RegularExpressions.Regex(
      '(?m)^[ \t]*name[ \t]*=.*(?:\r?\n)?'
    )
    $invalidToml = $namePattern.Replace($toml, '', 1)
    [IO.File]::WriteAllText(
      $agentToml,
      $invalidToml,
      (New-Object Text.UTF8Encoding($false))
    )
    $negativeOutput = @(Invoke-AiddProcess -Phase 'preflight-negative' `
      -Category 'required-toml-negative' -Path $agentToml `
      -Executable 'powershell.exe' -ArgumentLine $preflightArgumentLine `
      -ExpectedExitCodes @(1))
    $negativeText = $negativeOutput -join "`n"
    if (-not $negativeText.Contains('[AIDD-PREFLIGHT] stage=toml') -or
        -not $negativeText.Contains('category=required-field')) {
      Stop-AiddSmoke -Phase 'preflight-negative' `
        -Category 'preflight-contract' -Path $agentToml -ExitCode '1' `
        -Message 'required TOML diagnostic missing'
    }

    $invalidNameToml = $toml.Replace(
      'name = "app_orchestrator"',
      'name = "Invalid-Name"'
    )
    if ($invalidNameToml -eq $toml) {
      Stop-AiddSmoke -Phase 'preflight-negative' -Category 'toml-fixture' `
        -Path $agentToml -ExitCode 'contract' -Message 'name marker missing'
    }
    [IO.File]::WriteAllText(
      $agentToml,
      $invalidNameToml,
      (New-Object Text.UTF8Encoding($false))
    )
    $invalidNameOutput = @(Invoke-AiddProcess -Phase 'preflight-negative' `
      -Category 'invalid-toml-name-negative' -Path $agentToml `
      -Executable 'powershell.exe' -ArgumentLine $preflightArgumentLine `
      -ExpectedExitCodes @(1))
    $invalidNameText = $invalidNameOutput -join "`n"
    if (-not $invalidNameText.Contains('[AIDD-PREFLIGHT] stage=toml') -or
        -not $invalidNameText.Contains('category=required-field')) {
      Stop-AiddSmoke -Phase 'preflight-negative' `
        -Category 'preflight-contract' -Path $agentToml -ExitCode '1' `
        -Message 'invalid TOML name diagnostic missing'
    }
  } finally {
    [IO.File]::WriteAllBytes($agentToml, $tomlBytes)
  }

  $beforeSnapshot = @(Get-AiddHomeSnapshot -UserProfile $realUserProfile)
  $env:AIDD_TARGET_HOME = $targetHome
  $env:AIDD_CODEX_TARGET = Join-Path $targetHome '.codex'
  $env:AIDD_NONINTERACTIVE = '1'

  $installer = Join-Path $fixtureKit 'install-windows.bat'
  if ($AssertMotwRecovery) {
    Write-AiddPhase -Phase 'motw-before' -Category 'mark-fixture' `
      -Path $fixtureKit
    foreach ($file in Get-ChildItem -LiteralPath $fixtureKit `
      -Recurse -Force -File) {
      Set-Content -LiteralPath $file.FullName -Stream 'Zone.Identifier' `
        -Value "[ZoneTransfer]`r`nZoneId=3"
    }
    $markedBefore = Get-AiddMotwCount -Root $fixtureKit
    if ($markedBefore -le 0) {
      Stop-AiddSmoke -Phase 'motw-before' -Category 'mark-fixture' `
        -Path $fixtureKit -ExitCode 'contract' `
        -Message 'fixture has no Zone.Identifier immediately before install'
    }
    Write-Host ('[AIDD-SMOKE] motw-before={0}' -f $markedBefore)
  }

  [void](Invoke-AiddBatch -Phase 'installer-first' `
    -Category 'windows-installer' -BatchPath $installer)

  if ($AssertMotwRecovery) {
    Write-AiddPhase -Phase 'motw-after' -Category 'unblock-fixture' `
      -Path $fixtureKit
    $markedAfter = Get-AiddMotwCount -Root $fixtureKit
    Write-Host ('[AIDD-SMOKE] motw-after={0}' -f $markedAfter)
    if ($markedAfter -ne 0) {
      Stop-AiddSmoke -Phase 'motw-after' -Category 'unblock-fixture' `
        -Path $fixtureKit -ExitCode 'contract' `
        -Message 'Zone.Identifier remained after successful install'
    }
  }

  Write-AiddPhase -Phase 'installer-artifacts' -Category 'required-files' `
    -Path $targetHome
  foreach ($path in @(
    (Join-Path $targetHome '.agents\skills\build-app\SKILL.md'),
    (Join-Path $targetHome '.codex\agents\app-orchestrator.toml'),
    (Join-Path $targetHome '.codex\aidd-agent-kit.manifest')
  )) {
    Assert-AiddFile -Phase 'installer-artifacts' -Path $path
  }

  # version ファイルは「存在する」だけの確認では不十分。
  # cmd.exe は `echo %VER%> file` の VER 末尾の数字をファイルハンドル番号と解釈するため、
  # 空の version ファイルができてもインストール自体は成功してしまう。
  # さらに :CHECK_NO_CHANGES の fc /b は「空 vs 空」で一致するので、以後ずっと無症状になる。
  # 中身まで照合して初めて、この種の欠陥がリリース前に落ちる。
  $expectedVersion = ([IO.File]::ReadAllText(
    (Join-Path $fixtureKit 'VERSION'))).Trim()
  if ([string]::IsNullOrWhiteSpace($expectedVersion)) {
    Stop-AiddSmoke -Phase 'installer-artifacts' -Category 'version-content' `
      -Path (Join-Path $fixtureKit 'VERSION') -ExitCode 'contract' `
      -Message 'fixture VERSION is empty'
  }
  foreach ($versionFile in @(
    (Join-Path $targetHome '.claude\aidd-agent-kit.version'),
    (Join-Path $targetHome '.codex\aidd-agent-kit.version')
  )) {
    Write-AiddPhase -Phase 'installer-artifacts' -Category 'version-content' `
      -Path $versionFile
    Assert-AiddFile -Phase 'installer-artifacts' -Path $versionFile
    $actualVersion = ([IO.File]::ReadAllText($versionFile)).Trim()
    if ($actualVersion -ne $expectedVersion) {
      Stop-AiddSmoke -Phase 'installer-artifacts' -Category 'version-content' `
        -Path $versionFile -ExitCode 'contract' `
        -Message "version mismatch: expected '$expectedVersion' but got '$actualVersion'"
    }
  }

  $installedToml = Join-Path $targetHome '.codex\agents\app-orchestrator.toml'
  Write-AiddPhase -Phase 'installer-artifacts' -Category 'toml-hash' `
    -Path $installedToml
  if ((Get-FileHash -LiteralPath $agentToml -Algorithm SHA256).Hash -ne
      (Get-FileHash -LiteralPath $installedToml -Algorithm SHA256).Hash) {
    Stop-AiddSmoke -Phase 'installer-artifacts' -Category 'toml-hash' `
      -Path $installedToml -ExitCode 'contract' -Message 'source hash differs'
  }
  foreach ($value in @(
    'model = "gpt-5.6-luna"',
    '[mcp_servers.fixture]',
    '[[skills.config]]'
  )) {
    Write-AiddPhase -Phase 'installer-artifacts' -Category 'toml-optional' `
      -Path $installedToml
    if (-not (Select-String -LiteralPath $installedToml `
      -SimpleMatch $value -Quiet)) {
      Stop-AiddSmoke -Phase 'installer-artifacts' -Category 'toml-optional' `
        -Path $installedToml -ExitCode 'contract' -Message 'optional TOML data missing'
    }
  }

  $manifestPath = Join-Path $targetHome '.codex\aidd-agent-kit.manifest'
  Write-AiddPhase -Phase 'installer-artifacts' -Category 'manifest' `
    -Path $manifestPath
  # ここも ANSI 読みを避ける。照合表は今のところ ASCII だけだが、
  # 読み方が環境依存のまま残ると、日本語を含めた瞬間に壊れる。
  # 下の照合は Multiline の $ で行末を見る。.NET の $ は \n の直前に合うので、
  # CRLF のままだと行末に \r が残って一致しない。Get-Content は改行を
  # 落として返していたため、素朴に置き換えると静かに素通りする検査になる。
  $manifestText = ([IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8)) `
    -replace "`r`n", "`n"
  foreach ($pattern in @(
    '\|skills\\build-app\\SKILL\.md$',
    '\|agents\\app-orchestrator\.toml$'
  )) {
    if (-not [regex]::IsMatch($manifestText, $pattern, `
      [Text.RegularExpressions.RegexOptions]::Multiline)) {
      Stop-AiddSmoke -Phase 'installer-artifacts' -Category 'manifest' `
        -Path $manifestPath -ExitCode 'contract' -Message 'required entry missing'
    }
  }

  Assert-AiddNoOp -Phase 'installer-no-op' -Category 'windows-installer' `
    -BatchPath $installer -TargetHome $targetHome

  Remove-Item Env:AIDD_TARGET_HOME -ErrorAction SilentlyContinue
  Remove-Item Env:AIDD_CODEX_TARGET -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
  Copy-Item -LiteralPath $sourceKit `
    -Destination (Join-Path $projectRoot 'aidd-agent-kit') -Recurse
  $sync = Join-Path $projectRoot 'aidd-agent-kit\sync-project-windows.bat'
  [void](Invoke-AiddBatch -Phase 'project-sync-first' `
    -Category 'windows-project-sync' -BatchPath $sync)

  foreach ($path in @(
    (Join-Path $projectRoot '.agents\skills\build-app\SKILL.md'),
    (Join-Path $projectRoot '.codex\agents\app-orchestrator.toml'),
    (Join-Path $projectRoot '.codex\aidd-agent-kit.manifest')
  )) {
    Assert-AiddFile -Phase 'project-sync-artifacts' -Path $path
  }
  Assert-AiddNoOp -Phase 'project-sync-no-op' -Category 'windows-project-sync' `
    -BatchPath $sync -TargetHome $projectRoot

  Write-AiddPhase -Phase 'home-integrity' -Category 'snapshot' `
    -Path $realUserProfile
  $afterSnapshot = @(Get-AiddHomeSnapshot -UserProfile $realUserProfile)
  $homeDiff = Compare-Object $beforeSnapshot $afterSnapshot
  if ($homeDiff) {
    Stop-AiddSmoke -Phase 'home-integrity' -Category 'userprofile-content' `
      -Path $realUserProfile -ExitCode 'contract' -Message 'snapshot changed'
  }
  if ($env:USERPROFILE -ne $realUserProfile) {
    Stop-AiddSmoke -Phase 'home-integrity' -Category 'userprofile-variable' `
      -Path $realUserProfile -ExitCode 'contract' -Message 'USERPROFILE changed'
  }

  $completed = $true
  Write-AiddPhase -Phase 'complete' -Category 'windows-smoke' -Path $fixtureRoot
} catch {
  if ($_.Exception.Message.StartsWith(
    '[AIDD-SMOKE]',
    [StringComparison]::Ordinal
  )) {
    throw
  }
  $unexpectedMessage = $_.Exception.Message.Replace("`r", ' ').Replace("`n", ' ')
  Stop-AiddSmoke -Phase $script:CurrentPhase -Category $script:CurrentCategory `
    -Path $script:CurrentPath -ExitCode 'exception' `
    -Message ('unexpected PowerShell failure: {0}' -f $unexpectedMessage)
} finally {
  Restore-AiddEnvironment -Original $originalEnvironment
  if ($completed) {
    foreach ($path in $fixtureRoots) {
      if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
      }
    }
  } elseif (-not $completed) {
    foreach ($path in $fixtureRoots) {
      Write-Host ('[AIDD-SMOKE] phase=failed category=fixture-retained path="{0}"' -f `
        $path)
    }
  }
}
