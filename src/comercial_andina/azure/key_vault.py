"""Secret retrieval through Azure Key Vault and workload identity."""

from __future__ import annotations

import json
from typing import Any


def get_json_secret(vault_url: str, secret_name: str) -> dict[str, Any]:
    """Return one JSON secret using DefaultAzureCredential."""

    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    value = SecretClient(vault_url=vault_url, credential=credential).get_secret(secret_name).value
    if not value:
        raise ValueError(f"Secret {secret_name!r} is empty")
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError(f"Secret {secret_name!r} must contain a JSON object")
    return decoded
