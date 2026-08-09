"""Config persistence and theme registry tests."""

from __future__ import annotations

from pathlib import Path

from s3filer.config import (
    DEFAULT_THEME,
    get_theme_name,
    load_config,
    set_theme_name,
)
from s3filer.themes import THEMES, resolve_theme_name, theme_names


def test_theme_registry() -> None:
    names = theme_names()
    assert DEFAULT_THEME in names
    assert "amber-crt" in names
    assert len(names) >= 5
    for n in names:
        assert n in THEMES
        assert THEMES[n].name == n


def test_resolve_theme_name() -> None:
    assert resolve_theme_name("classic-blue") == "classic-blue"
    assert resolve_theme_name("nope") == DEFAULT_THEME
    assert resolve_theme_name(None) == DEFAULT_THEME


def test_config_roundtrip(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    monkeypatch.delenv("S3FILER_THEME", raising=False)
    monkeypatch.delenv("S3FILER_LANG", raising=False)

    assert get_theme_name() == DEFAULT_THEME
    set_theme_name("matrix-green")
    assert cfg.is_file()
    assert get_theme_name() == "matrix-green"
    data = load_config()
    assert data["theme"] == "matrix-green"
    assert data.get("language") in ("ja", "en")
    assert data.get("archive_extract_mode") in ("preserve", "flat")


def test_env_override(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    set_theme_name("light")
    monkeypatch.setenv("S3FILER_THEME", "midnight")
    assert get_theme_name() == "midnight"


def test_viewer_command_roundtrip(tmp_path: Path, monkeypatch) -> None:
    from s3filer.config import (
        get_viewer_commands,
        get_viewer_mode,
        set_viewer_command,
        viewer_command_for,
    )

    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)

    set_viewer_command("pdf", "mdview {}")
    assert get_viewer_commands() == {".pdf": "mdview {}"}
    assert viewer_command_for("report.PDF") == "mdview {}"
    assert get_viewer_mode() == "external_prefer"

    set_viewer_command(".md", "notepad")
    assert ".md" in get_viewer_commands()
    assert viewer_command_for("readme.md") == "notepad"

    # delete must actually remove the key
    set_viewer_command(".pdf", "")
    assert ".pdf" not in get_viewer_commands()
    assert viewer_command_for("report.pdf") is None
    assert viewer_command_for("readme.md") == "notepad"


def test_sixel_mode_roundtrip(tmp_path: Path, monkeypatch) -> None:
    from s3filer.config import get_sixel_mode, set_sixel_mode
    from s3filer.sixel_view import supports_sixel

    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    monkeypatch.delenv("S3FILER_SIXEL", raising=False)

    assert get_sixel_mode() == "auto"
    set_sixel_mode("off")
    assert get_sixel_mode() == "off"
    assert supports_sixel() is False
    set_sixel_mode("on")
    assert get_sixel_mode() == "on"
    # Textual often makes stdout.isatty() False — still allow force ON with WT/console
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("s3filer.sixel_view._stream_isatty", lambda stream: False)
    monkeypatch.setenv("WT_SESSION", "x")
    assert supports_sixel() is True
    set_sixel_mode("auto")
    assert get_sixel_mode() == "auto"


def test_config_cache_invalidates_on_save(tmp_path: Path, monkeypatch) -> None:
    from s3filer.config import load_config, save_config, set_language

    cfg = tmp_path / "config.json"
    monkeypatch.setattr("s3filer.config.config_path", lambda: cfg)
    monkeypatch.setattr("s3filer.config.config_dir", lambda: tmp_path)
    monkeypatch.delenv("S3FILER_LANG", raising=False)

    set_language("en")
    assert load_config()["language"] == "en"
    # second load hits cache
    assert load_config()["language"] == "en"
    set_language("ja")
    assert load_config()["language"] == "ja"


def test_i18n_ja_chrome(tmp_path: Path, monkeypatch) -> None:
    from s3filer.help_text import get_help_text
    from s3filer.i18n import set_runtime_language, t

    monkeypatch.delenv("S3FILER_LANG", raising=False)
    set_runtime_language("ja")
    assert t("pane_left") == "左"
    assert t("pane_right") == "右"
    assert "設定" in t("func_bar")
    assert "テーマ" not in t("func_bar")  # Theme key removed from status bar
    assert "選択" in t("func_bar")  # Spc has description
    assert "終了" in t("func_bar")  # Q has description
    assert "ペイン" in t("func_bar")  # h/l has description
    assert "フォルダ" in t("pane_stat", dirs=1, files=2, sel=0, err="")
    title = t("title_bar", version="0", profile="d", region="ap")
    assert "リージョン" in title
    assert "テーマ" not in title
    assert "ヘルプ" not in title
    assert "設定" not in title
    help_ja = get_help_text("ja")
    assert "キー操作" in help_ja
    assert "左ペイン" in help_ja
    help_en = get_help_text("en")
    assert "key bindings" in help_en
    assert "Focus left pane" in help_en
    set_runtime_language(None)
