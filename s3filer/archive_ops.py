"""List and extract compressed archives (zip / tar family)."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Optional

from .models import FileEntry
from .operations import entry_source_path
from .s3_client import S3Service, parse_s3_uri

MAX_ARCHIVE_BYTES = 200 * 1024 * 1024

_ARCHIVE_SUFFIXES = (
    ".zip",
    ".jar",
    ".war",
    ".ear",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".gz",
    ".bz2",
    ".xz",
)


@dataclass
class ArchiveMember:
    name: str
    size: int
    is_dir: bool
    compressed_size: int = 0


def is_archive_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(sfx) for sfx in _ARCHIVE_SUFFIXES)


def _safe_join(base: str, member: str) -> str:
    """Prevent zip-slip path traversal."""
    # normalize member
    member = member.replace("\\", "/").lstrip("/")
    target = os.path.normpath(os.path.join(base, member))
    base_abs = os.path.abspath(base)
    if not os.path.abspath(target).startswith(base_abs + os.sep) and os.path.abspath(
        target
    ) != base_abs:
        raise RuntimeError(f"Unsafe archive path: {member}")
    return target


def open_archive_path(path: str):
    """Return (kind, handle) kind in zip|tar."""
    lower = path.lower()
    if lower.endswith(".zip") or lower.endswith((".jar", ".war", ".ear")):
        return "zip", zipfile.ZipFile(path, "r")
    if lower.endswith(
        (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
    ):
        return "tar", tarfile.open(path, "r:*")
    # single-file compressions — treat as tar-like one member of stem
    if lower.endswith((".gz", ".bz2", ".xz")) and not any(
        lower.endswith(s) for s in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz")
    ):
        return "single", path
    # try zip then tar by sniffing
    if zipfile.is_zipfile(path):
        return "zip", zipfile.ZipFile(path, "r")
    try:
        return "tar", tarfile.open(path, "r:*")
    except tarfile.TarError as e:
        raise RuntimeError(f"Unsupported or corrupt archive: {e}") from e


def list_archive(path: str) -> list[ArchiveMember]:
    kind, handle = open_archive_path(path)
    try:
        if kind == "zip":
            zf: zipfile.ZipFile = handle  # type: ignore
            out: list[ArchiveMember] = []
            for info in zf.infolist():
                name = info.filename
                is_dir = name.endswith("/")
                out.append(
                    ArchiveMember(
                        name=name.rstrip("/") + ("/" if is_dir else ""),
                        size=0 if is_dir else int(info.file_size),
                        is_dir=is_dir,
                        compressed_size=int(info.compress_size),
                    )
                )
            out.sort(key=lambda m: (not m.is_dir, m.name.lower()))
            return out
        if kind == "tar":
            tf: tarfile.TarFile = handle  # type: ignore
            out = []
            for info in tf.getmembers():
                is_dir = info.isdir()
                name = info.name.rstrip("/") + ("/" if is_dir else "")
                out.append(
                    ArchiveMember(
                        name=name,
                        size=0 if is_dir else int(info.size or 0),
                        is_dir=is_dir,
                    )
                )
            out.sort(key=lambda m: (not m.is_dir, m.name.lower()))
            return out
        # single compressed file
        stem = Path(path).name
        for sfx in (".gz", ".bz2", ".xz"):
            if stem.lower().endswith(sfx):
                stem = stem[: -len(sfx)]
                break
        size = os.path.getsize(path)
        return [ArchiveMember(name=stem, size=size, is_dir=False, compressed_size=size)]
    finally:
        if kind in ("zip", "tar") and handle is not None:
            handle.close()


def _norm_member(name: str) -> str:
    return name.replace("\\", "/").rstrip("/")


def _find_zip_info(zf: zipfile.ZipFile, name: str):
    """Resolve a ZipInfo by flexible name matching."""
    want = _norm_member(name)
    candidates = [name, name.replace("\\", "/"), want, want + "/"]
    for c in candidates:
        try:
            return zf.getinfo(c)
        except KeyError:
            continue
    for info in zf.infolist():
        if _norm_member(info.filename) == want:
            return info
    return None


def _find_tar_member(tf: tarfile.TarFile, name: str):
    want = _norm_member(name)
    try:
        return tf.getmember(want)
    except KeyError:
        pass
    for info in tf.getmembers():
        if _norm_member(info.name) == want:
            return info
    return None


def _target_path(dest_dir: str, member_name: str, *, mode: str) -> str:
    """
    mode:
      preserve — keep archive internal directories under dest_dir
      flat     — put only basename into dest_dir (no subfolders)
    """
    member_name = member_name.replace("\\", "/")
    if mode == "flat":
        base = os.path.basename(member_name.rstrip("/")) or "file"
        return _safe_join(dest_dir, base)
    return _safe_join(dest_dir, member_name)


def extract_members(
    path: str,
    members: list[str],
    dest_dir: str,
    progress=None,
    *,
    mode: str = "preserve",
) -> int:
    """Extract named members into dest_dir. Returns count of files written."""
    os.makedirs(dest_dir, exist_ok=True)
    mode = "flat" if mode == "flat" else "preserve"
    kind, handle = open_archive_path(path)
    count = 0
    try:
        if kind == "zip":
            zf: zipfile.ZipFile = handle  # type: ignore
            for name in members:
                if progress:
                    progress(name)
                info = _find_zip_info(zf, name)
                if info is None:
                    continue
                internal = info.filename.replace("\\", "/")
                if info.is_dir() or internal.endswith("/"):
                    if mode == "preserve":
                        os.makedirs(_target_path(dest_dir, internal, mode=mode), exist_ok=True)
                    continue
                target = _target_path(dest_dir, internal, mode=mode)
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                # flat mode: avoid overwrite silent loss — suffix if exists
                if mode == "flat" and os.path.exists(target):
                    stem, ext = os.path.splitext(target)
                    n = 1
                    while os.path.exists(f"{stem}_{n}{ext}"):
                        n += 1
                    target = f"{stem}_{n}{ext}"
                with zf.open(info, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
            return count
        if kind == "tar":
            tf: tarfile.TarFile = handle  # type: ignore
            for name in members:
                if progress:
                    progress(name)
                info = _find_tar_member(tf, name)
                if info is None:
                    continue
                internal = info.name.replace("\\", "/")
                if info.isdir():
                    if mode == "preserve":
                        os.makedirs(_target_path(dest_dir, internal, mode=mode), exist_ok=True)
                    continue
                target = _target_path(dest_dir, internal, mode=mode)
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                if mode == "flat" and os.path.exists(target):
                    stem, ext = os.path.splitext(target)
                    n = 1
                    while os.path.exists(f"{stem}_{n}{ext}"):
                        n += 1
                    target = f"{stem}_{n}{ext}"
                src = tf.extractfile(info)
                if src is None:
                    continue
                with src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
            return count
        # single compressed file
        if members:
            import gzip
            import bz2
            import lzma

            if progress:
                progress(members[0])
            lower = path.lower()
            out_name = os.path.basename(members[0])
            target = _target_path(dest_dir, out_name, mode="flat")
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if lower.endswith(".gz"):
                opener = gzip.open
            elif lower.endswith(".bz2"):
                opener = bz2.open
            elif lower.endswith(".xz"):
                opener = lzma.open
            else:
                opener = open  # type: ignore
            with opener(path, "rb") as src, open(target, "wb") as dst:  # type: ignore
                shutil.copyfileobj(src, dst)
            return 1
        return 0
    finally:
        if kind in ("zip", "tar") and handle is not None:
            handle.close()


def extract_all(path: str, dest_dir: str, progress=None, *, mode: str = "preserve") -> int:
    members = [m.name for m in list_archive(path) if not m.is_dir]
    return extract_members(path, members, dest_dir, progress=progress, mode=mode)


def read_member_bytes(path: str, member: str, max_bytes: int = 512 * 1024) -> bytes:
    kind, handle = open_archive_path(path)
    try:
        if kind == "zip":
            zf: zipfile.ZipFile = handle  # type: ignore
            with zf.open(member.rstrip("/") if not member.endswith("/") else member) as f:
                return f.read(max_bytes)
        if kind == "tar":
            tf: tarfile.TarFile = handle  # type: ignore
            info = tf.getmember(member.rstrip("/"))
            src = tf.extractfile(info)
            if src is None:
                return b""
            with src:
                return src.read(max_bytes)
        # single
        import gzip
        import bz2
        import lzma

        lower = path.lower()
        if lower.endswith(".gz"):
            with gzip.open(path, "rb") as f:
                return f.read(max_bytes)
        if lower.endswith(".bz2"):
            with bz2.open(path, "rb") as f:
                return f.read(max_bytes)
        if lower.endswith(".xz"):
            with lzma.open(path, "rb") as f:
                return f.read(max_bytes)
        with open(path, "rb") as f:
            return f.read(max_bytes)
    finally:
        if kind in ("zip", "tar") and handle is not None:
            handle.close()


def materialize_archive(
    entry: FileEntry,
    s3: S3Service,
    *,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> tuple[str, Optional[str]]:
    """Local path to archive file; temp dir if downloaded from S3."""
    if entry.is_dir:
        raise IsADirectoryError(entry.name)
    if entry.location and entry.location.is_s3():
        uri = entry_source_path(entry)
        bucket, key = parse_s3_uri(uri)
        try:
            meta = s3.head(bucket, key)
            size = int(meta.get("ContentLength") or 0)
            if size > max_bytes:
                raise RuntimeError(
                    f"Archive too large ({size} bytes; max {max_bytes})"
                )
        except RuntimeError:
            raise
        except Exception:
            pass
        tmp_dir = tempfile.mkdtemp(prefix="s3filer-arc-")
        local = os.path.join(tmp_dir, os.path.basename(entry.name) or "archive")
        s3.download_file(bucket, key, local)
        return local, tmp_dir
    path = entry_source_path(entry)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path, None
