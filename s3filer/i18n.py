"""Simple JA/EN message catalog for S3 Filer UI strings."""

from __future__ import annotations

from typing import Any, Optional

from . import config as cfg

# key -> {"ja": "...", "en": "..."}
_MSG: dict[str, dict[str, str]] = {
    # generic
    "ok": {"ja": "OK", "en": "OK"},
    "cancel": {"ja": "キャンセル", "en": "Cancel"},
    "close": {"ja": "閉じる", "en": "Close"},
    "yes": {"ja": "はい [Y]", "en": "Yes [Y]"},
    "no": {"ja": "いいえ [N]", "en": "No [N]"},
    "please_wait": {"ja": "お待ちください…", "en": "Please wait…"},
    "starting": {"ja": "開始しています…", "en": "Starting…"},
    # settings
    "settings_title": {"ja": "設定", "en": "Settings"},
    "settings_hint": {
        "ja": "項目を選んで Enter · Esc で閉じる · 変更は自動保存",
        "en": "Enter to open · Esc to close · changes are saved automatically",
    },
    "set_language": {"ja": "言語 / Language", "en": "Language"},
    "set_theme": {"ja": "カラーテーマ", "en": "Color theme"},
    "set_viewer": {"ja": "ファイル表示 (View)", "en": "File viewer"},
    "set_archive": {"ja": "アーカイブ展開", "en": "Archive extract"},
    "set_sixel": {"ja": "SIXEL 画像表示", "en": "SIXEL image view"},
    "sixel_mode_auto": {
        "ja": "自動 (対応端末のみ)",
        "en": "Auto (capable terminals only)",
    },
    "sixel_mode_on": {
        "ja": "強制 ON",
        "en": "Force ON",
    },
    "sixel_mode_off": {
        "ja": "強制 OFF",
        "en": "Force OFF",
    },
    "sixel_mode_set": {
        "ja": "SIXEL 画像表示: {mode}",
        "en": "SIXEL image view: {mode}",
    },
    "set_config_edit": {
        "ja": "設定ファイルをエディタで開く",
        "en": "Open config file in editor",
    },
    "config_edit_done": {
        "ja": "設定ファイルを編集しました（再読込済み）: {path}",
        "en": "Config edited (reloaded): {path}",
    },
    "config_edit_failed": {
        "ja": "設定ファイルを開けませんでした: {err}",
        "en": "Could not open config file: {err}",
    },
    "pane_left": {"ja": "左", "en": "Left"},
    "pane_right": {"ja": "右", "en": "Right"},
    "kind_local": {"ja": "LOCAL", "en": "LOCAL"},
    "kind_s3": {"ja": "S3", "en": "S3"},
    "title_bar": {
        "ja": " S3 Filer v{version}  |  AWS: {profile}  リージョン: {region} ",
        "en": " S3 Filer v{version}  |  AWS: {profile}  region: {region} ",
    },
    "title_help": {"ja": "F1=ヘルプ  u=設定", "en": "F1=Help  u=Settings"},
    "func_bar": {
        "ja": "F1 ヘルプ  v 表示  c/C コピー  m/M 移動  n 作成  x 実行  ! コマンド  o シェル  a 書庫  u 設定  d 削除  |  \\ ドライブ  h/l ペイン  j/k 上下  Spc 選択  Q 終了",
        "en": "F1 Help  v View  c/C Copy  m/M Move  n MkDir  x Exec  ! Cmd  o Shell  a Archive  u Settings  d Del  |  \\ Drive  h/l Pane  j/k Up/Dn  Spc Select  Q Quit",
    },
    "help_title": {"ja": "S3 Filer ヘルプ", "en": "S3 Filer Help"},
    "help_hint": {
        "ja": " [Esc/Q] 閉じる  |  ↑↓/jk  PgUp/PgDn/Space  Home/End",
        "en": " [Esc/Q] Close  |  ↑↓/jk  PgUp/PgDn/Space  Home/End",
    },
    "pane_stat": {
        "ja": " {dirs} フォルダ  {files} ファイル  選択:{sel}{err}",
        "en": " {dirs} dirs  {files} files  sel:{sel}{err}",
    },
    "pane_err": {"ja": "  エラー: {err}", "en": "  ERR: {err}"},
    "empty_hint": {
        "ja": "(空 — Ctrl+L ローカル · Ctrl+S S3 · g 移動 · f 再読込)",
        "en": "(empty — Ctrl+L local · Ctrl+S S3 · g go · f refresh)",
    },
    "viewer_cmd_list_title": {
        "ja": "外部ビューアコマンド一覧",
        "en": "External viewer commands",
    },
    "viewer_cmd_add": {"ja": "＋ 新規追加…", "en": "+ Add new…"},
    "viewer_cmd_empty": {
        "ja": "(未登録 — Enter で追加)",
        "en": "(none — Enter to add)",
    },
    "viewer_cmd_hint": {
        "ja": "Enter: 編集  d: 削除  n: 追加  Esc: 戻る",
        "en": "Enter: edit  d: delete  n: add  Esc: back",
    },
    "viewer_external_opening": {
        "ja": "外部ビューアを起動中: {cmd}",
        "en": "Starting external viewer: {cmd}",
    },
    "viewer_external_started": {
        "ja": "外部ビューアを起動しました: {cmd}",
        "en": "External viewer started: {cmd}",
    },
    "viewer_external_done": {
        "ja": "外部ビューア終了: {msg}",
        "en": "External viewer finished: {msg}",
    },
    "viewer_external_fail": {
        "ja": "外部ビューア失敗: {err} — 組み込みに切替",
        "en": "External viewer failed: {err} — falling back to built-in",
    },
    "lang_ja": {"ja": "日本語", "en": "Japanese"},
    "lang_en": {"ja": "English", "en": "English"},
    "lang_set": {"ja": "言語を {lang} に設定しました", "en": "Language set to {lang}"},
    "viewer_mode_builtin": {
        "ja": "組み込みビューアを使う",
        "en": "Use built-in viewer",
    },
    "viewer_mode_external": {
        "ja": "拡張子ごとに外部コマンドを優先",
        "en": "Prefer external command per extension",
    },
    "viewer_edit_cmd": {
        "ja": "拡張子ごとの外部コマンドを編集",
        "en": "Edit external command by extension",
    },
    "viewer_mode_set": {
        "ja": "View モード: {mode}",
        "en": "Viewer mode: {mode}",
    },
    "viewer_cmd_prompt_ext": {
        "ja": "拡張子 (例: .pdf / pdf):",
        "en": "Extension (e.g. .pdf / pdf):",
    },
    "viewer_cmd_prompt_cmd": {
        "ja": "コマンド ({} がファイルパスに置換)。空で削除:",
        "en": "Command ({} = file path). Empty to remove:",
    },
    "viewer_cmd_saved": {
        "ja": "ビューアコマンドを保存: {ext} → {cmd}",
        "en": "Viewer command saved: {ext} → {cmd}",
    },
    "viewer_cmd_removed": {
        "ja": "ビューアコマンドを削除: {ext}",
        "en": "Viewer command removed: {ext}",
    },
    "archive_mode_preserve": {
        "ja": "アーカイブ内のディレクトリ構造を維持して展開",
        "en": "Preserve archive directory structure",
    },
    "archive_mode_flat": {
        "ja": "カレント(展開先)にフラット展開 (ファイル名のみ)",
        "en": "Extract flat into destination (basename only)",
    },
    "archive_mode_set": {
        "ja": "展開モード: {mode}",
        "en": "Extract mode: {mode}",
    },
    "config_path_msg": {
        "ja": "設定ファイル: {path}",
        "en": "Config file: {path}",
    },
    # panes / actions
    "switched_local": {
        "ja": "ローカルファイルシステムに切り替えました{note}",
        "en": "Switched to local filesystem{note}",
    },
    "switched_s3": {
        "ja": "S3 に切り替えました (profile={profile}){note}",
        "en": "Switched to S3 (profile={profile}){note}",
    },
    "places_root": {"ja": "PC", "en": "This PC"},
    "root_msg": {
        "ja": "ルート: {path}{note}",
        "en": "Root: {path}{note}",
    },
    "places_no_ops": {
        "ja": "PC 一覧では作成・削除・名前変更・コピーはできません。ドライブや場所を開いてください",
        "en": "Cannot copy, delete, rename, or mkdir on This PC — open a drive or place first",
    },
    "places_not_dest": {
        "ja": "コピー/移動先に PC 一覧は指定できません。ドライブや場所を開いてください",
        "en": "This PC is not a destination — open a drive or place first",
    },
    "refreshed": {"ja": "再読込しました", "en": "Refreshed"},
    "refreshed_note": {"ja": "再読込 — {note}", "en": "Refreshed — {note}"},
    "goto_msg": {"ja": "移動: {path}{note}", "en": "Go to {path}{note}"},
    "goto_title": {"ja": "パス指定", "en": "Go to path"},
    "goto_prompt": {
        "ja": "ローカルパス、thispc:、UNC、または s3://bucket/prefix",
        "en": "Local path, thispc:, UNC, or s3://bucket/prefix",
    },
    "profile_set": {
        "ja": "AWS プロファイル: {name}{note}",
        "en": "AWS profile: {name}{note}",
    },
    "profile_error": {"ja": "プロファイルエラー: {err}", "en": "Profile error: {err}"},
    "theme_set": {
        "ja": "テーマ: {name}  ({path})",
        "en": "Theme: {name}  ({path})",
    },
    "theme_unchanged": {"ja": "テーマは変更しませんでした", "en": "Theme unchanged"},
    "theme_error": {"ja": "テーマエラー: {err}", "en": "Theme error: {err}"},
    "nothing_selected": {"ja": "何も選択されていません", "en": "Nothing selected"},
    "nothing_selected_op": {
        "ja": "{op} する項目が選択されていません",
        "en": "Nothing selected to {op}",
    },
    "nothing_to_rename": {"ja": "名前変更する項目がありません", "en": "Nothing to rename"},
    "nothing_to_delete": {"ja": "削除する項目がありません", "en": "Nothing to delete"},
    "select_file_view": {
        "ja": "表示するファイルを選択してください",
        "en": "Select a file to view",
    },
    "select_file_exec": {
        "ja": "実行するファイルを選択してください",
        "en": "Select a file to execute",
    },
    "select_archive": {
        "ja": "アーカイブファイルを選択してください",
        "en": "Select an archive file",
    },
    "not_archive": {
        "ja": "対応していないアーカイブです: {name}",
        "en": "Not a known archive: {name}",
    },
    "view_failed": {"ja": "表示に失敗: {err}", "en": "View failed: {err}"},
    "viewer_toggle_table": {
        "ja": "表/テキスト",
        "en": "Table/Raw",
    },
    "viewer_find_placeholder": {
        "ja": "/ 検索   n/N 次/前   Esc",
        "en": "/ find   n/N next/prev   Esc",
    },
    "sixel_loading": {
        "ja": "画像を SIXEL で表示しています: {name}",
        "en": "Showing image via SIXEL: {name}",
    },
    "sixel_done": {
        "ja": "SIXEL 表示終了 — {msg}",
        "en": "SIXEL view closed — {msg}",
    },
    "sixel_view_fail": {
        "ja": "SIXEL 表示に失敗: {err} — テキスト表示に切替",
        "en": "SIXEL view failed: {err} — falling back to text view",
    },
    "sixel_need_pillow": {
        "ja": "この Python に Pillow がありません。次を実行: {cmd}",
        "en": "Pillow missing for this Python. Run: {cmd}",
    },
    "info_failed": {"ja": "情報取得に失敗: {err}", "en": "Info failed: {err}"},
    "exec_cancelled": {"ja": "実行をキャンセルしました", "en": "Execute cancelled"},
    "exec_failed": {"ja": "実行に失敗: {err}", "en": "Execute failed: {err}"},
    "exec_confirm_title": {"ja": "実行", "en": "Execute"},
    "exec_confirm": {"ja": "'{name}' を実行しますか？", "en": "Run '{name}'?"},
    "cmd_failed": {"ja": "コマンド失敗: {err}", "en": "Command failed: {err}"},
    "run_cmd_title": {"ja": "コマンド実行", "en": "Run command"},
    "run_cmd_prompt": {
        "ja": "ファイル: {files}\n{{}} がファイル一覧に置換。省略時は末尾に追加。\n例: python {{}}   |   code -r\n(対話シェル: o / Ctrl+O)",
        "en": "Files: {files}\nUse {{}} for file list, or paths are appended.\nExample: python {{}}   |   code -r\n(Interactive shell: press o / Ctrl+O)",
    },
    "archive_open_failed": {
        "ja": "アーカイブを開けません: {err}",
        "en": "Open archive failed: {err}",
    },
    "rename_title": {"ja": "名前変更", "en": "Rename"},
    "rename_prompt": {
        "ja": "'{name}' の新しい名前:",
        "en": "Rename '{name}' to:",
    },
    "delete_title": {"ja": "削除", "en": "Delete"},
    "delete_confirm": {
        "ja": "{n} 件を削除しますか？\n{names}",
        "en": "Delete {n} item(s)?\n{names}",
    },
    "subshell_failed": {"ja": "サブシェル失敗: {err}", "en": "Subshell failed: {err}"},
    "invalid_dest": {"ja": "不正な移動先: {err}", "en": "Invalid destination: {err}"},
    "transfer_hint": {
        "ja": "{op}: Enter=開く, h/Bksp=親, Tab=Local/S3, /=絞込, s/g=確定",
        "en": "{op}: Enter=open dir, h/Bksp=parent, Tab=Local/S3, /=filter, s/g=confirm",
    },
    "transfer_browse_title": {
        "ja": "{op} — 移動先を選択  ({n} 件{more})",
        "en": "{op} — browse destination  ({n} item(s){more})",
    },
    "transfer_confirm": {
        "ja": "{op} {n} 件 →\n{dest}\n\n{names}",
        "en": "{op} {n} item(s) →\n{dest}\n\n{names}",
    },
    "transfer_confirm_btn": {
        "ja": "s/g: ここにコピー/移動",
        "en": "s/g: copy/move HERE",
    },
    "more_items": {"ja": " (+{n} 件)", "en": " (+{n} more)"},
    "mkdir_local_title": {"ja": "ディレクトリ作成", "en": "Make directory"},
    "mkdir_s3_title": {
        "ja": "S3 プレフィックス (ディレクトリ) 作成",
        "en": "Make S3 prefix (directory)",
    },
    "mkdir_local_prompt": {
        "ja": "新しいフォルダ名 (入れ子可: a/b/c):",
        "en": "New folder name (nested ok: a/b/c):",
    },
    "mkdir_s3_prompt": {
        "ja": "新しいプレフィックス名 (入れ子可: logs/2026):",
        "en": "New prefix name (nested ok: logs/2026):",
    },
    "mkdir_open_bucket": {
        "ja": "先にバケットを開いてからプレフィックスを作成してください (F7/n)",
        "en": "Open a bucket first, then create a prefix (F7/n)",
    },
    "copy": {"ja": "コピー", "en": "Copy"},
    "move": {"ja": "移動", "en": "Move"},
    "delete": {"ja": "削除", "en": "Delete"},
    "cancelled": {"ja": "{op} をキャンセルしました", "en": "{op} cancelled"},
    "subshell_banner": {
        "ja": "=== S3 Filer サブシェル ===\nshell : {shell}\ncwd   : {cwd}\nleft  : {left}\nright : {right}\nexit または Ctrl+D でファイラーに戻ります。\n=========================\n\n",
        "en": "=== S3 Filer subshell ===\nshell : {shell}\ncwd   : {cwd}\nleft  : {left}\nright : {right}\nType 'exit' (or Ctrl+D) to return to S3 Filer.\n=========================\n\n",
    },
    "subshell_msg": {
        "ja": "サブシェル: {shell}  (cwd={cwd})  — 終了すると戻ります",
        "en": "Subshell: {shell}  (cwd={cwd})  — exit shell to return",
    },
    "archive_open_msg": {
        "ja": "アーカイブ: {name}  (展開先 → {dest})",
        "en": "Archive: {name}  (extract → {dest})",
    },
    "archive_closed": {"ja": "アーカイブを閉じました", "en": "Archive closed"},
    "extract_nothing": {
        "ja": "展開するファイルがありません (Space で選択、またはファイルをハイライト)",
        "en": "Nothing to extract (Space to select, or highlight a file)",
    },
    "extract_progress": {
        "ja": "展開中: {name}",
        "en": "Extracting: {name}",
    },
    "extract_done_item": {"ja": "完了: {name}", "en": "Done: {name}"},
    "extract_result": {
        "ja": "展開 {done}/{total} 件 → {dest}",
        "en": "Extracted {done}/{total} → {dest}",
    },
    "extract_failed": {
        "ja": "展開失敗 ({n} エラー) → {dest}",
        "en": "Extract FAILED ({n} error(s)) → {dest}",
    },
    "progress_copy": {"ja": "コピー {n} 件", "en": "Copy {n} item(s)"},
    "progress_move": {"ja": "移動 {n} 件", "en": "Move {n} item(s)"},
    "progress_delete": {"ja": "削除 {n} 件", "en": "Delete {n} item(s)"},
    "please_wait_hint": {"ja": "処理中です…", "en": "Working…"},
}


_lang_override: Optional[str] = None


def set_runtime_language(lang: Optional[str]) -> None:
    """Override language for the current process (None = use config)."""
    global _lang_override
    if lang is None:
        _lang_override = None
    else:
        _lang_override = "en" if str(lang).lower().startswith("en") else "ja"


def current_language() -> str:
    if _lang_override:
        return _lang_override
    return cfg.get_language()


def t(key: str, **kwargs: Any) -> str:
    """Translate message key to the active language."""
    lang = current_language()
    entry = _MSG.get(key) or {}
    text = entry.get(lang) or entry.get("en") or entry.get("ja") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
