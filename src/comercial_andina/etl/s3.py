"""RAW and manifest persistence in Amazon S3."""

from __future__ import annotations

from pathlib import Path


def upload_file(
    local_path: str | Path,
    bucket: str,
    key: str,
    region: str,
    metadata: dict[str, str] | None = None,
) -> str:
    """Upload one immutable pipeline artifact using bucket-managed encryption."""

    import boto3

    client = boto3.client("s3", region_name=region)
    client.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={"Metadata": metadata or {}},
    )
    return f"s3://{bucket}/{key}"
