"""Idempotent Azure ETL steps reusable from Prefect and the command line."""

from __future__ import annotations

import csv
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from comercial_andina.azure.storage import download_file, upload_file
from comercial_andina.etl.azure_sql import AzureSqlExecutor
from comercial_andina.etl.postgres import extract_source_csv
from comercial_andina.settings import AzureSettings
from comercial_andina.source.manifest import build_manifest, write_manifest

SAFE_BATCH_ID = re.compile(r"^[A-Z0-9-]+$")
BUSINESS_TIMEZONE = ZoneInfo("America/Lima")


def create_batch_id(now: datetime | None = None) -> str:
    current = now or datetime.now(BUSINESS_TIMEZONE)
    return current.strftime("BATCH-%Y%m%d-%H%M%S")


def select_batch_id(batch_id: str | None = None) -> str:
    selected_batch = batch_id or create_batch_id()
    if not SAFE_BATCH_ID.fullmatch(selected_batch):
        raise ValueError("batch_id contains unsupported characters")
    return selected_batch


def extract_and_persist_raw(
    settings: AzureSettings,
    batch_id: str,
    now: datetime | None = None,
) -> dict[str, str | int]:
    """Extract PostgreSQL and preserve RAW plus manifest before transformation."""

    selected_batch = select_batch_id(batch_id)
    current = now or datetime.now(BUSINESS_TIMEZONE)
    date_prefix = current.strftime("%Y/%m/%d")
    with tempfile.TemporaryDirectory(prefix="comercial-andina-") as directory:
        temp = Path(directory)
        csv_path = temp / "ventas_origen.csv"
        extracted_count = extract_source_csv(
            settings.key_vault_url,
            settings.postgres_secret_name,
            csv_path,
            settings.postgres_host,
            settings.postgres_database,
        )
        manifest = build_manifest(csv_path, batch_id=selected_batch)
        try:
            batch_time = datetime.strptime(selected_batch, "BATCH-%Y%m%d-%H%M%S").replace(
                tzinfo=BUSINESS_TIMEZONE
            )
            manifest["extracted_at_utc"] = batch_time.astimezone(ZoneInfo("UTC")).isoformat()
        except ValueError:
            pass
        manifest_path = write_manifest(manifest, temp / "manifest.json")
        raw_uri = upload_file(
            csv_path,
            settings.storage_account,
            settings.raw_container,
            f"ventas/{date_prefix}/{selected_batch}/ventas_origen.csv",
            metadata={"batch_id": selected_batch, "schema_version": "1.0"},
        )
        manifest_uri = upload_file(
            manifest_path,
            settings.storage_account,
            settings.manifest_container,
            f"ventas/{date_prefix}/{selected_batch}/manifest.json",
            metadata={"batch_id": selected_batch},
        )
    return {
        "batch_id": selected_batch,
        "date_prefix": date_prefix,
        "extracted_count": extracted_count,
        "raw_uri": raw_uri,
        "manifest_uri": manifest_uri,
    }


def load_staging(settings: AzureSettings, batch_id: str, raw_uri: str) -> None:
    """Load one immutable RAW batch into the Azure SQL validation workspace."""

    selected_batch = select_batch_id(batch_id)
    executor = _sql_executor(settings)
    with tempfile.TemporaryDirectory(prefix="comercial-andina-stage-") as directory:
        source = download_file(
            raw_uri,
            settings.storage_account,
            Path(directory) / "ventas_origen.csv",
        )
        with source.open("r", encoding="utf-8", newline="") as payload:
            rows = [
                (*row, selected_batch, datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None))
                for row in csv.reader(payload)
                if row and row[0] != "id_venta"
            ]
    executor.execute("DELETE FROM staging.stg_ventas_raw WHERE batch_id = ?", (selected_batch,))
    executor.execute_many(
        "INSERT INTO staging.stg_ventas_raw "
        "(id_venta, fecha_venta, producto, categoria, region, cantidad, precio_unitario, "
        "batch_id, ingestion_timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def process_quality_and_warehouse(settings: AzureSettings, batch_id: str) -> None:
    """Apply quality rules and publish valid rows into the dimensional warehouse."""

    _sql_executor(settings).execute(
        "EXEC etl.sp_procesar_lote @p_batch_id = ?", (select_batch_id(batch_id),)
    )


def export_quarantine(settings: AzureSettings, batch_id: str, date_prefix: str) -> str:
    """Export rejected rows and rule evidence to the quarantine container."""

    selected_batch = select_batch_id(batch_id)
    records = _sql_executor(settings).query_all(
        "SELECT * FROM audit.dq_rechazos WHERE batch_id = ? ORDER BY rechazo_key",
        (selected_batch,),
    )
    with tempfile.TemporaryDirectory(prefix="comercial-andina-quarantine-") as directory:
        path = Path(directory) / "rechazos.jsonl"
        with path.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
        return upload_file(
            path,
            settings.storage_account,
            settings.quarantine_container,
            f"ventas/{date_prefix}/{selected_batch}/rechazos.jsonl",
            metadata={"batch_id": selected_batch, "record_count": str(len(records))},
        )


def reconcile_batch(
    settings: AzureSettings,
    batch_id: str,
    expected_source_count: int,
) -> dict[str, Any]:
    """Fail the flow when audit counts or publication status do not reconcile."""

    selected_batch = select_batch_id(batch_id)
    control = _sql_executor(settings).query_one(
        "SELECT registros_origen, registros_validos, registros_rechazados, "
        "registros_publicados, importe_publicado, estado FROM audit.etl_control "
        "WHERE batch_id = ?",
        (selected_batch,),
    )
    if control is None:
        raise RuntimeError(f"No audit control found for {batch_id}")
    source_count = int(control["registros_origen"])
    valid_count = int(control["registros_validos"])
    rejected_count = int(control["registros_rechazados"])
    published_count = int(control["registros_publicados"])
    status = str(control["estado"])
    if source_count != expected_source_count:
        raise RuntimeError(
            f"Source reconciliation failed: extracted={expected_source_count}, audit={source_count}"
        )
    if valid_count + rejected_count != source_count:
        raise RuntimeError("Quality reconciliation failed: valid + rejected != source")
    if valid_count != published_count or status != "SUCCESS":
        raise RuntimeError("Warehouse reconciliation failed: valid rows were not fully published")
    return {
        "source_count": source_count,
        "valid_count": valid_count,
        "rejected_count": rejected_count,
        "published_count": published_count,
        "published_amount": control["importe_publicado"],
        "status": status,
    }


def run_daily_pipeline(settings: AzureSettings, batch_id: str | None = None) -> dict[str, Any]:
    """Run every ETL step without requiring the Prefect orchestrator."""

    selected_batch = select_batch_id(batch_id)
    raw = extract_and_persist_raw(settings, selected_batch)
    load_staging(settings, selected_batch, str(raw["raw_uri"]))
    process_quality_and_warehouse(settings, selected_batch)
    quarantine_uri = export_quarantine(settings, selected_batch, str(raw["date_prefix"]))
    reconciliation = reconcile_batch(settings, selected_batch, int(raw["extracted_count"]))
    return {**raw, **reconciliation, "quarantine_uri": quarantine_uri}


def _sql_executor(settings: AzureSettings) -> AzureSqlExecutor:
    return AzureSqlExecutor(
        settings.key_vault_url,
        settings.sql_secret_name,
        settings.sql_server,
        settings.sql_database,
    )
