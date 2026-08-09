@echo off
setlocal EnableExtensions
REM S3 Filer - Windows cmd fallback launcher
cd /d "%~dp0"

where powershell >nul 2>&1
if %ERRORLEVEL%==0 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0s3filer.ps1" %*
  exit /b %ERRORLEVEL%
)

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  echo Python not found. Install Python 3.10+ or create .venv
  exit /b 1
)

set "PYTHONPATH=%~dp0;%PYTHONPATH%"
%PY% -c "import s3filer" 2>nul
if errorlevel 1 (
  echo Installing s3filer dependencies...
  %PY% -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 exit /b 1
  %PY% -m pip install -e "%~dp0"
  if errorlevel 1 exit /b 1
)

%PY% -m s3filer %*
exit /b %ERRORLEVEL%
