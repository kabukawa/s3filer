"""Windows drives, cloud folders (Box / OneDrive), and WSL UNC places."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import FileEntry, LocationKind, PathLocation

# Virtual local root (same idea as s3://). Not a real filesystem path.
PLACES_ROOT = "thispc:"

_DRIVE_RE = re.compile(r"^[A-Za-z]:$")
_CLOUD_HOME_DIRS: tuple[tuple[str, str], ...] = (
    ("Box", "Box"),
    ("OneDrive", "OneDrive"),
    ("Dropbox", "Dropbox"),
    ("Google Drive", "Google Drive"),
    ("iCloud Drive", "iCloudDrive"),
)
# FOLDERID_OneDrive
_FOLDERID_ONEDRIVE = "{A52BBA46-E9E1-435F-B3D9-28DAA648C0F6}"

_DRIVE_TYPES = {
    0: "UNKNOWN",
    1: "NO_ROOT",
    2: "REMOVABLE",
    3: "FIXED",
    4: "REMOTE",
    5: "CDROM",
    6: "RAMDISK",
}


def is_places_root(path: str) -> bool:
    if not path:
        return False
    p = path.strip().rstrip("/\\").lower()
    return p in ("thispc:", "thispc://", "pc:", "pc://")


def is_unc_path(path: str) -> bool:
    return path.startswith("\\\\") or path.startswith("//")


def is_volume_root(path: str) -> bool:
    """True for C:\\, \\\\host\\share, or Unix /."""
    if not path or is_places_root(path):
        return False
    if os.name != "nt":
        norm = os.path.normpath(path)
        return norm in ("/", "\\")
    p = path.replace("/", "\\").rstrip("\\")
    if _DRIVE_RE.fullmatch(p):
        return True
    if p.startswith("\\\\"):
        parts = [x for x in p.split("\\") if x]
        return len(parts) == 2
    return False


def volume_root_of(path: str) -> str:
    """Drive / UNC share / Unix / for *path*. Places root stays places root."""
    if is_places_root(path):
        return PLACES_ROOT
    if os.name != "nt":
        return "/"
    p = path.replace("/", "\\")
    drive, _tail = os.path.splitdrive(p)
    if drive:
        if drive.startswith("\\\\"):
            return drive
        return drive + "\\"
    return PLACES_ROOT


def local_parent_path(path: str) -> str:
    """Parent directory; volume roots on Windows go to the places list."""
    if is_places_root(path):
        return PLACES_ROOT
    if os.name == "nt" and is_volume_root(path):
        return PLACES_ROOT
    stripped = path.rstrip("\\/")
    parent = os.path.dirname(stripped)
    if not parent or parent == path or parent == stripped:
        if os.name == "nt":
            return PLACES_ROOT
        return path
    return parent


def _unc_parts(path: str) -> list[str]:
    p = path.replace("/", "\\")
    if p.startswith("\\\\"):
        return [x for x in p[2:].split("\\") if x]
    return [x for x in p.split("\\") if x]


def normalize_unc(path: str) -> str:
    p = path.replace("/", "\\")
    while "\\\\\\" in p:
        p = p.replace("\\\\\\", "\\\\")
    parts = _unc_parts(p)
    if len(parts) <= 2:
        return "\\\\" + "\\".join(parts)
    return "\\\\" + "\\".join(parts)


@dataclass(frozen=True)
class Place:
    name: str
    path: str
    kind: str  # DRIVE | CLOUD | WSL


def list_drive_letters() -> list[str]:
    """Return roots like ``C:\\``."""
    if os.name != "nt":
        return []
    if hasattr(os, "listdrives"):
        try:
            return list(os.listdrives())
        except OSError:
            pass
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return []
    out: list[str] = []
    for i in range(26):
        if mask & (1 << i):
            out.append(f"{chr(ord('A') + i)}:\\")
    return out


def _volume_label(root: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(261)
        fsbuf = ctypes.create_unicode_buffer(261)
        serial = wintypes.DWORD()
        maxcomp = wintypes.DWORD()
        flags = wintypes.DWORD()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            root,
            buf,
            261,
            ctypes.byref(serial),
            ctypes.byref(maxcomp),
            ctypes.byref(flags),
            fsbuf,
            261,
        )
        if ok and buf.value:
            return buf.value
    except Exception:
        pass
    return ""


def _drive_type_name(root: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        GetDriveTypeW.restype = wintypes.UINT
        return _DRIVE_TYPES.get(int(GetDriveTypeW(root)), "")
    except Exception:
        return ""


def _short(label: str, max_len: int = 28) -> str:
    label = " ".join(label.split())
    if len(label) <= max_len:
        return label
    return label[: max_len - 1] + "…"


def iter_drive_places() -> list[Place]:
    places: list[Place] = []
    for root in list_drive_letters():
        letter = root[:2] if len(root) >= 2 else root.rstrip("\\")
        label = _short(_volume_label(root))
        dtype = _drive_type_name(root)
        extra = label
        if dtype in ("REMOVABLE", "REMOTE", "CDROM", "RAMDISK") and not extra:
            extra = dtype
        name = f"{letter}  {extra}" if extra else letter
        places.append(Place(name=name, path=root, kind="DRIVE"))
    return places


def _known_folder_path(folder_id: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        ole32 = ctypes.windll.ole32
        shell32 = ctypes.windll.shell32
        guid = GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(folder_id), ctypes.byref(guid))
        path_ptr = ctypes.c_void_p()
        SHGetKnownFolderPath = shell32.SHGetKnownFolderPath
        SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        SHGetKnownFolderPath.restype = ctypes.HRESULT
        hr = SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
        if hr != 0 or not path_ptr.value:
            return None
        value = ctypes.wstring_at(path_ptr.value)
        ole32.CoTaskMemFree(path_ptr)
        return value or None
    except Exception:
        return None


def _isdir(path: str) -> bool:
    try:
        return os.path.isdir(path)
    except OSError:
        return False


def iter_cloud_places() -> list[Place]:
    if os.name != "nt":
        return []
    found: list[Place] = []
    seen: set[str] = set()

    def add(name: str, path: str) -> None:
        if not path or not _isdir(path):
            return
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            return
        seen.add(key)
        found.append(Place(name=name, path=path, kind="CLOUD"))

    od = _known_folder_path(_FOLDERID_ONEDRIVE)
    if od:
        add("OneDrive", od)

    home = Path.home()
    for label, dirname in _CLOUD_HOME_DIRS:
        add(label, str(home / dirname))
    try:
        for p in home.glob("OneDrive*"):
            if p.is_dir():
                add(p.name, str(p))
    except OSError:
        pass
    return found


def list_wsl_distros() -> list[str]:
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    raw = result.stdout or b""
    if not raw:
        return []
    # wsl.exe writes UTF-16LE; fall back if a wrapper emits UTF-8
    if b"\x00" in raw[:8] or (len(raw) >= 2 and raw[1] == 0):
        text = raw.decode("utf-16-le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    names: list[str] = []
    for line in text.splitlines():
        name = line.replace("\x00", "").strip()
        if name:
            names.append(name)
    return names


def iter_wsl_places() -> list[Place]:
    places: list[Place] = []
    for distro in list_wsl_distros():
        for base in (r"\\wsl.localhost", r"\\wsl$"):
            path = f"{base}\\{distro}"
            if _isdir(path):
                places.append(Place(name=f"WSL  {distro}", path=path, kind="WSL"))
                break
    return places


def iter_places() -> list[Place]:
    """Drives first, then cloud folders, then WSL (Windows only)."""
    if os.name != "nt":
        return []
    seen: set[str] = set()
    out: list[Place] = []
    for group in (iter_drive_places(), iter_cloud_places(), iter_wsl_places()):
        for place in group:
            key = os.path.normcase(os.path.normpath(place.path))
            if key in seen:
                continue
            seen.add(key)
            out.append(place)
    return out


def list_places_entries() -> list[FileEntry]:
    loc = PathLocation(LocationKind.LOCAL, PLACES_ROOT)
    entries: list[FileEntry] = []
    for place in iter_places():
        entries.append(
            FileEntry(
                name=place.name,
                is_dir=True,
                parent_path=PLACES_ROOT,
                location=loc,
                target_path=place.path,
                storage_class=place.kind,
            )
        )
    return entries


def places_location() -> PathLocation:
    return PathLocation(LocationKind.LOCAL, PLACES_ROOT)
