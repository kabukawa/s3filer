"""Reusable dialog screens and pane widgets."""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual import events
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


class ProgressScreen(ModalScreen[None]):
    """
    Blocking progress overlay. Updated via ``set_progress`` from the main thread
    (use ``app.call_from_thread`` from workers).
    """

    # No escape — wait for the operation to finish
    BINDINGS: list[Binding] = []

    def __init__(self, title: str, total: int = 0) -> None:
        super().__init__()
        self._title = title
        self._total = max(0, total)
        self._current = 0
        self._detail = "Starting…"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog progress-dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._count_text(), id="prog-count")
            yield Static(self._detail, id="prog-detail")
            yield Static("Please wait…", classes="dialog-hint")

    def _count_text(self) -> str:
        if self._total > 0:
            pct = int(100 * self._current / self._total) if self._total else 0
            return f"{self._current} / {self._total}  ({pct}%)"
        return f"Processed: {self._current}"

    def set_progress(
        self,
        current: int,
        total: Optional[int] = None,
        detail: str = "",
    ) -> None:
        self._current = current
        if total is not None:
            self._total = max(0, total)
        if detail:
            self._detail = detail
        try:
            self.query_one("#prog-count", Static).update(self._count_text())
            self.query_one("#prog-detail", Static).update(self._detail)
        except Exception:
            pass


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation dialog."""

    BINDINGS = [
        Binding("y", "yes", "Yes", show=False),
        Binding("n", "no", "No", show=False),
        Binding("escape", "no", "Cancel", show=False),
        Binding("enter", "yes", "Yes", show=False),
    ]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._message)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Yes [Y]", variant="primary", id="yes")
                yield Button("No [N]", id="no")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)


class InputScreen(ModalScreen[Optional[str]]):
    """Single-line input dialog."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, prompt: str, default: str = "") -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._prompt)
            yield Input(value=self._default, id="value")
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.dismiss(self.query_one("#value", Input).value)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


class ProfileScreen(ModalScreen[Optional[str]]):
    """Pick AWS profile."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "choose", "OK", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, profiles: list[str], current: Optional[str]) -> None:
        super().__init__()
        self._profiles = profiles
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("AWS Profile", classes="dialog-title")
            yield Static("Select a profile (from ~/.aws/config):")
            options = []
            for i, p in enumerate(self._profiles):
                mark = " *" if p == self._current else ""
                options.append(Option(f"{p}{mark}", id=p))
            yield OptionList(*options, id="profile-list", compact=True, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        ol = self.query_one("#profile-list", OptionList)
        ol.focus()
        if self._current and self._current in self._profiles:
            ol.highlighted = self._profiles.index(self._current)

    def action_cursor_up(self) -> None:
        ol = self.query_one("#profile-list", OptionList)
        ol.focus()
        ol.action_cursor_up()

    def action_cursor_down(self) -> None:
        ol = self.query_one("#profile-list", OptionList)
        ol.focus()
        ol.action_cursor_down()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_choose(self) -> None:
        self._accept()

    def _accept(self) -> None:
        ol = self.query_one("#profile-list", OptionList)
        if ol.highlighted is None:
            self.dismiss(None)
            return
        opt = ol.get_option_at_index(ol.highlighted)
        self.dismiss(str(opt.id) if opt.id else None)

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id) if event.option.id else None)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self._accept()

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


class ThemeScreen(ModalScreen[Optional[str]]):
    """Pick UI color theme (persisted to config file)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "choose", "OK", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(
        self,
        themes: list[tuple[str, str]],
        current: Optional[str],
    ) -> None:
        """
        themes: list of (theme_id, label)
        """
        super().__init__()
        self._themes = themes
        self._current = current
        self._ids = [t[0] for t in themes]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Color theme", classes="dialog-title")
            yield Static("j/k move · Enter select · saved for next launch")
            options = []
            for tid, label in self._themes:
                mark = " *" if tid == self._current else ""
                options.append(Option(f"{label}{mark}", id=tid))
            yield OptionList(*options, id="theme-list", compact=True, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        ol = self.query_one("#theme-list", OptionList)
        ol.focus()
        if self._current and self._current in self._ids:
            ol.highlighted = self._ids.index(self._current)

    def action_cursor_up(self) -> None:
        ol = self.query_one("#theme-list", OptionList)
        ol.focus()
        ol.action_cursor_up()

    def action_cursor_down(self) -> None:
        ol = self.query_one("#theme-list", OptionList)
        ol.focus()
        ol.action_cursor_down()

    def _restore_previous(self) -> None:
        if self._current:
            try:
                self.app.theme = self._current
            except Exception:
                pass

    def action_cancel(self) -> None:
        self._restore_previous()
        self.dismiss(None)

    def action_choose(self) -> None:
        self._accept()

    def _accept(self) -> None:
        ol = self.query_one("#theme-list", OptionList)
        if ol.highlighted is None:
            self.dismiss(None)
            return
        opt = ol.get_option_at_index(ol.highlighted)
        self.dismiss(str(opt.id) if opt.id else None)

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id) if event.option.id else None)

    @on(OptionList.OptionHighlighted)
    def on_highlight(self, event: OptionList.OptionHighlighted) -> None:
        # Live preview while moving the highlight (not saved until OK / Enter)
        if event.option and event.option.id:
            try:
                self.app.theme = str(event.option.id)
            except Exception:
                pass

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self._accept()

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self._restore_previous()
        self.dismiss(None)


