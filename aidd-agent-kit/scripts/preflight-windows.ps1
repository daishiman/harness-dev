[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$KitRoot,

    [ValidateSet('0', '1')]
    [string]$LegacyPrompts = '0'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# 診断に出す日本語が ??? に化けないようにする。Windows PowerShell 5.1 の
# 既定の出力コードページは英語 Windows では 437 で、日本語を落とす。
# 失敗の原因を書いた行が読めなければ、検査があっても支援側は動けない。
try {
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
} catch {
    # 出力先がコンソールでない場合は設定できない。診断が読みにくくなるだけで
    # 検査そのものは成立するため、ここで止めない。
}

# ファイルは必ず UTF-8 として読む。
# Windows PowerShell 5.1 の Get-Content は BOM が無いと ANSI コードページ
# (英語 Windows なら 1252、日本語 Windows なら 932) で読む。UTF-8 で書かれた
# 日本語はそこで別の文字に化け、日本語の判定に通らなくなる。つまり
# 「日本語が書かれていない」と誤って落ちる。利用者の Windows の言語設定で
# 結果が変わる検査になってはいけない。
function Read-AiddText {
    param([Parameter(Mandatory = $true)][string]$FilePath)
    $full = (Resolve-Path -LiteralPath $FilePath -ErrorAction Stop).ProviderPath
    return [IO.File]::ReadAllText($full, [Text.Encoding]::UTF8)
}

function Read-AiddLines {
    param([Parameter(Mandatory = $true)][string]$FilePath)
    $full = (Resolve-Path -LiteralPath $FilePath -ErrorAction Stop).ProviderPath
    return [IO.File]::ReadAllLines($full, [Text.Encoding]::UTF8)
}

$script:CurrentStage = 'bootstrap'
$script:CurrentCategory = 'unexpected'
$script:CurrentPath = $KitRoot

function Set-PreflightContext {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$Category,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $script:CurrentStage = $Stage
    $script:CurrentCategory = $Category
    $script:CurrentPath = $Path
}

function Format-PreflightMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$Category,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $safePath = $Path.Replace("`r", '').Replace("`n", '').Replace('"', "'")
    $safeMessage = $Message.Replace("`r", ' ').Replace("`n", ' ')
    return ('[AIDD-PREFLIGHT] stage={0} category={1} path="{2}" message={3}' -f `
        $Stage, $Category, $safePath, $safeMessage)
}

function Throw-PreflightFailure {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$Category,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Set-PreflightContext -Stage $Stage -Category $Category -Path $Path
    throw (Format-PreflightMessage `
        -Stage $Stage `
        -Category $Category `
        -Path $Path `
        -Message $Message)
}

function Test-SkillMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedName,

        [Parameter(Mandatory = $true)]
        [hashtable]$SeenNames
    )

    Set-PreflightContext -Stage 'skill' -Category 'read' -Path $FilePath
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'missing-file' `
            -Path $FilePath `
            -Message 'SKILL.md is missing.'
    }

    $text = Read-AiddText -FilePath $FilePath
    Set-PreflightContext -Stage 'skill' -Category 'frontmatter' -Path $FilePath
    $frontmatter = [regex]::Match($text, '(?s)\A---\r?\n(.*?)\r?\n---')
    if (-not $frontmatter.Success) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'frontmatter' `
            -Path $FilePath `
            -Message 'Frontmatter is missing or is not closed.'
    }

    $metadata = $frontmatter.Groups[1].Value
    $nameMatch = [regex]::Match(
        $metadata,
        '(?m)^name:[ \t]*([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)[ \t]*\r?$'
    )
    $descriptionMatch = [regex]::Match(
        $metadata,
        '(?m)^description:[ \t]*(?<value>[^\r\n]*)\r?$'
    )
    if (-not $nameMatch.Success -or $nameMatch.Groups[1].Value -ne $ExpectedName) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'name' `
            -Path $FilePath `
            -Message ('Skill name must match its distribution directory: {0}' -f $ExpectedName)
    }
    if (-not $descriptionMatch.Success) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'description' `
            -Path $FilePath `
            -Message 'Description is missing.'
    }

    $descriptionHead = $descriptionMatch.Groups['value'].Value.Trim()
    $descriptionText = $descriptionHead
    if ($descriptionHead -match '^[>|](?:[1-9][+-]?|[+-][1-9]?)?(?:[ \t]+#.*)?$') {
        $hasBlockBody = $false
        $descriptionLines = @()
        $tail = $metadata.Substring(
            $descriptionMatch.Index + $descriptionMatch.Length
        )
        foreach ($line in ($tail -split '\r?\n')) {
            if ($line -match '^[ \t]+\S') {
                $hasBlockBody = $true
                $descriptionLines += $line.Trim()
                continue
            }
            if ($line -match '^\S') {
                break
            }
        }
        if (-not $hasBlockBody) {
            Throw-PreflightFailure `
                -Stage 'skill' `
                -Category 'description' `
                -Path $FilePath `
                -Message 'Block scalar description is empty.'
        }
        $descriptionText = $descriptionLines -join "`n"
    }
    elseif ([string]::IsNullOrWhiteSpace($descriptionHead)) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'description' `
            -Path $FilePath `
            -Message 'Description is empty.'
    }

    $japanesePattern = '[ぁ-んァ-ヶ一-龯々ー]'
    $bodyStart = $frontmatter.Index + $frontmatter.Length
    $body = $text.Substring($bodyStart)
    if ($descriptionText -notmatch $japanesePattern -or $body -notmatch $japanesePattern) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'japanese-interface' `
            -Path $FilePath `
            -Message 'Skill description and operating instructions must include Japanese.'
    }

    if ($SeenNames.ContainsKey($ExpectedName)) {
        Throw-PreflightFailure `
            -Stage 'skill' `
            -Category 'duplicate-name' `
            -Path $FilePath `
            -Message ('Duplicate Codex skill name: {0}' -f $ExpectedName)
    }
    $SeenNames[$ExpectedName] = $true
}

