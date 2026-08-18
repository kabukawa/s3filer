"""Text search helpers for the built-in file Viewer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rich.syntax import Syntax
from rich.text import Text

from .view_highlight import make_view_renderable

STYLE_MATCH = "black on #d4aa00"
STYLE_CURRENT = "bold black on #ffe566"


@dataclass(frozen=True)
class SearchMatch:
    """One hit. *line* is 0-based (text line, or table row; -1 = header)."""

    line: int
    start: int
    end: int
    column: int = 0  # table column when where != "text"
    where: str = "text"  # text | header | cell


def find_text_matches(text: str, query: str, *, ignore_case: bool = True) -> list[SearchMatch]:
    if not query:
        return []
    needle = query.casefold() if ignore_case else query
    if not needle:
        return []
    out: list[SearchMatch] = []
    for i, line in enumerate(text.splitlines()):
        hay = line.casefold() if ignore_case else line
        pos = 0
        while True:
            found = hay.find(needle, pos)
            if found < 0:
                break
            end = min(found + len(needle), len(line))
            if end > found:
                out.append(SearchMatch(line=i, start=found, end=end, where="text"))
            pos = found + max(1, len(needle))
    return out


def find_table_matches(data, query: str, *, ignore_case: bool = True) -> list[SearchMatch]:
    if not query or data is None:
        return []
    needle = query.casefold() if ignore_case else query
    if not needle:
        return []
    out: list[SearchMatch] = []
    for c, header in enumerate(data.headers):
        hay = header.casefold() if ignore_case else header
        if needle in hay:
            out.append(SearchMatch(line=-1, start=0, end=1, column=c, where="header"))
    for r, row in enumerate(data.rows):
        for c, cell in enumerate(row):
            hay = (cell or "").casefold() if ignore_case else (cell or "")
            if needle in hay:
                out.append(SearchMatch(line=r, start=0, end=1, column=c, where="cell"))
    return out


def highlight_query_in_text(
    text: str,
    query: str,
    *,
    ignore_case: bool = True,
    current: bool = False,
) -> Text:
    """Return *text* with every occurrence of *query* styled."""
    if not query:
        return Text(text)
    needle = query.casefold() if ignore_case else query
    hay = text.casefold() if ignore_case else text
    out = Text()
    pos = 0
    style = STYLE_CURRENT if current else STYLE_MATCH
    while True:
        found = hay.find(needle, pos)
        if found < 0:
            out.append(text[pos:])
            break
        out.append(text[pos:found])
        out.append(text[found : found + len(query)], style=style)
        pos = found + max(1, len(query))
    return out


def apply_text_match_styles(
    styled: Text,
    matches: list[SearchMatch],
    current_index: int,
) -> Text:
    """Stylize *styled* (one Text of the whole file) at match spans, per line."""
    if not matches:
        return styled
    lines = styled.split("\n")
    by_line: dict[int, list[tuple[int, SearchMatch]]] = {}
    for i, m in enumerate(matches):
        if m.where != "text":
            continue
        by_line.setdefault(m.line, []).append((i, m))
    out = Text()
    for li, line in enumerate(lines):
        if li:
            out.append("\n")
        hits = by_line.get(li)
        if hits:
            for i, m in hits:
                start = max(0, min(m.start, len(line.plain)))
                end = max(start, min(m.end, len(line.plain)))
                if end > start:
                    style = STYLE_CURRENT if i == current_index else STYLE_MATCH
                    line.stylize(style, start, end)
        out.append_text(line)
    return out


def add_line_numbers(styled: Text, *, current_line: Optional[int] = None) -> Text:
    lines = styled.split("\n")
    width = max(3, len(str(max(1, len(lines)))))
    out = Text()
    for i, line in enumerate(lines):
        if i:
            out.append("\n")
        num_style = "bold yellow" if current_line is not None and i == current_line else "dim"
        out.append(f"{i + 1:>{width}} │ ", style=num_style)
        out.append_text(line)
    return out


def render_text_with_search(
    text: str,
    *,
    filename: str = "",
    is_binary: bool = False,
    app_theme: Optional[str] = None,
    matches: Optional[list[SearchMatch]] = None,
    current_index: int = 0,
):
    """Renderable for the viewer, with optional search marks."""
    renderable, lexer, syntax_theme = make_view_renderable(
        text,
        filename=filename,
        is_binary=is_binary,
        app_theme=app_theme,
        line_numbers=not bool(matches),
    )
    if not matches:
        return renderable, lexer, syntax_theme

    if isinstance(renderable, Syntax):
        try:
            styled = renderable.highlight(text)
        except Exception:
            styled = Text(text)
    elif isinstance(renderable, Text):
        styled = renderable
    else:
        styled = Text(text)

    current = matches[current_index] if 0 <= current_index < len(matches) else None
    styled = apply_text_match_styles(styled, matches, current_index)
    numbered = add_line_numbers(styled, current_line=current.line if current else None)
    return numbered, lexer, syntax_theme
