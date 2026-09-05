"""Environment-based runtime configuration with no embedded credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AwsSettings:
    """Identifiers required by the AWS ETL runtime."""

    region: str
    raw_bucket: str
    rds_host: str
    rds_database: str
    rds_secret_arn: str
    redshift_workgroup: str
    redshift_database: str
    redshift_secret_arn: str

    @classmethod
    def from_environment(cls) -> AwsSettings:
        values = {
            "region": os.getenv("AWS_REGION", "us-east-1"),
            "raw_bucket": os.getenv("CA_RAW_BUCKET", ""),
            "rds_host": os.getenv("CA_RDS_HOST", ""),
            "rds_database": os.getenv("CA_RDS_DATABASE", "comercial_andina"),
            "rds_secret_arn": os.getenv("CA_RDS_SECRET_ARN", ""),
            "redshift_workgroup": os.getenv("CA_REDSHIFT_WORKGROUP", ""),
            "redshift_database": os.getenv("CA_REDSHIFT_DATABASE", "comercial_andina_dw"),
            "redshift_secret_arn": os.getenv("CA_REDSHIFT_SECRET_ARN", ""),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment settings: {', '.join(missing)}")
        return cls(**values)
