"""Idempotent ETL steps reusable from Prefect and the command line."""

from __future__ import annotations

import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from comercial_andina.etl.rds import extract_source_csv
from comercial_andina.etl.redshift import RedshiftDataExecutor
from comercial_andina.etl.s3 import upload_file
from comercial_andina.settings import AwsSettings
from comercial_andina.source.manifest import build_manifest, write_manifest

SAFE_BATCH_ID = re.compile(r"^[A-Z0-9-]+$")
BUSINESS_TIMEZONE = ZoneInfo("America/Lima")


def create_batch_id(now: datetime | None = None) -> str:
    """Create the traceability key using the configured business timezone."""

    current = now or datetime.now(BUSINESS_TIMEZONE)
    return current.strftime("BATCH-%Y%m%d-%H%M%S")


def select_batch_id(batch_id: str | None = None) -> str:
    """Create or validate a batch identifier before any external operation."""

    selected_batch = batch_id or create_batch_id()
    if not SAFE_BATCH_ID.fullmatch(selected_batch):
        raise ValueError("batch_id contains unsupported characters")
    return selected_batch


def extract_and_persist_raw(
    settings: AwsSettings,
    batch_id: str,
    now: datetime | None = None,
) -> dict[str, str | int]:
    """Extract RDS and persist the source plus its manifest before transformation."""

    selected_batch = select_batch_id(batch_id)
    current = now or datetime.now(BUSINESS_TIMEZONE)
    date_prefix = current.strftime("%Y/%m/%d")

    with tempfile.TemporaryDirectory(prefix="comercial-andina-") as temp_directory:
        temp = Path(temp_directory)
        csv_path = temp / "ventas_origen.csv"
        extracted_count = extract_source_csv(
            settings.rds_secret_arn,
            settings.region,
            csv_path,
            settings.rds_host,
            settings.rds_database,
        )
        manifest = build_manifest(csv_path, batch_id=selected_batch)
        manifest_path = write_manifest(manifest, temp / "manifest.json")

        raw_key = f"raw/ventas/{date_prefix}/{selected_batch}/ventas_origen.csv"
        manifest_key = f"manifests/ventas/{date_prefix}/{selected_batch}/manifest.json"
        raw_uri = upload_file(
            csv_path,
            settings.raw_bucket,
            raw_key,
            settings.region,
            metadata={"batch-id": selected_batch, "schema-version": "1.0"},
        )
        manifest_uri = upload_file(
            manifest_path,
            settings.raw_bucket,
            manifest_key,
            settings.region,
            metadata={"batch-id": selected_batch},
        )

    return {
        "batch_id": selected_batch,
        "date_prefix": date_prefix,
        "extracted_count": extracted_count,
        "raw_uri": raw_uri,
        "manifest_uri": manifest_uri,
    }


def load_staging(settings: AwsSettings, batch_id: str, raw_uri: str) -> None:
    """Replace the controlled Staging workspace with one RAW batch."""

    escaped_batch = select_batch_id(batch_id).replace("'", "''")
    escaped_uri = raw_uri.replace("'", "''")
    executor = _redshift_executor(settings)
    executor.execute("TRUNCATE TABLE staging.stg_ventas_raw")
    executor.execute(
        "COPY staging.stg_ventas_raw "
        "(id_venta, fecha_venta, producto, categoria, region, cantidad, precio_unitario) "
        f"FROM '{escaped_uri}' IAM_ROLE default CSV IGNOREHEADER 1 "
        "DATEFORMAT 'auto' TIMEFORMAT 'auto' BLANKSASNULL EMPTYASNULL"
    )
    executor.execute(
        "UPDATE staging.stg_ventas_raw "
        f"SET batch_id = '{escaped_batch}', ingestion_timestamp = GETDATE()"
    )


def process_quality_and_warehouse(settings: AwsSettings, batch_id: str) -> None:
    """Apply quality rules and publish valid rows into the dimensional warehouse."""

    escaped_batch = select_batch_id(batch_id).replace("'", "''")
    _redshift_executor(settings).execute(f"CALL etl.sp_procesar_lote('{escaped_batch}')")


def export_quarantine(
    settings: AwsSettings,
    batch_id: str,
    date_prefix: str,
) -> str:
    """Export rejected records and evidence to the encrypted S3 quarantine prefix."""

    escaped_batch = select_batch_id(batch_id).replace("'", "''")
    quarantine_uri = f"s3://{settings.raw_bucket}/quarantine/{date_prefix}/{batch_id}/"
    escaped_quarantine = quarantine_uri.replace("'", "''")
    _redshift_executor(settings).execute(
        "UNLOAD ('SELECT * FROM audit.dq_rechazos "
        f"WHERE batch_id = ''{escaped_batch}''') "
        f"TO '{escaped_quarantine}rechazos-' IAM_ROLE default "
        "FORMAT AS JSON ALLOWOVERWRITE PARALLEL OFF"
    )
    return quarantine_uri


def reconcile_batch(
    settings: AwsSettings,
    batch_id: str,
    expected_source_count: int,
) -> dict[str, Any]:
    """Fail the flow when audit counts or publication status do not reconcile."""

    escaped_batch = select_batch_id(batch_id).replace("'", "''")
    control = _redshift_executor(settings).query_one(
        "SELECT registros_origen, registros_validos, registros_rechazados, "
        "registros_publicados, importe_publicado, estado "
        "FROM audit.etl_control "
        f"WHERE batch_id = '{escaped_batch}'"
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


def run_daily_pipeline(settings: AwsSettings, batch_id: str | None = None) -> dict[str, Any]:
    """Run every ETL step without requiring the Prefect orchestrator."""

    selected_batch = select_batch_id(batch_id)
    raw = extract_and_persist_raw(settings, selected_batch)
    load_staging(settings, selected_batch, str(raw["raw_uri"]))
    process_quality_and_warehouse(settings, selected_batch)
    quarantine_uri = export_quarantine(
        settings,
        selected_batch,
        str(raw["date_prefix"]),
    )
    reconciliation = reconcile_batch(
        settings,
        selected_batch,
        int(raw["extracted_count"]),
    )
    return {
        **raw,
        **reconciliation,
        "quarantine_uri": quarantine_uri,
    }


def _redshift_executor(settings: AwsSettings) -> RedshiftDataExecutor:
    return RedshiftDataExecutor(
        settings.region,
        settings.redshift_workgroup,
        settings.redshift_database,
        settings.redshift_secret_arn,
    )
