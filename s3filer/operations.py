"""High-level copy / move / delete / rename across local and S3."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from . import local_fs
from .models import FileEntry, PathLocation
from .s3_client import S3Service, make_s3_uri, parse_s3_uri

ProgressCb = Callable[[str], None]


@dataclass
class OpResult:
    ok: bool
    message: str
    count: int = 0


def _noop(_: str) -> None:
    pass


def entry_source_path(entry: FileEntry) -> str:
    """Full local path or s3 URI for an entry."""
    if entry.name == "..":
        raise ValueError("Cannot operate on ..")
    if entry.target_path:
        return entry.target_path
    if entry.location and entry.location.is_s3():
        if entry.parent_path in ("s3://", "s3:"):
            return f"s3://{entry.name}/"
        bucket, prefix = parse_s3_uri(entry.parent_path)
        if entry.key:
            return make_s3_uri(bucket, entry.key)
        if entry.is_dir:
            pfx = prefix if prefix.endswith("/") or not prefix else prefix + "/"
            return make_s3_uri(bucket, f"{pfx}{entry.name}/")
        pfx = prefix if prefix.endswith("/") or not prefix else prefix + "/"
        return make_s3_uri(bucket, f"{pfx}{entry.name}")
    return os.path.join(entry.parent_path, entry.name)


class Operations:
    def __init__(self, s3: S3Service):
        self.s3 = s3

    def copy_entries(
        self,
        entries: list[FileEntry],
        dest: PathLocation,
        progress: ProgressCb = _noop,
    ) -> OpResult:
        if not entries:
            return OpResult(False, "No files selected")
        total = len(entries)
        count = 0
        errors: list[str] = []
        for i, entry in enumerate(entries, start=1):
            try:
                progress(f"Copy {i}/{total}: {entry.name}")
                n = self._copy_one(entry, dest, progress)
                count += n
                progress(f"Copy {i}/{total}: {entry.name} — done")
            except Exception as e:
                errors.append(f"{entry.name}: {e}")
                progress(f"Copy {i}/{total}: {entry.name} — ERROR")
        if errors:
            return OpResult(
                False,
                f"Copied {count}/{total} item(s); errors: {'; '.join(errors[:5])}",
                count,
            )
        return OpResult(True, f"Copied {count}/{total} item(s) → {dest.display()}", count)

    def move_entries(
        self,
        entries: list[FileEntry],
        dest: PathLocation,
        progress: ProgressCb = _noop,
    ) -> OpResult:
        if not entries:
            return OpResult(False, "No files selected")
        total = len(entries)
        count = 0
        errors: list[str] = []
        for i, entry in enumerate(entries, start=1):
            try:
                progress(f"Move {i}/{total}: {entry.name}")
                n = self._move_one(entry, dest, progress)
                count += n
                progress(f"Move {i}/{total}: {entry.name} — done")
            except Exception as e:
                errors.append(f"{entry.name}: {e}")
                progress(f"Move {i}/{total}: {entry.name} — ERROR")
        if errors:
            return OpResult(
                False,
                f"Moved {count}/{total} item(s); errors: {'; '.join(errors[:5])}",
                count,
            )
        return OpResult(True, f"Moved {count}/{total} item(s) → {dest.display()}", count)

    def delete_entries(
        self,
        entries: list[FileEntry],
        progress: ProgressCb = _noop,
    ) -> OpResult:
        if not entries:
            return OpResult(False, "No files selected")
        total = len(entries)
        count = 0
        errors: list[str] = []
        for i, entry in enumerate(entries, start=1):
            try:
                progress(f"Delete {i}/{total}: {entry.name}")
                n = self._delete_one(entry)
                count += n
            except Exception as e:
                errors.append(f"{entry.name}: {e}")
        if errors:
            return OpResult(
                False,
                f"Deleted {count}/{total}; errors: {'; '.join(errors[:5])}",
                count,
            )
        return OpResult(True, f"Deleted {count}/{total} item(s)", count)

    def rename_entry(self, entry: FileEntry, new_name: str) -> OpResult:
        if not new_name or new_name in (".", "..") or "/" in new_name or "\\" in new_name:
            return OpResult(False, "Invalid name")
        try:
            if entry.location and entry.location.is_s3():
                src = entry_source_path(entry)
                bucket, key = parse_s3_uri(src)
                if entry.is_dir:
                    key = key if key.endswith("/") else key + "/"
                    parent = key.rsplit("/", 2)[0] + "/" if key.count("/") >= 2 else ""
                    # key like a/b/c/ -> parent a/b/, new a/b/new/
                    parts = key.rstrip("/").rsplit("/", 1)
                    parent = (parts[0] + "/") if len(parts) == 2 else ""
                    dest_key = f"{parent}{new_name}/"
                    self.s3.rename_prefix(bucket, key, dest_key)
                else:
                    parent = key.rsplit("/", 1)[0]
                    dest_key = f"{parent}/{new_name}" if "/" in key else new_name
                    self.s3.rename_object(bucket, key, dest_key)
            else:
                src = entry_source_path(entry)
                local_fs.rename(src, new_name)
            return OpResult(True, f"Renamed to {new_name}")
        except Exception as e:
            return OpResult(False, str(e))

    def mkdir(self, location: PathLocation, name: str) -> OpResult:
        """
        Create a directory (local) or prefix (S3).
        Nested names with ``/`` are allowed (e.g. ``a/b/c``).
        """
        name = name.strip().strip("/\\")
        if not name:
            return OpResult(False, "Invalid folder name")
        # Disallow absolute / drive paths
        if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
            return OpResult(False, "Invalid folder name")
        try:
            from .places import is_places_root

            if location.is_local() and is_places_root(location.path):
                return OpResult(False, "Cannot create a folder on This PC")
            if location.is_s3():
                # S3: allow nested prefixes a/b/c
                if "\\" in name:
                    return OpResult(False, "Use / for nested S3 prefixes")
                path = self.s3.mkdir(location, name)
                return OpResult(True, f"Created S3 prefix {path}")
            # Local: nested dirs via makedirs
            import os

            target = os.path.join(local_fs.normalize_local_path(location.path), name)
            if os.path.exists(target):
                return OpResult(False, f"Already exists: {target}")
            os.makedirs(target, exist_ok=False)
            return OpResult(True, f"Created directory {target}")
        except Exception as e:
            return OpResult(False, str(e))

    # --- internals ---

    def _copy_one(self, entry: FileEntry, dest: PathLocation, progress: ProgressCb) -> int:
        src_is_s3 = bool(entry.location and entry.location.is_s3())
        dest_is_s3 = dest.is_s3()
        name = entry.name

        if not src_is_s3 and not dest_is_s3:
            src = entry_source_path(entry)
            progress(f"Copy {name} -> local")
            local_fs.copy_path(src, dest.path)
            return 1

        if src_is_s3 and dest_is_s3:
            return self._copy_s3_to_s3(entry, dest, progress)

        if not src_is_s3 and dest_is_s3:
            return self._copy_local_to_s3(entry, dest, progress)

        # s3 -> local
        return self._copy_s3_to_local(entry, dest, progress)

    def _move_one(self, entry: FileEntry, dest: PathLocation, progress: ProgressCb) -> int:
        src_is_s3 = bool(entry.location and entry.location.is_s3())
        dest_is_s3 = dest.is_s3()

        if not src_is_s3 and not dest_is_s3:
            src = entry_source_path(entry)
            progress(f"Move {entry.name}")
            local_fs.move_path(src, dest.path)
            return 1

        # Cross-storage move = copy + delete
        n = self._copy_one(entry, dest, progress)
        self._delete_one(entry)
        return n

    def _delete_one(self, entry: FileEntry) -> int:
        if entry.location and entry.location.is_s3():
            if entry.parent_path in ("s3://", "s3:"):
                raise RuntimeError("Cannot delete a bucket from the filer")
            uri = entry_source_path(entry)
            bucket, key = parse_s3_uri(uri)
            if entry.is_dir:
                return self.s3.delete_prefix(bucket, key if key.endswith("/") else key + "/")
            self.s3.delete_object(bucket, key)
            return 1
        local_fs.delete(entry_source_path(entry))
        return 1

    def _copy_local_to_s3(self, entry: FileEntry, dest: PathLocation, progress: ProgressCb) -> int:
        src = entry_source_path(entry)
        bucket, prefix = parse_s3_uri(dest.path)
        if not bucket:
            raise RuntimeError("Select an S3 bucket/prefix as destination")
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        count = 0
        if os.path.isdir(src) and not os.path.islink(src):
            for full, rel in local_fs.iter_files_recursive(src):
                key = f"{prefix}{entry.name}/{rel}"
                progress(f"Upload {rel}")
                self.s3.upload_file(full, bucket, key)
                count += 1
            if count == 0:
                # empty dir marker
                self.s3.client.put_object(Bucket=bucket, Key=f"{prefix}{entry.name}/", Body=b"")
                count = 1
        else:
            key = f"{prefix}{entry.name}"
            progress(f"Upload {entry.name}")
            self.s3.upload_file(src, bucket, key)
            count = 1
        return count

    def _copy_s3_to_local(self, entry: FileEntry, dest: PathLocation, progress: ProgressCb) -> int:
        dest_dir = local_fs.normalize_local_path(dest.path)
        os.makedirs(dest_dir, exist_ok=True)
        uri = entry_source_path(entry)
        bucket, key = parse_s3_uri(uri)
        count = 0

        if entry.is_dir or key.endswith("/"):
            pfx = key if key.endswith("/") else key + "/"
            keys = self.s3.list_all_keys(bucket, pfx)
            base_name = entry.name
            for k in keys:
                rel = k[len(pfx) :]
                local_path = os.path.join(dest_dir, base_name, rel.replace("/", os.sep))
                progress(f"Download {rel}")
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.s3.download_file(bucket, k, local_path)
                count += 1
            if count == 0:
                os.makedirs(os.path.join(dest_dir, base_name), exist_ok=True)
                count = 1
        else:
            local_path = os.path.join(dest_dir, entry.name)
            progress(f"Download {entry.name}")
            self.s3.download_file(bucket, key, local_path)
            count = 1
        return count

    def _copy_s3_to_s3(self, entry: FileEntry, dest: PathLocation, progress: ProgressCb) -> int:
        src_uri = entry_source_path(entry)
        src_bucket, src_key = parse_s3_uri(src_uri)
        dest_bucket, dest_prefix = parse_s3_uri(dest.path)
        if not dest_bucket:
            raise RuntimeError("Select an S3 bucket/prefix as destination")
        if dest_prefix and not dest_prefix.endswith("/"):
            dest_prefix += "/"

        count = 0
        if entry.is_dir or src_key.endswith("/"):
            pfx = src_key if src_key.endswith("/") else src_key + "/"
            keys = self.s3.list_all_keys(src_bucket, pfx)
            for k in keys:
                rel = k[len(pfx) :]
                dest_key = f"{dest_prefix}{entry.name}/{rel}"
                progress(f"Copy s3://{src_bucket}/{k}")
                self.s3.copy_object(src_bucket, k, dest_bucket, dest_key)
                count += 1
            if count == 0:
                self.s3.client.put_object(
                    Bucket=dest_bucket, Key=f"{dest_prefix}{entry.name}/", Body=b""
                )
                count = 1
        else:
            dest_key = f"{dest_prefix}{entry.name}"
            progress(f"Copy {entry.name}")
            self.s3.copy_object(src_bucket, src_key, dest_bucket, dest_key)
            count = 1
        return count


def read_entry_bytes(
    entry: FileEntry,
    s3: S3Service,
    max_bytes: int = 2 * 1024 * 1024,
) -> bytes:
    if entry.is_dir:
        raise IsADirectoryError(entry.name)
    if entry.location and entry.location.is_s3():
        uri = entry_source_path(entry)
        bucket, key = parse_s3_uri(uri)
        return s3.get_bytes(bucket, key, max_bytes=max_bytes)
    return local_fs.read_bytes(entry_source_path(entry), max_bytes=max_bytes)


def get_file_info(entry: FileEntry, s3: S3Service):
    from .encoding_util import count_lines, decode_for_view, detect_encoding, mime_hint
    from .models import FileInfo  # noqa: F811 — re-export style local import

    if entry.location and entry.location.is_s3():
        uri = entry_source_path(entry)
        info = s3.file_info(uri)
    else:
        info = local_fs.file_info(entry_source_path(entry))

    if not info.is_dir and info.size is not None and info.size <= 2 * 1024 * 1024:
        try:
            data = read_entry_bytes(entry, s3, max_bytes=min(info.size or 0, 64 * 1024) or 64 * 1024)
            enc, conf, binary = detect_encoding(data)
            info.encoding = enc
            info.encoding_confidence = conf
            info.is_binary = binary
            info.mime_hint = mime_hint(entry.name, binary)
            if not binary and enc:
                text, _, _ = decode_for_view(data, enc)
                info.line_count = count_lines(text)
        except Exception:
            pass
    elif not info.is_dir:
        info.mime_hint = mime_hint(entry.name, True)
    return info
