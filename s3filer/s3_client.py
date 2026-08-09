"""Amazon S3 operations via boto3."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import unquote

from .models import FileEntry, FileInfo, LocationKind, PathLocation

# botocore exceptions are resolved lazily with the client (import cost ~250ms)


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/prefix into (bucket, prefix). prefix may be empty."""
    uri = uri.strip()
    if uri.startswith("s3://"):
        uri = uri[5:]
    elif uri.startswith("S3://"):
        uri = uri[5:]
    if not uri:
        return "", ""
    parts = uri.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def make_s3_uri(bucket: str, key: str = "") -> str:
    key = key.lstrip("/")
    if not bucket:
        return "s3://"
    if not key:
        return f"s3://{bucket}/"
    return f"s3://{bucket}/{key}"


def normalize_s3_dir(uri: str) -> str:
    """Ensure s3 directory URI ends with / (except bare s3://)."""
    if uri in ("s3://", "s3:", ""):
        return "s3://"
    bucket, prefix = parse_s3_uri(uri)
    if not bucket:
        return "s3://"
    if not prefix:
        return f"s3://{bucket}/"
    if not prefix.endswith("/"):
        # if it looks like a "directory" we still force trailing slash for browsing
        prefix = prefix + "/"
    return f"s3://{bucket}/{prefix}"


