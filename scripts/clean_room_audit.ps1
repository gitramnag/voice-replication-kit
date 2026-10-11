[CmdletBinding()]
param(
    [string]$SourceRoot = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Split-Path -Parent $PSScriptRoot
}

function Assert-LastExitCode {
    param([Parameter(Mandatory)][string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$source = (Resolve-Path -LiteralPath $SourceRoot).Path
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$auditRoot = Join-Path $temporaryRoot ("voice-kit-clean-room-" + [guid]::NewGuid().ToString('N'))
$cloneRoot = Join-Path $auditRoot 'repository'
$privateTermsArguments = @()
if (-not [string]::IsNullOrWhiteSpace($env:VOICE_KIT_PRIVATE_TERMS_FILE)) {
    $privateTermsArguments = @(
        '--private-terms-file',
        $env:VOICE_KIT_PRIVATE_TERMS_FILE
    )
}

if (-not $auditRoot.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Clean-room target must stay below the system temporary directory'
}

New-Item -ItemType Directory -Path $auditRoot | Out-Null
try {
    Write-Host "+ git clone --no-local $source $cloneRoot"
    git clone --no-local --quiet -- $source $cloneRoot
    Assert-LastExitCode 'no-local clone'

    Push-Location -LiteralPath $cloneRoot
    try {
        Write-Host '+ python -m venv .venv'
        python -m venv .venv
        Assert-LastExitCode 'clean-room virtual environment'
        & .\.venv\Scripts\Activate.ps1

        Write-Host '+ python -m pip install --require-hashes -r configs/public-tools-lock.txt'
        python -m pip install --require-hashes -r configs/public-tools-lock.txt
        Assert-LastExitCode 'hash-locked public tools install'

        Write-Host '+ python -m pip install --no-build-isolation --no-deps -e .'
        python -m pip install --no-build-isolation --no-deps -e .
        Assert-LastExitCode 'editable public kit install'

        Write-Host '+ python -m pytest'
        python -m pytest
        Assert-LastExitCode 'test suite'

        Write-Host '+ python -m voice_replication_kit.corpus'
        python -m voice_replication_kit.corpus --source corpus/recording-script.json --output-dir corpus
        Assert-LastExitCode 'corpus regeneration'

        Write-Host '+ python tools/build_scorecard.py --check'
        python tools/build_scorecard.py --check evaluation/voice-evaluation-scorecard.xlsx
        Assert-LastExitCode 'scorecard byte check'

        Write-Host '+ python tools/build_diagrams.py --check'
        python tools/build_diagrams.py --check
        Assert-LastExitCode 'diagram byte checks'

        Write-Host '+ python scripts/check_links.py'
        python scripts/check_links.py --root .
        Assert-LastExitCode 'documentation link check'

        Write-Host '+ voice-kit audit --mode tree'
        voice-kit audit --mode tree --root . @privateTermsArguments
        Assert-LastExitCode 'tree privacy audit'

        Write-Host '+ voice-kit audit --mode history'
        voice-kit audit --mode history --root . @privateTermsArguments
        Assert-LastExitCode 'history privacy audit'

        Write-Host '+ git status --porcelain'
        $status = @(git status --porcelain)
        Assert-LastExitCode 'clean-worktree check'
        if ($status.Count -ne 0) {
            $status | Write-Host
            throw 'Generated public assets differ from committed bytes'
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if (Test-Path -LiteralPath $auditRoot) {
        Remove-Item -LiteralPath $auditRoot -Recurse -Force
    }
}

Write-Host 'Clean-room release audit passed.'
