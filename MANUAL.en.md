# S3 Filer User Manual (English)

Launcher: **`sss`** (three s’s ≈ S3)  
Install steps: [README.en.md](README.en.md). Japanese primary manual: [MANUAL.md](MANUAL.md).

---

## 1. Overview

S3 Filer is a **dual-pane TUI file manager** inspired by classic FD/FILMTN tools.

- Browse **local** and **S3** side by side
- Copy / move / delete / rename / view / edit / archives / commands / subshell
- **SIXEL image view**, per-extension external viewers, Japanese / English UI
- Settings persist in a user config file

---

## 2. Start & quit

```bash
# Git Bash / Linux / macOS
./sss -p myprofile
```

```powershell
# Windows PowerShell (do not use .\sss — that file is bash-only)
.\sss.ps1
.\sss.ps1 -p myprofile
```

```bat
REM Windows cmd
sss.cmd -p myprofile
```

| Key | Action |
|-----|--------|
| **q** / **Esc** | Quit (confirm) |
| **F1** / **?** | In-app help (**follows UI language**) |
| **u** | **Settings** |

---

## 3. Screen & navigation

- **Title bar**: version, AWS profile, region (no theme name / F1·u hints)
- **Panes**: headers “Left” / “Right” (or 左 / 右); `*` multi-select
- **Message line**: results and warnings
- **Function bar**: key summary (theme key is not listed; change theme under **u**)

### Vim-style navigation

| Key | Action |
|-----|--------|
| **h** / ← | Left pane |
| **l** / → | Right pane |
| **j** / ↓ | Cursor down |
| **k** / ↑ | Cursor up |
| **Tab** | Switch pane |
| **Enter** | Open dir / run executable / open archive / else View |
| **Backspace** | Parent |
| **Space** | Multi-select |

### Common operations

| Key | Action |
|-----|--------|
| **c** / F5 | Copy → other pane |
| **C** | Copy → destination browser |
| **m** / F6 | Move → other pane |
| **M** | Move → destination browser |
| **v** / F3 | View (SIXEL for images when enabled) |
| **e** (in View) | External editor |
| **n** / F7 | Mkdir / S3 prefix |
| **d** / F8 | Delete |
| **!** | Command with selected files |
| **x** | Execute file/script |
| **a** | Open archive |
| **o** / **Ctrl+O** | Temporary subshell (inherits parent shell) |
| **p** / F9 | AWS profile |
| **t** / F10 | Browse & jump |
| **u** | Settings |
| **g** | Go to path |
| **Ctrl+L** / **s** | Local / S3 |
| **f** | Refresh |

---

## 4. Settings (`u`)

Saved to:

| OS | Path |
|----|------|
| Windows | `%APPDATA%\s3filer\config.json` |
| Linux / macOS / WSL | `~/.config/s3filer/config.json` |

### Language

Japanese / English UI messages, settings UI, **help body**, and function bar.  
Override: `S3FILER_LANG=en`.

### Theme

App colors + View syntax theme pairing. Also: `./sss --theme NAME --save-theme`.  
Change theme from Settings (not a dedicated status-bar key).

### File viewer

| Mode | Behavior |
|------|----------|
| **Built-in** | Text with highlight; images via SIXEL when enabled; else HEX/etc. |
| **External prefer** | Per-extension command when configured; else built-in |

#### External viewer commands

Manage under **External viewer commands** (list / add / edit / delete):

- `{}` = file path (otherwise paths are appended)
- Registered extensions always use that command on **v**
- Launched **in the background** (filer stays visible; status on the message line)
- Paths are converted for the parent shell (e.g. Git Bash `/c/...`)
- Windows `.CMD` wrappers (e.g. `mdview`) resolve via the user shell

You can also **open `config.json` in an editor** from Settings (reload after save).

### Archive extract

| Mode | Behavior |
|------|----------|
| **preserve** | Keep internal folders under the destination |
| **flat** | Write basenames only into the destination (suffix if collision) |

Destination defaults to the **other local pane** when possible.

### SIXEL image view

Controls whether View (**v**) shows images with **terminal SIXEL** graphics.

