import pytest

from comercial_andina.settings import AzureSettings


def test_settings_never_default_credentials(monkeypatch):
    variables = [
        "CA_STORAGE_ACCOUNT",
        "CA_KEY_VAULT_URL",
        "CA_POSTGRES_HOST",
        "CA_SQL_SERVER",
    ]
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValueError, match="Missing required"):
        AzureSettings.from_environment()
