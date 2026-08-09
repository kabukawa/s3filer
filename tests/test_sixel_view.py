"""Tests for SIXEL image helpers (encode path; no live terminal required)."""

from __future__ import annotations

import io
import os

import pytest

from s3filer.sixel_view import (
    encode_image_to_sixel,
    is_image_name,
    supports_sixel,
)


def test_is_image_name() -> None:
    assert is_image_name("photo.PNG")
    assert is_image_name("a.jpeg")
    assert is_image_name("x.webp")
    assert not is_image_name("readme.md")
    assert not is_image_name("archive.tar.gz")


def test_encode_png_to_sixel() -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    buf = io.BytesIO()
    # Small RGB image with distinct colors
    im = Image.new("RGB", (32, 24), (255, 0, 0))
    for x in range(16, 32):
        for y in range(12):
            im.putpixel((x, y), (0, 255, 0))
    im.save(buf, format="PNG")
    data = buf.getvalue()

    sixel, meta = encode_image_to_sixel(data, max_width=64, max_height=48, max_colors=16)
    assert "q" in sixel[:20]
    assert sixel.startswith("\033P") or sixel.startswith("\x1bP")
    assert sixel.endswith("\033\\") or sixel.endswith("\x1b\\")
    # 1:1 pixel aspect + geometry (fixes squashed images on WT/WezTerm)
    assert '"1;1;' in sixel or "\x1bP0;0;0q\"1;1;" in sixel or 'q"1;1;' in sixel
    assert "#" in sixel  # palette / color select
    assert meta["width"] <= 64
    assert meta["height"] <= 48
    assert meta["bytes"] == len(data)
    assert meta["colors"] >= 1


def test_encode_respects_max_size() -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 20, 30)).save(buf, format="PNG")
    sixel, meta = encode_image_to_sixel(
        buf.getvalue(), max_width=100, max_height=50, max_colors=8
    )
    assert meta["width"] <= 100
    assert meta["height"] <= 50
    assert meta["orig_width"] == 400
    assert sixel.startswith("\033P") or sixel.startswith("\x1bP")
    assert '"1;1;' in sixel


def test_supports_sixel_env_override(monkeypatch) -> None:
    monkeypatch.setenv("S3FILER_SIXEL", "1")
    assert supports_sixel() is True
    monkeypatch.setenv("S3FILER_SIXEL", "0")
    assert supports_sixel() is False


def test_supports_sixel_config_mode(tmp_path, monkeypatch) -> None:
    from s3filer.config import set_sixel_mode

    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    monkeypatch.delenv("S3FILER_SIXEL", raising=False)
    # Simulate Textual: stdout is NOT a tty, but we are under Windows Terminal
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr(
        "s3filer.sixel_view._stream_isatty", lambda stream: False
    )
    monkeypatch.setenv("WT_SESSION", "test-session")
    monkeypatch.setenv("WT_PROFILE_ID", "{guid}")

    set_sixel_mode("off")
    assert supports_sixel() is False
    set_sixel_mode("on")
    assert supports_sixel() is True  # force ON despite isatty False
    set_sixel_mode("auto")
    assert supports_sixel() is True  # WT_SESSION → auto detects


def test_supports_sixel_on_without_isatty_but_console(monkeypatch, tmp_path) -> None:
    """Force ON must work when Textual wraps stdout (isatty False)."""
    from s3filer.config import set_sixel_mode

    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    monkeypatch.delenv("S3FILER_SIXEL", raising=False)
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.delenv("WT_PROFILE_ID", raising=False)
    monkeypatch.setattr("s3filer.sixel_view._stream_isatty", lambda stream: False)
    monkeypatch.setattr("s3filer.sixel_view._has_windows_console", lambda: True)

    set_sixel_mode("on")
    assert supports_sixel() is True
