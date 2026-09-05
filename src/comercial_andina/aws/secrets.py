"""AWS Secrets Manager access."""

from __future__ import annotations

import json
from typing import Any


def get_json_secret(secret_arn: str, region: str) -> dict[str, Any]:
    """Retrieve and decode a JSON secret at runtime."""

    import boto3

    response = boto3.client("secretsmanager", region_name=region).get_secret_value(
        SecretId=secret_arn
    )
    if "SecretString" not in response:
        raise ValueError("Binary secrets are not supported by this pipeline")
    return json.loads(response["SecretString"])
