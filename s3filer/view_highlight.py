"""Syntax highlighting helpers for the file Viewer (Rich + Pygments)."""

from __future__ import annotations

from typing import Optional

from rich.console import RenderableType
from rich.syntax import Syntax
from rich.text import Text

from .themes import syntax_theme_for, viewer_bg_for

_DEFAULT_SYNTAX = "monokai"


def guess_lexer(filename: str, code: str) -> str:
    """Return a Pygments lexer name for the given file name / content."""
    try:
        name = Syntax.guess_lexer(filename, code)
        if name:
            return str(name)
    except Exception:
        pass

    # Extension fallbacks (when content is empty or guess fails)
    lower = filename.lower()
    ext_map = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".json": "json",
        ".md": "markdown",
        ".markdown": "markdown",
        ".html": "html",
        ".htm": "html",
        ".xml": "xml",
        ".css": "css",
        ".scss": "scss",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "nginx",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".ps1": "powershell",
        ".bat": "batch",
        ".cmd": "batch",
        ".sql": "sql",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".r": "r",
        ".lua": "lua",
        ".swift": "swift",
        ".dockerfile": "docker",
        ".tf": "terraform",
        ".hcl": "terraform",
        ".graphql": "graphql",
        ".vue": "vue",
        ".svelte": "svelte",
        ".diff": "diff",
        ".patch": "diff",
        ".log": "text",
        ".csv": "text",
        ".txt": "text",
    }
    for ext, lexer in ext_map.items():
        if lower.endswith(ext):
            return lexer
    if lower == "dockerfile" or lower.endswith("/dockerfile"):
        return "docker"
    if lower in ("makefile", "gnumakefile") or lower.endswith("makefile"):
        return "make"
    return "text"


def make_view_renderable(
    text: str,
    *,
    filename: str = "",
    is_binary: bool = False,
    theme: Optional[str] = None,
    app_theme: Optional[str] = None,
    background_color: Optional[str] = None,
    line_numbers: bool = True,
) -> tuple[RenderableType, Optional[str], str]:
    """
    Build a Rich renderable for the viewer.

    Returns (renderable, lexer_name_or_None, syntax_theme_used).

    ``app_theme`` is the S3 Filer UI theme name (classic-blue, …) and selects
    a matching Pygments style. ``theme`` overrides the syntax style directly.
    """
    syntax_theme = theme or syntax_theme_for(app_theme) or _DEFAULT_SYNTAX
    bg = background_color or viewer_bg_for(app_theme) or "default"

    if is_binary or not text:
        return Text(text or ""), None, syntax_theme

    # Heuristic: hex dump preview from encoding_util
    first = text.lstrip()[:20]
    if first.startswith("00000000") and "  " in text[:80]:
        return Text(text), None, syntax_theme

    lexer = guess_lexer(filename, text)

    def _build(lex: str) -> Syntax:
        return Syntax(
            text,
            lex,
            theme=syntax_theme,
            line_numbers=line_numbers,
            word_wrap=False,
            indent_guides=(lex not in ("text", "Text only")),
            background_color=bg if bg != "default" else "default",
        )

    if lexer in ("text", "Text only"):
        try:
            return _build("text"), "text", syntax_theme
        except Exception:
            return Text(text), None, syntax_theme

    try:
        return _build(lexer), lexer, syntax_theme
    except Exception:
        try:
            return _build("text"), "text", syntax_theme
        except Exception:
            return Text(text), None, syntax_theme
