"""CSV / TSV table rendering for the built-in file Viewer."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Optional

from rich import box
from rich.table import Table
from rich.text import Text

from .themes import viewer_bg_for

TABULAR_EXTS = (".csv", ".tsv", ".tab")
MAX_TABLE_ROWS = 2000
MAX_COL_WIDTH = 40
MAX_COLS = 64
_SNIFF_DELIMS = ",\t;|"


def is_tabular_name(filename: str) -> bool:
    lower = (filename or "").lower()
    return any(lower.endswith(ext) for ext in TABULAR_EXTS)


def delimiter_label(delim: str) -> str:
    return {
        ",": "csv",
        "\t": "tsv",
        ";": "scsv",
        "|": "psv",
    }.get(delim, "table")


@dataclass
class TabularData:
    headers: list[str]
    rows: list[list[str]]
    delimiter: str
    total_rows: int = 0
    total_cols: int = 0
    truncated_rows: bool = False
    truncated_cols: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def shape_label(self) -> str:
        shown_r = len(self.rows)
        shown_c = len(self.headers)
        label = f"{self.total_rows}×{self.total_cols}"
        if self.truncated_rows or self.truncated_cols:
            label += f"  show {shown_r}×{shown_c}"
        return label


def _sample(text: str, limit: int = 8192) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    nl = cut.rfind("\n")
    return cut if nl < 512 else cut[: nl + 1]


def _strip_bom(cell: str) -> str:
    return cell.lstrip("\ufeff")


def _dialect_for(text: str, filename: str) -> csv.Dialect:
    lower = (filename or "").lower()
    if lower.endswith((".tsv", ".tab")):
        return csv.excel_tab
    sample = _sample(text)
    try:
        return csv.Sniffer().sniff(sample, delimiters=_SNIFF_DELIMS)
    except csv.Error:
        return csv.excel


def parse_tabular(text: str, filename: str = "") -> Optional[TabularData]:
    """
    Parse CSV/TSV text. Returns None when the content is not tabular enough
    to be worth a table (empty, or sniff/parse failure).
    """
    if not text or not text.strip():
        return None
    try:
        dialect = _dialect_for(text, filename)
    except Exception:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    raw_rows: list[list[str]] = []
    try:
        for i, row in enumerate(reader):
            if i == 0 and row:
                row = [_strip_bom(row[0]), *row[1:]]
            raw_rows.append(["" if c is None else str(c) for c in row])
            if i >= MAX_TABLE_ROWS + 8:
                # keep reading a bit past the cap so total_rows is meaningful
                # but do not slurp a huge remainder
                break
    except csv.Error:
        if not raw_rows:
            return None

    # Drop trailing completely empty lines
    while raw_rows and all(not c.strip() for c in raw_rows[-1]):
        raw_rows.pop()
    if not raw_rows:
        return None

    # Count remaining lines cheaply if we stopped early
    total_data_lines = len(raw_rows)
    if total_data_lines > MAX_TABLE_ROWS + 1:
        # header + leftover
        extra = text.count("\n") + (0 if text.endswith("\n") else 1)
        total_data_lines = max(total_data_lines, extra)

    header = raw_rows[0]
    body = raw_rows[1:]
    width = max(len(r) for r in raw_rows)
    if width == 0:
        return None

    # A 1-column "table" is only useful when the name is tabular; otherwise
    # the sniffer probably guessed wrong.
    if width == 1 and not is_tabular_name(filename):
        return None

    truncated_cols = width > MAX_COLS
    width_shown = min(width, MAX_COLS)
    headers = _unique_headers(_pad_row(header, width_shown))
    truncated_rows = len(body) > MAX_TABLE_ROWS
    rows = [_pad_row(r, width_shown) for r in body[:MAX_TABLE_ROWS]]
    delim = getattr(dialect, "delimiter", ",") or ","
    return TabularData(
        headers=headers,
        rows=rows,
        delimiter=delim,
        total_rows=max(len(body), total_data_lines - 1 if total_data_lines else len(body)),
        total_cols=width,
        truncated_rows=truncated_rows,
        truncated_cols=truncated_cols,
    )


def _pad_row(row: list[str], width: int) -> list[str]:
    if len(row) >= width:
        return row[:width]
    return row + [""] * (width - len(row))


def _unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, raw in enumerate(headers):
        base = raw.strip() or f"col{i + 1}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(base if n == 0 else f"{base}_{n + 1}")
    return out


def _clip(cell: str) -> str:
    cell = cell.replace("\r\n", "\n").replace("\r", "\n")
    cell = " ".join(cell.splitlines())
    if len(cell) <= MAX_COL_WIDTH:
        return cell
    return cell[: MAX_COL_WIDTH - 1] + "…"


def _header_label(
    header: str,
    col: int,
    query: str,
    current,
) -> object:
    clipped = _clip(header)
    if not query:
        return clipped
    from .view_search import highlight_query_in_text

    is_current = (
        current is not None
        and getattr(current, "where", "") == "header"
        and getattr(current, "column", -1) == col
    )
    return highlight_query_in_text(clipped, query, current=is_current)


def _cell_label(
    cell: str,
    row: int,
    col: int,
    query: str,
    current,
) -> object:
    clipped = _clip(cell)
    if not query:
        return clipped
    from .view_search import highlight_query_in_text

    is_current = (
        current is not None
        and getattr(current, "where", "") == "cell"
        and getattr(current, "line", -2) == row
        and getattr(current, "column", -1) == col
    )
    return highlight_query_in_text(clipped, query, current=is_current)


def make_table_renderable(
    data: TabularData,
    *,
    app_theme: Optional[str] = None,
    query: str = "",
    current_match=None,
) -> Table:
    bg = viewer_bg_for(app_theme) or "default"
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAD,
        pad_edge=False,
        collapse_padding=True,
        expand=False,
        show_lines=False,
        padding=(0, 1),
        border_style="dim",
        title=None,
    )
    if bg and bg != "default" and not query:
        table.row_styles = ["", "dim"]

    for i, h in enumerate(data.headers):
        table.add_column(
            _header_label(h, i, query, current_match),
            overflow="ellipsis",
            max_width=MAX_COL_WIDTH,
            no_wrap=True,
        )

    for r, row in enumerate(data.rows):
        table.add_row(
            *(_cell_label(c, r, i, query, current_match) for i, c in enumerate(row))
        )

    if data.truncated_rows or data.truncated_cols:
        table.caption = Text(
            "truncated — press t for raw text",
            style="dim italic",
        )
    return table


def try_tabular_renderable(
    text: str,
    *,
    filename: str = "",
    app_theme: Optional[str] = None,
) -> Optional[tuple[Table, TabularData]]:
    if not is_tabular_name(filename):
        return None
    data = parse_tabular(text, filename)
    if data is None:
        return None
    return make_table_renderable(data, app_theme=app_theme), data
