"""Main dual-pane S3 Filer application (Textual)."""

from __future__ import annotations

import os
import sys
import unicodedata
from datetime import datetime
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from . import __version__, local_fs
from .browser import (
    default_local_location,
    default_s3_location,
    go_to,
    navigate_into,
    refresh_pane,
)
from .config import DEFAULT_THEME, get_theme_name, set_theme_name, viewer_command_for
from .i18n import set_runtime_language, t
from .models import LocationKind, PaneState, PathLocation
from .operations import Operations
from .s3_client import S3Service
from .themes import (
    THEME_LABELS,
    get_theme,
    register_all_themes,
    resolve_theme_name,
    theme_names,
)
from .widgets import (
    ArchiveBrowserScreen,
    ConfirmScreen,
    DestBrowserScreen,
    HelpScreen,
    InfoScreen,
    InputScreen,
    ProfileScreen,
    ProgressScreen,
    ThemeScreen,
    ViewerScreen,
)

# Fixed trailing columns (display columns, not Python len)
_SIZE_COL = 8
_DATE_COL = 16
# mark(1) + sp + name + sp + size + sp + date
_ROW_FIXED = 1 + 1 + 1 + _SIZE_COL + 1 + _DATE_COL


def _char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1


def _disp_width(s: str) -> int:
    # Fast path: pure ASCII is common for English names / sizes / dates
    if not s:
        return 0
    if s.isascii():
        return len(s)
    return sum(_char_width(ch) for ch in s)


def _truncate_disp(s: str, max_w: int) -> str:
    """Truncate string to at most max_w terminal columns."""
    if max_w <= 0:
        return ""
    w0 = _disp_width(s)
    if w0 <= max_w:
        return s
    if s.isascii():
        if max_w <= 1:
            return "…"[:max_w]
        return s[: max_w - 1] + "…"
    ell = "…"
    budget = max(0, max_w - 1)  # ellipsis is 1 col
    out: list[str] = []
    w = 0
    for ch in s:
        cw = _char_width(ch)
        if w + cw > budget:
            break
        out.append(ch)
        w += cw
    return "".join(out) + ell


def _pad_disp(s: str, width: int, align: str = "left") -> str:
    """Pad/truncate to exactly `width` terminal columns."""
    s = _truncate_disp(s, width)
    pad = width - _disp_width(s)
    if pad <= 0:
        return s
    if align == "right":
        return (" " * pad) + s
    return s + (" " * pad)


def _fmt_size(n: int) -> str:
    if n < 0:
        return ""
    if n < 1024:
        return f"{n}B"
    if n < 1024**2:
        return f"{n / 1024:.1f}K"
    if n < 1024**3:
        return f"{n / 1024**2:.1f}M"
    return f"{n / 1024**3:.1f}G"


