"""Built-in color themes for S3 Filer (Textual Theme + custom CSS vars)."""

from __future__ import annotations

from textual.theme import Theme

from .config import DEFAULT_THEME  # re-exported for callers

# Custom CSS variable keys used in app.css
# pane-bg, pane-border, pane-active-border, title-bg, title-fg,
# header-bg, header-fg, path-bg, path-fg, list-bg, list-fg,
# highlight-bg, highlight-fg, hover-bg, status-bg, status-fg,
# func-bg, func-fg, message-fg, error-fg, dialog-bg, dialog-border,
# dialog-title-fg, button-bg, button-fg, viewer-bg, viewer-fg


def _vars(**kwargs: str) -> dict[str, str]:
    return kwargs


def _theme(
    name: str,
    *,
    primary: str,
    background: str,
    foreground: str,
    surface: str,
    panel: str,
    accent: str,
    dark: bool = True,
    syntax_theme: str = "monokai",
    **extra: str,
) -> Theme:
    """Build a Theme with required base colors + filer-specific variables."""
    base_vars = {
        "pane-bg": surface,
        "pane-border": "#555555",
        "pane-active-border": accent,
        "title-bg": primary,
        "title-fg": "#ffffff",
        "header-bg": primary,
        "header-fg": accent,
        "path-bg": panel,
        "path-fg": "#55ffff",
        "list-bg": surface,
        "list-fg": "#aaaaaa",
        "highlight-bg": primary,
        "highlight-fg": "#ffffff",
        "hover-bg": panel,
        "status-bg": panel,
        "status-fg": "#aaaaaa",
        "func-bg": primary,
        "func-fg": "#ffffff",
        "message-fg": "#55ff55",
        "error-fg": "#ff5555",
        "dialog-bg": primary,
        "dialog-border": accent,
        "dialog-title-fg": accent,
        "button-bg": "#00aaaa",
        "button-fg": "#000000",
        "viewer-bg": background,
        "viewer-fg": foreground,
        # Pygments / Rich Syntax style name used by the file Viewer
        "syntax-theme": syntax_theme,
        "block-cursor-background": primary,
        "block-cursor-foreground": "#ffffff",
    }
    base_vars.update(extra)
    return Theme(
        name=name,
        primary=primary,
        secondary=panel,
        accent=accent,
        foreground=foreground,
        background=background,
        surface=surface,
        panel=panel,
        dark=dark,
        variables=base_vars,
    )


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

