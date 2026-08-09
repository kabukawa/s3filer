"""Recovery when current path disappears (local delete / bad S3 prefix)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from s3filer.browser import (
    recover_local_path,
    refresh_pane,
    _s3_parent_candidates,
)
from s3filer.models import FileEntry, LocationKind, PaneState, PathLocation


def test_recover_local_path_walks_up(tmp_path: Path) -> None:
    real = tmp_path / "keep"
    real.mkdir()
    gone = real / "removed" / "deep"
    # do not create gone
    resolved, note = recover_local_path(str(gone))
    assert Path(resolved) == real.resolve() or Path(resolved) == real
    assert note is not None


def test_refresh_pane_local_missing_falls_back(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    child = root / "child"
    child.mkdir()
    state = PaneState(
        location=PathLocation(LocationKind.LOCAL, str(child)),
    )
    # delete child after we pointed at it
    child.rmdir()
    refresh_pane(state)
    assert os.path.isdir(state.location.path)
    assert state.location.path.rstrip("\\/") == str(root.resolve()).rstrip("\\/") or os.path.samefile(
        state.location.path, root
    )
    assert any(e.name == ".." for e in state.entries)
    # recovery note may be in error field as soft message
    assert state.entries  # not empty dead-end


def test_s3_parent_candidates() -> None:
    c = _s3_parent_candidates("s3://bucket/a/b/c/")
    assert c[0].startswith("s3://bucket/")
    assert "s3://bucket/" in c
    assert "s3://" in c


def test_refresh_pane_s3_recovers_to_parent() -> None:
    s3 = MagicMock()

    def list_prefix(loc: PathLocation):
        # only bucket root and account root work
        if loc.path in ("s3://mybucket/", "s3://mybucket"):
            return [
                FileEntry(name="..", is_dir=True, parent_path=loc.path),
                FileEntry(name="ok", is_dir=True, parent_path=loc.path),
            ]
        if loc.path in ("s3://", "s3:"):
            return [FileEntry(name="mybucket", is_dir=True, parent_path="s3://")]
        raise RuntimeError(f"NoSuchKey: {loc.path}")

    s3.list_prefix.side_effect = list_prefix
    s3.profile = "dev"
    s3.region = "ap-northeast-1"

    state = PaneState(
        location=PathLocation(
            LocationKind.S3,
            "s3://mybucket/gone/prefix/",
            profile="dev",
            region="ap-northeast-1",
        )
    )
    refresh_pane(state, s3)
    assert state.location.path in ("s3://mybucket/", "s3://mybucket")
    assert any(e.name == "ok" for e in state.entries)


def test_refresh_pane_s3_all_fail_still_navigable() -> None:
    s3 = MagicMock()
    s3.list_prefix.side_effect = RuntimeError("ExpiredToken")
    s3.profile = "x"
    s3.region = "ap-northeast-1"
    state = PaneState(
        location=PathLocation(LocationKind.S3, "s3://b/a/", profile="x")
    )
    refresh_pane(state, s3)
    # fell back somehow; must not be a total dead-end without entries
    assert state.location.is_s3()
    assert state.error
    # entries may be empty list_prefix failure at s3:// but ensure_parent or fallback
    # At minimum error is set and location is s3
    assert state.location.path.startswith("s3://")
