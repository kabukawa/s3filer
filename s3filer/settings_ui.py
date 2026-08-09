"""Settings modal screen."""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from . import config as cfg
from .i18n import set_runtime_language, t
from .themes import THEME_LABELS, theme_names


class SettingsScreen(ModalScreen[Optional[str]]):
    """Top-level settings menu. Dismisses with a status message (or None)."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("enter", "open_item", "Open", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._status: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(t("settings_title"), classes="dialog-title")
            yield Static(t("settings_hint"), classes="dialog-hint")
            yield OptionList(id="settings-list", compact=True, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("close"), variant="primary", id="close")

    def on_mount(self) -> None:
        self._reload_list()
        self.query_one("#settings-list", OptionList).focus()

    def _items(self) -> list[tuple[str, str]]:
        lang = cfg.get_language()
        theme = cfg.get_theme_name()
        vmode = cfg.get_viewer_mode()
        amode = cfg.get_archive_extract_mode()
        smode = cfg.get_sixel_mode()
        n_cmds = len(cfg.get_viewer_commands())
        vlabel = (
            t("viewer_mode_external")
            if vmode == "external_prefer"
            else t("viewer_mode_builtin")
        )
        alabel = (
            t("archive_mode_flat")
            if amode == "flat"
            else t("archive_mode_preserve")
        )
        slabel = {
            "on": t("sixel_mode_on"),
            "off": t("sixel_mode_off"),
        }.get(smode, t("sixel_mode_auto"))
        return [
            ("language", f"{t('set_language')}: {lang}"),
            ("theme", f"{t('set_theme')}: {theme}"),
            ("viewer_mode", f"{t('set_viewer')}: {vlabel}"),
            ("viewer_cmd", f"{t('viewer_cmd_list_title')} ({n_cmds})"),
            ("archive", f"{t('set_archive')}: {alabel}"),
            ("sixel", f"{t('set_sixel')}: {slabel}"),
            ("config_edit", t("set_config_edit")),
        ]

    def _reload_list(self) -> None:
        ol = self.query_one("#settings-list", OptionList)
        items = self._items()
        hi = ol.highlighted or 0
        ol.set_options([Option(label, id=iid) for iid, label in items])
        ol.highlighted = min(hi, max(0, len(items) - 1))

    def _list(self) -> OptionList:
        return self.query_one("#settings-list", OptionList)

    def action_cursor_up(self) -> None:
        self._list().focus()
        self._list().action_cursor_up()

    def action_cursor_down(self) -> None:
        self._list().focus()
        self._list().action_cursor_down()

    def action_close(self) -> None:
        self.dismiss(self._status)

    def action_open_item(self) -> None:
        ol = self._list()
        if ol.highlighted is None:
            return
        opt = ol.get_option_at_index(ol.highlighted)
        self._handle(str(opt.id) if opt.id else "")

    def _handle(self, iid: str) -> None:
        if iid == "language":
            self._pick_language()
        elif iid == "theme":
            self._pick_theme()
        elif iid == "viewer_mode":
            self._pick_viewer_mode()
        elif iid == "viewer_cmd":
            self._manage_viewer_cmds()
        elif iid == "archive":
            self._pick_archive_mode()
        elif iid == "sixel":
            self._pick_sixel_mode()
        elif iid == "config_edit":
            self._edit_config_file()

    def _pick_language(self) -> None:
        choices = [("ja", t("lang_ja")), ("en", t("lang_en"))]

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            cfg.set_language(name)
            set_runtime_language(name)
            self._status = t("lang_set", lang=name)
            try:
                self.query_one(".dialog-title", Label).update(t("settings_title"))
            except Exception:
                pass
            self._reload_list()
            # Refresh main chrome immediately
            try:
                app = self.app
                app.query_one("#title-bar", Static).update(app._title_text())  # type: ignore
                app.query_one("#func-bar", Static).update(app._func_bar_text())  # type: ignore
                for i in (0, 1):
                    app._render_pane(i, force_list=False)  # type: ignore
            except Exception:
                pass
            try:
                self.app.notify(self._status)
            except Exception:
                pass

        self.app.push_screen(
            _SimplePickScreen(t("set_language"), choices, cfg.get_language()),
            _done,
        )

    def _pick_theme(self) -> None:
        from .widgets import ThemeScreen

        current = cfg.get_theme_name()
        choices = [(n, THEME_LABELS.get(n, n)) for n in theme_names()]

        def _done(name: Optional[str]) -> None:
            if not name:
                try:
                    self.app.theme = current
                except Exception:
                    pass
                return
            from .themes import resolve_theme_name

            name = resolve_theme_name(name)
            try:
                self.app.theme = name
                if hasattr(self.app, "_current_theme"):
                    self.app._current_theme = name  # type: ignore[attr-defined]
                path = cfg.set_theme_name(name)
                self._status = t(
                    "theme_set", name=THEME_LABELS.get(name, name), path=path
                )
                try:
                    self.app.query_one("#title-bar", Static).update(
                        self.app._title_text()  # type: ignore
                    )
                except Exception:
                    pass
                self._reload_list()
            except Exception as e:
                self._status = str(e)

        self.app.push_screen(ThemeScreen(choices, current), _done)

    def _pick_viewer_mode(self) -> None:
        choices = [
            ("builtin", t("viewer_mode_builtin")),
            ("external_prefer", t("viewer_mode_external")),
        ]

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            cfg.set_viewer_mode(name)
            self._status = t("viewer_mode_set", mode=name)
            self._reload_list()

        self.app.push_screen(
            _SimplePickScreen(t("set_viewer"), choices, cfg.get_viewer_mode()),
            _done,
        )

    def _manage_viewer_cmds(self) -> None:
        def _done(msg: Optional[str]) -> None:
            if msg:
                self._status = msg
            self._reload_list()

        self.app.push_screen(ViewerCommandsScreen(), _done)

    def _pick_archive_mode(self) -> None:
        choices = [
            ("preserve", t("archive_mode_preserve")),
            ("flat", t("archive_mode_flat")),
        ]

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            cfg.set_archive_extract_mode(name)
            self._status = t("archive_mode_set", mode=name)
            self._reload_list()

        self.app.push_screen(
            _SimplePickScreen(t("set_archive"), choices, cfg.get_archive_extract_mode()),
            _done,
        )

    def _pick_sixel_mode(self) -> None:
        choices = [
            ("auto", t("sixel_mode_auto")),
            ("on", t("sixel_mode_on")),
            ("off", t("sixel_mode_off")),
        ]

        def _done(name: Optional[str]) -> None:
            if not name:
                return
            cfg.set_sixel_mode(name)
            label = {
                "on": t("sixel_mode_on"),
                "off": t("sixel_mode_off"),
            }.get(name, t("sixel_mode_auto"))
            self._status = t("sixel_mode_set", mode=label)
            self._reload_list()
            try:
                self.app.notify(self._status)
            except Exception:
                pass

        self.app.push_screen(
            _SimplePickScreen(t("set_sixel"), choices, cfg.get_sixel_mode()),
            _done,
        )

    def _edit_config_file(self) -> None:
        """Open config.json in external editor, then reload settings."""
        from .editor import resolve_editor, run_editor

        path = cfg.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            cfg.save_config({})  # write defaults
        try:
            with self.app.suspend():
                run_editor(str(path))
            # Reload language/theme from disk after edit
            cfg.invalidate_config_cache()
            set_runtime_language(None)
            try:
                self.app.theme = cfg.get_theme_name()
                if hasattr(self.app, "_current_theme"):
                    self.app._current_theme = cfg.get_theme_name()  # type: ignore
            except Exception:
                pass
            self._status = t("config_edit_done", path=str(path))
            try:
                self.query_one(".dialog-title", Label).update(t("settings_title"))
            except Exception:
                pass
            self._reload_list()
            try:
                app = self.app
                app.query_one("#title-bar", Static).update(app._title_text())  # type: ignore
                app.query_one("#func-bar", Static).update(app._func_bar_text())  # type: ignore
                for i in (0, 1):
                    app._render_pane(i, force_list=False)  # type: ignore
            except Exception:
                pass
        except Exception as e:
            self._status = t("config_edit_failed", err=str(e))

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._handle(str(event.option.id) if event.option.id else "")

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.action_close()


class ViewerCommandsScreen(ModalScreen[Optional[str]]):
    """List / add / edit / delete per-extension external viewer commands."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "edit", "Edit", show=False),
        Binding("n", "add", "Add", show=False),
        Binding("d", "delete", "Del", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._status: Optional[str] = None
        self._keys: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(t("viewer_cmd_list_title"), classes="dialog-title")
            yield Static(t("viewer_cmd_hint"), classes="dialog-hint")
            yield OptionList(id="vcmd-list", compact=True, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("viewer_cmd_add"), id="add")
                yield Button(t("close"), variant="primary", id="close")

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#vcmd-list", OptionList).focus()

    def _reload(self) -> None:
        cmds = cfg.get_viewer_commands()
        self._keys = sorted(cmds.keys())
        ol = self.query_one("#vcmd-list", OptionList)
        opts: list[Option] = []
        if not self._keys:
            opts.append(Option(t("viewer_cmd_empty"), id="__empty__"))
        else:
            for i, ext in enumerate(self._keys):
                opts.append(Option(f"{ext}  →  {cmds[ext]}", id=f"e{i}"))
        opts.append(Option(t("viewer_cmd_add"), id="__add__"))
        ol.set_options(opts)
        ol.highlighted = 0

    def _list(self) -> OptionList:
        return self.query_one("#vcmd-list", OptionList)

    def action_cursor_up(self) -> None:
        self._list().action_cursor_up()

    def action_cursor_down(self) -> None:
        self._list().action_cursor_down()

    def action_close(self) -> None:
        self.dismiss(self._status)

    def action_add(self) -> None:
        self._prompt_new()

    def action_edit(self) -> None:
        ol = self._list()
        if ol.highlighted is None:
            return
        opt = ol.get_option_at_index(ol.highlighted)
        oid = str(opt.id) if opt.id else ""
        if oid in ("__add__", "__empty__"):
            self._prompt_new()
            return
        if oid.startswith("e"):
            idx = int(oid[1:])
            if 0 <= idx < len(self._keys):
                self._prompt_edit(self._keys[idx])

    def action_delete(self) -> None:
        ol = self._list()
        if ol.highlighted is None:
            return
        opt = ol.get_option_at_index(ol.highlighted)
        oid = str(opt.id) if opt.id else ""
        if not oid.startswith("e"):
            return
        idx = int(oid[1:])
        if 0 <= idx < len(self._keys):
            ext = self._keys[idx]
            cfg.set_viewer_command(ext, "")
            self._status = t("viewer_cmd_removed", ext=ext)
            self._reload()

    def _prompt_new(self) -> None:
        from .widgets import InputScreen

        def _ext(ext: Optional[str]) -> None:
            if not ext:
                return
            ext = ext.strip()
            if not ext.startswith("."):
                ext = "." + ext
            self._prompt_edit(ext.lower())

        self.app.push_screen(
            InputScreen(t("viewer_cmd_list_title"), t("viewer_cmd_prompt_ext"), ".pdf"),
            _ext,
        )

    def _prompt_edit(self, ext: str) -> None:
        from .widgets import InputScreen

        current = cfg.get_viewer_commands().get(ext, "")

        def _cmd(cmd: Optional[str]) -> None:
            if cmd is None:
                return
            cfg.set_viewer_command(ext, cmd)
            # set_viewer_command already enables external_prefer when cmds exist
            if cmd.strip():
                self._status = t("viewer_cmd_saved", ext=ext, cmd=cmd.strip())
            else:
                self._status = t("viewer_cmd_removed", ext=ext)
            self._reload()
            try:
                self.app.notify(self._status)
            except Exception:
                pass

        self.app.push_screen(
            InputScreen(
                f"{t('viewer_edit_cmd')}: {ext}",
                t("viewer_cmd_prompt_cmd"),
                current,
            ),
            _cmd,
        )

    @on(OptionList.OptionSelected)
    def on_sel(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_edit()

    @on(Button.Pressed, "#add")
    def on_add(self) -> None:
        self._prompt_new()

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.action_close()


class _SimplePickScreen(ModalScreen[Optional[str]]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "choose", "OK", show=False),
        Binding("j", "down", "Down", show=False),
        Binding("k", "up", "Up", show=False),
    ]

    def __init__(
        self,
        title: str,
        choices: list[tuple[str, str]],
        current: Optional[str],
    ) -> None:
        super().__init__()
        self._title = title
        self._choices = choices
        self._ids = [c[0] for c in choices]
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            options = []
            for iid, label in self._choices:
                mark = " *" if iid == self._current else ""
                options.append(Option(f"{label}{mark}", id=iid))
            yield OptionList(*options, id="pick-list", compact=True, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("ok"), variant="primary", id="ok")
                yield Button(t("cancel"), id="cancel")

    def on_mount(self) -> None:
        ol = self.query_one("#pick-list", OptionList)
        ol.focus()
        if self._current in self._ids:
            ol.highlighted = self._ids.index(self._current)

    def action_up(self) -> None:
        self.query_one("#pick-list", OptionList).action_cursor_up()

    def action_down(self) -> None:
        self.query_one("#pick-list", OptionList).action_cursor_down()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_choose(self) -> None:
        ol = self.query_one("#pick-list", OptionList)
        if ol.highlighted is None:
            self.dismiss(None)
            return
        opt = ol.get_option_at_index(ol.highlighted)
        self.dismiss(str(opt.id) if opt.id else None)

    @on(OptionList.OptionSelected)
    def on_sel(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id) if event.option.id else None)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.action_choose()

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
