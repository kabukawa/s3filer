"""Shared data models for local and S3 entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class LocationKind(Enum):
    LOCAL = auto()
    S3 = auto()


@dataclass(frozen=True)
class PathLocation:
    """A browsable location: local path or s3://bucket/prefix."""

    kind: LocationKind
    path: str  # absolute local path, or s3://bucket/key/
    profile: Optional[str] = None  # AWS profile (S3 only)
    region: Optional[str] = None

    def display(self) -> str:
        if self.kind == LocationKind.LOCAL:
            return self.path
        prof = f" [{self.profile}]" if self.profile else ""
        return f"{self.path}{prof}"

    def is_s3(self) -> bool:
        return self.kind == LocationKind.S3

    def is_local(self) -> bool:
        return self.kind == LocationKind.LOCAL

    def bucket_and_prefix(self) -> tuple[str, str]:
        """Parse s3://bucket/prefix into (bucket, prefix)."""
        if not self.is_s3():
            raise ValueError("Not an S3 location")
        raw = self.path
        if raw.startswith("s3://"):
            raw = raw[5:]
        parts = raw.split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        if prefix and not prefix.endswith("/"):
            # directory-style prefix
            if not prefix:
                pass
            elif not any(c == "/" for c in prefix.split("/")[-1] if False):
                # keep as-is; caller decides
                pass
        return bucket, prefix


@dataclass
class FileEntry:
    """One row in a pane listing."""

    name: str
    is_dir: bool
    size: int = 0
    mtime: Optional[datetime] = None
    # Full location of this entry (parent dir + name encoded)
    location: Optional[PathLocation] = None
    # For S3: full key (without bucket)
    key: Optional[str] = None
    # Parent path for navigation
    parent_path: str = ""
    # Storage class / extra
    storage_class: Optional[str] = None
    etag: Optional[str] = None

    @property
    def display_name(self) -> str:
        return f"{self.name}/" if self.is_dir and not self.name.endswith("/") else self.name

    def full_path(self) -> str:
        """Resolve absolute path or s3 URI for this entry."""
        if self.location and self.location.is_s3():
            bucket, prefix = self.location.bucket_and_prefix()
            if self.name == "..":
                return self.parent_path
            base = self.location.path.rstrip("/")
            if self.is_dir:
                return f"{base}/{self.name}/" if not base.endswith(self.name) else f"{base}/"
            return f"{base}/{self.name}"
        # local
        import os

        if self.name == "..":
            return os.path.dirname(self.parent_path.rstrip(os.sep)) or self.parent_path
        return os.path.join(self.parent_path, self.name)


@dataclass
class FileInfo:
    """Detailed metadata for the info panel."""

    name: str
    path: str
    is_dir: bool
    size: int
    mtime: Optional[datetime] = None
    kind: LocationKind = LocationKind.LOCAL
    encoding: Optional[str] = None
    encoding_confidence: Optional[float] = None
    mime_hint: Optional[str] = None
    line_count: Optional[int] = None
    is_binary: Optional[bool] = None
    storage_class: Optional[str] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None
    permissions: Optional[str] = None
    owner: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class PaneState:
    """Runtime state of one pane."""

    location: PathLocation
    entries: list[FileEntry] = field(default_factory=list)
    cursor: int = 0
    selected: set[str] = field(default_factory=set)  # entry names
    filter_text: str = ""
    error: Optional[str] = None
    loading: bool = False

    def current_entry(self) -> Optional[FileEntry]:
        if not self.entries:
            return None
        idx = max(0, min(self.cursor, len(self.entries) - 1))
        return self.entries[idx]

    def selected_entries(self) -> list[FileEntry]:
        if not self.selected:
            cur = self.current_entry()
            if cur and cur.name != "..":
                return [cur]
            return []
        return [e for e in self.entries if e.name in self.selected and e.name != ".."]