def _fmt_mtime(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_row(entry, selected: bool, width: int = 60) -> str:
    """
    Build one list row that never exceeds `width` terminal columns.
    Uses East-Asian display width so full-width (日本語) names do not wrap.
    """
    mark = "*" if selected else " "
    if entry.name == "..":
        name = ".."
        size_s = "<UP>"
        mt = ""
    elif entry.is_dir:
        name = entry.name + "/"
        size_s = "<DIR>"
        mt = _fmt_mtime(entry.mtime)
    else:
        name = entry.name
        size_s = _fmt_size(entry.size)
        mt = _fmt_mtime(entry.mtime)

    # Keep size/date only when there is enough room; name gets the rest.
    width = max(12, width)
    if width < _ROW_FIXED + 4:
        # Very narrow: name only
        return _pad_disp(f"{mark} {name}", width)

    name_w = width - _ROW_FIXED
    name_part = _pad_disp(name, name_w, "left")
    # size/date are ASCII-only → cheap pad (avoid East-Asian width scans)
    size_part = (size_s if len(size_s) <= _SIZE_COL else size_s[:_SIZE_COL]).rjust(
        _SIZE_COL
    )
    date_part = (mt + " " * _DATE_COL)[:_DATE_COL]
    return f"{mark} {name_part} {size_part} {date_part}"


def _format_path(path: str, width: int) -> str:
    return _pad_disp(path, max(8, width), "left")


class S3FilerApp(App[None]):
    """FD/FILMTN-style dual-pane file manager for Local + S3."""

    CSS_PATH = "app.css"
    TITLE = f"S3 Filer v{__version__}"
    BINDINGS = [
        # --- Function keys (classic) ---
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "rename", "Rename", priority=True),
        Binding("f3", "view", "View", priority=True),
        Binding("f4", "info", "Info", priority=True),
        Binding("f5", "copy", "Copy", priority=True),
        Binding("f6", "move", "Move", priority=True),
        Binding("f7", "mkdir", "MkDir", priority=True),
        Binding("f8", "delete", "Delete", priority=True),
        Binding("f9", "profile", "Profile", priority=True),
        Binding("f10", "tree", "Tree", priority=True),
        # --- Letter keys (FD / FILMTN style) ---
        Binding("question_mark", "help", "Help", show=False),
        Binding("r", "rename", "Rename", show=False),
        Binding("v", "view", "View", show=False),
        Binding("i", "info", "Info", show=False),
        Binding("c", "copy", "Copy", show=False),
        Binding("m", "move", "Move", show=False),
        # Uppercase C/M: pick destination from directory tree.
        # Real terminals send "C"/"M"; pilot/some envs also send "shift+c".
        Binding("C", "copy_tree", "CopyTree", show=False, priority=True),
        Binding("M", "move_tree", "MoveTree", show=False, priority=True),
        Binding("shift+c", "copy_tree", "CopyTree", show=False, priority=True),
        Binding("shift+m", "move_tree", "MoveTree", show=False, priority=True),
        Binding("n", "mkdir", "MkDir", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("p", "profile", "Profile", show=False),
        Binding("t", "tree", "Tree", show=False),
        # Theme is under Settings (u); keep y as hidden shortcut only
        Binding("y", "theme", "Theme", show=False),
        Binding("u", "settings", "Settings", show=False),
        Binding("g", "goto", "GoTo", show=False),
        Binding("f", "refresh", "Refresh", show=False),
        Binding("s", "to_s3", "S3", show=False),
        # Run / archive / shell
        Binding("exclamation_mark", "run_command", "Cmd", show=False),
        Binding("x", "execute_file", "Exec", show=False),
        Binding("a", "open_archive", "Archive", show=False),
        Binding("o", "shell", "Shell", show=False),
        Binding("ctrl+o", "shell", "Shell", show=False, priority=True),
        # --- Vim-style navigation ---
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "focus_left", "LeftPane", show=False),
        Binding("l", "focus_right", "RightPane", show=False),
        # --- Navigation / selection ---
        Binding("tab", "switch_pane", "Pane", priority=True),
        Binding("left", "focus_left", "Left", show=False),
        Binding("right", "focus_right", "Right", show=False),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("insert", "toggle_select", "Select", show=False),
        Binding("asterisk", "select_all_files", "SelAll", show=False),
        Binding("ctrl+a", "select_toggle_all", "SelAll", show=False),
        Binding("backspace", "parent", "Up", show=False),
        Binding("ctrl+g", "goto", "GoTo", show=False),
        Binding("ctrl+l", "to_local", "Local", show=False),
        Binding("ctrl+s", "to_s3", "S3", show=False),
        Binding("ctrl+r", "refresh", "Refresh", show=False),
        Binding("q", "quit_app", "Quit", show=False),
        Binding("escape", "quit_app", "Quit", show=False),
    ]

    def __init__(
        self,
        profile: Optional[str] = None,
        left: Optional[str] = None,
        right: Optional[str] = None,
    ) -> None:
        super().__init__()
        # Apply language from config before compose/render uses t()
        set_runtime_language(None)
        self.profile = profile
        self.s3 = S3Service(profile=profile)
        self.ops = Operations(self.s3)
        self.active = 0  # 0=left, 1=right
        # Last measured list content widths (display columns)
        self._list_widths: list[int] = [0, 0]
        self._ui_ready = False
        self._current_theme = resolve_theme_name(get_theme_name())

        left_loc = self._parse_start(left) if left else default_local_location()
        right_loc = self._parse_start(right) if right else default_s3_location(profile)

        self.panes: list[PaneState] = [
            PaneState(location=left_loc),
            PaneState(location=right_loc),
        ]

    def _parse_start(self, path: str) -> PathLocation:
        path = path.strip()
        if path.lower().startswith("s3://"):
            return PathLocation(LocationKind.S3, path, profile=self.profile)
        return PathLocation(LocationKind.LOCAL, local_fs.normalize_local_path(path))

    def compose(self) -> ComposeResult:
        yield Static(self._title_text(), id="title-bar")
        with Horizontal(id="panes"):
            with Vertical(id="pane-0", classes="pane active-pane"):
                yield Static(t("pane_left"), classes="pane-header", id="hdr-0")
                yield Static("", classes="pane-path", id="path-0")
                # compact: no default tall border/padding (pane already has border).
                # markup=False: filenames with [] etc. must not be parsed as Rich markup.
                yield OptionList(id="list-0", classes="file-list", compact=True, markup=False)
                yield Static("", classes="pane-status", id="stat-0")
            with Vertical(id="pane-1", classes="pane"):
                yield Static(t("pane_right"), classes="pane-header", id="hdr-1")
                yield Static("", classes="pane-path", id="path-1")
                yield OptionList(id="list-1", classes="file-list", compact=True, markup=False)
                yield Static("", classes="pane-status", id="stat-1")
        yield Static("", id="message")
        yield Static(self._func_bar_text(), id="func-bar")

    def _title_text(self) -> str:
        prof = self.profile or "default"
        region = self.s3.region or "?"
        return t(
            "title_bar",
            version=__version__,
            profile=prof,
            region=region,
        )

    def _func_bar_text(self) -> str:
        # Theme key (y) intentionally omitted — theme is under Settings (u)
        return t("func_bar")

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Provide filer CSS variables before the first theme is applied."""
        base = super().get_theme_variable_defaults()
        try:
            t = get_theme(DEFAULT_THEME)
            # Flatten ColorSystem variables from the default filer theme
            cs = t.to_color_system()
            # Theme.variables are the custom keys we need for app.css
            base = {**base, **(t.variables or {})}
        except Exception:
            pass
        return base

    def on_mount(self) -> None:
        # Language + themes from config
        set_runtime_language(None)  # follow config / env
        register_all_themes(self)
        preferred = resolve_theme_name(get_theme_name())
        try:
            self.theme = preferred
        except Exception:
            self.theme = DEFAULT_THEME
        self._current_theme = preferred

        # Load local pane first (usually instant), S3 in parallel when needed.
        self._reload_both()
        self._ui_ready = True
        self._focus_active()
        # First paint often happens before layout settles; reflow once if width changed.
        self.call_after_refresh(self._reflow_lists_if_needed)
        self.query_one("#title-bar", Static).update(self._title_text())

    def on_resize(self) -> None:
        # Terminal / split size changed — reflow rows to new column widths.
        # Resize can fire before mount; ignore until UI is ready.
        if not getattr(self, "_ui_ready", False):
            return
        self._reflow_lists_if_needed()

    def _reflow_lists(self) -> None:
        for i in (0, 1):
            self._render_pane(i, force_list=True, update_chrome=(i == 1))

    def _reflow_lists_if_needed(self) -> None:
        """Rebuild lists only when content width actually changed (avoids double work on mount)."""
        changed = False
        for i in (0, 1):
            ol = self.query_one(f"#list-{i}", OptionList)
            w = self._content_width(ol)
            if w != self._list_widths[i]:
                changed = True
                break
        if changed:
            self._reflow_lists()

    def _reload_both(self) -> None:
        # Parallel refresh: local listing + S3 API often dominate startup time.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _one(i: int) -> int:
            refresh_pane(self.panes[i], self.s3)
            return i

        # Always use a small pool so left (local) and right (S3) overlap.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(_one, i) for i in (0, 1)]
            for _ in as_completed(futs):
                pass
        for i in (0, 1):
            self._render_pane(i, force_list=True, update_chrome=False)
        self.query_one("#title-bar", Static).update(self._title_text())
        self._update_active_chrome()

    def _content_width(self, ol: OptionList) -> int:
        """
        Columns available for the option *prompt text*.

        Textual OptionList wraps each option at:
            scrollable_content_region.width - option_padding.width
        Using size.width alone is too large → date/time wraps to the next line
        (the bug shown in sc1.png).
        """
        w = 0
        try:
            w = int(ol.scrollable_content_region.width or 0)
        except Exception:
            w = 0
        if w <= 0:
            try:
                w = int(ol.size.width or 0)
            except Exception:
                w = 0
        if w <= 0:
            try:
                tw = int(self.size.width or 80)
            except Exception:
                tw = 80
            w = max(20, (tw - 6) // 2)

        pad = 0
        try:
            pad = int(ol.get_component_styles("option-list--option").padding.width)
        except Exception:
            pad = 2  # matches CSS: padding 0 1

        # scrollable already excludes widget border/padding; subtract option pad
        # and 1 column safety for scrollbar / rounding on some terminals.
        return max(16, w - pad - 1)

    def _pane_kind_label(self, state: PaneState) -> str:
        return t("kind_local") if state.location.is_local() else t("kind_s3")

    def _update_active_chrome(self) -> None:
        """Update headers / borders without rebuilding file lists (avoids flicker)."""
        for index in (0, 1):
            state = self.panes[index]
            kind = self._pane_kind_label(state)
            side = t("pane_left") if index == 0 else t("pane_right")
            active = "●" if index == self.active else " "
            self.query_one(f"#hdr-{index}", Static).update(f"{active} {side} [{kind}]")

        p0 = self.query_one("#pane-0")
        p1 = self.query_one("#pane-1")
        if self.active == 0:
            p0.add_class("active-pane")
            p1.remove_class("active-pane")
        else:
            p1.add_class("active-pane")
            p0.remove_class("active-pane")

    def _render_pane(
        self,
        index: int,
        force_list: bool = True,
        *,
        update_chrome: bool = True,
    ) -> None:
        state = self.panes[index]
        kind = self._pane_kind_label(state)
        side = t("pane_left") if index == 0 else t("pane_right")
        active = "●" if index == self.active else " "
        self.query_one(f"#hdr-{index}", Static).update(f"{active} {side} [{kind}]")

        ol = self.query_one(f"#list-{index}", OptionList)
        width = self._content_width(ol)
        self._list_widths[index] = width

        path_widget = self.query_one(f"#path-{index}", Static)
        try:
            path_w = max(8, int(path_widget.size.width or width) - 2)
        except Exception:
            path_w = width
        path_widget.update(_format_path(state.location.display(), path_w))

        if force_list:
            # Prefer set_options over clear+add to reduce layout thrash
            options: list[Option] = []
            selected = state.selected
            entries = state.entries
            for i, entry in enumerate(entries):
                label = _format_row(entry, entry.name in selected, width=width)
                options.append(Option(label, id=f"e{i}"))
            if options:
                if hasattr(ol, "set_options"):
                    ol.set_options(options)
                else:
                    ol.clear_options()
                    ol.add_options(options)
                cursor = min(max(0, state.cursor), len(options) - 1)
                state.cursor = cursor
                ol.highlighted = cursor
            else:
                # Should be rare after recovery; still offer escape hatches via keys
                empty = [Option(t("empty_hint"), id="empty")]
                if hasattr(ol, "set_options"):
                    ol.set_options(empty)
                else:
                    ol.clear_options()
                    ol.add_options(empty)

        sel_n = len(state.selected)
        err = t("pane_err", err=state.error) if state.error else ""
        total_files = 0
        total_dirs = 0
        for e in state.entries:
            if e.name == "..":
                continue
            if e.is_dir:
                total_dirs += 1
            else:
                total_files += 1
        self.query_one(f"#stat-{index}", Static).update(
            t("pane_stat", dirs=total_dirs, files=total_files, sel=sel_n, err=err)
        )
        if update_chrome:
            self._update_active_chrome()

    def _focus_active(self) -> None:
        self.query_one(f"#list-{self.active}", OptionList).focus()

    def _active_state(self) -> PaneState:
        return self.panes[self.active]

    def _other_state(self) -> PaneState:
        return self.panes[1 - self.active]

    def _sync_cursor_from_list(self) -> None:
        ol = self.query_one(f"#list-{self.active}", OptionList)
        if ol.highlighted is not None:
            self._active_state().cursor = ol.highlighted

    def _set_msg(self, text: str, error: bool = False) -> None:
        style = "error-text" if error else ""
        msg = self.query_one("#message", Static)
        msg.set_class(error, "error-text")
        msg.update(f" {text}")

    # --- list events ---

    @on(OptionList.OptionHighlighted)
    def on_highlight(self, event: OptionList.OptionHighlighted) -> None:
        list_id = event.option_list.id
        if not list_id or not list_id.startswith("list-"):
            return
        idx = int(list_id.split("-")[1])
        if event.option_index is not None:
            self.panes[idx].cursor = event.option_index

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        list_id = event.option_list.id
        if not list_id or not list_id.startswith("list-"):
            return
        idx = int(list_id.split("-")[1])
        self.active = idx
        self.panes[idx].cursor = event.option_index
        entry = self.panes[idx].current_entry()
        if entry and (entry.is_dir or entry.name == ".."):
            navigate_into(self.panes[idx], self.s3)
            self._render_pane(idx)
            self._focus_active()
        elif entry:
            from .archive_ops import is_archive_name
            from .runner import is_runnable_name, is_executable_file
            from .operations import entry_source_path

            if is_archive_name(entry.name):
                self.action_open_archive()
                return
            # Local executables / scripts: run on Enter
            try:
                if entry.location and entry.location.is_local():
                    path = entry_source_path(entry)
                    if is_executable_file(path) or is_runnable_name(entry.name):
                        self.action_execute_file()
                        return
                elif is_runnable_name(entry.name):
                    # S3 script/binary: still offer execute (downloads temp)
                    self.action_execute_file()
                    return
            except Exception:
                pass
            self.action_view()

    # --- actions ---

    def action_switch_pane(self) -> None:
        self._sync_cursor_from_list()
        self.active = 1 - self.active
        # Do NOT rebuild file lists on focus change — that was re-wrapping rows
        # with a slightly different measured width and corrupting the display.
        self._update_active_chrome()
        self._focus_active()

    def action_focus_left(self) -> None:
        self._sync_cursor_from_list()
        self.active = 0
        self._update_active_chrome()
        self._focus_active()

    def action_focus_right(self) -> None:
        self._sync_cursor_from_list()
        self.active = 1
        self._update_active_chrome()
        self._focus_active()

    def action_cursor_up(self) -> None:
        """Move highlight up in the active pane (also bound to k)."""
        ol = self.query_one(f"#list-{self.active}", OptionList)
        ol.focus()
        ol.action_cursor_up()
        self._sync_cursor_from_list()

    def action_cursor_down(self) -> None:
        """Move highlight down in the active pane (also bound to j)."""
        ol = self.query_one(f"#list-{self.active}", OptionList)
        ol.focus()
        ol.action_cursor_down()
        self._sync_cursor_from_list()

    def action_toggle_select(self) -> None:
        self._sync_cursor_from_list()
        state = self._active_state()
        entry = state.current_entry()
        if not entry or entry.name == "..":
            return
        if entry.name in state.selected:
            state.selected.discard(entry.name)
        else:
            state.selected.add(entry.name)
        # move cursor down (classic filer)
        if state.cursor < len(state.entries) - 1:
            state.cursor += 1
        self._render_pane(self.active)
        self._focus_active()

    def action_select_all_files(self) -> None:
        state = self._active_state()
        files = [e.name for e in state.entries if not e.is_dir and e.name != ".."]
        if files and all(f in state.selected for f in files):
            state.selected -= set(files)
        else:
            state.selected.update(files)
        self._render_pane(self.active)

    def action_select_toggle_all(self) -> None:
        state = self._active_state()
        all_names = {e.name for e in state.entries if e.name != ".."}
        if state.selected >= all_names and all_names:
            state.selected.clear()
        else:
            state.selected = set(all_names)
        self._render_pane(self.active)

    def action_parent(self) -> None:
        state = self._active_state()
        # synthesize ".."
        if state.entries and state.entries[0].name == "..":
            state.cursor = 0
            navigate_into(state, self.s3)
            self._render_pane(self.active)
            self._focus_active()

    def action_refresh(self) -> None:
        state = self._active_state()
        refresh_pane(state, self.s3)
        self._render_pane(self.active)
        if state.error:
            self._set_msg(t("refreshed_note", note=state.error), error=True)
        else:
            self._set_msg(t("refreshed"))

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_to_local(self) -> None:
        state = self._active_state()
        state.location = default_local_location()
        state.cursor = 0
        state.selected.clear()
        refresh_pane(state, self.s3)
        self._render_pane(self.active)
        note = f" ({state.error})" if state.error else ""
        self._set_msg(t("switched_local", note=note))

    def action_to_s3(self) -> None:
        state = self._active_state()
        state.location = default_s3_location(self.profile, self.s3.region)
        state.cursor = 0
        state.selected.clear()
        refresh_pane(state, self.s3)
        self._render_pane(self.active)
        note = f" — {state.error}" if state.error else ""
        self._set_msg(
            t("switched_s3", profile=self.profile or "default", note=note),
            error=bool(state.error and "failed" in (state.error or "").lower()),
        )

    def action_goto(self) -> None:
        def _done(value: Optional[str]) -> None:
            if not value:
                return
            try:
                st = self._active_state()
                go_to(
                    st,
                    value,
                    self.s3,
                    profile=self.profile,
                    region=self.s3.region,
                )
                self._render_pane(self.active)
                note = f" — {st.error}" if st.error else ""
                self._set_msg(
                    t("goto_msg", path=st.location.display(), note=note),
                    error=bool(st.error and "fail" in st.error.lower()),
                )
            except Exception as e:
                self._set_msg(str(e), error=True)

        cur = self._active_state().location.display()
        self.push_screen(
            InputScreen(t("goto_title"), t("goto_prompt"), cur),
            _done,
        )

    def action_profile(self) -> None:
        from .aws_profiles import list_profiles

        profiles = list_profiles()

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            try:
                self.profile = name
                self.s3.refresh(profile=name)
                self.ops = Operations(self.s3)
                # Update S3 panes with new profile; refresh recovers if path
                # is invalid under the new account (→ parent / s3://).
                notes: list[str] = []
                for p in self.panes:
                    if p.location.is_s3():
                        p.location = PathLocation(
                            LocationKind.S3,
                            p.location.path,
                            profile=name,
                            region=self.s3.region,
                        )
                        p.cursor = 0
                        p.selected.clear()
                        refresh_pane(p, self.s3)
                        if p.error:
                            notes.append(p.error)
                self._reload_both()
                note = (" — " + "; ".join(notes[:2])) if notes else ""
                self._set_msg(t("profile_set", name=name, note=note), error=bool(notes))
                try:
                    self.query_one("#title-bar", Static).update(self._title_text())
                except Exception:
                    pass
            except Exception as e:
                self._set_msg(t("profile_error", err=str(e)), error=True)

        self.push_screen(ProfileScreen(profiles, self.profile), _done)

    def action_theme(self) -> None:
        """Pick a color theme and persist it (also available under Settings u)."""
        current = resolve_theme_name(
            getattr(self, "_current_theme", None) or get_theme_name()
        )
        choices = [(name, THEME_LABELS.get(name, name)) for name in theme_names()]

        def _done(name: Optional[str]) -> None:
            if not name:
                # Cancel may already have restored theme in ThemeScreen
                try:
                    self.theme = current
                except Exception:
                    pass
                self._set_msg(t("theme_unchanged"))
                return
            name = resolve_theme_name(name)
            try:
                self.theme = name
                self._current_theme = name
                path = set_theme_name(name)
                self.query_one("#title-bar", Static).update(self._title_text())
                self._set_msg(
                    t("theme_set", name=THEME_LABELS.get(name, name), path=path)
                )
            except Exception as e:
                self._set_msg(t("theme_error", err=str(e)), error=True)

        self.push_screen(ThemeScreen(choices, current), _done)

    def action_settings(self) -> None:
        """Open settings (language, theme, viewer, archive extract)."""
        from .settings_ui import SettingsScreen

        def _done(msg: Optional[str]) -> None:
            if msg:
                self._set_msg(msg)
            try:
                self.query_one("#title-bar", Static).update(self._title_text())
                self.query_one("#func-bar", Static).update(self._func_bar_text())
            except Exception:
                pass
            self._focus_active()

        self.push_screen(SettingsScreen(), _done)

    def action_mkdir(self) -> None:
        loc = self._active_state().location
        if loc.is_s3():
            title = t("mkdir_s3_title")
            prompt = t("mkdir_s3_prompt")
            if loc.path in ("s3://", "s3:"):
                self._set_msg(t("mkdir_open_bucket"), error=True)
                return
        else:
            title = t("mkdir_local_title")
            prompt = t("mkdir_local_prompt")

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            result = self.ops.mkdir(self._active_state().location, name)
            self._set_msg(result.message, error=not result.ok)
            refresh_pane(self._active_state(), self.s3)
            self._render_pane(self.active)

        self.push_screen(InputScreen(title, prompt), _done)

    def _extract_cwd(self) -> str:
        """
        Directory for extract / run cwd.
        Prefer the *other* local pane (classic filer: drop beside the archive),
        then the active local pane, then process cwd.
        """
        import os as _os

        other = self._other_state()
        active = self._active_state()
        if other.location.is_local() and _os.path.isdir(other.location.path):
            return other.location.path
        if active.location.is_local() and _os.path.isdir(active.location.path):
            return active.location.path
        return _os.getcwd()

    def action_shell(self) -> None:
        """Temporarily open an interactive subshell (o / Ctrl+O)."""
        from .runner import open_subshell, resolve_interactive_shell

        cwd = self._extract_cwd()
        # If active pane is local, prefer that path for the shell
        active = self._active_state().location
        if active.is_local() and os.path.isdir(active.path):
            cwd = active.path

        shell_cmd = " ".join(resolve_interactive_shell())
        left = self.panes[0].location.display()
        right = self.panes[1].location.display()
        extra = {
            "S3FILER_LEFT": left,
            "S3FILER_RIGHT": right,
            "S3FILER_ACTIVE": self._active_state().location.display(),
            "S3FILER_PROFILE": self.profile or "",
        }

        self._set_msg(t("subshell_msg", shell=shell_cmd, cwd=cwd))
        try:
            with self.suspend():
                # Banner on the free terminal
                try:
                    sys.stdout.write(
                        "\n"
                        + t(
                            "subshell_banner",
                            shell=shell_cmd,
                            cwd=cwd,
                            left=left,
                            right=right,
                        )
                    )
                    sys.stdout.flush()
                except Exception:
                    pass
                result = open_subshell(cwd, extra_env=extra)
            self._set_msg(result.message, error=not result.ok)
            # Refresh panes in case the user created/deleted files in the shell
            for i in (0, 1):
                refresh_pane(self.panes[i], self.s3)
                self._render_pane(i)
        except Exception as e:
            self._set_msg(t("subshell_failed", err=str(e)), error=True)
        self._focus_active()

    def action_run_command(self) -> None:
        """Run a shell command with selected files as arguments (!)."""
        self._sync_cursor_from_list()
        entries = self._active_state().selected_entries()
        names = ", ".join(e.name for e in entries[:5]) if entries else "(no files)"
        more = t("more_items", n=len(entries) - 5) if len(entries) > 5 else ""

        def _done(cmd: Optional[str]) -> None:
            if not cmd or not cmd.strip():
                return
            self._run_external(cmd.strip(), entries)

        self.push_screen(
            InputScreen(
                t("run_cmd_title"),
                t("run_cmd_prompt", files=f"{names}{more}"),
                "",
            ),
            _done,
        )

    def action_execute_file(self) -> None:
        """Execute selected file as a program/script (x)."""
        self._sync_cursor_from_list()
        entry = self._active_state().current_entry()
        if not entry or entry.is_dir or entry.name == "..":
            self._set_msg(t("select_file_exec"), error=True)
            return

        def _done(ok: bool) -> None:
            if not ok:
                self._set_msg(t("exec_cancelled"))
                return
            from .runner import run_entry_as_program

            cwd = self._extract_cwd()
            try:
                with self.suspend():
                    result = run_entry_as_program(entry, self.s3, cwd=cwd)
                self._set_msg(result.message, error=not result.ok)
            except Exception as e:
                self._set_msg(t("exec_failed", err=str(e)), error=True)
            self._focus_active()

        self.push_screen(
            ConfirmScreen(t("exec_confirm_title"), t("exec_confirm", name=entry.name)),
            _done,
        )

    def _run_external(self, command: str, entries: list) -> None:
        from .runner import run_command_with_entries

        cwd = self._extract_cwd()
        try:
            with self.suspend():
                result = run_command_with_entries(
                    command, entries, self.s3, cwd=cwd
                )
            self._set_msg(result.message, error=not result.ok)
        except Exception as e:
            self._set_msg(t("cmd_failed", err=str(e)), error=True)
        self._focus_active()

    def action_open_archive(self) -> None:
        """Open archive browser for selected/current file (a or Enter on archive)."""
        self._sync_cursor_from_list()
        entry = self._active_state().current_entry()
        if not entry or entry.is_dir or entry.name == "..":
            self._set_msg(t("select_archive"), error=True)
            return
        from .archive_ops import is_archive_name, materialize_archive

        if not is_archive_name(entry.name):
            self._set_msg(t("not_archive", name=entry.name), error=True)
            return
        try:
            path, temp_dir = materialize_archive(entry, self.s3)
        except Exception as e:
            self._set_msg(t("archive_open_failed", err=str(e)), error=True)
            return

        extract_dir = self._extract_cwd()

        def _done(msg: Optional[str]) -> None:
            if msg:
                self._set_msg(msg)
                try:
                    self.notify(msg, severity="information", timeout=6)
                except Exception:
                    pass
            else:
                self._set_msg(t("archive_closed"))
            refresh_pane(self._active_state(), self.s3)
            refresh_pane(self._other_state(), self.s3)
            self._render_pane(0)
            self._render_pane(1)
            self._focus_active()

        self.push_screen(
            ArchiveBrowserScreen(
                path,
                title=entry.name,
                extract_dir=extract_dir,
                temp_dir=temp_dir,
            ),
            _done,
        )
        self._set_msg(t("archive_open_msg", name=entry.name, dest=extract_dir))

    def action_rename(self) -> None:
        self._sync_cursor_from_list()
        entry = self._active_state().current_entry()
        if not entry or entry.name == "..":
            self._set_msg(t("nothing_to_rename"), error=True)
            return

        def _done(name: Optional[str]) -> None:
            if not name or name == entry.name:
                return
            result = self.ops.rename_entry(entry, name)
            self._set_msg(result.message, error=not result.ok)
            refresh_pane(self._active_state(), self.s3)
            self._render_pane(self.active)

        self.push_screen(
            InputScreen(
                t("rename_title"),
                t("rename_prompt", name=entry.name),
                entry.name,
            ),
            _done,
        )

    def action_delete(self) -> None:
        self._sync_cursor_from_list()
        state = self._active_state()
        entries = state.selected_entries()
        if not entries:
            self._set_msg(t("nothing_to_delete"), error=True)
            return
        names = ", ".join(e.name for e in entries[:5])
        more = t("more_items", n=len(entries) - 5) if len(entries) > 5 else ""

        def _done(ok: bool) -> None:
            if not ok:
                self._set_msg(t("cancelled", op=t("delete")))
                return
            self._run_delete(entries)

        self.push_screen(
            ConfirmScreen(
                t("delete_title"),
                t("delete_confirm", n=len(entries), names=f"{names}{more}"),
            ),
            _done,
        )

    @work(thread=True)
    def _run_delete(self, entries) -> None:
        total = len(entries)
        prog = ProgressScreen(t("progress_delete", n=total), total=total)
        self.call_from_thread(self.push_screen, prog)

        def progress(msg: str) -> None:
            # Parse "Delete i/total: name" if possible
            cur = 0
            if "/" in msg:
                try:
                    left = msg.split(":", 1)[0]
                    cur = int(left.split()[-1].split("/")[0])
                except Exception:
                    cur = 0
            self.call_from_thread(prog.set_progress, cur, total, msg)
            self.call_from_thread(self._set_msg, msg)

        result = self.ops.delete_entries(entries, progress=progress)
        state = self._active_state()
        state.selected.clear()

        def _ui() -> None:
            try:
                self.pop_screen()
            except Exception:
                pass
            refresh_pane(self._active_state(), self.s3)
            self._render_pane(self.active)
            self._set_msg(result.message, error=not result.ok)
            try:
                self.notify(
                    result.message,
                    severity="error" if not result.ok else "information",
                    timeout=6,
                )
            except Exception:
                pass
            self._focus_active()

        self.call_from_thread(_ui)

    def action_copy(self) -> None:
        self._transfer(move=False)

    def action_move(self) -> None:
        self._transfer(move=True)

    def action_copy_tree(self) -> None:
        """Copy with destination picked from directory tree (Shift+C)."""
        self._transfer_via_tree(move=False)

    def action_move_tree(self) -> None:
        """Move with destination picked from directory tree (Shift+M)."""
        self._transfer_via_tree(move=True)

    def _transfer(self, move: bool) -> None:
        """Copy/Move to the opposite pane (classic dual-pane)."""
        self._sync_cursor_from_list()
        src_state = self._active_state()
        dest_state = self._other_state()
        entries = src_state.selected_entries()
        if not entries:
            self._set_msg(
                t("nothing_selected_op", op=t("move") if move else t("copy")),
                error=True,
            )
            return
        self._confirm_transfer(entries, dest_state.location, move)

    def _transfer_via_tree(self, move: bool) -> None:
        """Copy/Move after browsing to a destination (DestBrowserScreen)."""
        self._sync_cursor_from_list()
        src_state = self._active_state()
        entries = src_state.selected_entries()
        if not entries:
            self._set_msg(
                t("nothing_selected_op", op=t("move") if move else t("copy")),
                error=True,
            )
            return

        op = t("move") if move else t("copy")
        more = t("more_items", n=len(entries) - 5) if len(entries) > 5 else ""

        # Start at the other pane's location (classic dual-pane default dest)
        other = self._other_state().location
        local_start = (
            self.panes[0].location
            if self.panes[0].location.is_local()
            else self.panes[1].location
            if self.panes[1].location.is_local()
            else default_local_location()
        )
        if not local_start.is_local():
            local_start = default_local_location()
        s3_start = (
            self.panes[0].location
            if self.panes[0].location.is_s3()
            else self.panes[1].location
            if self.panes[1].location.is_s3()
            else default_s3_location(self.profile)
        )
        if not s3_start.is_s3():
            s3_start = default_s3_location(self.profile)

        def _on_dest(path: Optional[str]) -> None:
            if not path:
                self._set_msg(t("cancelled", op=op))
                return
            try:
                dest = self._path_to_location(path)
            except Exception as e:
                self._set_msg(t("invalid_dest", err=str(e)), error=True)
                return
            self._confirm_transfer(entries, dest, move, dest_label=path)

        self.push_screen(
            DestBrowserScreen(
                t("transfer_browse_title", op=op, n=len(entries), more=more),
                start=other,
                s3=self.s3,
                local_start=local_start,
                s3_start=s3_start,
                confirm_label=t("transfer_confirm_btn"),
            ),
            _on_dest,
        )
        self._set_msg(t("transfer_hint", op=op))

    def _confirm_transfer(
        self,
        entries: list,
        dest: PathLocation,
        move: bool,
        dest_label: Optional[str] = None,
    ) -> None:
        op = t("move") if move else t("copy")
        names = ", ".join(e.name for e in entries[:5])
        more = t("more_items", n=len(entries) - 5) if len(entries) > 5 else ""
        dest_s = dest_label or dest.display()

        def _done(ok: bool) -> None:
            if not ok:
                self._set_msg(t("cancelled", op=op))
                return
            self._run_transfer(entries, dest, move)

        self.push_screen(
            ConfirmScreen(
                op,
                t(
                    "transfer_confirm",
                    op=op,
                    n=len(entries),
                    dest=dest_s,
                    names=f"{names}{more}",
                ),
            ),
            _done,
        )

    def _path_to_location(self, path: str) -> PathLocation:
        path = path.strip()
        if path.lower().startswith("s3://"):
            from .s3_client import normalize_s3_dir

            return PathLocation(
                LocationKind.S3,
                normalize_s3_dir(path),
                profile=self.profile,
                region=self.s3.region,
            )
        return PathLocation(LocationKind.LOCAL, local_fs.normalize_local_path(path))

    @work(thread=True)
    def _run_transfer(self, entries, dest: PathLocation, move: bool) -> None:
        op = t("move") if move else t("copy")
        total = len(entries)
        prog = ProgressScreen(
            t("progress_move" if move else "progress_copy", n=total),
            total=total,
        )
        self.call_from_thread(self.push_screen, prog)

        def progress(msg: str) -> None:
            cur = 0
            # Messages look like "Copy 2/5: name" or "Copy 2/5: name — done"
            try:
                token = msg.split(":", 1)[0].split()[-1]  # "2/5"
                cur = int(token.split("/")[0])
            except Exception:
                pass
            self.call_from_thread(prog.set_progress, cur, total, msg)
            self.call_from_thread(self._set_msg, msg)

        if move:
            result = self.ops.move_entries(entries, dest, progress=progress)
        else:
            result = self.ops.copy_entries(entries, dest, progress=progress)

        def _ui() -> None:
            try:
                self.pop_screen()
            except Exception:
                pass
            for i in (0, 1):
                refresh_pane(self.panes[i], self.s3)
                self.panes[i].selected.clear()
                self._render_pane(i)
            self._set_msg(result.message, error=not result.ok)
            try:
                self.notify(
                    result.message,
                    severity="error" if not result.ok else "information",
                    timeout=6,
                )
            except Exception:
                pass
            self._focus_active()

        self.call_from_thread(_ui)

    def action_view(self) -> None:
        self._sync_cursor_from_list()
        entry = self._active_state().current_entry()
        if not entry or entry.name == ".." or entry.is_dir:
            self._set_msg(t("select_file_view"), error=True)
            return

        # Always use a registered per-extension command when one exists.
        ext_cmd = viewer_command_for(entry.name)
        if ext_cmd:
            try:
                self._view_external(entry, ext_cmd)
                return
            except Exception as e:
                self._set_msg(t("viewer_external_fail", err=str(e)), error=True)
                # fall through to built-in viewer

        # SIXEL image view (terminal graphics) — before binary/text viewer
        try:
            if self._try_view_sixel(entry):
                return
        except Exception as e:
            self._set_msg(t("sixel_view_fail", err=str(e)), error=True)
            # fall through to text/binary viewer

        try:
            from .encoding_util import decode_for_view
            from .operations import read_entry_bytes

            data = read_entry_bytes(entry, self.s3, max_bytes=512 * 1024)
            text, enc, binary = decode_for_view(data)
            # limit lines for UI (highlighting large files is expensive)
            lines = text.splitlines()
            if len(lines) > 5000:
                text = "\n".join(lines[:5000]) + f"\n\n... truncated ({len(lines)} lines)"
            meta = f"[{enc}] {len(data)} bytes" + (" BINARY" if binary else "")

            def _edit():
                from .editor import edit_entry

                return edit_entry(entry, self.s3)

            def _on_close(msg: Optional[str]) -> None:
                if msg:
                    self._set_msg(msg)
                # Refresh pane in case local/S3 object changed
                refresh_pane(self._active_state(), self.s3)
                self._render_pane(self.active)
                self._focus_active()

            self.push_screen(
                ViewerScreen(
                    entry.name,
                    text,
                    meta,
                    is_binary=binary,
                    edit_handler=_edit,
                    app_theme=getattr(self, "_current_theme", None) or self.theme,
                ),
                _on_close,
            )
        except Exception as e:
            self._set_msg(t("view_failed", err=str(e)), error=True)

    def _try_view_sixel(self, entry) -> bool:
        """
        Show image via SIXEL when terminal supports it.
        Returns True if handled (success). False = not applicable (use fallback).
        Raises on failure after deciding to show.
        """
        from .operations import read_entry_bytes
        from .sixel_view import (
            MAX_IMAGE_BYTES,
            ensure_pillow,
            is_image_name,
            pillow_install_hint,
            show_sixel_fullscreen,
            supports_sixel,
        )

        if not is_image_name(entry.name):
            return False
        if not supports_sixel():
            return False
        # Pillow may be installed for a different Python than the one running
        # s3filer (common: pip3 vs .venv). Try ensure into *this* interpreter.
        if not ensure_pillow():
            self._set_msg(
                t("sixel_need_pillow", cmd=pillow_install_hint()),
                error=True,
            )
            return False

        self._set_msg(t("sixel_loading", name=entry.name))
        data = read_entry_bytes(entry, self.s3, max_bytes=MAX_IMAGE_BYTES)
        if not data:
            raise RuntimeError("empty image")

        with self.suspend():
            msg = show_sixel_fullscreen(data, title=entry.name)
        self._set_msg(t("sixel_done", msg=msg))
        self._focus_active()
        return True

    def _view_external(self, entry, command_template: str) -> None:
        """
        Open file with user-configured external command in the background.

        Does not suspend the TUI — the filer stays on screen; status goes to
        the message line. Temp downloads (S3) are cleaned up after the
        process exits.
        """
        from .runner import (
            build_command_line,
            cleanup_temps,
            materialize_entry,
            resolve_interactive_shell,
            start_via_user_shell,
        )

        path, temp_dir = materialize_entry(entry, self.s3)
        temps = [temp_dir] if temp_dir else []
        shell = resolve_interactive_shell()
        tmpl = command_template.strip()
        cmdline = build_command_line(tmpl, [path], shell_argv=shell)
        self._set_msg(t("viewer_external_opening", cmd=cmdline))

        def _on_exit(_rc: int) -> None:
            # Keep temp files until the viewer process ends (S3 downloads).
            cleanup_temps(temps)

        result = start_via_user_shell(
            cmdline,
            cwd=self._extract_cwd(),
            shell_argv=shell,
            on_exit=_on_exit if temps else None,
        )
        if not result.ok:
            cleanup_temps(temps)
            raise RuntimeError(result.message)

        self._set_msg(t("viewer_external_started", cmd=cmdline))
        self._focus_active()

    def action_info(self) -> None:
        self._sync_cursor_from_list()
        entry = self._active_state().current_entry()
        if not entry or entry.name == "..":
            self._set_msg(t("nothing_selected"), error=True)
            return
        try:
            from .operations import get_file_info

            info = get_file_info(entry, self.s3)
            lines = [
                f"Name:       {info.name}",
                f"Path:       {info.path}",
                f"Type:       {'Directory' if info.is_dir else 'File'}",
                f"Location:   {info.kind.name}",
                f"Size:       {info.size} bytes ({_fmt_size(info.size)})",
                f"Modified:   {_fmt_mtime(info.mtime)}",
            ]
            if info.permissions:
                lines.append(f"Mode:       {info.permissions}")
            if info.content_type:
                lines.append(f"ContentType:{info.content_type}")
            if info.storage_class:
                lines.append(f"Storage:    {info.storage_class}")
            if info.etag:
                lines.append(f"ETag:       {info.etag}")
            if info.mime_hint:
                lines.append(f"MIME hint:  {info.mime_hint}")
            if info.is_binary is not None:
                lines.append(f"Binary:     {info.is_binary}")
            if info.encoding:
                conf = (
                    f" ({info.encoding_confidence:.0%})"
                    if info.encoding_confidence is not None
                    else ""
                )
                lines.append(f"Encoding:   {info.encoding}{conf}")
            if info.line_count is not None:
                lines.append(f"Lines:      {info.line_count}")
            self.push_screen(InfoScreen("File information", "\n".join(lines)))
        except Exception as e:
            self._set_msg(t("info_failed", err=str(e)), error=True)

    def action_tree(self) -> None:
        """Browse directories and jump the active pane there (s/g to confirm)."""
        state = self._active_state()
        local_start = (
            state.location
            if state.location.is_local()
            else default_local_location()
        )
        s3_start = (
            state.location
            if state.location.is_s3()
            else default_s3_location(self.profile)
        )

        def _done(path: Optional[str]) -> None:
            if not path:
                return
            try:
                st = self._active_state()
                go_to(
                    st,
                    path,
                    self.s3,
                    profile=self.profile,
                    region=self.s3.region,
                )
                self._render_pane(self.active)
                msg = f"Jump → {st.location.display()}"
                if st.error:
                    msg += f" — {st.error}"
                self._set_msg(msg, error=bool(st.error and "fail" in (st.error or "").lower()))
            except Exception as e:
                self._set_msg(str(e), error=True)

        self.push_screen(
            DestBrowserScreen(
                "Jump — browse path  (s/g: go here)",
                start=state.location,
                s3=self.s3,
                local_start=local_start,
                s3_start=s3_start,
                confirm_label="s/g: jump HERE",
            ),
            _done,
        )

    def action_quit_app(self) -> None:
        def _done(ok: bool) -> None:
            if ok:
                self.exit()

        self.push_screen(ConfirmScreen("Quit", "Exit S3 Filer?"), _done)


def run_app(
    profile: Optional[str] = None,
    left: Optional[str] = None,
    right: Optional[str] = None,
) -> None:
    app = S3FilerApp(profile=profile, left=left, right=right)
    app.run()
