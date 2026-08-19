@echo off
setlocal EnableExtensions
REM sss - S3 Filer launcher for Windows cmd
REM PowerShell users: run  .\sss.ps1
REM Keep the caller's cwd so the left pane opens there.

set "PS_EXE="
where pwsh >nul 2>&1
if not errorlevel 1 (
  set "PS_EXE=pwsh"
  goto run_ps
)
where powershell >nul 2>&1
if not errorlevel 1 (
  set "PS_EXE=powershell"
  goto run_ps
)

call "%~dp0s3filer.cmd" %*
exit /b %ERRORLEVEL%

:run_ps
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0s3filer.ps1" %*
exit /b %ERRORLEVEL%
