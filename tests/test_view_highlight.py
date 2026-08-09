"""Tests for View syntax highlighting."""

from __future__ import annotations

from rich.syntax import Syntax
from rich.text import Text

from s3filer.view_highlight import guess_lexer, make_view_renderable


def test_guess_python() -> None:
    code = "def hello(name: str) -> str:\n    return name\n"
    assert guess_lexer("app.py", code) == "python"


def test_guess_by_extension() -> None:
    assert guess_lexer("data.json", "{}") in ("json", "JSON")
    assert guess_lexer("script.sh", "echo hi") in ("bash", "sh", "shell")


def test_highlight_python() -> None:
    code = "def hello(name: str) -> str:\n    return name\n"
    renderable, lang, syn = make_view_renderable(code, filename="app.py")
    assert lang == "python"
    assert isinstance(renderable, Syntax)
    assert syn  # syntax theme name


def test_binary_no_highlight() -> None:
    renderable, lang, syn = make_view_renderable(
        "00000000  61 62",
        filename="x.bin",
        is_binary=True,
    )
    assert lang is None
    assert isinstance(renderable, Text)


def test_syntax_theme_follows_app_theme() -> None:
    code = "x = 1\n"
    _, _, syn_light = make_view_renderable(
        code, filename="a.py", app_theme="light"
    )
    _, _, syn_mid = make_view_renderable(
        code, filename="a.py", app_theme="midnight"
    )
    assert syn_light == "friendly"
    assert syn_mid == "dracula"
    assert syn_light != syn_mid
