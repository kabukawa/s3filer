"""Filesystem browsing helpers (refresh pane listings)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from . import local_fs
from .models import FileEntry, LocationKind, PaneState, PathLocation
from .places import PLACES_ROOT, is_places_root, local_parent_path
from .s3_client import S3Service, make_s3_uri, normalize_s3_dir, parse_s3_uri


def default_local_location() -> PathLocation:
    return PathLocation(LocationKind.LOCAL, local_fs.normalize_local_path(os.getcwd()))


def default_s3_location(profile: Optional[str] = None, region: Optional[str] = None) -> PathLocation:
    return PathLocation(LocationKind.S3, "s3://", profile=profile, region=region)


def _local_isdir(path: str) -> bool:
    try:
        return os.path.isdir(path)
    except OSError:
        return False


def recover_local_path(path: str) -> tuple[str, Optional[str]]:
    """
    Find an existing directory near ``path``.
    Returns (resolved_path, note_or_None).
    """
    original = path
    if is_places_root(path):
        return PLACES_ROOT if os.name == "nt" else local_fs.normalize_local_path(os.sep), None
    try:
        p = local_fs.normalize_local_path(path)
    except Exception:
        p = path
    if is_places_root(p):
        return p, None

    seen: set[str] = set()
    while p and p not in seen:
        seen.add(p)
        if _local_isdir(p):
            note = None
            if os.path.normcase(os.path.normpath(p)) != os.path.normcase(
                os.path.normpath(str(original))
            ):
                note = f"Path missing; moved to {p}"
            return p, note
        parent = os.path.dirname(p.rstrip("\\/"))
        if not parent or parent == p:
            break
        p = parent

    for cand in (os.getcwd(), str(Path.home())):
        try:
            c = local_fs.normalize_local_path(cand)
        except Exception:
            c = cand
        if _local_isdir(c):
            return c, f"Path missing ({original}); fell back to {c}"

    # Last resort: cwd even if questionable
    return local_fs.normalize_local_path(os.getcwd()), f"Path missing ({original}); using cwd"


def _s3_parent_candidates(uri: str) -> list[str]:
    """Walk s3://bucket/a/b/ → parents → s3://bucket/ → s3://."""
    out: list[str] = []
    bucket, prefix = parse_s3_uri(uri)
    if not bucket:
        return ["s3://"]
    p = prefix
    # normalize trailing slash for prefixes
    if p and not p.endswith("/"):
        p = p + "/"
    while p:
        out.append(make_s3_uri(bucket, p))
        body = p.rstrip("/")
        if not body:
            break
        if "/" not in body:
            break
        p = body.rsplit("/", 1)[0] + "/"
    out.append(f"s3://{bucket}/")
    out.append("s3://")
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        nu = normalize_s3_dir(u) if u != "s3://" else "s3://"
        if nu not in seen:
            seen.add(nu)
            uniq.append(nu)
    return uniq


def _ensure_parent_entry(entries: list[FileEntry], location: PathLocation) -> list[FileEntry]:
    """Guarantee a '..' row so the user can always leave a broken/empty view."""
    if any(e.name == ".." for e in entries):
        return entries
    # At true roots, still show .. for local (goes to parent drive/path) and S3 (s3://)
    if location.is_s3() and location.path in ("s3://", "s3:"):
        return entries
    if location.is_local() and is_places_root(location.path):
        return entries
    parent_path = location.path
    return [
        FileEntry(
            name="..",
            is_dir=True,
            parent_path=parent_path,
            location=location,
        )
    ] + list(entries)


