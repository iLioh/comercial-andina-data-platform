"""Amazon Redshift Serverless Data API execution."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


class RedshiftDataExecutor:
    """Execute and monitor SQL without storing database passwords locally."""

    def __init__(
        self,
        region: str,
        workgroup: str,
        database: str,
        secret_arn: str,
    ) -> None:
        import boto3

        self.client = boto3.client("redshift-data", region_name=region)
        self.workgroup = workgroup
        self.database = database
        self.secret_arn = secret_arn

    def execute(self, sql: str, timeout_seconds: int = 600) -> dict[str, Any]:
        response = self.client.execute_statement(
            WorkgroupName=self.workgroup,
            Database=self.database,
            SecretArn=self.secret_arn,
            Sql=sql,
        )
        statement_id = response["Id"]
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = self.client.describe_statement(Id=statement_id)
            if status["Status"] == "FINISHED":
                return status
            if status["Status"] in {"FAILED", "ABORTED"}:
                raise RuntimeError(status.get("Error", f"Redshift statement {status['Status']}"))
            time.sleep(2)
        self.client.cancel_statement(Id=statement_id)
        raise TimeoutError(f"Redshift statement exceeded {timeout_seconds} seconds")

    def execute_file(self, sql_path: str | Path) -> None:
        """Execute every complete SQL statement in a repository script."""

        import sqlparse

        sql = Path(sql_path).read_text(encoding="utf-8")
        for statement in sqlparse.split(sql):
            if statement.strip():
                self.execute(statement)