function Test-Skills {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $seenNames = @{}
    foreach ($relativeRoot in @('skills', 'codex\workflow-skills')) {
        $skillRoot = Join-Path $Root $relativeRoot
        Set-PreflightContext -Stage 'skill' -Category 'enumerate' -Path $skillRoot
        $directories = @(
            Get-ChildItem `
                -LiteralPath $skillRoot `
                -Directory `
                -Force `
                -ErrorAction Stop
        )
        foreach ($directory in $directories) {
            Test-SkillMetadata `
                -FilePath (Join-Path $directory.FullName 'SKILL.md') `
                -ExpectedName $directory.Name `
                -SeenNames $seenNames
        }
    }

    Test-SkillMetadata `
        -FilePath (Join-Path $Root 'agents\app-orchestrator.md') `
        -ExpectedName 'app-orchestrator' `
        -SeenNames $seenNames
}

function Assert-TomlRequiredString {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        Throw-PreflightFailure `
            -Stage 'toml' `
            -Category 'required-field' `
            -Path $FilePath `
            -Message ('Required string is empty: {0}' -f $Key)
    }
    if ($Key -eq 'name' -and $Value -notmatch '^[a-z][a-z0-9_]*$') {
        Throw-PreflightFailure `
            -Stage 'toml' `
            -Category 'required-field' `
            -Path $FilePath `
            -Message 'Required name must match [a-z][a-z0-9_]*.'
    }
}

function Test-AgentToml {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath
    )

    Set-PreflightContext -Stage 'toml' -Category 'read' -Path $FilePath
    $lines = @(Read-AiddLines -FilePath $FilePath)
    Set-PreflightContext -Stage 'toml' -Category 'parse' -Path $FilePath
    $requiredKeys = @('name', 'description', 'developer_instructions')
    $seen = @{}
    $inTopLevel = $true
    $multilineKey = $null
    $multilineDelimiter = $null
    $multilineValue = New-Object System.Text.StringBuilder

    foreach ($rawLine in $lines) {
        if ($null -ne $multilineKey) {
            $closingIndex = $rawLine.IndexOf(
                $multilineDelimiter,
                [System.StringComparison]::Ordinal
            )
            if ($closingIndex -lt 0) {
                [void]$multilineValue.AppendLine($rawLine)
                continue
            }

            [void]$multilineValue.Append($rawLine.Substring(0, $closingIndex))
            $afterClosing = $rawLine.Substring(
                $closingIndex + $multilineDelimiter.Length
            )
            if ($afterClosing -notmatch '^[ \t]*(?:#.*)?$') {
                Throw-PreflightFailure `
                    -Stage 'toml' `
                    -Category 'string-syntax' `
                    -Path $FilePath `
                    -Message ('Unexpected content after multiline string: {0}' -f $multilineKey)
            }
            Assert-TomlRequiredString `
                -FilePath $FilePath `
                -Key $multilineKey `
                -Value $multilineValue.ToString()
            $multilineKey = $null
            $multilineDelimiter = $null
            $multilineValue.Length = 0
            continue
        }

        if (-not $inTopLevel) {
            continue
        }
        if ($rawLine -match '^[ \t]*(?:#.*)?$') {
            continue
        }
        if ($rawLine -match '^[ \t]*\[\[?.*\]\]?[ \t]*(?:#.*)?$') {
            $inTopLevel = $false
            continue
        }
        if ($rawLine -notmatch '^[ \t]*(name|description|developer_instructions)[ \t]*=[ \t]*(.*)$') {
            continue
        }

        $key = $Matches[1]
        $rawValue = $Matches[2]
        if ($seen.ContainsKey($key)) {
            Throw-PreflightFailure `
                -Stage 'toml' `
                -Category 'required-field' `
                -Path $FilePath `
                -Message ('Required key is duplicated: {0}' -f $key)
        }
        $seen[$key] = $true

        $delimiter = $null
        if ($rawValue.StartsWith('"""')) {
            $delimiter = '"""'
        }
        elseif ($rawValue.StartsWith("'''")) {
            $delimiter = "'''"
        }

        if ($null -ne $delimiter) {
            $afterOpening = $rawValue.Substring($delimiter.Length)
            $closingIndex = $afterOpening.IndexOf(
                $delimiter,
                [System.StringComparison]::Ordinal
            )
            if ($closingIndex -ge 0) {
                $value = $afterOpening.Substring(0, $closingIndex)
                $afterClosing = $afterOpening.Substring(
                    $closingIndex + $delimiter.Length
                )
                if ($afterClosing -notmatch '^[ \t]*(?:#.*)?$') {
                    Throw-PreflightFailure `
                        -Stage 'toml' `
                        -Category 'string-syntax' `
                        -Path $FilePath `
                        -Message ('Unexpected content after multiline string: {0}' -f $key)
                }
                Assert-TomlRequiredString `
                    -FilePath $FilePath `
                    -Key $key `
                    -Value $value
                continue
            }

            $multilineKey = $key
            $multilineDelimiter = $delimiter
            [void]$multilineValue.AppendLine($afterOpening)
            continue
        }

        $basicString = [regex]::Match(
            $rawValue,
            '^"(?<value>(?:\\.|[^"\\])*)"[ \t]*(?:#.*)?$'
        )
        $literalString = [regex]::Match(
            $rawValue,
            "^'(?<value>[^']*)'[ \\t]*(?:#.*)?$"
        )
        if ($basicString.Success) {
            Assert-TomlRequiredString `
                -FilePath $FilePath `
                -Key $key `
                -Value $basicString.Groups['value'].Value
            continue
        }
        if ($literalString.Success) {
            Assert-TomlRequiredString `
                -FilePath $FilePath `
                -Key $key `
                -Value $literalString.Groups['value'].Value
            continue
        }

        Throw-PreflightFailure `
            -Stage 'toml' `
            -Category 'required-field' `
            -Path $FilePath `
            -Message ('Required value must be a non-empty TOML string: {0}' -f $key)
    }

    if ($null -ne $multilineKey) {
        Throw-PreflightFailure `
            -Stage 'toml' `
            -Category 'string-syntax' `
            -Path $FilePath `
            -Message ('Multiline string is not closed: {0}' -f $multilineKey)
    }

    foreach ($requiredKey in $requiredKeys) {
        if (-not $seen.ContainsKey($requiredKey)) {
            Throw-PreflightFailure `
                -Stage 'toml' `
                -Category 'required-field' `
                -Path $FilePath `
                -Message ('Required string is missing: {0}' -f $requiredKey)
        }
    }
}

