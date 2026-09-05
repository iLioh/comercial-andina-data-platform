"""Observable Prefect orchestration for the D+1 sales pipeline."""

from __future__ import annotations

from typing import Any

from prefect import flow, get_run_logger, task

from comercial_andina.etl.pipeline import (
    export_quarantine,
    extract_and_persist_raw,
    load_staging,
    process_quality_and_warehouse,
    reconcile_batch,
    select_batch_id,
)
from comercial_andina.settings import AwsSettings


@task(name="01 - Preparar lote", retries=0)
def prepare_batch(batch_id: str | None = None) -> str:
    """Create and validate the traceability identifier."""

    return select_batch_id(batch_id)


@task(name="02 - Extraer RDS y persistir RAW", retries=2, retry_delay_seconds=30)
def extract_raw(settings: AwsSettings, batch_id: str) -> dict[str, str | int]:
    """Extract the operational source and durably preserve it before transformation."""

    result = extract_and_persist_raw(settings, batch_id)
    get_run_logger().info(
        "RAW persisted: batch=%s records=%s uri=%s",
        batch_id,
        result["extracted_count"],
        result["raw_uri"],
    )
    return result


@task(name="03 - Cargar Staging", retries=2, retry_delay_seconds=30)
def stage_raw(settings: AwsSettings, batch_id: str, raw_uri: str) -> None:
    """Load the immutable source copy into the Redshift validation workspace."""

    load_staging(settings, batch_id, raw_uri)


@task(name="04 - Validar y publicar Data Warehouse", retries=1, retry_delay_seconds=60)
def publish_warehouse(settings: AwsSettings, batch_id: str) -> None:
    """Apply DQ rules, quarantine invalid rows and publish valid dimensional data."""

    process_quality_and_warehouse(settings, batch_id)


@task(name="05 - Exportar cuarentena", retries=2, retry_delay_seconds=30)
def persist_quarantine(settings: AwsSettings, batch_id: str, date_prefix: str) -> str:
    """Store rejected records and their failed rules outside the warehouse."""

    return export_quarantine(settings, batch_id, date_prefix)


@task(name="06 - Conciliar y auditar", retries=1, retry_delay_seconds=30)
def verify_reconciliation(
    settings: AwsSettings,
    batch_id: str,
    expected_source_count: int,
) -> dict[str, Any]:
    """Verify source, valid, rejected and published totals."""

    result = reconcile_batch(settings, batch_id, expected_source_count)
    get_run_logger().info(
        "Reconciliation: source=%s valid=%s rejected=%s published=%s status=%s",
        result["source_count"],
        result["valid_count"],
        result["rejected_count"],
        result["published_count"],
        result["status"],
    )
    return result


@flow(name="comercial-andina-daily-sales", log_prints=True)
def daily_sales_flow(batch_id: str | None = None) -> dict[str, Any]:
    """Orchestrate one visible, traceable and reconciled D+1 sales batch."""

    settings = AwsSettings.from_environment()
    selected_batch = prepare_batch(batch_id)
    raw = extract_raw(settings, selected_batch)
    stage_raw(settings, selected_batch, str(raw["raw_uri"]))
    publish_warehouse(settings, selected_batch)
    quarantine_uri = persist_quarantine(
        settings,
        selected_batch,
        str(raw["date_prefix"]),
    )
    reconciliation = verify_reconciliation(
        settings,
        selected_batch,
        int(raw["extracted_count"]),
    )
    return {
        **raw,
        **reconciliation,
        "quarantine_uri": quarantine_uri,
    }


if __name__ == "__main__":
    daily_sales_flow()