THEMES: dict[str, Theme] = {
    "classic-blue": _theme(
        "classic-blue",
        primary="#0000aa",
        background="#0c0c0c",
        foreground="#c0c0c0",
        surface="#000055",
        panel="#000088",
        accent="#ffff55",
        syntax_theme="monokai",
        **{
            "path-fg": "#55ffff",
            "message-fg": "#55ff55",
            "pane-border": "#555555",
            "button-bg": "#00aaaa",
        },
    ),
    "norton-cyan": _theme(
        "norton-cyan",
        primary="#008080",
        background="#000000",
        foreground="#00ffff",
        surface="#000040",
        panel="#004040",
        accent="#ffff00",
        syntax_theme="native",
        **{
            "path-fg": "#00ffff",
            "list-fg": "#00cccc",
            "header-fg": "#ffff00",
            "message-fg": "#00ff00",
            "pane-border": "#008080",
            "pane-active-border": "#ffff00",
            "button-bg": "#00aaaa",
            "dialog-bg": "#008080",
        },
    ),
    "amber-crt": _theme(
        "amber-crt",
        primary="#804000",
        background="#1a0f00",
        foreground="#ffb000",
        surface="#2a1800",
        panel="#3d2200",
        accent="#ffcc00",
        syntax_theme="coffee",
        **{
            "path-fg": "#ffcc66",
            "list-fg": "#cc8800",
            "header-fg": "#ffdd55",
            "title-fg": "#ffcc00",
            "highlight-bg": "#a05000",
            "highlight-fg": "#1a0f00",
            "message-fg": "#ffaa00",
            "error-fg": "#ff4400",
            "pane-border": "#664400",
            "pane-active-border": "#ffcc00",
            "button-bg": "#cc8800",
            "button-fg": "#1a0f00",
            "dialog-bg": "#3d2200",
            "dialog-border": "#ffcc00",
        },
    ),
    "matrix-green": _theme(
        "matrix-green",
        primary="#003300",
        background="#000000",
        foreground="#00ff66",
        surface="#001a00",
        panel="#002b00",
        accent="#00ff00",
        syntax_theme="monokai",
        **{
            "path-fg": "#66ff99",
            "list-fg": "#33cc66",
            "header-fg": "#00ff00",
            "title-fg": "#00ff66",
            "highlight-bg": "#00aa44",
            "highlight-fg": "#000000",
            "message-fg": "#00ff88",
            "error-fg": "#ff3333",
            "pane-border": "#005500",
            "pane-active-border": "#00ff00",
            "button-bg": "#00aa44",
            "button-fg": "#000000",
            "dialog-bg": "#002b00",
            "dialog-border": "#00ff00",
        },
    ),
    "midnight": _theme(
        "midnight",
        primary="#3d2b6b",
        background="#0d0b14",
        foreground="#d4d0e0",
        surface="#1a1528",
        panel="#2a2040",
        accent="#c4a0ff",
        syntax_theme="dracula",
        **{
            "path-fg": "#a898d8",
            "list-fg": "#a8a0b8",
            "header-fg": "#e0c8ff",
            "highlight-bg": "#5a3d9a",
            "highlight-fg": "#ffffff",
            "message-fg": "#90e0a0",
            "error-fg": "#ff6b8a",
            "pane-border": "#3a3050",
            "pane-active-border": "#c4a0ff",
            "button-bg": "#7b5ea7",
            "button-fg": "#ffffff",
            "dialog-bg": "#2a2040",
            "dialog-border": "#c4a0ff",
        },
    ),
    "solarized-dark": _theme(
        "solarized-dark",
        primary="#073642",
        background="#002b36",
        foreground="#839496",
        surface="#073642",
        panel="#586e75",
        accent="#b58900",
        syntax_theme="solarized-dark",
        **{
            "path-fg": "#2aa198",
            "list-fg": "#93a1a1",
            "header-fg": "#b58900",
            "title-fg": "#eee8d5",
            "highlight-bg": "#268bd2",
            "highlight-fg": "#fdf6e3",
            "message-fg": "#859900",
            "error-fg": "#dc322f",
            "pane-border": "#586e75",
            "pane-active-border": "#b58900",
            "button-bg": "#268bd2",
            "button-fg": "#fdf6e3",
            "dialog-bg": "#073642",
            "dialog-border": "#b58900",
            "status-bg": "#073642",
            "status-fg": "#93a1a1",
        },
    ),
    "light": _theme(
        "light",
        primary="#0055aa",
        background="#e8e8e8",
        foreground="#202020",
        surface="#f5f5f5",
        panel="#d0d8e0",
        accent="#aa5500",
        dark=False,
        syntax_theme="friendly",
        **{
            "path-fg": "#005588",
            "list-fg": "#303030",
            "header-fg": "#ffffff",
            "title-fg": "#ffffff",
            "highlight-bg": "#0066cc",
            "highlight-fg": "#ffffff",
            "hover-bg": "#c8d0d8",
            "message-fg": "#007700",
            "error-fg": "#cc0000",
            "pane-border": "#888888",
            "pane-active-border": "#aa5500",
            "button-bg": "#0066cc",
            "button-fg": "#ffffff",
            "dialog-bg": "#0055aa",
            "dialog-border": "#aa5500",
            "status-bg": "#d0d8e0",
            "status-fg": "#303030",
            "func-bg": "#0055aa",
            "func-fg": "#ffffff",
        },
    ),
    "monochrome": _theme(
        "monochrome",
        primary="#404040",
        background="#000000",
        foreground="#d0d0d0",
        surface="#1a1a1a",
        panel="#2a2a2a",
        accent="#ffffff",
        syntax_theme="bw",
        **{
            "path-fg": "#c0c0c0",
            "list-fg": "#a0a0a0",
            "header-fg": "#ffffff",
            "title-fg": "#ffffff",
            "highlight-bg": "#606060",
            "highlight-fg": "#ffffff",
            "message-fg": "#e0e0e0",
            "error-fg": "#ffffff",
            "pane-border": "#505050",
            "pane-active-border": "#ffffff",
            "button-bg": "#707070",
            "button-fg": "#000000",
            "dialog-bg": "#2a2a2a",
            "dialog-border": "#ffffff",
        },
    ),
}

# Human-readable labels for the picker
THEME_LABELS: dict[str, str] = {
    "classic-blue": "Classic Blue (FD / FILMTN)",
    "norton-cyan": "Norton Cyan",
    "amber-crt": "Amber CRT",
    "matrix-green": "Matrix Green",
    "midnight": "Midnight Purple",
    "solarized-dark": "Solarized Dark",
    "light": "Light",
    "monochrome": "Monochrome",
}


def theme_names() -> list[str]:
    return list(THEMES.keys())


def get_theme(name: str) -> Theme:
    if name in THEMES:
        return THEMES[name]
    return THEMES[DEFAULT_THEME]


def resolve_theme_name(name: str | None) -> str:
    if name and name in THEMES:
        return name
    return DEFAULT_THEME


def syntax_theme_for(app_theme_name: str | None) -> str:
    """Pygments/Rich style name paired with an app theme."""
    name = resolve_theme_name(app_theme_name)
    theme = THEMES.get(name)
    if not theme:
        return "monokai"
    return str(theme.variables.get("syntax-theme") or "monokai")


def viewer_bg_for(app_theme_name: str | None) -> str:
    """Background color for Syntax highlighting (matches viewer chrome)."""
    name = resolve_theme_name(app_theme_name)
    theme = THEMES.get(name)
    if not theme:
        return "default"
    return str(
        theme.variables.get("viewer-bg")
        or theme.background
        or "default"
    )


def register_all_themes(app) -> None:
    """Register every built-in theme on a Textual App."""
    for theme in THEMES.values():
        app.register_theme(theme)
