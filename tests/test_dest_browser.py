"""Tests for destination browser (C/M/t)."""

from __future__ import annotations

import asyncio
import os
import tempfile

from s3filer.app import S3FilerApp
from s3filer.browser import default_local_location, default_s3_location
from s3filer.models import LocationKind, PathLocation
from s3filer.s3_client import S3Service
from s3filer.widgets import DestBrowserScreen


def test_dest_browser_local_nav_and_confirm() -> None:
    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        dest = os.path.join(right, "dest")
        os.makedirs(dest)
        open(os.path.join(left, "a.txt"), "w", encoding="utf-8").write("A")

        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.pause(0.3)
            for i, e in enumerate(app.panes[0].entries):
                if e.name == "a.txt":
                    app.panes[0].cursor = i
                    app._render_pane(0)
                    break
            await pilot.press("space")
            await pilot.pause(0.05)
            await pilot.press("C")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "DestBrowserScreen"
            sc = app.screen
            assert sc._location.is_local()

            ol = sc.query_one("#dest-list")
            for i, e in enumerate(sc._filtered()):
                if e.name == "dest":
                    ol.highlighted = i
                    break
            await pilot.press("enter")
            await pilot.pause(0.25)
            assert sc._location.path.rstrip("\\/").endswith("dest")

            # parent
            await pilot.press("h")
            await pilot.pause(0.2)
            assert not sc._location.path.rstrip("\\/").endswith("dest")

            # re-enter dest and confirm with s
            for i, e in enumerate(sc._filtered()):
                if e.name == "dest":
                    ol.highlighted = i
                    break
            await pilot.press("enter")
            await pilot.pause(0.2)
            await pilot.press("s")
            await pilot.pause(0.25)
            assert type(app.screen).__name__ == "ConfirmScreen"
            await pilot.press("y")
            for _ in range(30):
                await pilot.pause(0.1)
                if os.path.exists(os.path.join(dest, "a.txt")):
                    break
            assert os.path.exists(os.path.join(dest, "a.txt"))

    asyncio.run(main())


def test_dest_browser_toggle_local_s3() -> None:
    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        open(os.path.join(left, "a.txt"), "w", encoding="utf-8").write("x")
        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.25)
            for i, e in enumerate(app.panes[0].entries):
                if e.name == "a.txt":
                    app.panes[0].cursor = i
                    app._render_pane(0)
                    break
            await pilot.press("space")
            await pilot.press("C")
            await pilot.pause(0.3)
            sc = app.screen
            assert isinstance(sc, DestBrowserScreen)
            assert sc._location.is_local()

            # 2 = S3 (listing may fail without creds; location must still switch)
            await pilot.press("2")
            await pilot.pause(0.35)
            assert sc._location.is_s3(), sc._location
            assert sc._location.path.startswith("s3://")

            # 1 = Local
            await pilot.press("1")
            await pilot.pause(0.25)
            assert sc._location.is_local()

            # Toggle via action (Tab is intercepted by some Textual focus paths;
            # 1/2 and on-screen buttons are the reliable switches)
            sc.action_toggle_side()
            await pilot.pause(0.25)
            assert sc._location.is_s3()

            # Button: Local
            await pilot.click("#btn-local")
            await pilot.pause(0.25)
            assert sc._location.is_local()

    asyncio.run(main())


def test_dest_browser_root_to_places() -> None:
    if os.name != "nt":
        return

    from s3filer.places import is_places_root, is_volume_root

    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.25)
            await pilot.press("t")
            await pilot.pause(0.3)
            sc = app.screen
            assert isinstance(sc, DestBrowserScreen)
            sc.action_root()
            await pilot.pause(0.2)
            assert is_volume_root(sc._location.path) or is_places_root(sc._location.path)
            if is_volume_root(sc._location.path):
                sc.action_root()
                await pilot.pause(0.2)
            assert is_places_root(sc._location.path)
            assert any(getattr(e, "target_path", None) for e in sc._dir_entries)

    asyncio.run(main())


def test_dest_browser_filter() -> None:
    async def main() -> None:
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "alpha"))
        os.makedirs(os.path.join(root, "beta"))
        os.makedirs(os.path.join(root, "alphabet"))
        s3 = S3Service()
        loc = PathLocation(LocationKind.LOCAL, root)
        app = S3FilerApp(left=root, right=root)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            screen = DestBrowserScreen(
                "test",
                start=loc,
                s3=s3,
                local_start=loc,
                s3_start=default_s3_location(),
            )
            app.push_screen(screen)
            await pilot.pause(0.3)
            sc = app.screen
            assert isinstance(sc, DestBrowserScreen)
            names = {e.name for e in sc._filtered()}
            assert "alpha" in names and "beta" in names

            await pilot.press("slash")
            await pilot.pause(0.1)
            await pilot.press("a")
            await pilot.press("l")
            await pilot.pause(0.15)
            filtered = {e.name for e in sc._filtered() if e.name != ".."}
            assert "alpha" in filtered
            assert "alphabet" in filtered
            assert "beta" not in filtered

    asyncio.run(main())
