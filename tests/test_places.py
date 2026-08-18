"""Drive / This PC / WSL place listing and navigation."""

from __future__ import annotations

import os
from pathlib import Path
from s3filer.browser import go_to, navigate_into, recover_local_path, refresh_pane
from s3filer.local_fs import normalize_local_path
from s3filer.models import FileEntry, LocationKind, PaneState, PathLocation
from s3filer.operations import Operations, entry_source_path
from s3filer.places import (
    PLACES_ROOT,
    is_places_root,
    is_unc_path,
    is_volume_root,
    iter_places,
    local_parent_path,
    volume_root_of,
)
from s3filer.s3_client import S3Service


def test_is_places_root() -> None:
    assert is_places_root("thispc:")
    assert is_places_root("thispc://")
    assert is_places_root("PC:")
    assert is_places_root(" ThisPC: ")
    assert not is_places_root("C:\\")
    assert not is_places_root("")
    assert not is_places_root("s3://")


def test_is_volume_root_and_parent() -> None:
    if os.name == "nt":
        assert is_volume_root("C:\\")
        assert is_volume_root("C:")
        assert is_volume_root(r"\\wsl.localhost\Ubuntu-22.04")
        assert is_volume_root(r"\\server\share")
        assert not is_volume_root(r"C:\Users")
        assert not is_volume_root(r"\\wsl.localhost\Ubuntu-22.04\home")
        assert local_parent_path("C:\\") == PLACES_ROOT
        assert local_parent_path(r"\\wsl.localhost\Ubuntu-22.04") == PLACES_ROOT
        assert volume_root_of(r"C:\Users\foo") == "C:\\"
        assert volume_root_of(r"\\wsl.localhost\Ubuntu-22.04\home\u") == (
            r"\\wsl.localhost\Ubuntu-22.04"
        )
    else:
        assert is_volume_root("/")
        assert local_parent_path("/") == "/"
        assert volume_root_of("/usr/bin") == "/"


def test_normalize_special_paths() -> None:
    if os.name != "nt":
        return
    assert normalize_local_path("thispc:") == PLACES_ROOT
    assert normalize_local_path("\\") == PLACES_ROOT
    assert normalize_local_path("D:").rstrip("\\").upper() == "D:"
    unc = normalize_local_path(r"\\wsl.localhost\Ubuntu-22.04\home")
    assert unc.startswith("\\\\")
    assert "Ubuntu-22.04" in unc
    assert is_unc_path(unc)


def test_recover_places_root() -> None:
    if os.name != "nt":
        return
    path, note = recover_local_path("thispc:")
    assert path == PLACES_ROOT
    assert note is None


def test_refresh_places_root() -> None:
    if os.name != "nt":
        return
    state = PaneState(location=PathLocation(LocationKind.LOCAL, PLACES_ROOT))
    refresh_pane(state)
    assert is_places_root(state.location.path)
    assert not any(e.name == ".." for e in state.entries)
    drives = [e for e in state.entries if e.storage_class == "DRIVE"]
    assert drives
    assert any(
        (e.target_path or "").upper().startswith("C:") for e in drives
    )


def test_navigate_into_place_and_back(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    state = PaneState(location=PathLocation(LocationKind.LOCAL, PLACES_ROOT))
    refresh_pane(state)
    c = next(e for e in state.entries if (e.target_path or "").upper().startswith("C:"))
    state.cursor = state.entries.index(c)
    navigate_into(state)
    assert os.path.isdir(state.location.path)
    assert not is_places_root(state.location.path)
    # parent of drive root is This PC
    if is_volume_root(state.location.path):
        state.cursor = 0
        assert state.entries[0].name == ".."
        navigate_into(state)
        assert is_places_root(state.location.path)


def test_go_to_thispc() -> None:
    if os.name != "nt":
        return
    state = PaneState(
        location=PathLocation(LocationKind.LOCAL, normalize_local_path("."))
    )
    go_to(state, "thispc:")
    assert is_places_root(state.location.path)
    assert state.entries


def test_entry_source_path_target() -> None:
    entry = FileEntry(
        name="Box",
        is_dir=True,
        parent_path=PLACES_ROOT,
        target_path=r"C:\Users\someone\Box",
    )
    assert entry_source_path(entry) == r"C:\Users\someone\Box"
    assert entry.full_path() == r"C:\Users\someone\Box"


def test_mkdir_rejected_on_places() -> None:
    ops = Operations(S3Service())
    result = ops.mkdir(PathLocation(LocationKind.LOCAL, PLACES_ROOT), "folder")
    assert not result.ok


def test_iter_places_windows_has_drive() -> None:
    if os.name != "nt":
        assert iter_places() == []
        return
    places = iter_places()
    assert any(p.kind == "DRIVE" and p.path.upper().startswith("C:") for p in places)


def test_navigate_uses_target_path(tmp_path: Path) -> None:
    dest = tmp_path / "place"
    dest.mkdir()
    state = PaneState(location=PathLocation(LocationKind.LOCAL, PLACES_ROOT))
    state.entries = [
        FileEntry(
            name="FakePlace",
            is_dir=True,
            parent_path=PLACES_ROOT,
            target_path=str(dest),
            storage_class="CLOUD",
        )
    ]
    state.cursor = 0
    navigate_into(state)
    assert Path(state.location.path).resolve() == dest.resolve()


def test_app_root_action_reaches_places() -> None:
    if os.name != "nt":
        return
    import asyncio
    import tempfile

    from s3filer.app import S3FilerApp

    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            app.action_root()
            await pilot.pause(0.15)
            loc = app.panes[app.active].location
            if is_volume_root(loc.path):
                app.action_root()
                await pilot.pause(0.15)
                loc = app.panes[app.active].location
            assert is_places_root(loc.path)
            assert any(e.storage_class == "DRIVE" for e in app.panes[app.active].entries)

    asyncio.run(main())


def test_local_parent_from_tmp(tmp_path: Path) -> None:
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)
    parent = local_parent_path(str(child))
    assert Path(parent).resolve() == (tmp_path / "a").resolve()
