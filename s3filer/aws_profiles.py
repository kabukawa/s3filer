"""AWS CLI profile discovery and session helpers."""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import boto3


def _aws_config_paths() -> list[Path]:
    home = Path.home()
    paths = [
        home / ".aws" / "config",
        home / ".aws" / "credentials",
    ]
    # Windows / env overrides
    if os.environ.get("AWS_CONFIG_FILE"):
        paths.insert(0, Path(os.environ["AWS_CONFIG_FILE"]))
    if os.environ.get("AWS_SHARED_CREDENTIALS_FILE"):
        paths.insert(0, Path(os.environ["AWS_SHARED_CREDENTIALS_FILE"]))
    return paths


def list_profiles() -> list[str]:
    """Return sorted AWS profile names (includes 'default' if present)."""
    names: set[str] = set()
    # Prefer parsing config files (fast; no boto3 import).
    for path in _aws_config_paths():
        if not path.is_file():
            continue
        try:
            cp = configparser.ConfigParser()
            cp.read(path, encoding="utf-8")
            for section in cp.sections():
                if section == "default":
                    names.add("default")
                elif section.startswith("profile "):
                    names.add(section[len("profile ") :])
                else:
                    # credentials file uses bare profile names
                    names.add(section)
        except Exception:
            continue

    # Optional enrichment via botocore if available and already imported / cheap
    if not names:
        try:
            from botocore.session import Session as BotocoreSession

            session = BotocoreSession()
            names.update(session.available_profiles)
        except Exception:
            pass

    if not names:
        names.add("default")
    return sorted(names, key=lambda x: (x != "default", x.lower()))


def create_session(
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    """Create a boto3 Session for the given profile/region (imports boto3 on demand)."""
    import boto3

    kwargs: dict = {}
    if profile and profile != "default":
        kwargs["profile_name"] = profile
    elif profile == "default":
        kwargs["profile_name"] = "default"
    if region:
        kwargs["region_name"] = region
    return boto3.Session(**kwargs)


def resolve_region(session, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    return session.region_name or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get(
        "AWS_REGION"
    )
