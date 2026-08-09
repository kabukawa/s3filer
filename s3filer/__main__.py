"""CLI entry point for s3filer."""

from __future__ import annotations

import argparse
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s3filer",
        description="Dual-pane console file manager for local filesystem and Amazon S3 "
        "(FD/FILMTN style).",
    )
    p.add_argument(
        "-p",
        "--profile",
        default=os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE"),
        help="AWS CLI profile name (default: env AWS_PROFILE or 'default')",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION"),
        help="AWS region (optional)",
    )
    p.add_argument(
        "-l",
        "--left",
        default=None,
        help="Initial left pane path (local path or s3:// URI)",
    )
    p.add_argument(
        "-r",
        "--right",
        default=None,
        help="Initial right pane path (local path or s3:// URI)",
    )
    p.add_argument(
        "--theme",
        default=None,
        help="UI theme name (overrides saved config for this session only unless --save-theme)",
    )
    p.add_argument(
        "--save-theme",
        action="store_true",
        help="Persist --theme to the config file",
    )
    p.add_argument(
        "--list-themes",
        action="store_true",
        help="List available themes and exit",
    )
    p.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        from . import __version__

        print(f"s3filer {__version__}")
        return 0

    if args.list_themes:
        from .themes import THEME_LABELS, theme_names
        from .config import get_theme_name, config_path

        current = get_theme_name()
        print(f"Config: {config_path()}")
        print(f"Current theme: {current}\n")
        for name in theme_names():
            mark = " *" if name == current else ""
            print(f"  {name:18} {THEME_LABELS.get(name, '')}{mark}")
        return 0

    # Apply region via env if provided (picked up by boto3 session)
    if args.region:
        os.environ.setdefault("AWS_DEFAULT_REGION", args.region)

    if args.theme:
        from .config import set_theme_name
        from .themes import resolve_theme_name

        name = resolve_theme_name(args.theme)
        if args.save_theme:
            set_theme_name(name)
        else:
            # Session-only: write a process-local override via env
            os.environ["S3FILER_THEME"] = name

    try:
        from .app import run_app

        run_app(profile=args.profile, left=args.left, right=args.right)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