class S3Service:
    """
    Thin wrapper around boto3 S3.

    Session/client creation is deferred until the first real API call so that
    pure-local startup does not pay the boto3 import + credential cost.
    """

    def __init__(self, profile: Optional[str] = None, region: Optional[str] = None):
        self.profile = profile
        # May be filled from the session on first connect
        self.region = region or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get(
            "AWS_REGION"
        )
        self._session: Any = None
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: F401
        from .aws_profiles import create_session, resolve_region

        self._session = create_session(self.profile, self.region)
        self.region = resolve_region(self._session, self.region)
        self._client = self._session.client("s3", region_name=self.region)
        return self._client

    def refresh(self, profile: Optional[str] = None, region: Optional[str] = None) -> None:
        if profile is not None:
            self.profile = profile
        if region is not None:
            self.region = region
        self._session = None
        self._client = None
        # Eager reconnect when profile is switched so the next list is correct
        self._ensure_client()

    @property
    def client(self):
        return self._ensure_client()

    def _s3_errors(self):
        from botocore.exceptions import BotoCoreError, ClientError

        return (ClientError, BotoCoreError)

    def list_buckets(self) -> list[FileEntry]:
        loc = PathLocation(LocationKind.S3, "s3://", profile=self.profile, region=self.region)
        entries: list[FileEntry] = []
        try:
            resp = self.client.list_buckets()
        except self._s3_errors() as e:
            raise RuntimeError(f"list_buckets failed: {e}") from e
        for b in sorted(resp.get("Buckets", []), key=lambda x: x["Name"].lower()):
            name = b["Name"]
            mtime = b.get("CreationDate")
            if mtime and mtime.tzinfo:
                mtime = mtime.astimezone().replace(tzinfo=None)
            entries.append(
                FileEntry(
                    name=name,
                    is_dir=True,
                    mtime=mtime,
                    parent_path="s3://",
                    location=loc,
                    key="",
                )
            )
        return entries

    def list_prefix(self, location: PathLocation) -> list[FileEntry]:
        uri = location.path
        bucket, prefix = parse_s3_uri(uri)

        if not bucket:
            return self.list_buckets()

        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        entries: list[FileEntry] = []
        # parent ".."
        parent_uri = self._parent_uri(bucket, prefix)
        entries.append(
            FileEntry(
                name="..",
                is_dir=True,
                parent_path=normalize_s3_dir(uri),
                location=location,
            )
        )

        paginator = self.client.get_paginator("list_objects_v2")
        try:
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/")
        except self._s3_errors() as e:
            raise RuntimeError(f"list_objects failed: {e}") from e

        dirs: list[FileEntry] = []
        files: list[FileEntry] = []

        for page in pages:
            for cp in page.get("CommonPrefixes", []):
                p = cp["Prefix"]
                # name is last segment
                rel = p[len(prefix) :] if p.startswith(prefix) else p
                name = rel.rstrip("/")
                if not name:
                    continue
                dirs.append(
                    FileEntry(
                        name=name,
                        is_dir=True,
                        parent_path=normalize_s3_dir(uri),
                        location=location,
                        key=p,
                    )
                )
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key == prefix:
                    continue  # folder marker
                rel = key[len(prefix) :] if key.startswith(prefix) else key
                if "/" in rel:
                    continue  # should not happen with Delimiter
                name = rel
                if not name:
                    continue
                mtime = obj.get("LastModified")
                if mtime and getattr(mtime, "tzinfo", None):
                    mtime = mtime.astimezone().replace(tzinfo=None)
                files.append(
                    FileEntry(
                        name=name,
                        is_dir=False,
                        size=int(obj.get("Size", 0)),
                        mtime=mtime,
                        parent_path=normalize_s3_dir(uri),
                        location=location,
                        key=key,
                        storage_class=obj.get("StorageClass"),
                        etag=obj.get("ETag"),
                    )
                )

        dirs.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())
        return entries + dirs + files

    def _parent_uri(self, bucket: str, prefix: str) -> str:
        if not prefix:
            return "s3://"
        # strip trailing slash, go up one
        p = prefix.rstrip("/")
        if "/" not in p:
            return f"s3://{bucket}/"
        parent = p.rsplit("/", 1)[0] + "/"
        return f"s3://{bucket}/{parent}"

    def entry_uri(self, entry: FileEntry) -> str:
        if entry.name == "..":
            bucket, prefix = parse_s3_uri(entry.parent_path)
            return self._parent_uri(bucket, prefix if prefix.endswith("/") or not prefix else prefix + "/")
        if entry.is_dir:
            if entry.key:
                bucket, _ = parse_s3_uri(entry.parent_path)
                if not bucket and entry.parent_path in ("s3://", "s3:"):
                    return f"s3://{entry.name}/"
                return make_s3_uri(bucket, entry.key if entry.key.endswith("/") else entry.key + "/")
            return entry.parent_path.rstrip("/") + "/" + entry.name + "/"
        bucket, _ = parse_s3_uri(entry.parent_path)
        key = entry.key or (parse_s3_uri(entry.parent_path)[1] + entry.name)
        return make_s3_uri(bucket, key)

    def mkdir(self, location: PathLocation, name: str) -> str:
        """
        Create a zero-byte folder marker key ending with ``/``.
        ``name`` may contain ``/`` for nested prefixes (e.g. ``logs/2026``).
        """
        bucket, prefix = parse_s3_uri(location.path)
        if not bucket:
            raise RuntimeError(
                "Cannot create folder at account root; open a bucket first "
                "(Enter a bucket, then F7/n)"
            )
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        rel = name.strip().strip("/")
        if not rel:
            raise RuntimeError("Empty folder name")
        key = f"{prefix}{rel}/"
        try:
            self.client.put_object(Bucket=bucket, Key=key, Body=b"")
        except self._s3_errors() as e:
            raise RuntimeError(f"mkdir failed: {e}") from e
        return make_s3_uri(bucket, key)

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def delete_prefix(self, bucket: str, prefix: str) -> int:
        """Delete all objects under prefix. Returns count deleted."""
        if prefix and not prefix.endswith("/"):
            # single object?
            try:
                self.client.head_object(Bucket=bucket, Key=prefix)
                self.delete_object(bucket, prefix)
                return 1
            except self._s3_errors():
                prefix = prefix + "/"

        paginator = self.client.get_paginator("list_objects_v2")
        count = 0
        batch: list[dict] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                batch.append({"Key": obj["Key"]})
                if len(batch) >= 1000:
                    self.client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
                    count += len(batch)
                    batch = []
        if batch:
            self.client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
            count += len(batch)
        return count

    def rename_object(self, bucket: str, src_key: str, dest_key: str) -> None:
        self.client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": src_key},
            Key=dest_key,
        )
        self.client.delete_object(Bucket=bucket, Key=src_key)

    def rename_prefix(self, bucket: str, src_prefix: str, dest_prefix: str) -> int:
        if src_prefix and not src_prefix.endswith("/"):
            # file
            self.rename_object(bucket, src_prefix, dest_prefix)
            return 1
        if not dest_prefix.endswith("/"):
            dest_prefix += "/"
        paginator = self.client.get_paginator("list_objects_v2")
        count = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=src_prefix):
            for obj in page.get("Contents", []):
                old_key = obj["Key"]
                suffix = old_key[len(src_prefix) :]
                new_key = dest_prefix + suffix
                self.client.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": old_key},
                    Key=new_key,
                )
                self.client.delete_object(Bucket=bucket, Key=old_key)
                count += 1
        return count

    def copy_object(
        self,
        src_bucket: str,
        src_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        self.client.copy_object(
            Bucket=dest_bucket,
            CopySource={"Bucket": src_bucket, "Key": src_key},
            Key=dest_key,
        )

    def download_file(self, bucket: str, key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        self.client.download_file(bucket, key, local_path)

    def upload_file(self, local_path: str, bucket: str, key: str) -> None:
        self.client.upload_file(local_path, bucket, key)

    def get_bytes(self, bucket: str, key: str, max_bytes: int = 2 * 1024 * 1024) -> bytes:
        resp = self.client.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{max_bytes - 1}")
        return resp["Body"].read(max_bytes)

    def head(self, bucket: str, key: str) -> dict:
        return self.client.head_object(Bucket=bucket, Key=key)

    def file_info(self, uri: str) -> FileInfo:
        bucket, key = parse_s3_uri(uri)
        if not bucket or not key or key.endswith("/"):
            return FileInfo(
                name=key.rstrip("/") or bucket,
                path=uri,
                is_dir=True,
                size=0,
                kind=LocationKind.S3,
            )
        meta = self.head(bucket, key)
        mtime = meta.get("LastModified")
        if mtime and getattr(mtime, "tzinfo", None):
            mtime = mtime.astimezone().replace(tzinfo=None)
        return FileInfo(
            name=os.path.basename(key),
            path=uri,
            is_dir=False,
            size=int(meta.get("ContentLength", 0)),
            mtime=mtime,
            kind=LocationKind.S3,
            etag=meta.get("ETag"),
            content_type=meta.get("ContentType"),
            storage_class=meta.get("StorageClass"),
            extra={
                "Metadata": meta.get("Metadata") or {},
                "VersionId": meta.get("VersionId"),
            },
        )

    def walk_tree(self, uri: str, max_depth: int = 4, max_nodes: int = 500) -> list[tuple[int, str, bool]]:
        """Tree of common prefixes under uri."""
        bucket, prefix = parse_s3_uri(uri)
        result: list[tuple[int, str, bool]] = []
        if not bucket:
            for e in self.list_buckets()[:max_nodes]:
                result.append((0, e.name, True))
            return result

        result.append((0, bucket if not prefix else prefix.rstrip("/").split("/")[-1], True))

        def _walk(pfx: str, depth: int) -> None:
            if depth >= max_depth or len(result) >= max_nodes:
                return
            try:
                paginator = self.client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=pfx, Delimiter="/"):
                    for cp in page.get("CommonPrefixes", []):
                        if len(result) >= max_nodes:
                            return
                        p = cp["Prefix"]
                        name = p[len(pfx) :].rstrip("/") if p.startswith(pfx) else p.rstrip("/")
                        result.append((depth + 1, name, True))
                        _walk(p, depth + 1)
                    break  # one page of prefixes is enough per level for tree UI
            except self._s3_errors():
                return

        _walk(prefix if not prefix or prefix.endswith("/") else prefix + "/", 0)
        return result

    def list_all_keys(self, bucket: str, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                k = obj["Key"]
                if not k.endswith("/"):
                    keys.append(k)
        return keys
