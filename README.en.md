# S3 Filer (`sss`)

A **dual-pane console file manager** for local files and Amazon S3.  
The launcher command is **`sss`** (three s’s ≈ S3).

> Full usage, feature details, and troubleshooting: **[MANUAL.en.md](MANUAL.en.md)**.  
> Changelog: **[HISTORY.md](HISTORY.md)** (Japanese).  
> Japanese (primary docs): [README.md](README.md) · [MANUAL.md](MANUAL.md)

## Highlights

- **Dual panes** for local / S3 (FD/FILMTN-style keys)
- Copy / move / delete / rename / mkdir
- **Windows**: `\` switches drives and places (`C:`, Box / OneDrive, WSL `\\wsl.localhost\…`)
- **View**: syntax-highlighted text, **CSV/TSV tables**, **`/` find**, **SIXEL** images on capable terminals
- Per-extension **external viewers** (run in the background; filer UI stays up)
- External editor (`$VISUAL` / `$EDITOR`), archives, shell commands, subshell
- Settings (**u**): language, theme, viewers, archive extract, **SIXEL**, edit config file
- UI language **Japanese / English** (help text follows the language too)
- Subshell / external commands inherit the **parent shell**; Git Bash gets paths as `/c/...`

## Requirements

- Python **3.10+**
- Dependencies: `boto3`, `textual`, `rich`, `chardet`, **`pillow`** (SIXEL images)
- AWS credentials (`~/.aws` or env / SSO)
- A terminal (**Windows Terminal**, WezTerm, Git Bash, Linux, macOS, …)

## Install

```bash
python3 -m venv .venv          # Windows: python -m venv .venv

# Activate
# Linux / macOS / WSL:
source .venv/bin/activate
# Windows Git Bash:
source .venv/Scripts/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

A venv is optional. The `sss` launcher prefers `.venv` when present, otherwise uses Python on `PATH`. An empty project `.venv` is auto-installed; launchers no longer spawn extra Python processes on every start. Pillow is prompted for when viewing an image.

> If the app says Pillow is missing, install it for the **same Python that runs s3filer**:  
> prefer `python -m pip install pillow` (not a different `pip3`).

## Launch

| Environment | Command |
|-------------|---------|
| Linux / macOS / WSL / Git Bash | `./sss` |
| **Windows PowerShell** | **`.\sss.ps1`** |
| Windows cmd | `sss.cmd` or `sss` |

> **PowerShell cannot run `.\sss`.**  
> The extensionless `sss` file is a bash script. From PowerShell use **`.\sss.ps1`**  
> (or `.\sss.cmd`).

```bash
# Git Bash / Linux / macOS
./sss -p myprofile
./sss -l . -r s3://my-bucket/
```

```powershell
# Windows PowerShell / PowerShell 7+
.\sss.ps1
.\sss.ps1 -p myprofile
.\sss.ps1 --version
```

```bat
REM Windows cmd
sss.cmd -p myprofile
```

Legacy `s3fd` / `s3fd.cmd` wrappers remain as aliases to `sss`.

### Common options

| Option | Description |
|--------|-------------|
| `-p` / `--profile` | AWS CLI profile |
| `--region` | Region |
| `-l` / `--left` | Left pane start path |
| `-r` / `--right` | Right pane start path |
| `--theme NAME` | Theme for this session |
| `--theme NAME --save-theme` | Persist theme |
| `--list-themes` | List themes |
| `--version` | Version |

## Config file

| OS | Path |
|----|------|
| Windows | `%APPDATA%\s3filer\config.json` |
| Linux / macOS / WSL | `~/.config/s3filer/config.json` |

Press **`u`** in the app for Settings:

| Item | Purpose |
|------|---------|
| Language | Japanese / English |
| Color theme | UI palette (theme key is not shown on the title bar) |
| File viewer | Built-in vs prefer external by extension |
| External viewer commands | List / add / edit / delete per-extension commands |
| Archive extract | Preserve tree / flat |
| **SIXEL image view** | Auto / force ON / force OFF |
| Open config in editor | Edit `config.json` and reload |

Example keys:

```json
{
  "theme": "midnight",
  "language": "en",
  "viewer_mode": "external_prefer",
  "viewer_commands": { ".pdf": "xdg-open {}" },
  "archive_extract_mode": "preserve",
  "sixel_mode": "auto"
}
```

Env overrides: `S3FILER_LANG`, `S3FILER_THEME`, `S3FILER_SIXEL` (`1`/`0`), `S3FILER_SHELL`

## Docs

| File | Content |
|------|---------|
| **[MANUAL.en.md](MANUAL.en.md)** | Usage, features, cautions, troubleshooting |
| [MANUAL.md](MANUAL.md) | Japanese manual (primary) |
| [README.md](README.md) | Japanese install overview |

## License

MIT
