"""Shared help / keybinding text for the in-app Help screen (JA / EN)."""

from __future__ import annotations

from .i18n import current_language

HELP_TEXT_EN = """\
S3 Filer — key bindings (FD / FILMTN style)
==========================================

Navigation (Vim-style + arrows)
  h / ←                Focus left pane
  l / →                Focus right pane
  j / ↓                Move cursor down
  k / ↑                Move cursor up
  Tab                  Toggle active pane
  PgUp / PgDn          Page cursor in list
  Enter                Open directory / View file
  Backspace            Go to parent directory
  Space / Insert       Toggle multi-select (* mark)
  *                    Select all files (not dirs)
  Ctrl+A               Select all / clear selection

Operations (letter key  OR  function key)
  c / F5               Copy  → other pane
  C (Shift+c)          Copy  → browse destination (see Dest browser)
  m / F6               Move  → other pane
  M (Shift+m)          Move  → browse destination
  v / F3               View file contents (syntax highlight)
                       Images: SIXEL when the terminal supports it
  e (in View)          Open in external editor (EDITOR/VISUAL)
                       Local: edit in place  |  S3: download → edit → upload
  i / F4               File info (size, encoding, …)
  r / F2               Rename
  n / F7               Make directory / S3 prefix (nested: a/b)
  d / F8               Delete
  !                    Run command with selected files as args
  x                    Execute selected file/script
  a                    Open archive browser (zip/tar/…)
                       (Enter on archive also opens it)
  p / F9               AWS profile
  u                    Settings (language, theme, viewer, archive, config file)
  t / F10              Browse path and jump (same UI as C/M dest)
  g / Ctrl+G           Go to path or s3:// URI
  f / Ctrl+R           Refresh listing
  Ctrl+L               Switch active pane to Local
  s / Ctrl+S           Switch active pane to S3
  F1 / ?               This help
  q / Esc              Quit (with confirm)

Help / View scroll
  j k / ↑ ↓            Line scroll
  Space / PgDn         Page down
  b / PgUp             Page up
  Home / End           Top / bottom
  e                    Edit with $EDITOR / $VISUAL (then reload View)
  Esc / q              Close

Editor
  • Uses VISUAL, then EDITOR, then OS default (notepad / nano / vim).
  • S3 objects: temp download, edit, upload only if the file changed.
  • S3 edit size limit: 50 MiB.

Themes (Settings → u)
  classic-blue, norton-cyan, amber-crt, matrix-green,
  midnight, solarized-dark, light, monochrome
  Saved under the user config file (see README).

Destination browser (C / M / t)
  Enter / l            Open directory under cursor
  h / Backspace        Parent directory (..)
  j k / ↑ ↓            Move cursor
  1 / Local button     Switch to local filesystem
  2 / S3 button        Switch to S3 (s3:// or last S3 path)
  Tab                  Toggle Local ↔ S3 (when available)
  Ctrl+L / Ctrl+S      Same as 1 / 2
  /                    Focus filter (incremental search)
  s / g                Confirm *current* folder (start copy/move/jump)
  Esc                  Clear filter / cancel

Run / Archive / Shell
  ! command            {} = file list; otherwise paths are appended
  x                    Run .sh/.bat/.ps1/.py/.exe (S3: download temp)
  o / Ctrl+O           Temporary interactive subshell (exit to return)
                       cwd = active local pane (or other local / process cwd)
                       env: S3FILER_LEFT, S3FILER_RIGHT, S3FILER_ACTIVE, S3FILER_CWD
                       shell: $SHELL / COMSPEC, or override with $S3FILER_SHELL
  a / Enter on zip     List archive · Spc select · x/e extract · a all · v view
                       Extract goes to the *other* local pane when possible
  Copy/Move/Delete     Progress dialog shows n/N; status bar shows result

Notes
  • c/m copy/move to the opposite pane (classic dual-pane).
  • C/M open the destination browser (not a full expanded tree).
  • n/F7 creates local dirs and S3 prefixes (open a bucket first on S3).
  • Multi-select with Space, then c / m / d / C / M / !.
  • Launch: ./sss (bash)  ·  .\\sss.ps1 (PowerShell)  ·  .\\sss.cmd (cmd)
  • Settings (u): language, theme, external viewers, archive extract mode
"""

