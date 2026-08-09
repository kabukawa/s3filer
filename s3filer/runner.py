"""Run shell commands and executables/scripts with selected files."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .models import FileEntry
from .operations import entry_source_path
from .s3_client import S3Service, parse_s3_uri

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

# Extensions treated as "run this file" (plus executable bit on POSIX)
_SCRIPT_EXTS = {
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".cmd",
    ".ps1",
    ".py",
    ".rb",
    ".pl",
    ".exe",
    ".com",
    ".msi",
    ".js",
    ".mjs",
}

# Process basenames recognized as interactive shells (parent walk)
_SHELL_BASENAMES = frozenset(
    {
        "cmd.exe",
        "cmd",
        "powershell.exe",
        "powershell",
        "pwsh.exe",
        "pwsh",
        "bash.exe",
        "bash",
        "zsh",
        "zsh.exe",
        "fish",
        "fish.exe",
        "sh",
        "sh.exe",
        "dash",
        "ksh",
        "tcsh",
        "csh",
        "nu",
        "nu.exe",
        "busybox",
    }
)


@dataclass
class RunResult:
    ok: bool
    message: str
    returncode: Optional[int] = None


def is_runnable_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in _SCRIPT_EXTS)


def is_executable_file(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if is_runnable_name(os.path.basename(path)):
        return True
    if os.name != "nt":
        try:
            mode = os.stat(path).st_mode
            if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                return True
        except OSError:
            pass
    return False


def _quote_win(path: str) -> str:
    """Quote for cmd.exe / CreateProcess-style command lines."""
    if not path:
        return '""'
    if any(c in path for c in ' \t"&|^<>'):
        return '"' + path.replace('"', '\\"') + '"'
    return path


def _quote_powershell(path: str) -> str:
    """Single-quote a path for PowerShell (no expansion of $ etc.)."""
    # PowerShell single-quoted string: escape ' as ''
    return "'" + (path or "").replace("'", "''") + "'"


def _abs_path(path: str) -> str:
    """Best-effort absolute path without requiring the file to exist."""
    if not path:
        return path
    try:
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(p.resolve(strict=False))
    except Exception:
        try:
            return os.path.abspath(path)
        except Exception:
            return path


def windows_path_to_msys(path: str) -> str:
    """
    Convert a Windows path to MSYS / Git Bash form.

    Examples:
      C:\\Users\\a\\b  →  /c/Users/a/b
      c:/Users/a      →  /c/Users/a
      \\\\?\\C:\\x    →  /c/x
      \\\\server\\s   →  //server/s
    """
    p = (path or "").strip()
    if not p:
        return p
    # Already MSYS-style (/c/...) or POSIX absolute without drive
    if p.startswith("/") and not p.startswith("//"):
        return p.replace("\\", "/")
    # Long-path / UNC prefixes
    if p.startswith("\\\\?\\UNC\\") or p.startswith("//?/UNC/"):
        p = "//" + p.replace("\\", "/")[8:]
    elif p.startswith("\\\\?\\") or p.startswith("//?/"):
        p = p.replace("\\", "/")[4:]
    else:
        p = p.replace("\\", "/")
    # Drive letter
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        drive = p[0].lower()
        rest = p[2:]
        if not rest.startswith("/"):
            rest = "/" + rest if rest else ""
        return f"/{drive}{rest}"
    # UNC //server/share
    if p.startswith("//"):
        return p
    return p


def windows_path_to_cygwin(path: str) -> str:
    """Convert a Windows path to Cygwin form (/cygdrive/c/...)."""
    msys = windows_path_to_msys(path)
    if len(msys) >= 2 and msys[0] == "/" and msys[1].isalpha() and (
        len(msys) == 2 or msys[2] == "/"
    ):
        return "/cygdrive" + msys
    return msys


def _bash_flavor(shell_exe: str) -> str:
    """
    Distinguish Git Bash / MSYS vs Cygwin for path conversion.
    Returns: 'msys' | 'cygwin' | 'posix'
    """
    low = (shell_exe or "").replace("\\", "/").lower()
    if "cygwin" in low:
        return "cygwin"
    if os.name == "nt":
        # Git for Windows, MSYS2, etc.
        if any(x in low for x in ("/git/", "\\git\\", "msys", "mingw")):
            return "msys"
        # bash.exe on Windows is almost always MSYS-compatible
        base = os.path.basename(low)
        if base in ("bash.exe", "bash", "zsh.exe", "zsh", "sh.exe", "sh", "fish.exe", "fish"):
            return "msys"
    return "posix"


def convert_path_for_shell(
    path: str,
    *,
    shell_argv: Optional[list[str]] = None,
) -> str:
    """
    Convert a filesystem path into the form expected by the target shell.

    Git Bash / MSYS:  C:\\Users\\x → /c/Users/x
    Cygwin:           C:\\Users\\x → /cygdrive/c/Users/x
    cmd / PowerShell: Windows path with backslashes (normalized)
    Native Unix:      unchanged (absolute when possible)
    """
    if not path:
        return path
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    kind = shell_kind(shell)
    exe = shell[0] if shell else ""

    if os.name == "nt" and kind in ("bash", "sh"):
        abs_win = _abs_path(path)
        flavor = _bash_flavor(exe)
        if flavor == "cygwin":
            return windows_path_to_cygwin(abs_win)
        # msys / Git Bash
        return windows_path_to_msys(abs_win)

    if os.name == "nt":
        # cmd / PowerShell: keep native Windows path
        return _abs_path(path).replace("/", "\\")

    return _abs_path(path)


def quote_path_for_shell(
    path: str,
    *,
    shell_argv: Optional[list[str]] = None,
) -> str:
    """Convert path for the shell, then apply shell-appropriate quoting."""
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    kind = shell_kind(shell)
    converted = convert_path_for_shell(path, shell_argv=shell)
    if kind == "powershell":
        return _quote_powershell(converted)
    if kind == "cmd":
        return _quote_win(converted)
    # bash / sh / zsh / fish (incl. Git Bash): POSIX quoting — never leave bare \\
    return shlex.quote(converted)


def build_command_line(
    command: str,
    file_paths: list[str],
    *,
    shell_argv: Optional[list[str]] = None,
) -> str:
    """
    Build a single shell command-line string with paths substituted/appended.

    Paths are converted and quoted for the target shell (Git Bash → /c/..., etc.).
    ``{}`` / ``{f}`` in the template are replaced with space-joined quoted paths.
    Otherwise quoted paths are appended.
    """
    command = (command or "").strip().replace("{f}", "{}")
    if not command:
        raise ValueError("Empty command")
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    paths = list(file_paths)
    joined = " ".join(quote_path_for_shell(p, shell_argv=shell) for p in paths)
    if "{}" in command:
        return command.replace("{}", joined)
    if paths:
        return f"{command} {joined}".rstrip()
    return command


def build_command_argv(command: str, file_paths: list[str]) -> tuple[list[str] | str, bool]:
    """
    Build argv or shell string.
    Returns (cmd, use_shell).

    Prefer :func:`run_via_user_shell` for external tools (PATH / .cmd resolution).
    This helper still supports direct argv for tests and simple cases.

    On Windows, the first token is resolved with ``shutil.which`` so that
    ``mdview.CMD`` / ``code.CMD`` style PATH entries work with shell=False.
    """
    command = (command or "").strip().replace("{f}", "{}")
    if not command:
        raise ValueError("Empty command")

    paths = list(file_paths)

    if "{}" in command:
        # Shell command line with shell-aware path conversion
        return build_command_line(command, paths), True

    try:
        parts = shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        parts = command.split()

    if not parts:
        raise ValueError("Empty command")

    # Resolve first token on PATH (critical on Windows for *.CMD without shell)
    resolved = shutil.which(parts[0])
    if resolved:
        parts = [resolved] + parts[1:]
    # Direct argv keeps native OS paths (CreateProcess / execve)
    return parts + [_abs_path(p) if os.name == "nt" else p for p in paths], False


def _win_parent_chain_exes(max_depth: int = 12) -> list[str]:
    """Return executable paths of parent processes (closest first) on Windows."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
    CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    Process32FirstW = kernel32.Process32FirstW
    Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    Process32FirstW.restype = wintypes.BOOL
    Process32NextW = kernel32.Process32NextW
    Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    Process32NextW.restype = wintypes.BOOL
    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL
    QueryFullProcessImageNameW = getattr(kernel32, "QueryFullProcessImageNameW", None)
    OpenProcess = kernel32.OpenProcess
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    OpenProcess.restype = wintypes.HANDLE
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE or not snap:
        return []

    # pid -> (ppid, exe_name)
    table: dict[int, tuple[int, str]] = {}
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not Process32FirstW(snap, ctypes.byref(pe)):
            return []
        while True:
            table[int(pe.th32ProcessID)] = (
                int(pe.th32ParentProcessID),
                pe.szExeFile,
            )
            if not Process32NextW(snap, ctypes.byref(pe)):
                break
    finally:
        CloseHandle(snap)

    def _full_path(pid: int, fallback_name: str) -> str:
        if QueryFullProcessImageNameW is not None:
            h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(1024)
                    ok = QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
                    if ok:
                        return buf.value
                finally:
                    CloseHandle(h)
        # fallback: search PATH for the basename
        which = shutil.which(fallback_name)
        return which or fallback_name

    out: list[str] = []
    pid = os.getpid()
    seen: set[int] = set()
    for _ in range(max_depth):
        if pid not in table:
            break
        ppid, _name = table[pid]
        if not ppid or ppid == pid or ppid in seen:
            break
        seen.add(pid)
        if ppid not in table:
            break
        _ppid2, pname = table[ppid]
        out.append(_full_path(ppid, pname))
        pid = ppid
    return out


