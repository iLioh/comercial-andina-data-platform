"""End-to-end daily sales pipeline independent from the orchestrator."""

from __future__ import annotations

import re
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from comercial_andina.etl.rds import extract_source_csv
from comercial_andina.etl.redshift import RedshiftDataExecutor
from comercial_andina.etl.s3 import upload_file
from comercial_andina.settings import AwsSettings
from comercial_andina.source.manifest import build_manifest, write_manifest

SAFE_BATCH_ID = re.compile(r"^[A-Z0-9-]+$")


def create_batch_id(now: datetime | None = None) -> str:
    current = now or datetime.now(ZoneInfo("America/Lima"))
    return current.strftime("BATCH-%Y%m%d-%H%M%S")


def run_daily_pipeline(settings: AwsSettings, batch_id: str | None = None) -> dict[str, str | int]:
    """Extract RDS, persist RAW, load Staging, process DQ and publish the DW."""

    selected_batch = batch_id or create_batch_id()
    if not SAFE_BATCH_ID.fullmatch(selected_batch):
        raise ValueError("batch_id contains unsupported characters")

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

        date_prefix = datetime.now(ZoneInfo("America/Lima")).strftime("%Y/%m/%d")
        raw_key = f"raw/ventas/{date_prefix}/{selected_batch}/ventas_origen.csv"
        manifest_key = f"manifests/ventas/{date_prefix}/{selected_batch}/manifest.json"
        raw_uri = upload_file(
            csv_path,
            settings.raw_bucket,
            raw_key,
            settings.region,
            metadata={"batch-id": selected_batch, "schema-version": "1.0"},
        )
        upload_file(
            manifest_path,
            settings.raw_bucket,
            manifest_key,
            settings.region,
            metadata={"batch-id": selected_batch},
        )

        executor = RedshiftDataExecutor(
            settings.region,
            settings.redshift_workgroup,
            settings.redshift_database,
            settings.redshift_secret_arn,
        )
        escaped_uri = raw_uri.replace("'", "''")
        escaped_batch = selected_batch.replace("'", "''")
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
        executor.execute(f"CALL etl.sp_procesar_lote('{escaped_batch}')")
        quarantine_prefix = f"s3://{settings.raw_bucket}/quarantine/{date_prefix}/{selected_batch}/"
        escaped_quarantine = quarantine_prefix.replace("'", "''")
        executor.execute(
            "UNLOAD ('SELECT * FROM audit.dq_rechazos "
            f"WHERE batch_id = ''{escaped_batch}''') "
            f"TO '{escaped_quarantine}rechazos-' IAM_ROLE default "
            "FORMAT AS JSON ALLOWOVERWRITE PARALLEL OFF"
        )

    return {
        "batch_id": selected_batch,
        "extracted_count": extracted_count,
        "raw_uri": raw_uri,
        "quarantine_uri": quarantine_prefix,
        "status": "SUCCESS",
    }