HELP_TEXT_JA = """\
S3 Filer — キー操作一覧 (FD / FILMTN 風)
========================================

移動 (Vim 風 + 矢印)
  h / ←                左ペインへフォーカス
  l / →                右ペインへフォーカス
  j / ↓                カーソル下へ
  k / ↑                カーソル上へ
  Tab                  アクティブペイン切替
  PgUp / PgDn          リストをページ単位で移動
  Enter                ディレクトリを開く / ファイルを表示
  Backspace            親ディレクトリへ
  Space / Insert       複数選択の切替 (* マーク)
  *                    ファイルを全選択 (ディレクトリ除く)
  Ctrl+A               全選択 / 選択解除

操作 (文字キー または ファンクションキー)
  c / F5               コピー → 反対ペイン
  C (Shift+c)          コピー → 移動先をブラウズ (移動先ブラウザ)
  m / F6               移動 → 反対ペイン
  M (Shift+m)          移動 → 移動先をブラウズ
  v / F3               ファイル内容を表示 (シンタックスハイライト)
                       画像: 端末が対応していれば SIXEL で表示
  e (表示中)           外部エディタで開く (EDITOR/VISUAL)
                       ローカル: 直接編集  |  S3: ダウンロード → 編集 → アップロード
  i / F4               ファイル情報 (サイズ、文字コード など)
  r / F2               名前変更
  n / F7               ディレクトリ / S3 プレフィックス作成 (入れ子: a/b)
  d / F8               削除
  !                    選択ファイルを引数にコマンド実行
  x                    選択ファイル / スクリプトを実行
  a                    アーカイブブラウザ (zip/tar/…)
                       (アーカイブ上で Enter でも開く)
  p / F9               AWS プロファイル
  u                    設定 (言語・テーマ・ビューア・アーカイブ・設定ファイル)
  t / F10              パス閲覧・ジャンプ (C/M の移動先と同じ UI)
  g / Ctrl+G           パスまたは s3:// URI へ直接移動
  f / Ctrl+R           一覧を再読込
  Ctrl+L               アクティブペインをローカルへ
  s / Ctrl+S           アクティブペインを S3 へ
  F1 / ?               このヘルプ
  q / Esc              終了 (確認あり)

ヘルプ / 表示画面のスクロール
  j k / ↑ ↓            1 行スクロール
  Space / PgDn         ページ下
  b / PgUp             ページ上
  Home / End           先頭 / 末尾
  e                    $EDITOR / $VISUAL で編集 (表示を再読込)
  Esc / q              閉じる

エディタ
  • VISUAL → EDITOR → OS 既定 (notepad / nano / vim) の順で使用
  • S3 オブジェクト: 一時ダウンロード → 編集 → 変更時のみアップロード
  • S3 編集サイズ上限: 50 MiB

テーマ (設定 → u)
  classic-blue, norton-cyan, amber-crt, matrix-green,
  midnight, solarized-dark, light, monochrome
  ユーザー設定ファイルに保存 (README 参照)

移動先ブラウザ (C / M / t)
  Enter / l            カーソル下のディレクトリを開く
  h / Backspace        親ディレクトリ (..)
  j k / ↑ ↓            カーソル移動
  1 / Local ボタン     ローカルファイルシステムへ
  2 / S3 ボタン        S3 へ (s3:// または直前の S3 パス)
  Tab                  Local ↔ S3 切替 (可能なとき)
  Ctrl+L / Ctrl+S      1 / 2 と同じ
  /                    絞り込み入力 (インクリメンタル検索)
  s / g                *現在* のフォルダを確定 (コピー/移動/ジャンプ開始)
  Esc                  絞り込み解除 / キャンセル

実行 / アーカイブ / シェル
  ! コマンド           {} = ファイル一覧。省略時は末尾にパスを追加
  x                    .sh/.bat/.ps1/.py/.exe を実行 (S3 は一時ダウンロード)
  o / Ctrl+O           一時インタラクティブサブシェル (exit で戻る)
                       cwd = アクティブなローカルペイン (なければ反対側 / プロセス cwd)
                       環境変数: S3FILER_LEFT, S3FILER_RIGHT, S3FILER_ACTIVE, S3FILER_CWD
                       シェル: $SHELL / COMSPEC、または $S3FILER_SHELL で上書き
  a / zip 上で Enter   アーカイブ一覧 · Spc 選択 · x/e 展開 · a 全選択 · v 表示
                       展開先は可能な限り *反対側のローカルペイン*
  コピー/移動/削除     進捗ダイアログで n/N、結果はステータスバー

メモ
  • c/m は反対ペインへコピー/移動 (クラシック二画面)
  • C/M は移動先ブラウザ (全展開ツリーではない)
  • n/F7 はローカルディレクトリと S3 プレフィックスを作成 (S3 は先にバケットを開く)
  • Space で複数選択してから c / m / d / C / M / !
  • 起動: ./sss (bash)  ·  .\\sss.ps1 (PowerShell)  ·  .\\sss.cmd (cmd)
  • 設定 (u): 言語・テーマ・外部ビューア・アーカイブ展開モード
"""

# Back-compat alias (English)
HELP_TEXT = HELP_TEXT_EN


def get_help_text(lang: str | None = None) -> str:
    """Return help body for the active (or given) UI language."""
    if lang is None:
        lang = current_language()
    return HELP_TEXT_JA if str(lang).lower().startswith("ja") else HELP_TEXT_EN
