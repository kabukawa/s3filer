#!/usr/bin/env bash
# S3 Filer launcher for Linux / macOS / WSL / Git Bash (Windows)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  if [[ -f "$ROOT/.venv/bin/activate" ]]; then
    # Linux / macOS / WSL
    # shellcheck source=/dev/null
    source "$ROOT/.venv/bin/activate"
  elif [[ -f "$ROOT/.venv/Scripts/activate" ]]; then
    # Git Bash / MSYS on Windows
    # shellcheck source=/dev/null
    source "$ROOT/.venv/Scripts/activate"
  fi
fi

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

resolve_python() {
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
    return
  fi
  if [[ -x "$ROOT/.venv/bin/python3" ]]; then
    echo "$ROOT/.venv/bin/python3"
    return
  fi
  if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT/.venv/Scripts/python.exe"
    return
  fi
  if [[ -x "$ROOT/.venv/Scripts/python" ]]; then
    echo "$ROOT/.venv/Scripts/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  echo "error: neither python3 nor python found in PATH" >&2
  echo "  Ubuntu/WSL : sudo apt install python3 python3-venv python3-pip" >&2
  echo "  Windows    : install Python 3.10+ (Add to PATH)" >&2
  echo "  then       : python3 -m venv .venv && source .venv/bin/activate" >&2
  exit 1
}

ensure_package() {
  local py="$1"
  if ! "$py" -c "import s3filer" >/dev/null 2>&1; then
    echo "Installing s3filer dependencies..." >&2
    "$py" -m pip install -r "$ROOT/requirements.txt"
    "$py" -m pip install -e "$ROOT"
  fi
  # Pillow for SIXEL image view — must match *this* interpreter (not plain pip3)
  if ! "$py" -c "from PIL import Image" >/dev/null 2>&1; then
    echo "Installing Pillow for image view ($py)..." >&2
    "$py" -m pip install "pillow>=10.0.0" || {
      echo "Warning: Pillow install failed. SIXEL image view unavailable." >&2
      echo "  Fix:  $py -m pip install pillow" >&2
    }
  fi
}

PYTHON="$(resolve_python)"
ensure_package "$PYTHON"

# Prefer console script from active venv if it is not this wrapper
if [[ -n "${VIRTUAL_ENV:-}" ]] && command -v s3filer >/dev/null 2>&1; then
  _sf="$(command -v s3filer)"
  case "$_sf" in
    "$ROOT/s3filer.sh"|"$ROOT/s3fd"|"$ROOT/s3fd.cmd"|"$ROOT/s3filer.cmd") ;;
    *) exec s3filer "$@" ;;
  esac
fi

exec "$PYTHON" -m s3filer "$@"
