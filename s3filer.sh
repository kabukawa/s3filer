#!/usr/bin/env bash
# S3 Filer launcher for Linux / macOS / WSL / Git Bash (Windows)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Do not cd to $ROOT: default local pane is os.getcwd() (the caller's directory).

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

# Filesystem-only: do not spawn Python just to probe imports
# (import textual ~400ms, Pillow ~300ms on every launch).
textual_installed() {
  local py="$1"
  local prefix
  prefix="$(cd "$(dirname "$py")/.." && pwd)"
  if [[ -d "$prefix/Lib/site-packages/textual" || -d "$prefix/lib/site-packages/textual" ]]; then
    return 0
  fi
  local d
  for d in "$prefix"/lib/python*/site-packages/textual; do
    if [[ -d "$d" ]]; then
      return 0
    fi
  done
  return 1
}

is_project_venv_python() {
  local py="$1"
  case "$py" in
    "$ROOT/.venv/bin/python"|"$ROOT/.venv/bin/python3"|"$ROOT/.venv/Scripts/python.exe"|"$ROOT/.venv/Scripts/python"|"$ROOT/venv/Scripts/python.exe"|"$ROOT/venv/Scripts/python")
      return 0
      ;;
  esac
  return 1
}

ensure_package() {
  local py="$1"
  # Hot path: source tree is on PYTHONPATH. Auto-install only when the
  # selected interpreter is a project venv that does not yet have textual.
  # Pillow is optional (SIXEL) and is checked when viewing an image.
  if is_project_venv_python "$py" && ! textual_installed "$py"; then
    echo "Installing s3filer dependencies..." >&2
    "$py" -m pip install -r "$ROOT/requirements.txt"
    "$py" -m pip install -e "$ROOT"
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
