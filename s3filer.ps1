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
# Do not Set-Location to $Root: default local pane is os.getcwd() (the caller's directory).

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

function Test-TextualInstalled {
    param([string]$PythonExe)
    # Filesystem-only: do not spawn Python (import textual ~400ms, Pillow ~300ms).
    $leaf = Split-Path -Leaf $PythonExe
    if ($leaf -eq 'py.exe') { return $false }
    $prefix = Split-Path -Parent (Split-Path -Parent $PythonExe)
    $direct = @(
        (Join-Path $prefix 'Lib\site-packages\textual'),
        (Join-Path $prefix 'lib\site-packages\textual')
    )
    foreach ($p in $direct) {
        if (Test-Path -LiteralPath $p) { return $true }
    }
    $lib = Join-Path $prefix 'lib'
    if (Test-Path -LiteralPath $lib) {
        $hits = Get-ChildItem -Path $lib -Directory -Filter 'python*' -ErrorAction SilentlyContinue
        foreach ($dir in $hits) {
            if (Test-Path -LiteralPath (Join-Path $dir.FullName 'site-packages\textual')) {
                return $true
            }
        }
    }
    return $false
}

function Test-ProjectVenvPython {
    param([string]$PythonExe)
    return $PythonExe -match '[\\/]\.venv[\\/]Scripts[\\/]python(\.exe)?$' -or
        $PythonExe -match '[\\/]venv[\\/]Scripts[\\/]python(\.exe)?$'
}

$python = Resolve-Python
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$env:PYTHONPATH" } else { $Root }

# Hot path: no extra Python processes. Source tree is on PYTHONPATH.
# Auto-install only when the selected interpreter is a project venv that
# does not yet have textual (first run after `python -m venv .venv`).
# Pillow is optional (SIXEL) and is checked when viewing an image.
if ((Test-ProjectVenvPython -PythonExe $python) -and -not (Test-TextualInstalled -PythonExe $python)) {
    Write-Host "Installing dependencies into this interpreter..." -ForegroundColor Yellow
    & $python -m pip install -r (Join-Path $Root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install requirements failed (exit $LASTEXITCODE)" }
    & $python -m pip install -e $Root
    if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed (exit $LASTEXITCODE)" }
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