class DestBrowserScreen(ModalScreen[Optional[str]]):
    """
    Browse directories to pick a destination (copy/move) or jump target.

    One level at a time (not a fully expanded tree):
      Enter / l     open highlighted directory (or ..)
      Backspace / h parent directory
      j/k ↑↓        move cursor
      /             focus filter input (incremental search)
      Esc           clear filter / blur input, or cancel
      s / g         confirm *current* directory as destination
      Tab           toggle Local <-> S3
      \\            volume root / This PC (drives, Box, WSL)
      Ctrl+L        local bookmark/root
      Ctrl+S        S3 bookmark/root
    """

    BINDINGS = [
        Binding("escape", "escape", "Esc", show=False),
        Binding("enter", "open_dir", "Open", show=False),
        # No priority: Input (filter) must receive s/g while typing
        Binding("s", "confirm", "Start", show=False),
        Binding("g", "confirm", "Go", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("backspace", "back", "Parent", show=False),
        Binding("h", "parent", "Parent", show=False),
        Binding("l", "open_dir", "Open", show=False),
        # priority: prevent Tab from cycling focus among Input/List/Buttons
        Binding("tab", "toggle_side", "Local/S3", show=False, priority=True),
        Binding("ctrl+l", "to_local", "Local", show=False, priority=True),
        Binding("ctrl+s", "to_s3", "S3", show=False, priority=True),
        Binding("slash", "start_filter", "Filter", show=False),
        # Also allow 1/2 as unambiguous side switch
        Binding("1", "to_local", "Local", show=False),
        Binding("2", "to_s3", "S3", show=False),
        Binding("backslash", "root", "Root", show=False),
        Binding("yen", "root", "Root", show=False),
    ]

    def __init__(
        self,
        title: str,
        *,
        start,
        s3,
        local_start,
        s3_start,
        confirm_label: str = "s/g: set destination here",
    ) -> None:
        super().__init__()
        self._dialog_title = title
        self._s3 = s3
        self._location = start
        self._local_bookmark = local_start
        self._s3_bookmark = s3_start
        self._confirm_label = confirm_label
        self._dir_entries: list = []
        self._filter = ""
        self._error: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dest-dialog"):
            yield Label(self._dialog_title, classes="dialog-title")
            yield Static("", id="dest-path")
            yield Input(
                placeholder="Filter ( / to focus · type to search · Esc blur )",
                id="dest-filter-input",
            )
            yield OptionList(id="dest-list", compact=True, markup=False)
            yield Static("", id="dest-hint", classes="dialog-hint")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Local [1]", id="btn-local")
                yield Button("S3 [2]", id="btn-s3")
                yield Button("Set here [s/g]", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        # Only the directory list is focusable by default so Tab is free for
        # Local↔S3 (Input steals Tab for focus cycling if can_focus=True).
        for btn in self.query(Button):
            btn.can_focus = False
        filt = self._filter_input()
        filt.can_focus = False
        self._reload()
        self.query_one("#dest-list", OptionList).focus()

    def _filter_input(self) -> Input:
        return self.query_one("#dest-filter-input", Input)

    def _filter_focused(self) -> bool:
        try:
            return self._filter_input().has_focus
        except Exception:
            return False

    # --- listing ---------------------------------------------------------

    def _reload(self) -> None:
        from .browser import refresh_pane
        from .models import PaneState

        # Keep the requested location even if listing fails (e.g. expired AWS token)
        requested = self._location
        state = PaneState(location=requested)
        try:
            refresh_pane(state, self._s3)
            self._error = state.error
            self._dir_entries = [
                e for e in state.entries if e.is_dir or e.name == ".."
            ]
            # Prefer refreshed location (normalized paths) when available
            self._location = state.location or requested
        except Exception as e:
            self._error = str(e)
            self._dir_entries = []
            self._location = requested

        self._render_list()
        self._update_chrome()

    def _filtered(self) -> list:
        q = (self._filter or "").casefold()
        if not q:
            return list(self._dir_entries)
        out = []
        for e in self._dir_entries:
            if e.name == "..":
                out.append(e)
                continue
            hay = e.name
            if getattr(e, "target_path", None):
                hay = f"{hay} {e.target_path}"
            if q in hay.casefold():
                out.append(e)
        return out

    def _render_list(self) -> None:
        ol = self.query_one("#dest-list", OptionList)
        rows = self._filtered()
        options: list[Option] = []
        for i, e in enumerate(rows):
            label = ".." if e.name == ".." else e.name + ("/" if e.is_dir else "")
            options.append(Option(label, id=f"d{i}"))
        if not options:
            options = [Option("(no directories)", id="empty")]
        ol.set_options(options)
        ol.highlighted = 0

    def _update_chrome(self) -> None:
        kind = "LOCAL" if self._location.is_local() else "S3"
        err = f"  ERR: {self._error}" if self._error else ""
        n = len(self._filtered())
        self.query_one("#dest-path", Static).update(
            f"[{kind}] {self._location.display()}  ({n} dirs){err}"
        )
        self.query_one("#dest-hint", Static).update(
            f"Enter/l: open  h/Bksp: parent  \\: drives  j/k: move  "
            f"Tab/1/2: Local↔S3  / filter  {self._confirm_label}  Esc: cancel"
        )

    def _current_entry(self):
        rows = self._filtered()
        ol = self.query_one("#dest-list", OptionList)
        if not rows or ol.highlighted is None or ol.highlighted >= len(rows):
            return None
        return rows[ol.highlighted]

    def _list(self) -> OptionList:
        return self.query_one("#dest-list", OptionList)

    # --- actions ---------------------------------------------------------

    def action_cursor_up(self) -> None:
        if self._filter_focused():
            return
        ol = self._list()
        ol.focus()
        ol.action_cursor_up()

    def action_cursor_down(self) -> None:
        if self._filter_focused():
            return
        ol = self._list()
        ol.focus()
        ol.action_cursor_down()

    def action_page_up(self) -> None:
        if self._filter_focused():
            return
        ol = self._list()
        ol.focus()
        if hasattr(ol, "action_page_up"):
            ol.action_page_up()
        else:
            for _ in range(10):
                ol.action_cursor_up()

    def action_page_down(self) -> None:
        if self._filter_focused():
            return
        ol = self._list()
        ol.focus()
        if hasattr(ol, "action_page_down"):
            ol.action_page_down()
        else:
            for _ in range(10):
                ol.action_cursor_down()

    def action_start_filter(self) -> None:
        inp = self._filter_input()
        inp.can_focus = True
        inp.focus()

    def action_escape(self) -> None:
        if self._filter_focused():
            inp = self._filter_input()
            inp.blur()
            inp.can_focus = False
            self._list().focus()
            return
        if self._filter:
            self._filter = ""
            self._filter_input().value = ""
            self._render_list()
            self._update_chrome()
            return
        self.dismiss(None)

    def action_confirm(self) -> None:
        """s / g — use the *current* directory as destination."""
        if self._filter_focused():
            # Let Input handle the character; do not confirm while typing
            return
        from .places import is_places_root

        if self._location.is_local() and is_places_root(self._location.path):
            entry = self._current_entry()
            target = getattr(entry, "target_path", None) if entry else None
            if target:
                self.dismiss(target)
                return
            self._error = "Select a drive or place first"
            self._update_chrome()
            return
        self.dismiss(self._location.path)

    def action_root(self) -> None:
        """``\\`` — volume root, then This PC (same as the main pane)."""
        if self._filter_focused():
            return
        from .models import LocationKind, PathLocation
        from .places import (
            PLACES_ROOT,
            is_places_root,
            is_volume_root,
            volume_root_of,
        )
        from . import local_fs
        import os

        loc = self._location
        if loc.is_s3() or is_places_root(loc.path):
            if os.name == "nt":
                self._location = PathLocation(LocationKind.LOCAL, PLACES_ROOT)
            else:
                self._location = PathLocation(
                    LocationKind.LOCAL, local_fs.normalize_local_path(os.sep)
                )
        elif os.name == "nt" and loc.is_local() and is_volume_root(loc.path):
            self._location = PathLocation(LocationKind.LOCAL, PLACES_ROOT)
        elif loc.is_local():
            self._location = PathLocation(
                LocationKind.LOCAL,
                local_fs.normalize_local_path(volume_root_of(loc.path)),
            )
        else:
            return
        self._filter = ""
        try:
            self._filter_input().value = ""
        except Exception:
            pass
        self._bookmark_current()
        self._reload()
        try:
            self._list().focus()
        except Exception:
            pass

    def action_open_dir(self) -> None:
        from .browser import navigate_into
        from .models import PaneState

        if self._filter_focused():
            # Enter in filter: apply and return focus to list
            self._list().focus()
            return

        entry = self._current_entry()
        if not entry or (not entry.is_dir and entry.name != ".."):
            return

        # Map filtered highlight back into full dir list for navigate_into
        state = PaneState(location=self._location, entries=list(self._dir_entries))
        state.cursor = next(
            (i for i, e in enumerate(state.entries) if e.name == entry.name), 0
        )
        navigate_into(state, self._s3)
        self._location = state.location
        self._filter = ""
        self._filter_input().value = ""
        self._bookmark_current()
        self._reload()

    def action_parent(self) -> None:
        from .browser import navigate_into
        from .models import FileEntry, PaneState

        if self._filter_focused():
            return

        state = PaneState(location=self._location)
        state.entries = [
            FileEntry(
                name="..",
                is_dir=True,
                parent_path=self._location.path,
                location=self._location,
            )
        ]
        state.cursor = 0
        navigate_into(state, self._s3)
        self._location = state.location
        self._filter = ""
        self._filter_input().value = ""
        self._bookmark_current()
        self._reload()

    def action_back(self) -> None:
        if self._filter_focused():
            return  # Input handles backspace
        self.action_parent()

    def action_to_local(self) -> None:
        self._switch_to(self._local_bookmark)

    def action_to_s3(self) -> None:
        self._switch_to(self._s3_bookmark)

    def action_toggle_side(self) -> None:
        if self._location.is_local():
            self._switch_to(self._s3_bookmark)
        else:
            self._switch_to(self._local_bookmark)

    def _switch_to(self, target) -> None:
        """Switch side without clobbering the other side's bookmark."""
        self._bookmark_current()
        self._location = target
        self._filter = ""
        try:
            self._filter_input().value = ""
        except Exception:
            pass
        self._reload()
        try:
            self._list().focus()
        except Exception:
            pass

    def _bookmark_current(self) -> None:
        if self._location.is_local():
            self._local_bookmark = self._location
        else:
            self._s3_bookmark = self._location

    async def handle_key(self, event: events.Key) -> bool:
        """
        Intercept Tab before focus-cycling. 1/2 also handled here for reliability.
        Returns True if the key was consumed.
        """
        if not self._filter_focused():
            if event.key == "tab":
                self.action_toggle_side()
                return True
            if event.key == "1":
                self.action_to_local()
                return True
            if event.key == "2":
                self.action_to_s3()
                return True
            if event.key in ("backslash", "yen"):
                self.action_root()
                return True
        return await super().handle_key(event)

    @on(Input.Changed, "#dest-filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self._filter = event.value or ""
        self._render_list()
        self._update_chrome()

    @on(Input.Submitted, "#dest-filter-input")
    def on_filter_submit(self, event: Input.Submitted) -> None:
        inp = self._filter_input()
        inp.blur()
        inp.can_focus = False
        self._list().focus()

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        # Enter on option → open directory (do not dismiss as destination)
        event.stop()
        self.action_open_dir()

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.dismiss(self._location.path)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-local")
    def on_btn_local(self) -> None:
        self.action_to_local()

    @on(Button.Pressed, "#btn-s3")
    def on_btn_s3(self) -> None:
        self.action_to_s3()


class ArchiveBrowserScreen(ModalScreen[Optional[str]]):
    """
    Browse archive contents; extract selected members.

    Dismiss result: status message (or None).
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("space", "toggle_select", "Sel", show=False),
        Binding("x", "extract", "Extract", show=False),
        Binding("e", "extract", "Extract", show=False),
        Binding("a", "extract_all", "ExtractAll", show=False),
        Binding("v", "view_member", "View", show=False),
        Binding("enter", "view_member", "View", show=False),
    ]

    def __init__(
        self,
        archive_path: str,
        *,
        title: str,
        extract_dir: str,
        temp_dir: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._title = title
        self._extract_dir = extract_dir
        self._temp_dir = temp_dir
        self._members: list = []
        self._selected: set[str] = set()
        self._status: Optional[str] = None
        self._error: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dest-dialog"):
            yield Label(f"Archive: {self._title}", classes="dialog-title")
            yield Static("", id="arc-meta")
            yield OptionList(id="arc-list", compact=True, markup=False)
            yield Static("", id="arc-status", classes="dialog-hint")
            yield Static(
                "j/k move  Spc select  v/Enter view  x/e extract  a extract-all  Esc close",
                classes="dialog-hint",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Extract [x]", variant="primary", id="extract")
                yield Button("Extract all [a]", id="extract-all")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        from .archive_ops import list_archive

        try:
            self._members = list_archive(self._archive_path)
            self._error = None
        except Exception as e:
            self._members = []
            self._error = str(e)
        # NOTE: must not name this method ``_render`` — Textual Widget uses
        # ``_render()`` internally; overriding it causes:
        # AttributeError: 'NoneType' object has no attribute 'render_strips'
        self._refresh_member_list()
        self.query_one("#arc-list", OptionList).focus()

    def _refresh_member_list(self) -> None:
        def _sz(n: int) -> str:
            if n < 1024:
                return f"{n}B"
            if n < 1024**2:
                return f"{n / 1024:.1f}K"
            if n < 1024**3:
                return f"{n / 1024**2:.1f}M"
            return f"{n / 1024**3:.1f}G"

        ol = self.query_one("#arc-list", OptionList)
        opts: list[Option] = []
        for i, m in enumerate(self._members):
            mark = "*" if m.name in self._selected else " "
            if m.is_dir:
                size_s = "<DIR>"
            else:
                size_s = _sz(int(m.size or 0))
            label = f"{mark} {m.name}  {size_s}"
            opts.append(Option(label, id=f"a{i}"))
        if not opts:
            msg = self._error or "(empty archive)"
            opts = [Option(msg, id="empty")]
        ol.set_options(opts)
        ol.highlighted = 0
        meta = f"Extract to: {self._extract_dir}  |  {len(self._members)} entries"
        if self._error:
            meta += f"  ERR: {self._error}"
        self.query_one("#arc-meta", Static).update(meta)
        try:
            st = self.query_one("#arc-status", Static)
            st.update(self._status or "(select file(s), then x/e to extract)")
        except Exception:
            pass

    def _list(self) -> OptionList:
        return self.query_one("#arc-list", OptionList)

    def _current(self):
        ol = self._list()
        if ol.highlighted is None or ol.highlighted >= len(self._members):
            return None
        return self._members[ol.highlighted]

    def action_cursor_up(self) -> None:
        self._list().focus()
        self._list().action_cursor_up()

    def action_cursor_down(self) -> None:
        self._list().focus()
        self._list().action_cursor_down()

    def action_toggle_select(self) -> None:
        m = self._current()
        if not m or m.is_dir:
            return
        if m.name in self._selected:
            self._selected.discard(m.name)
        else:
            self._selected.add(m.name)
        # move down
        ol = self._list()
        hi = ol.highlighted if ol.highlighted is not None else 0
        if hi < len(self._members) - 1:
            hi += 1
        self._refresh_member_list()
        ol = self._list()
        if self._members:
            ol.highlighted = min(hi, len(self._members) - 1)

    def _names_to_extract(self) -> list[str]:
        names = list(self._selected)
        if not names:
            m = self._current()
            if m and not m.is_dir:
                names = [m.name]
            elif m and m.is_dir:
                # extract all files under this directory prefix
                prefix = m.name.rstrip("/") + "/"
                names = [
                    x.name
                    for x in self._members
                    if (not x.is_dir) and x.name.startswith(prefix)
                ]
        return names

    def action_extract(self) -> None:
        names = self._names_to_extract()
        if not names:
            self._status = "Nothing to extract (select a file with Space, or highlight one)"
            self._refresh_member_list()
            try:
                self.app.notify(self._status, severity="warning")
            except Exception:
                pass
            return
        self._run_extract(names, title=f"Extract {len(names)} file(s)")

    def action_extract_all(self) -> None:
        names = [m.name for m in self._members if not m.is_dir]
        if not names:
            self._status = "Archive has no files to extract"
            self._refresh_member_list()
            return
        self._run_extract(names, title=f"Extract all ({len(names)} files)")

    def _run_extract(self, names: list[str], *, title: str) -> None:
        """Show progress dialog, extract in a worker, update status + notify."""
        from .archive_ops import extract_members

        total = len(names)
        prog = ProgressScreen(title, total=total)
        self.app.push_screen(prog)

        import threading

        def work() -> None:
            done = 0
            errors: list[str] = []
            for name in names:
                try:
                    self.app.call_from_thread(
                        prog.set_progress, done, total, f"Extracting: {name}"
                    )
                    from . import config as _cfg

                    n = extract_members(
                        self._archive_path,
                        [name],
                        self._extract_dir,
                        mode=_cfg.get_archive_extract_mode(),
                    )
                    if n <= 0:
                        errors.append(f"{name}: not found in archive")
                    done += 1
                    self.app.call_from_thread(
                        prog.set_progress, done, total, f"Done: {name}"
                    )
                except Exception as e:
                    errors.append(f"{name}: {e}")
                    done += 1
                    self.app.call_from_thread(
                        prog.set_progress, done, total, f"Error: {name}"
                    )

            def finish() -> None:
                try:
                    self.app.pop_screen()
                except Exception:
                    pass
                if errors and done == len(errors):
                    self._status = f"Extract FAILED ({len(errors)} error(s)) → {self._extract_dir}"
                    self._error = "; ".join(errors[:3])
                    sev = "error"
                elif errors:
                    self._status = (
                        f"Extracted {done - len(errors)}/{total} → {self._extract_dir} "
                        f"({len(errors)} error(s))"
                    )
                    sev = "warning"
                else:
                    self._status = f"Extracted {done}/{total} file(s) → {self._extract_dir}"
                    sev = "information"
                self._selected.clear()
                self._refresh_member_list()
                try:
                    self.app.notify(self._status, severity=sev, timeout=6)
                except Exception:
                    pass
                # Keep focus on list
                try:
                    self._list().focus()
                except Exception:
                    pass

            self.app.call_from_thread(finish)

        threading.Thread(target=work, daemon=True).start()

    def action_view_member(self) -> None:
        from .archive_ops import read_member_bytes
        from .encoding_util import decode_for_view

        m = self._current()
        if not m or m.is_dir:
            return
        try:
            data = read_member_bytes(self._archive_path, m.name.rstrip("/"))
            text, enc, binary = decode_for_view(data)
            meta = f"[{enc}] archive:{self._title}"
            self.app.push_screen(
                ViewerScreen(m.name, text, meta, is_binary=binary)
            )
        except Exception as e:
            self._status = f"View failed: {e}"
            self._refresh_member_list()
            try:
                self.app.notify(self._status, severity="error")
            except Exception:
                pass

    def action_close(self) -> None:
        # cleanup temp download
        if self._temp_dir:
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self.dismiss(self._status)

    @on(Button.Pressed, "#extract")
    def on_extract_btn(self) -> None:
        self.action_extract()

    @on(Button.Pressed, "#extract-all")
    def on_extract_all_btn(self) -> None:
        self.action_extract_all()

    @on(Button.Pressed, "#close")
    def on_close_btn(self) -> None:
        self.action_close()




class InfoScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._body, id="info-body")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Close", variant="primary", id="close")

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("f1", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("question_mark", "close", "Close", show=False),
        Binding("up", "scroll_up", "Up", show=False),
        Binding("down", "scroll_down", "Down", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("space", "page_down", "PgDn", show=False),
        Binding("b", "page_up", "PgUp", show=False),
    ]

    def compose(self) -> ComposeResult:
        from .help_text import get_help_text
        from .i18n import t

        with Vertical(classes="dialog help-dialog"):
            yield Label(t("help_title"), classes="dialog-title")
            with VerticalScroll(id="help-body", can_focus=True):
                yield Static(get_help_text(), id="help-text", markup=False)
            yield Static(t("help_hint"), classes="dialog-hint")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("close"), variant="primary", id="close")

    def on_mount(self) -> None:
        self.query_one("#help-body", VerticalScroll).focus()

    def _scroll(self) -> VerticalScroll:
        return self.query_one("#help-body", VerticalScroll)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_scroll_up(self) -> None:
        self._scroll().scroll_relative(y=-1, animate=False)

    def action_scroll_down(self) -> None:
        self._scroll().scroll_relative(y=1, animate=False)

    def action_page_up(self) -> None:
        sc = self._scroll()
        sc.scroll_relative(y=-(max(1, sc.size.height - 1)), animate=False)

    def action_page_down(self) -> None:
        sc = self._scroll()
        sc.scroll_relative(y=max(1, sc.size.height - 1), animate=False)

    def action_scroll_home(self) -> None:
        self._scroll().scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self._scroll().scroll_end(animate=False)

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.dismiss(None)


class ViewerScreen(ModalScreen[Optional[str]]):
    """
    Full-screen file viewer with keyboard scrolling and syntax highlight.

    Dismiss result: optional status message for the main app (e.g. after edit).
    """

    BINDINGS = [
        Binding("escape", "escape", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("f3", "close", "Close", show=False),
        Binding("e", "edit", "Edit", show=False),
        Binding("up", "scroll_up", "Up", show=False),
        Binding("down", "scroll_down", "Down", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("space", "page_down", "PgDn", show=False),
        Binding("b", "page_up", "PgUp", show=False),
        Binding("left", "scroll_left", "Left", show=False),
        Binding("right", "scroll_right", "Right", show=False),
        Binding("h", "scroll_left", "Left", show=False),
        Binding("l", "scroll_right", "Right", show=False),
        Binding("t", "toggle_table", "Table", show=False),
        Binding("slash", "start_search", "Find", show=False),
        Binding("ctrl+f", "start_search", "Find", show=False),
        Binding("n", "find_next", "Next", show=False),
        Binding("N", "find_prev", "Prev", show=False),
        Binding("shift+n", "find_prev", "Prev", show=False),
    ]

    def __init__(
        self,
        title: str,
        body: str,
        meta: str = "",
        *,
        is_binary: bool = False,
        edit_handler=None,
        app_theme: Optional[str] = None,
    ) -> None:
        """
        edit_handler: optional callable() -> EditResult-like object, invoked
        while the TUI is suspended. Must be set for 'e' (edit) to work.
        app_theme: S3 Filer UI theme name — drives syntax colors + viewer bg.
        """
        super().__init__()
        self._file_title = title
        self._body = body
        self._meta = meta
        self._is_binary = is_binary
        self._edit_handler = edit_handler
        self._app_theme = app_theme
        self._status_msg: Optional[str] = None
        self._lexer_name: Optional[str] = None
        self._syntax_theme: Optional[str] = None
        self._table_data = None
        self._table_mode = False
        self._query = ""
        self._matches: list = []
        self._match_index = 0
        self._reparse_table()

    def compose(self) -> ComposeResult:
        header = self._header_text()
        with Vertical(id="viewer"):
            yield Static(header, id="viewer-header")
            from .i18n import t

            yield Input(
                placeholder=t("viewer_find_placeholder"),
                id="viewer-search",
            )
            with ScrollableContainer(id="viewer-body", can_focus=True):
                yield Static(self._make_renderable(), id="viewer-text", expand=True)
            yield Static(self._footer_text(), id="func-bar")

    def _resolve_app_theme(self) -> Optional[str]:
        if self._app_theme:
            return self._app_theme
        try:
            return str(self.app.theme)
        except Exception:
            return None

    def _footer_text(self) -> str:
        from .i18n import t

        edit = "  |  e Edit" if self._edit_handler else ""
        table = f"  |  t {t('viewer_toggle_table')}" if self._table_data else ""
        syn = self._syntax_theme or "?"
        return (
            " [Esc/Q] Close  |  / Find  n/N  ↑↓/jk  ←→/hl  PgUp/PgDn"
            f"{table}  |  syntax:{syn}{edit}"
        )

    def _header_text(self) -> str:
        lang = f"  lang:{self._lexer_name}" if self._lexer_name else ""
        ui = self._resolve_app_theme() or ""
        ui_s = f"  theme:{ui}" if ui else ""
        table = ""
        if self._table_data is not None:
            from .view_table import delimiter_label

            kind = delimiter_label(self._table_data.delimiter)
            mode = "table" if self._table_mode else "raw"
            table = f"  {kind}:{self._table_data.shape_label}  view:{mode}"
        find = ""
        if self._query:
            if self._matches:
                find = f"  find:{self._match_index + 1}/{len(self._matches)}"
            else:
                find = "  find:0"
        return f" View: {self._file_title}  {self._meta}{lang}{table}{find}{ui_s}"

    def _reparse_table(self) -> None:
        from .view_table import parse_tabular, is_tabular_name

        self._table_data = None
        if self._is_binary or not is_tabular_name(self._file_title):
            self._table_mode = False
            return
        self._table_data = parse_tabular(self._body, self._file_title)
        if self._table_data is None:
            self._table_mode = False
        else:
            self._table_mode = True

    def _make_renderable(self):
        from .view_search import render_text_with_search
        from .view_table import make_table_renderable

        current = None
        if self._matches and 0 <= self._match_index < len(self._matches):
            current = self._matches[self._match_index]

        if self._table_mode and self._table_data is not None:
            self._lexer_name = "table"
            self._syntax_theme = "table"
            return make_table_renderable(
                self._table_data,
                app_theme=self._resolve_app_theme(),
                query=self._query,
                current_match=current,
            )

        renderable, lexer, syntax_theme = render_text_with_search(
            self._body,
            filename=self._file_title,
            is_binary=self._is_binary,
            app_theme=self._resolve_app_theme(),
            matches=self._matches or None,
            current_index=self._match_index,
        )
        self._lexer_name = lexer
        self._syntax_theme = syntax_theme
        return renderable

    def _refresh_content(self) -> None:
        self.query_one("#viewer-header", Static).update(self._header_text())
        self.query_one("#viewer-text", Static).update(self._make_renderable())
        self.query_one("#func-bar", Static).update(self._footer_text())

    def on_mount(self) -> None:
        # Ensure lexer / syntax theme labels match the active UI theme
        self._app_theme = self._resolve_app_theme()
        inp = self._search_input()
        inp.can_focus = False
        self._refresh_content()
        body = self.query_one("#viewer-body", ScrollableContainer)
        body.focus()

    def _scroll(self) -> ScrollableContainer:
        return self.query_one("#viewer-body", ScrollableContainer)

    def _search_input(self) -> Input:
        return self.query_one("#viewer-search", Input)

    def _search_focused(self) -> bool:
        try:
            return self._search_input().has_focus
        except Exception:
            return False

    def _recompute_matches(self) -> None:
        from .view_search import find_table_matches, find_text_matches

        q = self._query
        if not q:
            self._matches = []
            self._match_index = 0
            return
        if self._table_mode and self._table_data is not None:
            self._matches = find_table_matches(self._table_data, q)
        else:
            self._matches = find_text_matches(self._body, q)
        if self._matches:
            self._match_index = min(self._match_index, len(self._matches) - 1)
        else:
            self._match_index = 0

    def _apply_search(self, query: str, *, reset_index: bool = True) -> None:
        self._query = query
        if reset_index:
            self._match_index = 0
        self._recompute_matches()
        try:
            self._refresh_content()
            self._scroll_to_match()
        except Exception:
            pass

    def _scroll_to_match(self) -> None:
        if not self._matches:
            return
        m = self._matches[self._match_index]
        if m.where in ("cell", "header"):
            y = 0 if m.line < 0 else m.line + 2
        else:
            y = max(0, m.line)
        try:
            self._scroll().scroll_to(y=max(0, y - 2), animate=False)
        except Exception:
            pass

    def action_start_search(self) -> None:
        if self._search_focused():
            return
        inp = self._search_input()
        inp.can_focus = True
        inp.focus()
        if self._query:
            inp.value = self._query
            inp.cursor_position = len(self._query)

    def action_find_next(self) -> None:
        if self._search_focused() and not self._query:
            return
        if not self._query:
            self.action_start_search()
            return
        if not self._matches:
            self._recompute_matches()
            try:
                self._refresh_content()
            except Exception:
                pass
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        try:
            self._refresh_content()
            self._scroll_to_match()
        except Exception:
            pass

    def action_find_prev(self) -> None:
        if self._search_focused():
            return
        if not self._query or not self._matches:
            return
        self._match_index = (self._match_index - 1) % len(self._matches)
        try:
            self._refresh_content()
            self._scroll_to_match()
        except Exception:
            pass

    def action_escape(self) -> None:
        if self._search_focused():
            inp = self._search_input()
            inp.blur()
            inp.can_focus = False
            try:
                self._scroll().focus()
            except Exception:
                pass
            return
        if self._query:
            try:
                self._search_input().value = ""
            except Exception:
                pass
            self._apply_search("", reset_index=True)
            return
        self.dismiss(self._status_msg)

    def action_close(self) -> None:
        self.dismiss(self._status_msg)

    def action_edit(self) -> None:
        if not self._edit_handler:
            self._status_msg = "Edit not available"
            return
        try:
            # Suspend TUI so the external editor owns the terminal
            with self.app.suspend():
                result = self._edit_handler()
        except Exception as e:
            self._status_msg = f"Edit failed: {e}"
            self.query_one("#viewer-header", Static).update(
                self._header_text() + f"  [error: {e}]"
            )
            return

        if result is None:
            return
        # Duck-typed EditResult
        ok = getattr(result, "ok", False)
        msg = getattr(result, "message", "")
        self._status_msg = msg
        if ok and getattr(result, "preview_text", None) is not None:
            self._body = result.preview_text
            self._is_binary = bool(getattr(result, "preview_binary", False))
            enc = getattr(result, "preview_encoding", None) or "?"
            size = getattr(result, "preview_size", 0)
            flag = " BINARY" if self._is_binary else ""
            changed = " saved" if getattr(result, "changed", False) else " unchanged"
            self._meta = f"[{enc}] {size} bytes{flag}{changed}"
            self._reparse_table()
            self._recompute_matches()
            self._refresh_content()
            self._scroll_to_match()
        elif not ok:
            # Show error in header briefly
            self.query_one("#viewer-header", Static).update(
                self._header_text() + f"  ! {msg}"
            )

    def action_scroll_up(self) -> None:
        self._scroll().scroll_relative(y=-1, animate=False)

    def action_scroll_down(self) -> None:
        self._scroll().scroll_relative(y=1, animate=False)

    def action_page_up(self) -> None:
        sc = self._scroll()
        sc.scroll_relative(y=-(max(1, sc.size.height - 1)), animate=False)

    def action_page_down(self) -> None:
        sc = self._scroll()
        sc.scroll_relative(y=max(1, sc.size.height - 1), animate=False)

    def action_scroll_home(self) -> None:
        self._scroll().scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self._scroll().scroll_end(animate=False)

    def action_scroll_left(self) -> None:
        self._scroll().scroll_relative(x=-8, animate=False)

    def action_scroll_right(self) -> None:
        self._scroll().scroll_relative(x=8, animate=False)

    def action_toggle_table(self) -> None:
        if not self._table_data:
            return
        if self._search_focused():
            return
        self._table_mode = not self._table_mode
        self._recompute_matches()
        self._refresh_content()
        self._scroll_to_match()

    @on(Input.Changed, "#viewer-search")
    def on_viewer_search_changed(self, event: Input.Changed) -> None:
        q = event.value or ""
        if q == self._query:
            return
        self._apply_search(q, reset_index=True)

    @on(Input.Submitted, "#viewer-search")
    def on_viewer_search_submitted(self, event: Input.Submitted) -> None:
        if self._query:
            self.action_find_next()
        else:
            inp = self._search_input()
            inp.blur()
            inp.can_focus = False
            self._scroll().focus()
