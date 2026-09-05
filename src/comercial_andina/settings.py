"""Environment-based Azure runtime configuration with no embedded credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AzureSettings:
    """Non-secret identifiers required by the Azure ETL runtime."""

    storage_account: str
    raw_container: str
    manifest_container: str
    quarantine_container: str
    key_vault_url: str
    postgres_host: str
    postgres_database: str
    postgres_secret_name: str
    sql_server: str
    sql_database: str
    sql_secret_name: str

    @classmethod
    def from_environment(cls) -> AzureSettings:
        values = {
            "storage_account": os.getenv("CA_STORAGE_ACCOUNT", ""),
            "raw_container": os.getenv("CA_RAW_CONTAINER", "raw"),
            "manifest_container": os.getenv("CA_MANIFEST_CONTAINER", "manifests"),
            "quarantine_container": os.getenv("CA_QUARANTINE_CONTAINER", "quarantine"),
            "key_vault_url": os.getenv("CA_KEY_VAULT_URL", ""),
            "postgres_host": os.getenv("CA_POSTGRES_HOST", ""),
            "postgres_database": os.getenv("CA_POSTGRES_DATABASE", "comercial_andina"),
            "postgres_secret_name": os.getenv("CA_POSTGRES_SECRET_NAME", "postgres-credentials"),
            "sql_server": os.getenv("CA_SQL_SERVER", ""),
            "sql_database": os.getenv("CA_SQL_DATABASE", "comercial_andina_dw"),
            "sql_secret_name": os.getenv("CA_SQL_SECRET_NAME", "sql-credentials"),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment settings: {', '.join(missing)}")
        return cls(**values)
