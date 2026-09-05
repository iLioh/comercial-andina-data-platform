"""Prefect orchestration for the D+1 sales pipeline."""

from __future__ import annotations

from prefect import flow, task

from comercial_andina.etl.pipeline import run_daily_pipeline
from comercial_andina.settings import AwsSettings


@task(retries=2, retry_delay_seconds=30, log_prints=True)
def process_sales_batch() -> dict[str, str | int]:
    return run_daily_pipeline(AwsSettings.from_environment())


@flow(name="comercial-andina-daily-sales", log_prints=True)
def daily_sales_flow() -> dict[str, str | int]:
    """Run the complete traceable daily batch."""

    result = process_sales_batch()
    print(f"Pipeline completed: {result}")
    return result


if __name__ == "__main__":
    daily_sales_flow()
