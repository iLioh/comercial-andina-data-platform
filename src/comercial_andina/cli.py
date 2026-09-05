"""Local command-line entry points for repeatable project operations."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

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


def _load_rds(args: argparse.Namespace) -> int:
    from comercial_andina.etl.rds import execute_source_ddl, load_source_csv

    execute_source_ddl(
        args.secret_arn, args.region, args.ddl, args.host, args.database
    )
    count = load_source_csv(
        args.secret_arn, args.region, args.input, args.host, args.database
    )
    print(f"Loaded {count} rows into oltp.ventas_origen")
    return 0


def _bootstrap_redshift(args: argparse.Namespace) -> int:
    from comercial_andina.etl.redshift import RedshiftDataExecutor

    executor = RedshiftDataExecutor(
        args.region,
        args.workgroup,
        args.database,
        args.secret_arn,
    )
    scripts = sorted(args.sql_directory.glob("*.sql"))
    if not scripts:
        raise ValueError(f"No SQL scripts found in {args.sql_directory}")
    for script in scripts:
        print(f"Executing {script}")
        executor.execute_file(script)
    print(f"Applied {len(scripts)} Redshift scripts")
    return 0


def _run_pipeline(args: argparse.Namespace) -> int:
    from comercial_andina.etl.pipeline import run_daily_pipeline
    from comercial_andina.settings import AwsSettings

    result = run_daily_pipeline(AwsSettings.from_environment(), args.batch_id)
    print(f"Pipeline completed: {result}")
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

    load_rds = subparsers.add_parser("load-rds", help="Create and load the RDS source table")
    load_rds.add_argument("--secret-arn", required=True)
    load_rds.add_argument("--host", required=True)
    load_rds.add_argument("--database", default="comercial_andina")
    load_rds.add_argument("--region", default="us-east-1")
    load_rds.add_argument("--ddl", type=Path, default=Path("sql/rds/01_create_source.sql"))
    load_rds.add_argument("--input", type=Path, default=Path("data/generated/ventas_origen.csv"))
    load_rds.set_defaults(handler=_load_rds)

    bootstrap = subparsers.add_parser(
        "bootstrap-redshift", help="Create Redshift schemas, tables, ETL and views"
    )
    bootstrap.add_argument("--secret-arn", required=True)
    bootstrap.add_argument("--region", default="us-east-1")
    bootstrap.add_argument("--workgroup", required=True)
    bootstrap.add_argument("--database", default="comercial_andina_dw")
    bootstrap.add_argument(
        "--sql-directory", type=Path, default=Path("sql/redshift")
    )
    bootstrap.set_defaults(handler=_bootstrap_redshift)

    pipeline = subparsers.add_parser("run-pipeline", help="Execute one controlled ETL batch")
    pipeline.add_argument("--batch-id")
    pipeline.set_defaults(handler=_run_pipeline)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
