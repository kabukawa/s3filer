# S3 Filer (`sss`)

ローカルと Amazon S3 を扱う **2ペイン型コンソール・ファイラー**です。  
起動コマンドは **`sss`**（s が 3 つ = S3）です。

> 使い方・機能詳細・トラブルシュートは **[MANUAL.md](MANUAL.md)**（日本語・メイン）を参照してください。  
> English: [README.en.md](README.en.md) · [MANUAL.en.md](MANUAL.en.md)

## 主な機能

- **2 ペイン**でローカル / S3 を同時にブラウズ（FD / FILMTN 風のキー操作）
- コピー / 移動 / 削除 / 改名・ディレクトリ作成
- **View**（テキストのシンタックスハイライト、画像は **SIXEL** 対応端末で表示）
- 拡張子ごとの **外部ビューア**（バックグラウンド起動、ファイラー画面を維持）
- 外部エディタ（`$VISUAL` / `$EDITOR`）、アーカイブ、コマンド実行、サブシェル
- 設定画面（**u**）: 言語・テーマ・ビューア・アーカイブ・**SIXEL**・設定ファイル編集
- UI **日本語 / English** 切替（ヘルプ本文も言語に連動）
- 親プロセスのシェルを引き継いだサブシェル / 外部コマンド（Git Bash ではパスを `/c/...` 形式に変換）

## 必要環境

- Python **3.10+**
- 依存パッケージ: `boto3`, `textual`, `rich`, `chardet`, **`pillow`**（画像 SIXEL 表示用）
- AWS 認証（`~/.aws` または環境変数 / SSO）
- ターミナル（**Windows Terminal** / WezTerm / Git Bash / Linux / macOS など）

## インストール

```bash
# リポジトリ直下
python3 -m venv .venv          # Windows: python -m venv .venv

# 仮想環境の有効化
# Linux / macOS / WSL:
source .venv/bin/activate
# Windows Git Bash:
source .venv/Scripts/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

venv は必須ではありません。`sss` は `.venv` があればそれを使い、なければ PATH の Python を使います。  
未導入時は依存関係の自動インストールを試みます（**Pillow も含む**）。

> 画像表示で「Pillow が必要」と出る場合は、**s3filer を動かしている同じ Python** に入れてください。  
> `pip3` ではなく例: `python -m pip install pillow`（メッセージに出るパスを推奨）

## 起動

| 環境 | コマンド |
|------|----------|
| Linux / macOS / WSL / Git Bash | `./sss` |
| **Windows PowerShell** | **`.\sss.ps1`** |
| Windows cmd | `sss.cmd` または `sss` |

> **PowerShell では `.\sss` は使えません。**  
> 拡張子なしの `sss` は bash 用スクリプトのため、PowerShell からは **`.\sss.ps1`** を実行してください。  
> （`.\sss.cmd` でも起動できます。）

```bash
# Git Bash / Linux / macOS
./sss -p myprofile
./sss -l . -r s3://my-bucket/
./sss --list-themes
```

```powershell
# Windows PowerShell / PowerShell 7+
.\sss.ps1
.\sss.ps1 -p myprofile
.\sss.ps1 -Left . -Right s3://
.\sss.ps1 --version
```

```bat
REM Windows cmd
sss.cmd -p myprofile
```

旧名 `s3fd` / `s3fd.cmd` も互換ラッパーとして残しています（内部で `sss` を呼びます）。

### 主なオプション

| オプション | 説明 |
|------------|------|
| `-p` / `--profile` | AWS CLI プロファイル |
| `--region` | リージョン |
| `-l` / `--left` | 左ペイン初期パス |
| `-r` / `--right` | 右ペイン初期パス |
| `--theme NAME` | テーマ（セッション） |
| `--theme NAME --save-theme` | テーマを設定ファイルに保存 |
| `--list-themes` | テーマ一覧 |
| `--version` | バージョン |

## 設定ファイル

| OS | パス |
|----|------|
| Windows | `%APPDATA%\s3filer\config.json` |
| Linux / macOS / WSL | `~/.config/s3filer/config.json` |

アプリ内 **`u`** キーで設定画面を開けます。

| 項目 | 内容 |
|------|------|
| 言語 | 日本語 / English |
| カラーテーマ | 配色（設定から変更。タイトルバーにテーマキーは出しません） |
| ファイル表示 | 組み込み / 外部コマンド優先 |
| 外部ビューアコマンド一覧 | 拡張子ごとのコマンドの追加・編集・削除 |
| アーカイブ展開 | 構造維持 / フラット |
| **SIXEL 画像表示** | 自動 / 強制 ON / 強制 OFF |
| 設定ファイルをエディタで開く | `config.json` を直接編集して再読込 |

主なキー例:

```json
{
  "theme": "midnight",
  "language": "ja",
  "viewer_mode": "external_prefer",
  "viewer_commands": { ".pdf": "cmd /c start \"\" {}" },
  "archive_extract_mode": "preserve",
  "sixel_mode": "auto"
}
```

環境変数の上書き例: `S3FILER_LANG`, `S3FILER_THEME`, `S3FILER_SIXEL`（`1`/`0`）, `S3FILER_SHELL`

## ドキュメント

| ファイル | 内容 |
|----------|------|
| **[MANUAL.md](MANUAL.md)** | 使い方・機能詳細・注意点・エラー対応（**日本語メイン**） |
| [MANUAL.en.md](MANUAL.en.md) | English manual |
| [README.en.md](README.en.md) | English install overview |

## ライセンス

MIT
