import pytest

from comercial_andina.settings import AwsSettings


def test_settings_never_default_credentials(monkeypatch):
    variables = [
        "CA_RAW_BUCKET",
        "CA_RDS_HOST",
        "CA_RDS_SECRET_ARN",
        "CA_REDSHIFT_WORKGROUP",
        "CA_REDSHIFT_SECRET_ARN",
    ]
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValueError, match="Missing required"):
        AwsSettings.from_environment()
