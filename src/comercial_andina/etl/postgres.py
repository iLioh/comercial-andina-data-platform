"""Azure Database for PostgreSQL source extraction and dataset loading."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from comercial_andina.azure.key_vault import get_json_secret
from comercial_andina.source.generator import SOURCE_COLUMNS


def _connect(secret: dict[str, Any], host: str, database: str):
    import psycopg

    return psycopg.connect(
        host=host,
        port=int(secret.get("port", 5432)),
        dbname=database,
        user=secret["username"],
        password=secret["password"],
        sslmode="require",
    )


def execute_source_ddl(
    vault_url: str,
    secret_name: str,
    sql_path: str | Path,
    host: str,
    database: str,
) -> None:
    """Create the simulated operational source."""

    secret = get_json_secret(vault_url, secret_name)
    with _connect(secret, host, database) as connection:
        connection.execute(Path(sql_path).read_text(encoding="utf-8"))


def load_source_csv(
    vault_url: str,
    secret_name: str,
    csv_path: str | Path,
    host: str,
    database: str,
) -> int:
    """Replace the source with a reproducible contract-compatible dataset."""

    source_path = Path(csv_path)
    secret = get_json_secret(vault_url, secret_name)
    copy_sql = (
        "COPY oltp.ventas_origen (id_venta, fecha_venta, producto, categoria, region, "
        "cantidad, precio_unitario) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    )
    with _connect(secret, host, database) as connection:
        connection.execute("TRUNCATE TABLE oltp.ventas_origen")
        with source_path.open("r", encoding="utf-8", newline="") as source:
            with connection.cursor().copy(copy_sql) as copy:
                while chunk := source.read(1024 * 1024):
                    copy.write(chunk)
        count = connection.execute("SELECT COUNT(*) FROM oltp.ventas_origen").fetchone()[0]
    return int(count)


def extract_source_csv(
    vault_url: str,
    secret_name: str,
    output_path: str | Path,
    host: str,
    database: str,
) -> int:
    """Extract the exact seven-field source contract required by the laboratory."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    secret = get_json_secret(vault_url, secret_name)
    query = """
        SELECT id_venta, fecha_venta, producto, categoria, region, cantidad, precio_unitario
        FROM oltp.ventas_origen
        ORDER BY id_venta
    """
    row_count = 0
    with _connect(secret, host, database) as connection, destination.open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output)
        writer.writerow(SOURCE_COLUMNS)
        with connection.cursor(name="ventas_extract") as cursor:
            cursor.execute(query)
            for row in cursor:
                writer.writerow(row)
                row_count += 1
    return row_count
