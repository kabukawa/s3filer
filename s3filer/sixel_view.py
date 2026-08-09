"""
SIXEL image display for terminals that support the DEC SIXEL graphics protocol.

View (v) uses this for common image types when:
  - the terminal is detected as SIXEL-capable (or S3FILER_SIXEL=1), and
  - Pillow can decode the image bytes.

Display path: suspend the TUI → write SIXEL to the real tty → wait for a key → resume.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
from typing import Optional

# Common raster formats Pillow handles well
IMAGE_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".ico",
        ".ppm",
        ".pgm",
        ".pbm",
        ".tga",
    }
)

# Max bytes to download/read for built-in image view
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def is_image_name(name: str) -> bool:
    lower = (name or "").lower()
    return any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS)


def _stream_isatty(stream) -> bool:
    try:
        return bool(stream is not None and stream.isatty())
    except Exception:
        return False


def _has_windows_console() -> bool:
    """True if this process is attached to a Windows console (conhost/WT)."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # STD_OUTPUT_HANDLE = -11
        h = kernel32.GetStdHandle(-11)
        if h is None or h == 0 or h == ctypes.c_void_p(-1).value:
            return False
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            return True
    except Exception:
        pass
    # Fallback: CONOUT$ openable
    try:
        with open("CONOUT$", "w", encoding="utf-8"):
            return True
    except Exception:
        return False


def _looks_like_interactive_terminal() -> bool:
    """
    Whether we appear to run under a real terminal.

    Textual wraps sys.stdout so ``sys.stdout.isatty()`` is often False even inside
    Windows Terminal / WezTerm. Prefer ``sys.__stdout__``, console APIs, and
    well-known terminal environment variables.
    """
    if _stream_isatty(sys.stdout):
        return True
    if _stream_isatty(getattr(sys, "__stdout__", None)):
        return True
    if _stream_isatty(getattr(sys, "__stderr__", None)):
        return True
    if _has_windows_console():
        return True
    # Known host markers (set even when Python stdout is redirected/wrapped)
    if os.environ.get("WT_SESSION") or os.environ.get("WT_PROFILE_ID"):
        return True
    if os.environ.get("WEZTERM_EXECUTABLE") or os.environ.get("WEZTERM_UNIX_SOCKET"):
        return True
    if os.environ.get("CONTOUR_VERSION") or os.environ.get("MLTERM"):
        return True
    term_program = (os.environ.get("TERM_PROGRAM") or "").lower()
    if term_program in ("wezterm", "contour", "mintty", "iterm.app", "vscode"):
        return True
    # Non-dumb TERM on POSIX
    term = (os.environ.get("TERM") or "").lower()
    if term and term not in ("dumb", "unknown") and os.name != "nt":
        return True
    return False


