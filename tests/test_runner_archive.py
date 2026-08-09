"""Tests for command runner and archive helpers."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

from s3filer.archive_ops import (
    extract_members,
    is_archive_name,
    list_archive,
)
from s3filer.runner import (
    build_command_argv,
    build_command_line,
    convert_path_for_shell,
    is_runnable_name,
    quote_path_for_shell,
    resolve_interactive_shell,
    run_subprocess,
    run_via_user_shell,
    shell_kind,
    start_via_user_shell,
    windows_path_to_cygwin,
    windows_path_to_msys,
    wrap_command_for_shell,
)


def test_is_archive_name() -> None:
    assert is_archive_name("a.zip")
    assert is_archive_name("b.tar.gz")
    assert is_archive_name("c.tgz")
    assert not is_archive_name("readme.txt")


def test_is_runnable_name() -> None:
    assert is_runnable_name("run.sh")
    assert is_runnable_name("app.exe")
    assert is_runnable_name("tool.ps1")
    assert is_runnable_name("x.py")
    assert not is_runnable_name("data.csv")


def test_build_command_append() -> None:
    cmd, shell = build_command_argv("echo", ["/tmp/a.txt", "/tmp/b.txt"])
    assert shell is False
    assert isinstance(cmd, list)
    # first token may be resolved to absolute path via shutil.which
    assert cmd[0] == "echo" or str(cmd[0]).endswith("echo") or "echo" in str(cmd[0]).lower()
    assert cmd[-1].endswith("b.txt")


def test_build_command_placeholder() -> None:
    cmd, shell = build_command_argv("python {}", ["a.py"])
    if shell:
        assert "a.py" in cmd  # type: ignore[operator]
    else:
        assert isinstance(cmd, list)
        assert "a.py" in " ".join(cmd) or cmd[-1] == "a.py"


def test_build_command_line_append_and_placeholder() -> None:
    line = build_command_line(
        "mdview", [r"C:\docs\readme.md"], shell_argv=["cmd.exe"]
    )
    assert line.startswith("mdview")
    assert "readme.md" in line
    line2 = build_command_line(
        "viewer {}", [r"C:\a b\file.md"], shell_argv=["cmd.exe"]
    )
    assert "viewer" in line2
    assert "file.md" in line2


def test_windows_path_to_msys() -> None:
    assert windows_path_to_msys(r"C:\Users\kabuk\Documents\README.md") == (
        "/c/Users/kabuk/Documents/README.md"
    )
    assert windows_path_to_msys(r"c:/Users/a") == "/c/Users/a"
    assert windows_path_to_msys(r"\\?\C:\x\y") == "/c/x/y"
    # already msys
    assert windows_path_to_msys("/c/Users/a") == "/c/Users/a"
    assert windows_path_to_cygwin(r"C:\Users\a") == "/cygdrive/c/Users/a"


def test_git_bash_path_conversion_in_command_line() -> None:
    git_bash = [r"C:\Program Files\Git\bin\bash.exe"]
    win = r"C:\Users\kabuk\Documents\20260805_s3filer\README.md"
    converted = convert_path_for_shell(win, shell_argv=git_bash)
    assert converted == "/c/Users/kabuk/Documents/20260805_s3filer/README.md"
    # no backslashes left for bash to eat
    assert "\\" not in converted

    line = build_command_line("mdview", [win], shell_argv=git_bash)
    assert line.startswith("mdview ")
    assert "/c/Users/kabuk/Documents/20260805_s3filer/README.md" in line
    assert "C:Users" not in line  # classic "backslash stripped" failure
    assert "\\" not in line

    line2 = build_command_line("cat {}", [win], shell_argv=git_bash)
    assert line2.startswith("cat ")
    assert "/c/Users/" in line2

    # spaces → POSIX quoted
    spaced = r"C:\Users\kabuk\My Docs\file.md"
    q = quote_path_for_shell(spaced, shell_argv=git_bash)
    assert q.startswith("'") or q.startswith('"') or "My" in q
    assert "\\" not in q


def test_powershell_path_keeps_drive() -> None:
    win = r"C:\Users\kabuk\Documents\README.md"
    line = build_command_line("mdview", [win], shell_argv=["pwsh.exe"])
    assert "README.md" in line
    # PowerShell form should retain drive letter (quoted)
    assert "C:" in line or "c:" in line.lower()


def test_wrap_command_for_shell_cmd() -> None:
    argv = wrap_command_for_shell("mdview file.md", shell_argv=["cmd.exe"])
    assert argv[0] == "cmd.exe"
    assert "/c" in argv
    assert argv[-1] == "mdview file.md"


def test_wrap_command_for_shell_powershell() -> None:
    argv = wrap_command_for_shell("mdview file.md", shell_argv=["pwsh.exe"])
    assert "pwsh.exe" in argv[0]
    assert "-Command" in argv
    assert argv[-1] == "mdview file.md"


def test_resolve_interactive_shell_returns_list() -> None:
    sh = resolve_interactive_shell()
    assert isinstance(sh, list) and len(sh) >= 1
    assert shell_kind(sh) in ("powershell", "cmd", "bash", "sh")


def test_run_via_user_shell_python_ok() -> None:
    # Use a command that must exist: the current Python interpreter
    py = _quote_for_test(sys.executable)
    r = run_via_user_shell(f"{py} -c \"print(1)\"")
    assert r.ok, r.message


def test_start_via_user_shell_background() -> None:
    """Background start returns immediately without waiting for the child."""
    import time

    py = _quote_for_test(sys.executable)
    done: list[int] = []
    t0 = time.perf_counter()
    r = start_via_user_shell(
        f"{py} -c \"import time; time.sleep(1.5)\"",
        on_exit=lambda rc: done.append(rc),
    )
    elapsed = time.perf_counter() - t0
    assert r.ok, r.message
    # Must return long before the 1.5s child sleep finishes
    assert elapsed < 1.0, f"start blocked too long: {elapsed:.2f}s"
    for _ in range(80):
        if done:
            break
        time.sleep(0.05)
    assert done, "on_exit was not called"


def _quote_for_test(path: str) -> str:
    if os.name == "nt":
        if any(c in path for c in ' \t"'):
            return '"' + path.replace('"', '\\"') + '"'
        return path
    import shlex

    return shlex.quote(path)


def test_run_subprocess_resolves_pathext_on_windows() -> None:
    """Bare command names that map to *.CMD must not raise FileNotFoundError."""
    if os.name != "nt":
        return
    # where.exe is always present on modern Windows as where.EXE
    which = shutil.which("where")
    if not which:
        return
    r = run_subprocess(["where", "where"], use_shell=False)
    assert r.returncode is not None  # ran without FileNotFoundError


def test_zip_list_and_extract(tmp_path: Path) -> None:
    zpath = tmp_path / "sample.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("hello.txt", "hello world\n")
        zf.writestr("dir/nested.txt", "nested\n")
    members = list_archive(str(zpath))
    names = {m.name.rstrip("/") for m in members}
    assert "hello.txt" in names
    assert any("nested" in n for n in names)

    out = tmp_path / "out"
    out.mkdir()
    n = extract_members(str(zpath), ["hello.txt"], str(out), mode="preserve")
    assert n == 1
    assert (out / "hello.txt").read_text(encoding="utf-8") == "hello world\n"

    out2 = tmp_path / "flat"
    out2.mkdir()
    n2 = extract_members(str(zpath), ["dir/nested.txt"], str(out2), mode="flat")
    assert n2 == 1
    assert (out2 / "nested.txt").is_file()
    assert not (out2 / "dir").exists()


def test_run_subprocess_ok() -> None:
    import sys

    r = run_subprocess([sys.executable, "-c", "print(1)"])
    assert r.ok
    assert r.returncode == 0
