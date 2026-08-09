"""Encoding detection and text preview helpers."""

from __future__ import annotations

from typing import Optional

import chardet


# Null-byte heuristic + control-char ratio for binary detection
_TEXT_SAMPLE = 8192


def is_probably_binary(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:_TEXT_SAMPLE]
    if b"\x00" in sample:
        return True
    # high ratio of non-printable (excluding common whitespace)
    non_print = 0
    for b in sample:
        if b in (9, 10, 13):  # tab, lf, cr
            continue
        if b < 32 or b == 127:
            non_print += 1
    return (non_print / max(len(sample), 1)) > 0.30


def detect_encoding(data: bytes) -> tuple[Optional[str], Optional[float], bool]:
    """
    Returns (encoding, confidence 0-1, is_binary).
    """
    if not data:
        return "utf-8", 1.0, False
    if is_probably_binary(data):
        return None, None, True

    # BOM checks
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", 1.0, False
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le", 1.0, False
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be", 1.0, False

    result = chardet.detect(data[: min(len(data), 64 * 1024)])
    enc = result.get("encoding")
    conf = result.get("confidence")
    if enc:
        enc = enc.lower()
        # normalize common aliases
        aliases = {
            "ascii": "utf-8",
            "windows-1252": "cp1252",
            "iso-8859-1": "latin-1",
            "shift_jis": "cp932",
            "shift-jis": "cp932",
            "euc-jp": "euc_jp",
            "gb2312": "gbk",
        }
        enc = aliases.get(enc, enc)
    return enc, conf, False


def decode_for_view(data: bytes, encoding: Optional[str] = None) -> tuple[str, str, bool]:
    """
    Decode bytes for viewer.
    Returns (text, used_encoding, is_binary).
    """
    if is_probably_binary(data) and not encoding:
        # hex dump style preview
        return _hex_preview(data), "binary", True

    if not encoding:
        encoding, _, binary = detect_encoding(data)
        if binary:
            return _hex_preview(data), "binary", True
        encoding = encoding or "utf-8"

    try:
        text = data.decode(encoding, errors="replace")
        return text, encoding, False
    except LookupError:
        text = data.decode("utf-8", errors="replace")
        return text, "utf-8", False


def _hex_preview(data: bytes, max_lines: int = 256) -> str:
    lines = []
    chunk = data[: max_lines * 16]
    for i in range(0, len(chunk), 16):
        row = chunk[i : i + 16]
        hexpart = " ".join(f"{b:02x}" for b in row)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{i:08x}  {hexpart:<48}  {asc}")
    if len(data) > len(chunk):
        lines.append(f"... ({len(data)} bytes total, showing first {len(chunk)})")
    return "\n".join(lines)


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def mime_hint(name: str, is_binary: bool) -> str:
    lower = name.lower()
    mapping = {
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".html": "text/html",
        ".htm": "text/html",
        ".xml": "application/xml",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".sh": "text/x-shellscript",
        ".bat": "text/x-bat",
        ".ps1": "text/x-powershell",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".gz": "application/gzip",
        ".tar": "application/x-tar",
        ".log": "text/plain",
        ".sql": "application/sql",
        ".css": "text/css",
    }
    for ext, mime in mapping.items():
        if lower.endswith(ext):
            return mime
    return "application/octet-stream" if is_binary else "text/plain"
