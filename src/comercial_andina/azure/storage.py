"""Immutable RAW, manifest and quarantine persistence in Azure Blob Storage."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse


def _service_client(account_name: str):
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    return BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=DefaultAzureCredential(exclude_interactive_browser_credential=True),
    )


def upload_file(
    local_path: str | Path,
    account_name: str,
    container: str,
    blob_name: str,
    metadata: dict[str, str] | None = None,
) -> str:
    """Upload one immutable artifact and reject accidental overwrites."""

    from azure.core.exceptions import ResourceExistsError

    source = Path(local_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    selected_metadata = {**(metadata or {}), "sha256": digest}
    client = _service_client(account_name).get_blob_client(container, blob_name)
    try:
        with source.open("rb") as payload:
            client.upload_blob(payload, overwrite=False, metadata=selected_metadata)
    except ResourceExistsError as error:
        if client.get_blob_properties().metadata.get("sha256") != digest:
            message = f"Immutable blob already exists with different content: {client.url}"
            raise RuntimeError(message) from error
    return client.url


def download_file(blob_uri: str, account_name: str, output_path: str | Path) -> Path:
    """Download a blob URI from the configured storage account."""

    parsed = urlparse(blob_uri)
    expected_host = f"{account_name}.blob.core.windows.net"
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise ValueError("RAW URI does not belong to the configured Azure Storage account")
    container, separator, blob_name = parsed.path.lstrip("/").partition("/")
    if not separator or not blob_name:
        raise ValueError("RAW URI must include a container and blob name")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = _service_client(account_name).get_blob_client(container, blob_name).download_blob()
    destination.write_bytes(payload.readall())
    return destination