def supports_sixel() -> bool:
    """
    Whether built-in SIXEL image view should run.

    Precedence:
      1. Env ``S3FILER_SIXEL`` (session override: 1/0)
      2. Config ``sixel_mode``: ``on`` / ``off`` / ``auto`` (Settings UI)
      3. When auto: terminal capability heuristics
    """
    env = (os.environ.get("S3FILER_SIXEL") or "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    if env in ("1", "true", "yes", "on"):
        return True

    try:
        from .config import get_sixel_mode

        mode = get_sixel_mode()
    except Exception:
        mode = "auto"

    if mode == "off":
        return False
    if mode == "on":
        # User force-on: only skip pure non-interactive hosts (no console at all)
        return _looks_like_interactive_terminal()

    # auto — heuristic detection
    return _detect_sixel_terminal()


def _detect_sixel_terminal() -> bool:
    """Heuristic: known SIXEL-capable terminals (used when mode is auto)."""
    # Do NOT require sys.stdout.isatty() — Textual makes it False under WT/etc.
    if not _looks_like_interactive_terminal():
        return False

    term = (os.environ.get("TERM") or "").lower()
    term_program = (os.environ.get("TERM_PROGRAM") or "").lower()
    colorterm = (os.environ.get("COLORTERM") or "").lower()

    if "sixel" in term or "sixel" in colorterm:
        return True

    if term in ("mlterm", "yaft") or term.startswith("foot"):
        return True
    if "mlterm" in term or os.environ.get("MLTERM"):
        return True

    if term_program in ("wezterm", "contour", "mintty", "iterm.app"):
        return True
    if "mintty" in term_program:
        return True

    # Windows Terminal (recent builds include sixel) — primary case on Windows
    if os.environ.get("WT_SESSION") or os.environ.get("WT_PROFILE_ID"):
        return True

    if os.environ.get("CONTOUR_VERSION"):
        return True
    if os.environ.get("WEZTERM_EXECUTABLE") or os.environ.get("WEZTERM_UNIX_SOCKET"):
        return True

    # Windows + attached console: often WT/conhost; allow auto so force-on isn't required
    if os.name == "nt" and _has_windows_console():
        return True

    # Generic xterm: use Settings → SIXEL 強制ON, or S3FILER_SIXEL=1
    return False


def _tty_out():
    """
    Best stream for writing SIXEL after Textual ``suspend()``.

    Prefer the real console / original stdout over Textual's wrapper.
    """
    for stream in (
        getattr(sys, "__stdout__", None),
        sys.stdout,
    ):
        if stream is None:
            continue
        try:
            # Prefer real TTY; otherwise any writable stream with a fileno
            if _stream_isatty(stream):
                return stream
        except Exception:
            pass
    if os.name == "nt":
        try:
            # Direct console output (works when Python stdout is redirected)
            return open("CONOUT$", "w", encoding="utf-8", errors="replace")
        except Exception:
            pass
    return sys.stdout


_pillow_ok: Optional[bool] = None
_pillow_error: Optional[str] = None


def pillow_import_error() -> Optional[str]:
    """Last import error message from :func:`pillow_available` (if any)."""
    return _pillow_error


def pillow_available(*, force_recheck: bool = False) -> bool:
    """
    True if ``from PIL import Image`` works in *this* interpreter.

    Note: ``pip install pillow`` may target a different Python than the one
    running s3filer — always install with::

        python -m pip install pillow
    where ``python`` is the same executable as ``sys.executable``.
    """
    global _pillow_ok, _pillow_error
    if _pillow_ok is not None and not force_recheck:
        return _pillow_ok
    try:
        from PIL import Image  # noqa: F401

        _pillow_ok = True
        _pillow_error = None
        return True
    except Exception as e:
        _pillow_ok = False
        _pillow_error = f"{type(e).__name__}: {e}"
        return False


def ensure_pillow() -> bool:
    """
    Ensure Pillow is importable; if missing, try ``python -m pip install pillow``
    once into the current interpreter. Returns True on success.
    """
    if pillow_available(force_recheck=True):
        return True
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pillow>=10.0.0"],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except Exception as e:
        global _pillow_error
        _pillow_error = f"pip install failed: {e}"
        return False
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        _pillow_error = err[-400:] if err else f"pip exit {proc.returncode}"
        return False
    return pillow_available(force_recheck=True)


def pillow_install_hint() -> str:
    """Human-readable install command for the running interpreter."""
    return f'"{sys.executable}" -m pip install pillow'


# Preview defaults: large enough for WT / WezTerm, still fast with optimized encoder.
_DEFAULT_MAX_COLORS = 32
# Soft performance caps (actual size is min(terminal, these))
_SOFT_MAX_WIDTH = 1600
_SOFT_MAX_HEIGHT = 1000


def _terminal_pixel_budget() -> tuple[int, int]:
    """
    Estimate max sixel pixel size that fits the terminal.

    Uses ~square device pixels. Character cell ≈ 10×20 px is a common WT/font
    approximation; we leave margin for the caption lines.
    """
    cols, rows = shutil.get_terminal_size((120, 40))
    # Slightly aggressive so images fill most of the window
    cell_w, cell_h = 10, 20
    max_w = max(160, (cols - 2) * cell_w)
    max_h = max(100, (rows - 5) * cell_h)
    return (
        min(max_w, _SOFT_MAX_WIDTH),
        min(max_h, _SOFT_MAX_HEIGHT),
    )


def encode_image_to_sixel(
    data: bytes,
    *,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    max_colors: int = _DEFAULT_MAX_COLORS,
) -> tuple[str, dict]:
    """
    Decode image bytes and return (sixel_payload_including_DCS, meta_dict).

    Preserves aspect ratio; emits 1:1 pixel aspect raster attributes so terminals
    (Windows Terminal, WezTerm, …) do not squash/stretch the image.
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Pillow is required for SIXEL image view. Install with: pip install pillow"
        ) from e

    budget_w, budget_h = _terminal_pixel_budget()
    if max_width is None:
        max_width = budget_w
    if max_height is None:
        max_height = budget_h

    max_colors = max(2, min(64, int(max_colors)))

    with Image.open(io.BytesIO(data)) as im:
        if getattr(im, "is_animated", False):
            try:
                im.seek(0)
            except Exception:
                pass

        orig_w, orig_h = im.size
        box_w, box_h = int(max_width), int(max_height)

        try:
            im.draft("RGB", (box_w, box_h))
        except Exception:
            pass
        im.load()

        # Flatten alpha onto dark background (keep geometry)
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (20, 20, 20, 255))
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")

        # thumbnail() preserves aspect ratio
        if im.size[0] > box_w or im.size[1] > box_h:
            im.thumbnail((box_w, box_h), Image.Resampling.BILINEAR)

        # Height must be multiple of 6 for clean sixel bands (pad bottom, no stretch)
        w0, h0 = im.size
        pad_h = (6 - (h0 % 6)) % 6
        if pad_h:
            padded = Image.new("RGB", (w0, h0 + pad_h), (20, 20, 20))
            padded.paste(im, (0, 0))
            im = padded

        try:
            q = im.quantize(colors=max_colors, method=Image.Quantize.FASTOCTREE)
        except Exception:
            try:
                q = im.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
            except Exception:
                q = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=max_colors)

        if q.mode != "P":
            q = q.convert("P", palette=Image.Palette.ADAPTIVE, colors=max_colors)

        w, h = q.size
        palette = q.getpalette() or []
        ncolors = min(max_colors, max(1, len(palette) // 3))
        raw = q.tobytes()
        used_set = set(raw)
        used_list = sorted(i for i in used_set if 0 <= i < ncolors)
        if not used_list:
            used_list = [0]
        remap = {old: new for new, old in enumerate(used_list)}
        colors: list[tuple[int, int, int]] = []
        for old in used_list:
            r = palette[old * 3] if old * 3 < len(palette) else 0
            g = palette[old * 3 + 1] if old * 3 + 1 < len(palette) else 0
            b = palette[old * 3 + 2] if old * 3 + 2 < len(palette) else 0
            colors.append((r, g, b))

        if len(used_list) == ncolors and used_list == list(range(ncolors)):
            pixels = raw
        else:
            pixels = bytes(remap.get(p, 0) for p in raw)

        # Content height for aspect (exclude bottom pad from meta display)
        content_h = h0
        sixel = _pixels_to_sixel_fast(pixels, w, h, colors)
        meta = {
            "width": w,
            "height": content_h,
            "orig_width": orig_w,
            "orig_height": orig_h,
            "colors": len(colors),
            "bytes": len(data),
        }
        return sixel, meta


def _rle_append(out: list[str], ch: str, run: int) -> None:
    if run <= 0:
        return
    if run == 1:
        out.append(ch)
    elif run == 2:
        out.append(ch + ch)
    elif run == 3:
        out.append(ch * 3)
    else:
        out.append(f"!{run}{ch}")


def _pixels_to_sixel_fast(
    pixels: bytes,
    width: int,
    height: int,
    colors: list[tuple[int, int, int]],
) -> str:
    """
    Encode indexed pixels (1 byte/pixel) as SIXEL.

    Single pass per 6-row band builds bitmasks for all colors (O(width*6)),
    then RLE-emits each used color — much faster than per-color full scans.
    """
    ncolors = max(1, len(colors))
    out: list[str] = []
    # P1=0: aspect from raster attrs; P2=0: keep background; then 1:1 pixels + size.
    # Without "1;1;w;h many terminals use legacy 2:1 pixels → wrong aspect ratio.
    out.append("\033P0;0;0q")
    out.append(f'"1;1;{width};{height}')
    for i, (r, g, b) in enumerate(colors):
        out.append(f"#{i};2;{r * 100 // 255};{g * 100 // 255};{b * 100 // 255}")

    # Pre-sized mask buffers reused across bands (ncolors * width bytes)
    masks = [bytearray(width) for _ in range(ncolors)]

    for y0 in range(0, height, 6):
        band_h = min(6, height - y0)
        # clear only used later — zero all masks for this band
        for c in range(ncolors):
            mv = masks[c]
            for x in range(width):
                mv[x] = 0

        used = set()
        for bit in range(band_h):
            row = (y0 + bit) * width
            bitv = 1 << bit
            for x in range(width):
                c = pixels[row + x]
                if c >= ncolors:
                    c = 0
                masks[c][x] |= bitv
                used.add(c)

        first = True
        for c in sorted(used):
            if not first:
                out.append("$")
            first = False
            out.append(f"#{c}")
            mv = masks[c]
            run_ch = ""
            run_len = 0
            for x in range(width):
                ch = chr(0x3F + mv[x])
                if ch == run_ch:
                    run_len += 1
                else:
                    _rle_append(out, run_ch, run_len)
                    run_ch = ch
                    run_len = 1
            _rle_append(out, run_ch, run_len)

        out.append("-")

    out.append("\033\\")
    return "".join(out)


# Back-compat alias
def _pixels_to_sixel(
    pixels,
    width: int,
    height: int,
    colors: list[tuple[int, int, int]],
) -> str:
    if not isinstance(pixels, (bytes, bytearray)):
        pixels = bytes(pixels)
    return _pixels_to_sixel_fast(pixels, width, height, colors)


def _wait_key() -> None:
    """Block until a single key is pressed (raw-ish)."""
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.getch()
            return
    except Exception:
        pass
    # POSIX
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return
    except Exception:
        pass
    # Fallback
    try:
        input()
    except Exception:
        pass


def show_sixel_fullscreen(
    data: bytes,
    *,
    title: str = "",
    max_colors: int = 256,
) -> str:
    """
    Encode and print SIXEL image to the real console/TTY, wait for a key.

    Caller should wrap with Textual ``app.suspend()`` so the terminal is free.
    Returns a short status message for the message line.
    """
    sixel, meta = encode_image_to_sixel(data, max_colors=max_colors)

    out = _tty_out()
    close_out = out is not sys.stdout and out is not getattr(sys, "__stdout__", None)

    caption = title or "image"
    dim = f"{meta['width']}x{meta['height']}"
    if meta["width"] != meta["orig_width"] or meta["height"] != meta["orig_height"]:
        dim += f" (from {meta['orig_width']}x{meta['orig_height']})"

    try:
        # Clear screen and home cursor; leave a one-line caption
        out.write("\033[?25l")  # hide cursor
        out.write("\033[H\033[2J")  # home + clear
        out.write(f" S3 Filer — {caption}  [{dim}, {meta['colors']} colors]\n")
        out.write(" Press any key to return…\n")
        out.write(sixel)
        if not sixel.endswith("\n"):
            out.write("\n")
        out.flush()

        _wait_key()
    finally:
        try:
            out.write("\033[?25h")  # show cursor
            out.write("\033[H\033[2J")
            out.flush()
        except Exception:
            pass
        if close_out:
            try:
                out.close()
            except Exception:
                pass

    return (
        f"SIXEL: {caption}  {meta['width']}x{meta['height']}  "
        f"{meta['bytes']} bytes"
    )


def try_view_image_sixel(data: bytes, filename: str) -> Optional[str]:
    """
    If possible, return the status string after showing the image.
    Returns None if SIXEL view is not applicable (caller should fall back).
    Raises on hard errors after deciding to show.
    """
    if not is_image_name(filename):
        return None
    if not supports_sixel():
        return None
    if not ensure_pillow():
        raise RuntimeError(
            "Terminal may support SIXEL, but Pillow is not available for "
            f"this Python. Run: {pillow_install_hint()}"
        )
    return show_sixel_fullscreen(data, title=filename)
