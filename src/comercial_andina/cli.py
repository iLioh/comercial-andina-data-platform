"""Local command-line entry points for repeatable project operations."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from comercial_andina.quality.validator import validate_rows
from comercial_andina.source.catalog import load_catalog
from comercial_andina.source.generator import (
    DEFAULT_PROCESSING_DATE,
    generate_sales,
    write_sales_csv,
)
from comercial_andina.source.manifest import build_manifest, write_manifest


def _generate(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    processing_date = date.fromisoformat(args.processing_date)
    rows = generate_sales(
        catalog,
        record_count=args.records,
        seed=args.seed,
        processing_date=processing_date,
    )
    output = write_sales_csv(rows, args.output)
    issues = validate_rows(rows, catalog, processing_date)
    manifest = build_manifest(output, batch_id=args.batch_id)
    manifest["quality_issue_count"] = len(issues)
    manifest["invalid_record_count"] = len({issue.sale_id for issue in issues})
    manifest_path = output.with_suffix(".manifest.json")
    write_manifest(manifest, manifest_path)
    print(f"Generated {len(rows)} rows at {output}")
    print(f"Detected {manifest['invalid_record_count']} controlled invalid records")
    print(f"Manifest written to {manifest_path}")
    return 0


def _load_postgres(args: argparse.Namespace) -> int:
    from comercial_andina.etl.postgres import execute_source_ddl, load_source_csv

    execute_source_ddl(
        args.vault_url, args.secret_name, args.ddl, args.host, args.database
    )
    count = load_source_csv(
        args.vault_url, args.secret_name, args.input, args.host, args.database
    )
    print(f"Loaded {count} rows into oltp.ventas_origen")
    return 0


def _bootstrap_azure_sql(args: argparse.Namespace) -> int:
    from comercial_andina.etl.azure_sql import AzureSqlExecutor

    executor = AzureSqlExecutor(
        args.vault_url,
        args.secret_name,
        args.server,
        args.database,
    )
    scripts = sorted(args.sql_directory.glob("*.sql"))
    if not scripts:
        raise ValueError(f"No SQL scripts found in {args.sql_directory}")
    for script in scripts:
        print(f"Executing {script}")
        executor.execute_file(script)
    print(f"Applied {len(scripts)} Azure SQL scripts")
    return 0


def _run_pipeline(args: argparse.Namespace) -> int:
    from comercial_andina.etl.pipeline import run_daily_pipeline
    from comercial_andina.settings import AzureSettings

    result = run_daily_pipeline(AzureSettings.from_environment(), args.batch_id)
    print(f"Pipeline completed: {result}")
    return 0


def _initialize(_args: argparse.Namespace) -> int:
    """Bootstrap both databases and load the reproducible laboratory dataset."""

    from comercial_andina.etl.azure_sql import AzureSqlExecutor
    from comercial_andina.etl.postgres import execute_source_ddl, load_source_csv
    from comercial_andina.settings import AzureSettings

    settings = AzureSettings.from_environment()
    catalog = load_catalog(Path("config/catalogs.json"))
    processing_date = datetime.now(ZoneInfo("America/Lima")).date()
    rows = generate_sales(
        catalog,
        record_count=10_000,
        seed=20260905,
        processing_date=processing_date,
    )
    dataset = write_sales_csv(rows, Path("/tmp/ventas_origen.csv"))
    execute_source_ddl(
        settings.key_vault_url,
        settings.postgres_secret_name,
        Path("sql/postgres/01_create_source.sql"),
        settings.postgres_host,
        settings.postgres_database,
    )
    loaded = load_source_csv(
        settings.key_vault_url,
        settings.postgres_secret_name,
        dataset,
        settings.postgres_host,
        settings.postgres_database,
    )
    executor = AzureSqlExecutor(
        settings.key_vault_url,
        settings.sql_secret_name,
        settings.sql_server,
        settings.sql_database,
    )
    scripts = sorted(Path("sql/azure_sql").glob("*.sql"))
    for script in scripts:
        print(f"Executing {script}")
        executor.execute_file(script)
    print(f"Environment initialized: source={loaded}, Azure SQL scripts={len(scripts)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="comercial-andina")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate the synthetic OLTP dataset")
    generate.add_argument("--catalog", type=Path, default=Path("config/catalogs.json"))
    generate.add_argument("--output", type=Path, default=Path("data/generated/ventas_origen.csv"))
    generate.add_argument("--records", type=int, default=10_000)
    generate.add_argument("--seed", type=int, default=20260905)
    generate.add_argument("--processing-date", default=DEFAULT_PROCESSING_DATE.isoformat())
    generate.add_argument("--batch-id", default="BATCH-20260901-001")
    generate.set_defaults(handler=_generate)

    load_pg = subparsers.add_parser(
        "load-postgres", help="Create and load the Azure PostgreSQL source table"
    )
    load_pg.add_argument("--vault-url", required=True)
    load_pg.add_argument("--secret-name", default="postgres-credentials")
    load_pg.add_argument("--host", required=True)
    load_pg.add_argument("--database", default="comercial_andina")
    load_pg.add_argument("--ddl", type=Path, default=Path("sql/postgres/01_create_source.sql"))
    load_pg.add_argument("--input", type=Path, default=Path("data/generated/ventas_origen.csv"))
    load_pg.set_defaults(handler=_load_postgres)

    bootstrap = subparsers.add_parser(
        "bootstrap-azure-sql", help="Create Azure SQL schemas, tables, ETL and views"
    )
    bootstrap.add_argument("--vault-url", required=True)
    bootstrap.add_argument("--secret-name", default="sql-credentials")
    bootstrap.add_argument("--server", required=True)
    bootstrap.add_argument("--database", default="comercial_andina_dw")
    bootstrap.add_argument(
        "--sql-directory", type=Path, default=Path("sql/azure_sql")
    )
    bootstrap.set_defaults(handler=_bootstrap_azure_sql)

    pipeline = subparsers.add_parser("run-pipeline", help="Execute one controlled ETL batch")
    pipeline.add_argument("--batch-id")
    pipeline.set_defaults(handler=_run_pipeline)

    initialize = subparsers.add_parser(
        "initialize", help="Create schemas and load the controlled source dataset"
    )
    initialize.set_defaults(handler=_initialize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
