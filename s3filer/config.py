"""User configuration persisted across sessions."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

DEFAULT_THEME = "classic-blue"
DEFAULT_LANGUAGE = "ja"
DEFAULT_VIEWER_MODE = "builtin"  # builtin | external_prefer
DEFAULT_ARCHIVE_EXTRACT_MODE = "preserve"  # preserve | flat
DEFAULT_SIXEL_MODE = "auto"  # auto | on | off

# Built-in defaults for external viewers by extension (user can override)
DEFAULT_VIEWER_COMMANDS: dict[str, str] = {
    # examples only — empty means use builtin unless user sets them
}

_DEFAULTS: dict[str, Any] = {
    "theme": DEFAULT_THEME,
    "language": DEFAULT_LANGUAGE,
    "viewer_mode": DEFAULT_VIEWER_MODE,
    "viewer_commands": {},
    "archive_extract_mode": DEFAULT_ARCHIVE_EXTRACT_MODE,
    "sixel_mode": DEFAULT_SIXEL_MODE,
}

# In-process cache (mtime-invalidated). Avoids re-reading config.json on every t()/get_*.
_cache: Optional[dict[str, Any]] = None
_cache_mtime_ns: int = -1
_cache_path: Optional[str] = None


def config_dir() -> Path:
    """
    Config directory:
      Windows: %APPDATA%\\s3filer
      else:    ~/.config/s3filer  (or $XDG_CONFIG_HOME/s3filer)
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "s3filer"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "s3filer"
    return Path.home() / ".config" / "s3filer"


def config_path() -> Path:
    return config_dir() / "config.json"


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(_DEFAULTS)
    for k, v in data.items():
        if k == "viewer_commands" and isinstance(v, dict):
            out["viewer_commands"] = {str(kk).lower(): str(vv) for kk, vv in v.items()}
        else:
            out[k] = v
    # normalize
    lang = str(out.get("language") or DEFAULT_LANGUAGE).lower()
    out["language"] = "en" if lang.startswith("en") else "ja"
    mode = str(out.get("viewer_mode") or DEFAULT_VIEWER_MODE).lower()
    if mode not in ("builtin", "external_prefer"):
        mode = DEFAULT_VIEWER_MODE
    out["viewer_mode"] = mode
    amode = str(out.get("archive_extract_mode") or DEFAULT_ARCHIVE_EXTRACT_MODE).lower()
    if amode not in ("preserve", "flat"):
        amode = DEFAULT_ARCHIVE_EXTRACT_MODE
    out["archive_extract_mode"] = amode
    smode = str(out.get("sixel_mode") or DEFAULT_SIXEL_MODE).lower()
    # accept aliases from older docs / env-style values
    if smode in ("1", "true", "yes", "force", "always"):
        smode = "on"
    elif smode in ("0", "false", "no", "never", "disable", "disabled"):
        smode = "off"
    if smode not in ("auto", "on", "off"):
        smode = DEFAULT_SIXEL_MODE
    out["sixel_mode"] = smode
    if not isinstance(out.get("viewer_commands"), dict):
        out["viewer_commands"] = {}
    return out


def invalidate_config_cache() -> None:
    """Drop the in-memory config cache (e.g. after external edit)."""
    global _cache, _cache_mtime_ns, _cache_path
    _cache = None
    _cache_mtime_ns = -1
    _cache_path = None


def load_config(*, copy: bool = True) -> dict[str, Any]:
    """
    Load merged config.

    ``copy=False`` returns the cached dict for read-only use (getters).
    Callers that mutate the result must use the default ``copy=True``.
    """
    global _cache, _cache_mtime_ns, _cache_path
    path = config_path()
    path_s = str(path)
    try:
        st = path.stat()
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
    except OSError:
        # Missing file — cache defaults briefly
        if _cache is not None and _cache_path == path_s and _cache_mtime_ns == -2:
            return deepcopy(_cache) if copy else _cache
        data = deepcopy(_DEFAULTS)
        _cache = data
        _cache_mtime_ns = -2
        _cache_path = path_s
        return deepcopy(data) if copy else data

    if (
        _cache is not None
        and _cache_path == path_s
        and _cache_mtime_ns == mtime_ns
    ):
        return deepcopy(_cache) if copy else _cache

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            data = deepcopy(_DEFAULTS)
        else:
            data = _merge_defaults(raw)
    except (OSError, json.JSONDecodeError):
        data = deepcopy(_DEFAULTS)

    _cache = data
    _cache_mtime_ns = mtime_ns
    _cache_path = path_s
    return deepcopy(data) if copy else data


