"""External editor launch (EDITOR / VISUAL) with local + S3 support."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import FileEntry
from .operations import entry_source_path
from .s3_client import S3Service, parse_s3_uri

# Safety limit for downloading S3 objects into a temp file for editing
MAX_EDIT_BYTES = 50 * 1024 * 1024


@dataclass
class EditResult:
    ok: bool
    message: str
    changed: bool = False
    # Optional reloaded preview (truncated for View)
    preview_text: Optional[str] = None
    preview_encoding: Optional[str] = None
    preview_binary: bool = False
    preview_size: int = 0


def resolve_editor() -> list[str]:
    """
    Resolve editor command as argv list.

    Order: $VISUAL → $EDITOR → platform default.
    Values may include arguments, e.g. ``code -w`` or ``vim -n``.
    """
    for env_name in ("VISUAL", "EDITOR"):
        raw = (os.environ.get(env_name) or "").strip()
        if not raw:
            continue
        try:
            parts = shlex.split(raw, posix=(os.name != "nt"))
        except ValueError:
            parts = raw.split()
        if parts:
            return parts

    if os.name == "nt":
        # Prefer GUI editors that wait for close when available
        for candidate in (
            ["code", "-w", "-n"],
            ["notepad++"],
            ["notepad.exe"],
        ):
            if shutil.which(candidate[0]):
                return candidate
        return ["notepad.exe"]

    for name in ("nano", "nvim", "vim", "vi", "emacs"):
        if shutil.which(name):
            return [name]
    return ["vi"]


def run_editor(path: str) -> None:
    """Block until the external editor exits."""
    cmd = resolve_editor() + [path]
    # On Windows, notepad may need shell=False with list form
    env = os.environ.copy()
    try:
        proc = subprocess.run(cmd, check=False, env=env)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Editor not found: {cmd[0]!r}. Set EDITOR or VISUAL."
        ) from e
    if proc.returncode not in (0, None):
        # Many editors return non-zero on some platforms; don't fail hard
        # unless the binary was missing (handled above).
        pass


def _file_fingerprint(path: str) -> tuple[int, int]:
    st = os.stat(path)
    return int(st.st_mtime_ns), int(st.st_size)


def _load_preview(path: str, max_bytes: int = 512 * 1024) -> tuple[str, str, bool, int]:
    from .encoding_util import decode_for_view

    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read(max_bytes)
    text, enc, binary = decode_for_view(data)
    lines = text.splitlines()
    if len(lines) > 5000:
        text = "\n".join(lines[:5000]) + f"\n\n... truncated ({len(lines)} lines)"
    return text, enc or "binary", binary, size


def edit_entry(entry: FileEntry, s3: S3Service) -> EditResult:
    """
    Open entry in external editor. For S3, download → edit → upload if changed.
    """
    if entry.is_dir or entry.name == "..":
        return EditResult(False, "Cannot edit a directory")

    is_s3 = bool(entry.location and entry.location.is_s3())
    editor = " ".join(resolve_editor())

    if not is_s3:
        path = entry_source_path(entry)
        if not os.path.isfile(path):
            return EditResult(False, f"Not a file: {path}")
        try:
            before = _file_fingerprint(path)
            run_editor(path)
            after = _file_fingerprint(path)
        except Exception as e:
            return EditResult(False, str(e))
        changed = before != after
        text, enc, binary, size = _load_preview(path)
        msg = f"Edited (local) with {editor}" + (" — saved" if changed else " — no change")
        return EditResult(
            True,
            msg,
            changed=changed,
            preview_text=text,
            preview_encoding=enc,
            preview_binary=binary,
            preview_size=size,
        )

    # --- S3 ---
    uri = entry_source_path(entry)
    bucket, key = parse_s3_uri(uri)
    if not bucket or not key or key.endswith("/"):
        return EditResult(False, f"Cannot edit S3 path: {uri}")

    # Size check via HEAD when possible
    try:
        meta = s3.head(bucket, key)
        content_len = int(meta.get("ContentLength") or 0)
        if content_len > MAX_EDIT_BYTES:
            return EditResult(
                False,
                f"Object too large to edit ({content_len} bytes; max {MAX_EDIT_BYTES})",
            )
    except Exception:
        content_len = 0

    suffix = Path(entry.name).suffix or ".txt"
    tmp_dir = tempfile.mkdtemp(prefix="s3filer-edit-")
    tmp_path = os.path.join(tmp_dir, entry.name)
    # Keep safe name only
    safe_name = os.path.basename(entry.name) or "object"
    tmp_path = os.path.join(tmp_dir, safe_name)

    try:
        s3.download_file(bucket, key, tmp_path)
        before = _file_fingerprint(tmp_path)
        run_editor(tmp_path)
        after = _file_fingerprint(tmp_path)
        changed = before != after

        if changed:
            # Refuse absurd growth
            new_size = os.path.getsize(tmp_path)
            if new_size > MAX_EDIT_BYTES:
                return EditResult(
                    False,
                    f"Edited file too large to upload ({new_size} bytes)",
                )
            s3.upload_file(tmp_path, bucket, key)
            msg = f"Edited (S3) with {editor} — uploaded s3://{bucket}/{key}"
        else:
            msg = f"Edited (S3) with {editor} — no change (not uploaded)"

        text, enc, binary, size = _load_preview(tmp_path)
        return EditResult(
            True,
            msg,
            changed=changed,
            preview_text=text,
            preview_encoding=enc,
            preview_binary=binary,
            preview_size=size,
        )
    except Exception as e:
        return EditResult(False, f"S3 edit failed: {e}")
    finally:
        try:
            if os.path.isfile(tmp_path):
                os.chmod(tmp_path, stat.S_IWRITE | stat.S_IREAD)
                os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass
