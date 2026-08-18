"""Local filesystem operations."""

from __future__ import annotations

import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .models import FileEntry, FileInfo, LocationKind, PathLocation
from .places import (
    PLACES_ROOT,
    is_places_root,
    is_unc_path,
    list_places_entries,
    normalize_unc,
)


def normalize_local_path(path: str) -> str:
    path = (path or "").strip()
    if is_places_root(path) or (os.name == "nt" and path in ("\\", "/")):
        return PLACES_ROOT if os.name == "nt" else os.path.abspath(os.sep)
    if os.name == "nt" and len(path) == 2 and path[1] == ":":
        path = path + "\\"
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    if is_unc_path(path):
        # resolve() on WSL/cloud UNC can hang or fail; keep the path as-is
        return normalize_unc(path)
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        p = p.absolute()
    return str(p)


def list_dir(location: PathLocation) -> list[FileEntry]:
    if is_places_root(location.path):
        if os.name != "nt":
            location = PathLocation(LocationKind.LOCAL, os.path.abspath(os.sep))
        else:
            return list_places_entries()
    path = normalize_local_path(location.path)
    if is_places_root(path):
        return list_places_entries()
    entries: list[FileEntry] = []

    parent = str(Path(path).parent)
    if parent != path:
        entries.append(
            FileEntry(
                name="..",
                is_dir=True,
                parent_path=path,
                location=location,
            )
        )

    dirs: list[FileEntry] = []
    files: list[FileEntry] = []
    # scandir is significantly faster than listdir + lstat per name
    try:
        with os.scandir(path) as it:
            batch = list(it)
    except OSError as e:
        raise RuntimeError(f"Cannot list {path}: {e}") from e

    batch.sort(key=lambda e: e.name.lower())
    loc = PathLocation(LocationKind.LOCAL, path)
    for de in batch:
        try:
            st = de.stat(follow_symlinks=False)
        except OSError:
            continue
        is_dir = stat.S_ISDIR(st.st_mode)
        entry = FileEntry(
            name=de.name,
            is_dir=is_dir,
            size=0 if is_dir else st.st_size,
            mtime=datetime.fromtimestamp(st.st_mtime),
            parent_path=path,
            location=loc,
        )
        (dirs if is_dir else files).append(entry)

    # dirs first, then files (classic filer style)
    return entries + dirs + files


def mkdir(path: str, name: str) -> str:
    target = os.path.join(normalize_local_path(path), name)
    os.makedirs(target, exist_ok=False)
    return target


def rename(src: str, new_name: str) -> str:
    src = normalize_local_path(src)
    parent = os.path.dirname(src)
    dest = os.path.join(parent, new_name)
    if os.path.exists(dest):
        raise FileExistsError(f"Already exists: {dest}")
    os.rename(src, dest)
    return dest


def delete(path: str) -> None:
    path = normalize_local_path(path)
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def copy_path(src: str, dest_dir: str, new_name: Optional[str] = None) -> str:
    src = normalize_local_path(src)
    dest_dir = normalize_local_path(dest_dir)
    name = new_name or os.path.basename(src.rstrip(os.sep))
    dest = os.path.join(dest_dir, name)
    if os.path.isdir(src) and not os.path.islink(src):
        if os.path.exists(dest):
            raise FileExistsError(f"Already exists: {dest}")
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return dest


def move_path(src: str, dest_dir: str, new_name: Optional[str] = None) -> str:
    src = normalize_local_path(src)
    dest_dir = normalize_local_path(dest_dir)
    name = new_name or os.path.basename(src.rstrip(os.sep))
    dest = os.path.join(dest_dir, name)
    shutil.move(src, dest)
    return dest


def read_bytes(path: str, max_bytes: int = 2 * 1024 * 1024) -> bytes:
    path = normalize_local_path(path)
    with open(path, "rb") as f:
        return f.read(max_bytes)


def file_info(path: str) -> FileInfo:
    path = normalize_local_path(path)
    st = os.stat(path)
    is_dir = stat.S_ISDIR(st.st_mode)
    mode = stat.filemode(st.st_mode)
    info = FileInfo(
        name=os.path.basename(path.rstrip(os.sep)) or path,
        path=path,
        is_dir=is_dir,
        size=0 if is_dir else st.st_size,
        mtime=datetime.fromtimestamp(st.st_mtime),
        kind=LocationKind.LOCAL,
        permissions=mode,
    )
    return info


def walk_tree(root: str, max_depth: int = 6) -> list[tuple[int, str, bool]]:
    """Return [(depth, name, is_dir), ...] for tree display."""
    root = normalize_local_path(root)
    result: list[tuple[int, str, bool]] = [(0, root, True)]

    def _walk(current: str, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            names = sorted(os.listdir(current), key=lambda n: n.lower())
        except OSError:
            return
        dirs = []
        for name in names:
            full = os.path.join(current, name)
            try:
                if os.path.isdir(full) and not os.path.islink(full):
                    dirs.append((name, full))
            except OSError:
                continue
        for name, full in dirs:
            result.append((depth + 1, name, True))
            _walk(full, depth + 1)

    _walk(root, 0)
    return result


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(normalize_local_path(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def iter_files_recursive(path: str) -> Iterable[tuple[str, str]]:
    """Yield (absolute_path, relative_path) for all files under path."""
    path = normalize_local_path(path)
    if os.path.isfile(path):
        yield path, os.path.basename(path)
        return
    base = path
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, base)
            yield full, rel.replace("\\", "/")