def save_config(data: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_config()
    # viewer_commands: callers pass the full map (replace, not merge),
    # so deletes and edits stick correctly.
    if "viewer_commands" in data and isinstance(data["viewer_commands"], dict):
        current["viewer_commands"] = {
            str(k).lower(): str(v)
            for k, v in data["viewer_commands"].items()
            if str(v).strip()
        }
        data = {k: v for k, v in data.items() if k != "viewer_commands"}
    current.update(data)
    current = _merge_defaults(current)
    path.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Refresh cache from what we just wrote
    global _cache, _cache_mtime_ns, _cache_path
    _cache = current
    try:
        st = path.stat()
        _cache_mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
    except OSError:
        _cache_mtime_ns = -1
    _cache_path = str(path)
    return path


def get_theme_name() -> str:
    env = (os.environ.get("S3FILER_THEME") or "").strip()
    if env:
        return env
    return str(load_config(copy=False).get("theme") or DEFAULT_THEME)


def set_theme_name(name: str) -> Path:
    return save_config({"theme": name})


def get_language() -> str:
    env = (os.environ.get("S3FILER_LANG") or "").strip().lower()
    if env.startswith("en"):
        return "en"
    if env.startswith("ja"):
        return "ja"
    return str(load_config(copy=False).get("language") or DEFAULT_LANGUAGE)


def set_language(lang: str) -> Path:
    lang = "en" if str(lang).lower().startswith("en") else "ja"
    return save_config({"language": lang})


def get_viewer_mode() -> str:
    return str(load_config(copy=False).get("viewer_mode") or DEFAULT_VIEWER_MODE)


def set_viewer_mode(mode: str) -> Path:
    mode = mode if mode in ("builtin", "external_prefer") else DEFAULT_VIEWER_MODE
    return save_config({"viewer_mode": mode})


def get_viewer_commands() -> dict[str, str]:
    cfg = load_config(copy=False).get("viewer_commands") or {}
    return {str(k).lower(): str(v) for k, v in cfg.items() if v}


def set_viewer_command(ext: str, command: str) -> Path:
    ext = ext if ext.startswith(".") else f".{ext}"
    ext = ext.lower()
    cmds = dict(get_viewer_commands())
    command = (command or "").strip()
    if command:
        cmds[ext] = command
    else:
        cmds.pop(ext, None)
    # Persist full map. Also switch to external_prefer when any command is set
    # so that View (v) actually uses registered commands.
    payload: dict[str, Any] = {"viewer_commands": cmds}
    if cmds:
        payload["viewer_mode"] = "external_prefer"
    return save_config(payload)


def get_archive_extract_mode() -> str:
    return str(
        load_config(copy=False).get("archive_extract_mode") or DEFAULT_ARCHIVE_EXTRACT_MODE
    )


def set_archive_extract_mode(mode: str) -> Path:
    mode = mode if mode in ("preserve", "flat") else DEFAULT_ARCHIVE_EXTRACT_MODE
    return save_config({"archive_extract_mode": mode})


def get_sixel_mode() -> str:
    """Return ``auto`` | ``on`` | ``off`` for built-in SIXEL image view."""
    return str(load_config(copy=False).get("sixel_mode") or DEFAULT_SIXEL_MODE)


def set_sixel_mode(mode: str) -> Path:
    mode = str(mode or "").lower().strip()
    if mode in ("1", "true", "yes", "force", "always"):
        mode = "on"
    elif mode in ("0", "false", "no", "never", "disable", "disabled"):
        mode = "off"
    if mode not in ("auto", "on", "off"):
        mode = DEFAULT_SIXEL_MODE
    return save_config({"sixel_mode": mode})


def viewer_command_for(filename: str) -> Optional[str]:
    """Return external viewer command template for this file, if configured."""
    name = filename.lower()
    cmds = get_viewer_commands()
    # longest suffix match
    best = None
    best_len = -1
    for ext, cmd in cmds.items():
        if name.endswith(ext) and len(ext) > best_len:
            best = cmd
            best_len = len(ext)
    return best
