"""Tests for external editor resolution and local edit fingerprinting."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from s3filer.editor import (
    _file_fingerprint,
    edit_entry,
    resolve_editor,
)
from s3filer.models import FileEntry, LocationKind, PathLocation
from s3filer.s3_client import S3Service


def test_resolve_editor_from_env(monkeypatch) -> None:
    monkeypatch.setenv("EDITOR", "vim -n")
    monkeypatch.delenv("VISUAL", raising=False)
    cmd = resolve_editor()
    assert cmd[0] == "vim"
    assert "-n" in cmd


def test_resolve_editor_visual_wins(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL", "nano")
    monkeypatch.setenv("EDITOR", "vim")
    assert resolve_editor()[0] == "nano"


def test_edit_local_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    target.write_text("hello\n", encoding="utf-8")

    def fake_run(path: str) -> None:
        # Simulate editor saving a change
        Path(path).write_text("hello world\n", encoding="utf-8")

    monkeypatch.setattr("s3filer.editor.run_editor", fake_run)
    entry = FileEntry(
        name="note.txt",
        is_dir=False,
        size=6,
        parent_path=str(tmp_path),
        location=PathLocation(LocationKind.LOCAL, str(tmp_path)),
    )
    # S3Service may still be constructed; not used for local
    result = edit_entry(entry, S3Service())
    assert result.ok
    assert result.changed
    assert target.read_text(encoding="utf-8") == "hello world\n"
    assert result.preview_text is not None
    assert "hello world" in result.preview_text


def test_fingerprint_changes(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("a", encoding="utf-8")
    a = _file_fingerprint(str(p))
    p.write_text("ab", encoding="utf-8")
    b = _file_fingerprint(str(p))
    assert a != b
