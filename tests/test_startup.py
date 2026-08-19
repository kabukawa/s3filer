"""Startup must not wait on boto3 / list_buckets / extra launcher probes."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time

from s3filer.models import LocationKind, PaneState, PathLocation
from s3filer.s3_client import S3Service


def test_import_app_does_not_import_boto3() -> None:
    script = (
        "import s3filer.app, sys; "
        "assert 'boto3' not in sys.modules, sorted(sys.modules)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_s3service_defers_client() -> None:
    s = S3Service()
    assert s._client is None
    assert s._session is None


def test_first_paint_does_not_wait_for_s3(monkeypatch) -> None:
    import s3filer.s3_client as s3_mod
    from s3filer.app import S3FilerApp

    def _slow_list_prefix(self, location):
        time.sleep(1.4)
        return []

    monkeypatch.setattr(s3_mod.S3Service, "list_prefix", _slow_list_prefix)

    async def main() -> None:
        left = tempfile.mkdtemp()
        t0 = time.perf_counter()
        app = S3FilerApp(left=left, right="s3://")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.25)
            elapsed = time.perf_counter() - t0
            assert elapsed < 1.1, f"first paint waited on S3 ({elapsed:.2f}s)"
            assert app.panes[0].location.is_local()
            assert app.panes[0].entries
            assert app.panes[1].location.is_s3()
            assert app.panes[1].loading

    asyncio.run(main())


def test_iter_wsl_places_does_not_stat_unc(monkeypatch) -> None:
    if os.name != "nt":
        return
    from s3filer import places

    def _boom(path: str) -> bool:
        raise AssertionError(f"isdir must not touch WSL UNC: {path}")

    monkeypatch.setattr(places, "list_wsl_distros", lambda: ["Ubuntu-22.04"])
    monkeypatch.setattr(places, "_isdir", _boom)
    found = places.iter_wsl_places()
    assert len(found) == 1
    assert found[0].kind == "WSL"
    assert found[0].path == r"\\wsl.localhost\Ubuntu-22.04"


def test_apply_s3_prefetch_skips_navigated_pane() -> None:
    from s3filer.app import S3FilerApp

    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(80, 24)):
            started = "s3://"
            tmp = PaneState(location=PathLocation(LocationKind.S3, started))
            tmp.error = "should-not-apply"
            # Pane 1 is local (right=temp) — apply must not overwrite it.
            app._apply_s3_prefetch([(1, started, tmp)])
            assert app.panes[1].location.is_local()
            assert app.panes[1].error != "should-not-apply"

    asyncio.run(main())
