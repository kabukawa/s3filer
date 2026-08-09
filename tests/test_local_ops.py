"""Basic unit tests for local filesystem and encoding helpers."""

from __future__ import annotations

import os
from pathlib import Path

from s3filer.browser import default_local_location, refresh_pane
from s3filer.encoding_util import decode_for_view, detect_encoding
from s3filer.local_fs import copy_path, list_dir, mkdir, rename
from s3filer.models import PaneState, PathLocation, LocationKind
from s3filer.operations import Operations, entry_source_path
from s3filer.s3_client import S3Service, parse_s3_uri


def test_list_and_mkdir(tmp_path: Path) -> None:
    loc = PathLocation(LocationKind.LOCAL, str(tmp_path))
    entries = list_dir(loc)
    assert any(e.name == ".." for e in entries)
    mkdir(str(tmp_path), "folder")
    entries = list_dir(loc)
    assert any(e.name == "folder" and e.is_dir for e in entries)


def test_copy_rename(tmp_path: Path) -> None:
    src = tmp_path / "x.txt"
    src.write_text("hello", encoding="utf-8")
    dest = tmp_path / "out"
    dest.mkdir()
    copy_path(str(src), str(dest))
    assert (dest / "x.txt").read_text(encoding="utf-8") == "hello"
    rename(str(dest / "x.txt"), "y.txt")
    assert (dest / "y.txt").exists()


def test_encoding_utf8() -> None:
    data = "日本語テスト".encode("utf-8")
    enc, conf, binary = detect_encoding(data)
    assert not binary
    assert enc is not None
    text, used, is_bin = decode_for_view(data)
    assert "日本語" in text
    assert not is_bin


def test_encoding_binary() -> None:
    data = bytes(range(256))
    _enc, _conf, binary = detect_encoding(data)
    assert binary
    text, used, is_bin = decode_for_view(data)
    assert is_bin
    assert used == "binary"


def test_parse_s3_uri() -> None:
    assert parse_s3_uri("s3://bucket/a/b/") == ("bucket", "a/b/")
    assert parse_s3_uri("s3://bucket") == ("bucket", "")


def test_refresh_pane(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    state = PaneState(location=PathLocation(LocationKind.LOCAL, str(tmp_path)))
    refresh_pane(state)
    assert state.error is None
    names = [e.name for e in state.entries]
    assert "f.txt" in names


def test_ops_copy_local(tmp_path: Path) -> None:
    left = tmp_path / "L"
    right = tmp_path / "R"
    left.mkdir()
    right.mkdir()
    (left / "a.txt").write_text("A", encoding="utf-8")
    state = PaneState(location=PathLocation(LocationKind.LOCAL, str(left)))
    refresh_pane(state)
    entry = next(e for e in state.entries if e.name == "a.txt")
    ops = Operations(S3Service())
    result = ops.copy_entries([entry], PathLocation(LocationKind.LOCAL, str(right)))
    assert result.ok
    assert (right / "a.txt").read_text(encoding="utf-8") == "A"
