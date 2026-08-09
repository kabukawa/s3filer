#Requires -Version 5.1
<#
.SYNOPSIS
  S3 Filer launcher for Windows PowerShell / PowerShell 7+ (sss).

.DESCRIPTION
  Thin wrapper around s3filer.ps1. Use this from PowerShell:

    .\sss.ps1
    .\sss.ps1 -p myprofile
    .\sss.ps1 --version

  Note: the extensionless file "sss" is a bash script for Git Bash / Unix.
  PowerShell cannot run it; use this .ps1 (or .\sss.cmd from cmd).

.EXAMPLE
  .\sss.ps1
.EXAMPLE
  .\sss.ps1 -p default -Left . -Right s3://
#>

$ErrorActionPreference = 'Stop'

# Resolve own directory (works with -File and direct invocation)
if ($PSScriptRoot) {
    $Root = $PSScriptRoot
} else {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$launcher = Join-Path $Root 's3filer.ps1'
if (-not (Test-Path -LiteralPath $launcher)) {
    Write-Error "s3filer.ps1 not found next to sss.ps1: $launcher"
    exit 1
}

# Forward every argument (named flags and remaining CLI args) to s3filer.ps1
& $launcher @args
exit $LASTEXITCODE