def refresh_pane(state: PaneState, s3: Optional[S3Service] = None) -> PaneState:
    """
    Reload entries for the pane's current location.

    If the path no longer exists (deleted local dir, wrong profile / missing
    bucket, etc.), walk up to a working parent or a safe default so the UI
    never becomes a dead-end empty list without navigation.
    """
    state.error = None
    state.loading = True
    recovery_note: Optional[str] = None
    try:
        if state.location.is_local():
            path = state.location.path
            if is_places_root(path):
                path = PLACES_ROOT if os.name == "nt" else local_fs.normalize_local_path(os.sep)
            elif not _local_isdir(path):
                path, recovery_note = recover_local_path(path)
            else:
                try:
                    path = local_fs.normalize_local_path(path)
                except Exception:
                    path, recovery_note = recover_local_path(path)

            state.location = PathLocation(LocationKind.LOCAL, path)
            try:
                state.entries = local_fs.list_dir(state.location)
            except Exception:
                # Race: disappeared after exists check
                path, recovery_note = recover_local_path(path)
                state.location = PathLocation(LocationKind.LOCAL, path)
                state.entries = local_fs.list_dir(state.location)
        else:
            if s3 is None:
                raise RuntimeError("S3 service not available")
            # Stamp current profile/region from the live service when missing
            profile = state.location.profile or getattr(s3, "profile", None)
            region = state.location.region or getattr(s3, "region", None)
            raw = state.location.path
            if not raw.startswith("s3://") and not raw.startswith("S3://"):
                raw = f"s3://{raw}"
            candidates = _s3_parent_candidates(raw)
            # Always try original first (already first in list if well-formed)
            last_err: Optional[Exception] = None
            loaded = False
            for cand in candidates:
                loc = PathLocation(
                    LocationKind.S3,
                    cand if cand == "s3://" else normalize_s3_dir(cand),
                    profile=profile,
                    region=region,
                )
                try:
                    entries = s3.list_prefix(loc)
                    state.location = loc
                    state.entries = entries
                    loaded = True
                    if cand != (normalize_s3_dir(raw) if raw != "s3://" else "s3://"):
                        recovery_note = f"S3 path unavailable; moved to {loc.path}"
                    break
                except Exception as e:
                    last_err = e
                    continue
            if not loaded:
                # Absolute last resort: empty bucket list shell
                state.location = default_s3_location(profile, region)
                state.entries = [
                    FileEntry(
                        name="..",
                        is_dir=True,
                        parent_path="s3://",
                        location=state.location,
                    )
                ]
                state.error = str(last_err) if last_err else "S3 list failed"
                state.cursor = 0
                state.selected.clear()
                state.loading = False
                return state

        state.entries = _ensure_parent_entry(state.entries, state.location)
        if recovery_note:
            state.error = recovery_note  # shown as status, not fatal
        # clamp cursor
        if state.cursor >= len(state.entries):
            state.cursor = max(0, len(state.entries) - 1)
        names = {e.name for e in state.entries}
        state.selected = {n for n in state.selected if n in names}
    except Exception as e:
        # Ultimate safety net — never leave panes unusable
        state.error = str(e)
        try:
            if state.location.is_local():
                fb, note = recover_local_path(state.location.path)
                state.location = PathLocation(LocationKind.LOCAL, fb)
                state.entries = local_fs.list_dir(state.location)
                state.entries = _ensure_parent_entry(state.entries, state.location)
                if note:
                    state.error = f"{e}; {note}"
            else:
                prof = state.location.profile
                reg = state.location.region
                state.location = default_s3_location(prof, reg)
                if s3 is not None:
                    try:
                        state.entries = s3.list_prefix(state.location)
                    except Exception as e2:
                        state.entries = []
                        state.error = f"{e}; fallback s3:// also failed: {e2}"
                else:
                    state.entries = []
                state.entries = _ensure_parent_entry(state.entries, state.location)
        except Exception as e2:
            state.entries = [
                FileEntry(name="..", is_dir=True, parent_path=state.location.path)
            ]
            state.error = f"{e}; recovery failed: {e2}"
        state.cursor = 0
        state.selected.clear()
    finally:
        state.loading = False
    return state


def navigate_into(state: PaneState, s3: Optional[S3Service] = None) -> PaneState:
    entry = state.current_entry()
    if not entry:
        return state
    if not entry.is_dir and entry.name != "..":
        return state

    if state.location.is_local():
        if entry.name == "..":
            if is_places_root(state.location.path):
                return state
            new_path = local_fs.normalize_local_path(
                local_parent_path(state.location.path)
            )
        elif entry.target_path:
            new_path = local_fs.normalize_local_path(entry.target_path)
        else:
            new_path = local_fs.normalize_local_path(
                os.path.join(state.location.path, entry.name)
            )
        state.location = PathLocation(LocationKind.LOCAL, new_path)
        state.cursor = 0
        state.selected.clear()
        return refresh_pane(state, s3)

    # S3
    if entry.name == "..":
        if state.location.path in ("s3://", "s3:"):
            return state
        bucket, prefix = parse_s3_uri(state.location.path)
        if not prefix:
            new_uri = "s3://"
        else:
            p = prefix.rstrip("/")
            if "/" not in p:
                new_uri = f"s3://{bucket}/"
            else:
                new_uri = f"s3://{bucket}/{p.rsplit('/', 1)[0]}/"
        state.location = PathLocation(
            LocationKind.S3,
            new_uri,
            profile=state.location.profile,
            region=state.location.region,
        )
    else:
        if state.location.path in ("s3://", "s3:"):
            new_uri = f"s3://{entry.name}/"
        else:
            base = state.location.path.rstrip("/") + "/"
            new_uri = base + entry.name + "/"
        state.location = PathLocation(
            LocationKind.S3,
            normalize_s3_dir(new_uri),
            profile=state.location.profile,
            region=state.location.region,
        )
    state.cursor = 0
    state.selected.clear()
    return refresh_pane(state, s3)


def go_to(
    state: PaneState,
    path: str,
    s3: Optional[S3Service] = None,
    *,
    profile: Optional[str] = None,
    region: Optional[str] = None,
) -> PaneState:
    path = path.strip()
    prof = profile
    reg = region
    if path.startswith("s3://") or path.startswith("S3://"):
        if prof is None and state.location.is_s3():
            prof = state.location.profile
        if reg is None and state.location.is_s3():
            reg = state.location.region
        if s3 is not None:
            prof = prof or getattr(s3, "profile", None)
            reg = reg or getattr(s3, "region", None)
        state.location = PathLocation(
            LocationKind.S3,
            normalize_s3_dir(path),
            profile=prof,
            region=reg,
        )
    else:
        state.location = PathLocation(LocationKind.LOCAL, local_fs.normalize_local_path(path))
    state.cursor = 0
    state.selected.clear()
    return refresh_pane(state, s3)