| Option | Behavior |
|--------|----------|
| **Auto** (default) | Enable when the terminal looks SIXEL-capable |
| **Force ON** | Try SIXEL whenever possible |
| **Force OFF** | Always use text/HEX-style built-in view |

- Examples: **Windows Terminal** (recent), WezTerm, mintty, mlterm, foot, Contour  
- Env override (wins over config): `S3FILER_SIXEL=1` / `0`  
- Requires **Pillow** (`requirements.txt`; launcher may install into the running interpreter)  
- Temporarily leaves the TUI; **any key** returns to the filer  
- Sized to the terminal with **preserved aspect ratio** and **1:1 pixel** raster attributes  

Config key: `"sixel_mode": "auto" | "on" | "off"`

---

## 5. Destination browser (`C` / `M` / `t`)

Lists **one directory level** at a time (not a full expanded tree).

| Key | Action |
|-----|--------|
| Enter / l | Open directory |
| h / Backspace | Parent |
| 1 / 2 | Local / S3 |
| / | Filter |
| **s** / **g** | Confirm **current** folder |
| Esc | Cancel |

---

## 6. View / edit / run / shell

### View (`v` / F3)

Rough priority:

1. Per-extension **external viewer** if registered → background external app  
2. Image + SIXEL enabled → **SIXEL fullscreen**  
3. Else → built-in text / binary  

- **e** in View: `$VISUAL` / `$EDITOR`; S3 download → upload if changed  
- Text view reads the first ~512 KiB; SIXEL images allow larger payloads (capped)

### Command (`!`)

- Run with selected files via the user shell  
- `{}` = file list; otherwise paths are appended  
- Paths are quoted / converted for Git Bash, PowerShell, cmd, etc.

### Execute (`x`)

- Scripts/binaries after confirm; TUI suspends for the run  

### Subshell (`o` / Ctrl+O)

- Interactive shell until `exit`  
- cwd prefers the active local pane  
- **Inherits the parent process shell** (e.g. pwsh if launched from PowerShell)  
- Override: `S3FILER_SHELL`  
- Env: `S3FILER_LEFT` / `RIGHT` / `ACTIVE` / `CWD` / `PROFILE`

---

## 7. Archives (`a`)

zip / tar / tar.gz / …  

Space select · **x/e** extract · **a** extract all · **v** view member.  
Progress dialog shows n/N; status bar + toast show the result.

---

## 8. Copy / move / delete

Progress dialog (`Copy 2/5: name`) + status bar + toast on completion.

---

## 9. Mkdir (`n` / F7)

- Local: nested paths `a/b/c` allowed  
- S3: folder marker keys; open a bucket first (not at bare `s3://`)

---

## 10. Recovery when a path vanishes

If a local folder was deleted or a profile no longer sees a bucket/prefix, the app walks up to a valid parent or falls back to cwd / `s3://`.

Manual: **f** refresh · **Ctrl+L** · **s** · **g**

---

## 11. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| S3 auth / ExpiredToken | `aws sso login --profile …` or update keys; switch profile **p** |
| Empty pane / stuck | **f**, **Ctrl+L**, **s**, **g** |
| Extract “not found” | Check extract path in status (other pane); use Space to select files |
| External viewer fails | Settings **u** → command + `{}`; PATH; under Git Bash check path form |
| Images open as binary dump | **u** → SIXEL force ON; use Windows Terminal / WezTerm; install Pillow for **this** Python |
| “Pillow required” | `python -m pip install pillow` (same interpreter as the app, not a random `pip3`) |
| Windows launch fails | PowerShell: **`.\sss.ps1`**; cmd: `.\sss.cmd` |
| `.\sss` fails in PowerShell | Extensionless `sss` is bash-only → **`.\sss.ps1`** |
| `python` not found (Ubuntu) | Use `python3` or `./sss` |

---

## 12. Cautions

- Buckets are not deleted by this tool  
- View/edit/run of large S3 objects uses temp downloads with size limits  
- Be careful on production accounts  

---

## 13. Related files

| File | Role |
|------|------|
| `sss` / `sss.ps1` / `sss.cmd` | Unified launchers |
| `s3filer/` | Package (`sixel_view.py`, settings, …) |
| `config.json` | theme, language, viewers, archive mode, `sixel_mode`, … |

---

## License

MIT