function Test-AgentTomlFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $agentRoot = Join-Path $Root 'codex\agents'
    Set-PreflightContext -Stage 'toml' -Category 'enumerate' -Path $agentRoot
    $files = @(
        Get-ChildItem `
            -LiteralPath $agentRoot `
            -Filter '*.toml' `
            -File `
            -Force `
            -ErrorAction Stop
    )
    foreach ($file in $files) {
        Test-AgentToml -FilePath $file.FullName
    }
}

function Assert-NotReparsePoint {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileSystemInfo]$Item
    )

    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Throw-PreflightFailure `
            -Stage 'source-reparse' `
            -Category 'reparse-point' `
            -Path $Item.FullName `
            -Message 'Source path is a reparse point.'
    }
}

function Test-SourceReparsePoints {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$IncludeLegacyPrompts
    )

    $relativeRoots = @(
        'skills',
        'agents',
        'commands',
        'scripts',
        'codex\workflow-skills',
        'codex\agents'
    )
    if ($IncludeLegacyPrompts -eq '1') {
        $relativeRoots += 'codex\prompts'
    }

    foreach ($relativeRoot in $relativeRoots) {
        $sourceRoot = Join-Path $Root $relativeRoot
        Set-PreflightContext `
            -Stage 'source-reparse' `
            -Category 'enumerate' `
            -Path $sourceRoot
        $rootItem = Get-Item -LiteralPath $sourceRoot -Force -ErrorAction Stop
        Assert-NotReparsePoint -Item $rootItem
        $children = @(
            Get-ChildItem `
                -LiteralPath $sourceRoot `
                -Recurse `
                -Force `
                -ErrorAction Stop
        )
        foreach ($child in $children) {
            Assert-NotReparsePoint -Item $child
        }
    }

    $directPath = Join-Path $Root 'codex\app-orchestrator-openai.yaml'
    Set-PreflightContext `
        -Stage 'source-reparse' `
        -Category 'read' `
        -Path $directPath
    $directItem = Get-Item -LiteralPath $directPath -Force -ErrorAction Stop
    Assert-NotReparsePoint -Item $directItem

    # LICENSE / NOTICE / ATTRIBUTION.md は Apache-2.0 4(a) を満たすため
    # 配置物へ同行させる。差し替えの入り口にならないよう、他のコピー元と
    # 同じく reparse point でないことを確かめる。
    foreach ($legalName in @('LICENSE', 'NOTICE', 'ATTRIBUTION.md')) {
        $legalPath = Join-Path $Root $legalName
        Set-PreflightContext `
            -Stage 'source-reparse' `
            -Category 'read' `
            -Path $legalPath
        $legalItem = Get-Item -LiteralPath $legalPath -Force -ErrorAction Stop
        Assert-NotReparsePoint -Item $legalItem
    }
}

try {
    Set-PreflightContext -Stage 'bootstrap' -Category 'kit-root' -Path $KitRoot
    $normalizedRoot = [IO.Path]::GetFullPath($KitRoot)
    if (-not (Test-Path -LiteralPath $normalizedRoot -PathType Container)) {
        Throw-PreflightFailure `
            -Stage 'bootstrap' `
            -Category 'kit-root' `
            -Path $normalizedRoot `
            -Message 'Kit root directory does not exist.'
    }

    Test-Skills -Root $normalizedRoot
    Test-AgentTomlFiles -Root $normalizedRoot
    Test-SourceReparsePoints `
        -Root $normalizedRoot `
        -IncludeLegacyPrompts $LegacyPrompts
    exit 0
}
catch {
    $message = $_.Exception.Message
    if (-not $message.StartsWith(
        '[AIDD-PREFLIGHT]',
        [System.StringComparison]::Ordinal
    )) {
        $message = Format-PreflightMessage `
            -Stage $script:CurrentStage `
            -Category $script:CurrentCategory `
            -Path $script:CurrentPath `
            -Message $message
    }
    [Console]::Error.WriteLine($message)
    exit 1
}
