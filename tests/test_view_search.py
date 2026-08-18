"""Viewer text search."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from s3filer.view_search import (
    find_table_matches,
    find_text_matches,
    highlight_query_in_text,
    render_text_with_search,
)
from s3filer.view_table import parse_tabular
from s3filer.widgets import ViewerScreen


def test_find_text_basic() -> None:
    text = "alpha\nBeta\nalpha beta\n"
    hits = find_text_matches(text, "alpha")
    assert len(hits) == 2
    assert hits[0].line == 0
    assert hits[0].start == 0
    assert hits[1].line == 2


def test_find_text_case_insensitive() -> None:
    hits = find_text_matches("Foo foo FOO", "foo")
    assert len(hits) == 3


def test_find_text_empty() -> None:
    assert find_text_matches("abc", "") == []
    assert find_text_matches("", "x") == []


def test_find_text_overlapping_not_required() -> None:
    hits = find_text_matches("aaaa", "aa")
    assert len(hits) == 2
    assert hits[0].start == 0
    assert hits[1].start == 2


def test_find_table_matches() -> None:
    data = parse_tabular("name,city\nAda,London\nBob,Paris\n", "x.csv")
    assert data is not None
    hits = find_table_matches(data, "ada")
    assert len(hits) == 1
    assert hits[0].where == "cell"
    assert hits[0].line == 0
    city = find_table_matches(data, "city")
    assert any(h.where == "header" for h in city)


def test_highlight_query() -> None:
    t = highlight_query_in_text("one two one", "one")
    assert isinstance(t, Text)
    assert t.plain == "one two one"


def test_render_with_search_marks() -> None:
    text = "def hello():\n    return 1\n"
    hits = find_text_matches(text, "hello")
    renderable, lexer, _syn = render_text_with_search(
        text, filename="a.py", matches=hits, current_index=0
    )
    assert isinstance(renderable, Text)
    assert "hello" in renderable.plain


def test_viewer_search_state() -> None:
    body = "red\nblue\nred fox\n"
    sc = ViewerScreen("notes.txt", body, "meta")
    sc._apply_search("red")
    assert sc._query == "red"
    assert len(sc._matches) == 2
    assert sc._match_index == 0
    sc.action_find_next()
    assert sc._match_index == 1
    sc.action_find_next()
    assert sc._match_index == 0
    sc.action_find_prev()
    assert sc._match_index == 1
    sc._apply_search("")
    assert sc._matches == []


def test_viewer_search_in_table() -> None:
    sc = ViewerScreen("t.csv", "sku,qty\nA100,2\nB200,3\n", "meta")
    assert sc._table_mode
    sc._apply_search("b200")
    assert len(sc._matches) == 1
    assert sc._matches[0].where == "cell"
    assert isinstance(sc._make_renderable(), Table)


def test_viewer_search_ui() -> None:
    import asyncio
    import os
    import tempfile

    from s3filer.app import S3FilerApp
    from s3filer.widgets import ViewerScreen

    async def main() -> None:
        left = tempfile.mkdtemp()
        right = tempfile.mkdtemp()
        path = os.path.join(left, "notes.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("alpha\nbeta\nalpha fox\n")
        app = S3FilerApp(left=left, right=right)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.25)
            for i, e in enumerate(app.panes[0].entries):
                if e.name == "notes.txt":
                    app.panes[0].cursor = i
                    app._render_pane(0)
                    break
            await pilot.press("v")
            await pilot.pause(0.3)
            sc = app.screen
            assert isinstance(sc, ViewerScreen)
            sc._apply_search("alpha")
            await pilot.pause(0.1)
            assert len(sc._matches) == 2
            assert "find:1/2" in sc._header_text()
            sc.action_find_next()
            assert sc._match_index == 1
            assert "find:2/2" in sc._header_text()

    asyncio.run(main())


def test_viewer_no_match() -> None:
    sc = ViewerScreen("a.txt", "hello\n", "meta")
    sc._apply_search("zzz")
    assert sc._matches == []
    sc.action_find_next()
    assert sc._match_index == 0