def _posix_parent_chain_exes(max_depth: int = 12) -> list[str]:
    """Return executable paths of parent processes (closest first) on POSIX."""
    out: list[str] = []
    pid = os.getppid()
    seen: set[int] = set()
    for _ in range(max_depth):
        if not pid or pid in seen:
            break
        seen.add(pid)
        path: Optional[str] = None
        # Linux /proc
        try:
            path = os.path.realpath(f"/proc/{pid}/exe")
        except OSError:
            path = None
        if not path or path.endswith(" (deleted)"):
            try:
                with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                    path = f.read().strip()
            except OSError:
                path = None
        if path:
            out.append(path)
        # next parent
        next_pid: Optional[int] = None
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
                data = f.read().split()
                next_pid = int(data[3])
        except (OSError, IndexError, ValueError):
            # macOS / BSD fallback (one step only via ps)
            if not out:
                try:
                    r = subprocess.run(
                        ["ps", "-o", "command=", "-p", str(pid)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    line = (r.stdout or "").strip()
                    if line:
                        out.append(line.split()[0])
                except Exception:
                    pass
            break
        if not next_pid or next_pid == pid:
            break
        pid = next_pid
    return out


def _is_shell_exe(path: str) -> bool:
    base = os.path.basename(path or "").lower()
    return base in _SHELL_BASENAMES


_parent_shell_cache: Optional[str] = None
_parent_shell_resolved: bool = False
_interactive_shell_cache: Optional[list[str]] = None


def detect_parent_shell_exe() -> Optional[str]:
    """
    Find an interactive shell executable among parent processes.
    Skips Python / terminal emulators until a shell is found.
    Result is cached for the process lifetime.
    """
    global _parent_shell_cache, _parent_shell_resolved
    if _parent_shell_resolved:
        return _parent_shell_cache
    chain = _win_parent_chain_exes() if os.name == "nt" else _posix_parent_chain_exes()
    found_path: Optional[str] = None
    for path in chain:
        if _is_shell_exe(path):
            # Prefer absolute path when available
            if os.path.isfile(path):
                found_path = path
            else:
                found = shutil.which(os.path.basename(path))
                found_path = found or path
            break
    _parent_shell_cache = found_path
    _parent_shell_resolved = True
    return found_path


def resolve_interactive_shell() -> list[str]:
    """
    Command argv for an interactive subshell.

    Order:
      1. ``S3FILER_SHELL`` override (full command string)
      2. Parent process shell (inherit the shell that launched s3filer)
      3. ``$SHELL`` (Unix) / ``$COMSPEC`` (Windows)
      4. Platform defaults

    Cached after first resolution (override env is still re-checked).
    """
    global _interactive_shell_cache
    override = (os.environ.get("S3FILER_SHELL") or "").strip()
    if override:
        try:
            return shlex.split(override, posix=(os.name != "nt"))
        except ValueError:
            return override.split()

    if _interactive_shell_cache is not None:
        return list(_interactive_shell_cache)

    parent = detect_parent_shell_exe()
    if parent:
        _interactive_shell_cache = [parent]
        return list(_interactive_shell_cache)

    if os.name == "nt":
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        _interactive_shell_cache = [comspec]
        return list(_interactive_shell_cache)

    shell = (os.environ.get("SHELL") or "").strip()
    if shell and os.path.isfile(shell):
        _interactive_shell_cache = [shell]
        return list(_interactive_shell_cache)
    for cand in ("/bin/bash", "/usr/bin/bash", "/bin/zsh", "/bin/sh"):
        if os.path.isfile(cand):
            _interactive_shell_cache = [cand]
            return list(_interactive_shell_cache)
    _interactive_shell_cache = ["sh"]
    return list(_interactive_shell_cache)


def shell_kind(shell_argv: Optional[list[str]] = None) -> str:
    """
    Classify shell as one of: powershell, cmd, bash, sh.
    """
    argv = shell_argv if shell_argv is not None else resolve_interactive_shell()
    if not argv:
        return "cmd" if os.name == "nt" else "sh"
    base = os.path.basename(argv[0]).lower()
    if base in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        return "powershell"
    if base in ("cmd.exe", "cmd"):
        return "cmd"
    if base in (
        "bash",
        "bash.exe",
        "zsh",
        "zsh.exe",
        "fish",
        "fish.exe",
        "sh",
        "sh.exe",
        "dash",
        "ksh",
        "tcsh",
        "csh",
    ):
        return "bash"
    return "cmd" if os.name == "nt" else "sh"


def wrap_command_for_shell(
    command_line: str,
    *,
    shell_argv: Optional[list[str]] = None,
) -> list[str]:
    """
    Wrap a command-line string so it is executed by the user's shell.

    This makes PATH lookups, ``.CMD`` wrappers, and profile-provided tools work
    the same way as typing the command interactively.
    """
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    kind = shell_kind(shell)
    exe = shell[0]
    if kind == "powershell":
        # -NoProfile keeps startup fast; PATH is still inherited from this process.
        # Use -Command so external programs and cmdlets resolve like the parent shell.
        return [exe, "-NoLogo", "-NoProfile", "-Command", command_line]
    if kind == "cmd":
        return [exe, "/d", "/c", command_line]
    # bash / sh / zsh / fish (Git Bash, MSYS, Cygwin, …): -c
    # Prefer login-free non-interactive -c; paths in command_line must already be
    # converted (see build_command_line / quote_path_for_shell).
    return [exe, "-c", command_line]


def run_via_user_shell(
    command_line: str,
    *,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    shell_argv: Optional[list[str]] = None,
) -> RunResult:
    """Run ``command_line`` through the inherited / configured user shell (blocking)."""
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    argv = wrap_command_for_shell(command_line, shell_argv=shell)
    # cwd stays as a native OS path (Windows CreateProcess / chdir accepts it)
    return run_subprocess(argv, cwd=cwd, use_shell=False, env=env)


def start_via_user_shell(
    command_line: str,
    *,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    shell_argv: Optional[list[str]] = None,
    on_exit: Optional[Callable[[int], None]] = None,
) -> RunResult:
    """
    Start ``command_line`` in the background without blocking or taking over the TTY.

    Intended for external viewers (GUI / separate-window tools) so the filer UI
    stays visible. Stdio is detached; on Windows the child is created with
    CREATE_NO_WINDOW so a console flash does not steal the terminal.

    If ``on_exit`` is provided, it is called from a daemon thread with the
    process return code after the process exits (use for temp-file cleanup).
    """
    shell = list(shell_argv) if shell_argv is not None else resolve_interactive_shell()
    argv = wrap_command_for_shell(command_line, shell_argv=shell)
    run_env = env or os.environ.copy()
    popen_kwargs: dict = {
        "cwd": cwd or None,
        "env": run_env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        # Avoid allocating a new console that would blank/steal the TUI terminal.
        # GUI apps (notepad, browsers, etc.) still show their own windows.
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        create_new_pg = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        popen_kwargs["creationflags"] = create_no_window | create_new_pg
    else:
        # New session: not tied to the filer's controlling terminal
        popen_kwargs["start_new_session"] = True

    try:
        # Resolve argv[0] on Windows (.CMD etc.)
        if isinstance(argv, list) and argv:
            first = argv[0]
            if not os.path.isabs(first) and not os.path.isfile(first):
                found = shutil.which(first)
                if found:
                    argv = [found] + list(argv[1:])
        proc = subprocess.Popen(argv, **popen_kwargs)
    except FileNotFoundError as e:
        return RunResult(False, f"Command not found: {e}")
    except Exception as e:
        return RunResult(False, str(e))

    if on_exit is not None:
        def _wait() -> None:
            try:
                rc = proc.wait()
            except Exception:
                rc = -1
            try:
                on_exit(rc if rc is not None else -1)
            except Exception:
                pass

        threading.Thread(target=_wait, name="s3filer-bg-cmd", daemon=True).start()

    return RunResult(
        ok=True,
        message=f"pid {proc.pid}",
        returncode=None,
    )


def open_subshell(
    cwd: Optional[str] = None,
    *,
    extra_env: Optional[dict[str, str]] = None,
) -> RunResult:
    """
    Launch an interactive shell in ``cwd`` (blocking until the shell exits).
    Uses the parent process shell when possible so the environment matches
    the shell that launched s3filer.
    Caller should wrap with Textual ``app.suspend()``.
    """
    cmd = resolve_interactive_shell()
    kind = shell_kind(cmd)
    # Make shells start interactive when useful
    if kind == "powershell" and len(cmd) == 1:
        # Stay interactive until user exits (default for pwsh/powershell)
        pass
    elif kind == "bash" and len(cmd) == 1:
        # interactive login-like session so aliases/functions from rc may load
        cmd = [cmd[0], "-i"]

    work = cwd
    if work and not os.path.isdir(work):
        work = os.getcwd()
    env = os.environ.copy()
    if extra_env:
        env.update({k: v for k, v in extra_env.items() if v is not None})
    # Helpful context for scripts inside the subshell
    if work:
        env.setdefault("S3FILER_CWD", work)
    try:
        proc = subprocess.run(
            cmd,
            cwd=work or None,
            env=env,
            check=False,
        )
        rc = proc.returncode if proc.returncode is not None else 0
        shell_name = os.path.basename(cmd[0]) if cmd else "shell"
        return RunResult(
            ok=True,
            message=f"Subshell exited ({shell_name}, code {rc})",
            returncode=rc,
        )
    except FileNotFoundError as e:
        return RunResult(False, f"Shell not found: {e}")
    except Exception as e:
        return RunResult(False, f"Subshell failed: {e}")


def run_subprocess(
    cmd: list[str] | str,
    *,
    cwd: Optional[str] = None,
    use_shell: bool = False,
    env: Optional[dict] = None,
) -> RunResult:
    try:
        # When given a list on Windows, ensure argv[0] is resolvable (.CMD etc.)
        if isinstance(cmd, list) and cmd and not use_shell:
            first = cmd[0]
            if not os.path.isabs(first) and not os.path.isfile(first):
                found = shutil.which(first)
                if found:
                    cmd = [found] + list(cmd[1:])
        proc = subprocess.run(
            cmd,
            cwd=cwd or None,
            shell=use_shell,
            env=env or os.environ.copy(),
            check=False,
        )
        rc = proc.returncode
        ok = rc == 0
        return RunResult(
            ok=ok,
            message=f"Exit code {rc}" + (" (ok)" if ok else ""),
            returncode=rc,
        )
    except FileNotFoundError as e:
        return RunResult(False, f"Command not found: {e}")
    except Exception as e:
        return RunResult(False, str(e))


def materialize_entry(
    entry: FileEntry,
    s3: S3Service,
    *,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> tuple[str, Optional[str]]:
    """
    Return a local filesystem path for the entry.
    For S3, download to a temp file. Returns (path, temp_dir_or_None).
    """
    if entry.is_dir or entry.name == "..":
        raise IsADirectoryError(entry.name)

    if entry.location and entry.location.is_s3():
        uri = entry_source_path(entry)
        bucket, key = parse_s3_uri(uri)
        # size check
        try:
            meta = s3.head(bucket, key)
            size = int(meta.get("ContentLength") or 0)
            if size > max_bytes:
                raise RuntimeError(
                    f"Object too large to materialize ({size} bytes; max {max_bytes})"
                )
        except RuntimeError:
            raise
        except Exception:
            pass
        tmp_dir = tempfile.mkdtemp(prefix="s3filer-run-")
        local = os.path.join(tmp_dir, os.path.basename(entry.name) or "object")
        s3.download_file(bucket, key, local)
        # make scripts executable on POSIX
        if os.name != "nt":
            try:
                os.chmod(
                    local,
                    os.stat(local).st_mode | stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR,
                )
            except OSError:
                pass
        return local, tmp_dir

    path = entry_source_path(entry)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path, None


def materialize_entries(
    entries: list[FileEntry],
    s3: S3Service,
) -> tuple[list[str], list[str]]:
    """Returns (paths, temp_dirs_to_cleanup)."""
    paths: list[str] = []
    temps: list[str] = []
    for e in entries:
        if e.name == ".." or e.is_dir:
            continue
        p, td = materialize_entry(e, s3)
        paths.append(p)
        if td:
            temps.append(td)
    return paths, temps


def cleanup_temps(temp_dirs: list[str]) -> None:
    import shutil

    for td in temp_dirs:
        try:
            shutil.rmtree(td, ignore_errors=True)
        except Exception:
            pass


def run_command_with_entries(
    command: str,
    entries: list[FileEntry],
    s3: S3Service,
    *,
    cwd: Optional[str] = None,
) -> RunResult:
    paths, temps = materialize_entries(entries, s3)
    if not paths and "{}" not in command and "{f}" not in command:
        # allow pure commands without files
        paths = []
    try:
        # Run via user shell so PATH / .cmd / shell aliases match interactive use.
        # Paths are converted for Git Bash (/c/...) etc. before substitution.
        shell = resolve_interactive_shell()
        cmdline = build_command_line(command, paths, shell_argv=shell)
        return run_via_user_shell(cmdline, cwd=cwd, shell_argv=shell)
    finally:
        cleanup_temps(temps)


def run_entry_as_program(
    entry: FileEntry,
    s3: S3Service,
    *,
    cwd: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
) -> RunResult:
    """Execute a script/binary. Interpreters chosen by extension when needed."""
    path, temp_dir = materialize_entry(entry, s3)
    temps = [temp_dir] if temp_dir else []
    try:
        cmd = _launch_argv(path, extra_args or [])
        work = cwd
        if work is None and not (entry.location and entry.location.is_s3()):
            work = str(Path(path).parent)
        use_shell = False
        # .bat/.cmd need shell on Windows
        lower = path.lower()
        if os.name == "nt" and (lower.endswith(".bat") or lower.endswith(".cmd")):
            use_shell = True
            cmd = subprocess.list2cmdline(cmd) if isinstance(cmd, list) else cmd
        return run_subprocess(cmd, cwd=work, use_shell=use_shell)
    finally:
        cleanup_temps(temps)


def _launch_argv(path: str, extra_args: list[str]) -> list[str]:
    lower = path.lower()
    base = [path] + list(extra_args)

    if lower.endswith(".py"):
        return [sys.executable, path] + list(extra_args)
    if lower.endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            path,
        ] + list(extra_args)
    if lower.endswith((".js", ".mjs")):
        return ["node", path] + list(extra_args)
    if lower.endswith(".rb"):
        return ["ruby", path] + list(extra_args)
    if lower.endswith(".pl"):
        return ["perl", path] + list(extra_args)

    if os.name != "nt" and lower.endswith((".sh", ".bash", ".zsh")):
        # prefer bash if available
        shell = "bash" if os.path.exists("/bin/bash") else "sh"
        return [shell, path] + list(extra_args)

    if os.name == "nt" and lower.endswith((".sh", ".bash")):
        # Git Bash if present
        for bash in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.isfile(bash):
                return [bash, path] + list(extra_args)
        return ["bash", path] + list(extra_args)

    # Direct execution
    if os.name != "nt":
        return base
    # Windows: .exe etc.
    return base
