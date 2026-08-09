#Requires -Version 5.1
<#
.SYNOPSIS
  Launch S3 Filer (dual-pane console file manager for Local + S3).

.DESCRIPTION
  Works from Windows PowerShell 5.1 and PowerShell 7+.
  Prefers project .venv if present; otherwise uses python / python3 on PATH.

.EXAMPLE
  # Preferred from PowerShell:
  .\sss.ps1
  .\sss.ps1 -p emeradaco-dev

.EXAMPLE
  .\s3filer.ps1

.EXAMPLE
  .\s3filer.ps1 -AwsProfile emeradaco-dev

.EXAMPLE
  .\s3filer.ps1 -p scb-dev -Left . -Right s3://

.EXAMPLE
  # From cmd, or if ExecutionPolicy blocks direct .ps1:
  .\sss.cmd -p default
#>
[CmdletBinding()]
param(
    # AWS CLI profile name (do NOT name this $Profile — that is reserved in PowerShell)
    [Alias('p', 'Profile')]
    [string]$AwsProfile = $(if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { $env:AWS_DEFAULT_PROFILE }),

    [Alias('l')]
    [string]$Left,

    [Alias('r')]
    [string]$Right,

    [Alias('Region')]
    [string]$AwsRegion = $(if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { $env:AWS_REGION }),

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = 'Stop'

# Resolve script directory (works when called via -File or direct path)
if ($PSScriptRoot) {
    $Root = $PSScriptRoot
} else {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
Set-Location -LiteralPath $Root

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root 'venv\Scripts\python.exe')
    )
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }

    foreach ($name in @('python', 'python3', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        # `py` launcher: prefer `py -3`
        if ($name -eq 'py') {
            return $cmd.Source
        }
        return $cmd.Source
    }

    throw @"
Python was not found.

Install Python 3.10+ from https://www.python.org/downloads/
  (check "Add python.exe to PATH")

Or create a venv in this folder:
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe -m pip install -e .
"@
}

function Test-S3FilerModule {
    param([string]$PythonExe)
    & $PythonExe -c "import s3filer" 2>$null
    return ($LASTEXITCODE -eq 0)
}

$python = Resolve-Python
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$env:PYTHONPATH" } else { $Root }

# Ensure package is importable; give a clear install hint if not
if (-not (Test-S3FilerModule -PythonExe $python)) {
    Write-Host "s3filer package not installed for: $python" -ForegroundColor Yellow
    Write-Host "Installing dependencies into this interpreter..." -ForegroundColor Yellow
    & $python -m pip install -r (Join-Path $Root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install requirements failed (exit $LASTEXITCODE)" }
    & $python -m pip install -e $Root
    if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed (exit $LASTEXITCODE)" }
}

# Pillow is required for SIXEL image view — install into *this* Python if missing
# (pip3 may target a different interpreter than the one Resolve-Python selected)
& $python -c "from PIL import Image" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pillow not found for: $python — installing..." -ForegroundColor Yellow
    & $python -m pip install "pillow>=10.0.0"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Pillow install failed. Image (SIXEL) view will be unavailable." -ForegroundColor Yellow
        Write-Host "  Fix:  $python -m pip install pillow" -ForegroundColor Yellow
    }
}

$argList = [System.Collections.Generic.List[string]]::new()
if ($AwsProfile) {
    $argList.Add('-p')
    $argList.Add($AwsProfile)
}
if ($AwsRegion) {
    $argList.Add('--region')
    $argList.Add($AwsRegion)
}
if ($Left) {
    $argList.Add('-l')
    $argList.Add($Left)
}
if ($Right) {
    $argList.Add('-r')
    $argList.Add($Right)
}
if ($RemainingArgs) {
    foreach ($a in $RemainingArgs) { $argList.Add($a) }
}

# Prefer `python -m s3filer` (reliable). Use py -3 -m when using the launcher.
$exeArgs = @()
if ((Split-Path -Leaf $python) -eq 'py.exe') {
    $exeArgs = @('-3', '-m', 's3filer') + $argList
} else {
    $exeArgs = @('-m', 's3filer') + $argList
}

Write-Verbose "Launch: $python $($exeArgs -join ' ')"
& $python @exeArgs
exit $LASTEXITCODE

