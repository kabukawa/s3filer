"""CSV / TSV table viewer."""

from __future__ import annotations

from rich.table import Table

from s3filer.view_table import (
    is_tabular_name,
    make_table_renderable,
    parse_tabular,
    try_tabular_renderable,
)
from s3filer.widgets import ViewerScreen


def test_is_tabular_name() -> None:
    assert is_tabular_name("data.csv")
    assert is_tabular_name("DATA.TSV")
    assert is_tabular_name("x.tab")
    assert not is_tabular_name("data.csv.bak")
    assert not is_tabular_name("notes.txt")
    assert not is_tabular_name("code.py")


def test_parse_csv_basic() -> None:
    text = "name,age,city\nAda,36,London\nBob,21,Paris\n"
    data = parse_tabular(text, "people.csv")
    assert data is not None
    assert data.headers == ["name", "age", "city"]
    assert data.rows == [["Ada", "36", "London"], ["Bob", "21", "Paris"]]
    assert data.delimiter == ","
    assert data.total_cols == 3
    assert data.total_rows == 2


def test_parse_tsv() -> None:
    text = "a\tb\tc\n1\t2\t3\n"
    data = parse_tabular(text, "grid.tsv")
    assert data is not None
    assert data.headers == ["a", "b", "c"]
    assert data.rows == [["1", "2", "3"]]
    assert data.delimiter == "\t"


def test_parse_quoted_comma() -> None:
    text = 'title,note\n"hello, world","x,y"\n'
    data = parse_tabular(text, "q.csv")
    assert data is not None
    assert data.rows == [["hello, world", "x,y"]]


def test_parse_semicolon() -> None:
    text = "a;b;c\n1;2;3\n"
    data = parse_tabular(text, "eu.csv")
    assert data is not None
    assert data.delimiter == ";"
    assert data.rows == [["1", "2", "3"]]


def test_parse_bom() -> None:
    text = "\ufeffname,value\nx,1\n"
    data = parse_tabular(text, "bom.csv")
    assert data is not None
    assert data.headers[0] == "name"


def test_parse_empty_none() -> None:
    assert parse_tabular("", "a.csv") is None
    assert parse_tabular("   \n\n", "a.csv") is None


def test_one_column_txt_not_table() -> None:
    assert parse_tabular("hello\nworld\n", "notes.txt") is None


def test_try_renderable() -> None:
    got = try_tabular_renderable("a,b\n1,2\n", filename="x.csv")
    assert got is not None
    table, data = got
    assert isinstance(table, Table)
    assert data.total_cols == 2
    assert try_tabular_renderable("a,b\n1,2\n", filename="x.py") is None


def test_make_table_renderable() -> None:
    data = parse_tabular("h1,h2\nv1,v2\n", "a.csv")
    assert data is not None
    table = make_table_renderable(data)
    assert isinstance(table, Table)
    assert table.row_count == 1


def test_viewer_defaults_to_table() -> None:
    sc = ViewerScreen("sales.csv", "sku,qty\nA,2\nB,3\n", "meta")
    assert sc._table_mode
    assert sc._table_data is not None
    assert sc._table_data.headers == ["sku", "qty"]
    assert isinstance(sc._make_renderable(), Table)
    sc._table_mode = False
    assert not isinstance(sc._make_renderable(), Table)
    sc._table_mode = True
    assert isinstance(sc._make_renderable(), Table)


def test_viewer_non_csv_no_table() -> None:
    sc = ViewerScreen("app.py", "print(1)\n", "meta")
    assert sc._table_data is None
    assert sc._table_mode is False
    sc.action_toggle_table()
    assert sc._table_mode is False
