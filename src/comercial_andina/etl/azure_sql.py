"""Parameterized execution against Azure SQL Database."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from comercial_andina.azure.key_vault import get_json_secret


class AzureSqlExecutor:
    """Execute T-SQL using encrypted connections and Key Vault credentials."""

    def __init__(self, vault_url: str, secret_name: str, server: str, database: str) -> None:
        self.secret = get_json_secret(vault_url, secret_name)
        self.server = server
        self.database = database

    def _connect(self):
        import pyodbc

        connection_string = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER=tcp:{self.server},1433;DATABASE={self.database};"
            f"UID={self.secret['username']};PWD={self.secret['password']};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )
        return pyodbc.connect(connection_string)

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None:
        with self._connect() as connection:
            connection.execute(sql, parameters or ())
            connection.commit()

    def execute_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.fast_executemany = True
            cursor.executemany(sql, rows)
            connection.commit()

    def execute_file(self, sql_path: str | Path) -> None:
        """Execute batches separated by a line containing GO."""

        import re

        sql = Path(sql_path).read_text(encoding="utf-8")
        for batch in re.split(r"^\s*GO\s*$", sql, flags=re.IGNORECASE | re.MULTILINE):
            if batch.strip():
                self.execute(batch)

    def query_one(self, sql: str, parameters: Sequence[Any] | None = None) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(sql, parameters or ())
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [item[0] for item in cursor.description]
            return dict(zip(columns, row, strict=True))

    def query_all(self, sql: str, parameters: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(sql, parameters or ())
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
