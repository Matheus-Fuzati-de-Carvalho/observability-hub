import json
from unittest.mock import MagicMock, patch

from observability_hub.core import secrets


def _fake_secret_client(payload: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.payload.data = payload.encode("utf-8")
    client.access_secret_version.return_value = response
    return client


def test_get_secret_reads_latest_version_by_project():
    fake_client = _fake_secret_client("shhh")
    with (
        patch("observability_hub.core.secrets.get_runtime_project", return_value="proj-dev"),
        patch(
            "observability_hub.core.secrets.secretmanager.SecretManagerServiceClient",
            return_value=fake_client,
        ),
    ):
        result = secrets.get_secret("SOME_SECRET")

    assert result == "shhh"
    fake_client.access_secret_version.assert_called_once_with(
        name="projects/proj-dev/secrets/SOME_SECRET/versions/latest"
    )


def test_get_secret_is_cached_per_process():
    fake_client = _fake_secret_client("value")
    with (
        patch("observability_hub.core.secrets.get_runtime_project", return_value="proj-dev"),
        patch(
            "observability_hub.core.secrets.secretmanager.SecretManagerServiceClient",
            return_value=fake_client,
        ),
    ):
        secrets.get_secret("SOME_SECRET")
        secrets.get_secret("SOME_SECRET")

    assert fake_client.access_secret_version.call_count == 1


def test_get_oauth_client_id_uses_dev_suffix_when_not_prod():
    with (
        patch(
            "observability_hub.core.secrets.get_runtime_project",
            return_value="observability-hub-dev",
        ),
        patch("observability_hub.core.secrets.get_secret", return_value="client-id") as mock_get,
    ):
        secrets.get_oauth_client_id()

    mock_get.assert_called_once_with("GOOGLE_OAUTH_CLIENT_ID_DEV")


def test_get_oauth_client_secret_uses_prod_suffix_when_prod():
    with (
        patch(
            "observability_hub.core.secrets.get_runtime_project",
            return_value="observability-hub-prod",
        ),
        patch("observability_hub.core.secrets.get_secret", return_value="secret") as mock_get,
    ):
        secrets.get_oauth_client_secret()

    mock_get.assert_called_once_with("GOOGLE_OAUTH_CLIENT_SECRET_PROD")


def test_jwt_secret_and_allowlist_use_unsuffixed_names():
    with patch("observability_hub.core.secrets.get_secret") as mock_get:
        mock_get.return_value = "shared-secret"
        secrets.get_jwt_secret()
        mock_get.assert_called_with("JWT_SECRET")

        mock_get.return_value = json.dumps(
            {"allowed_domains": ["dp6.com.br"], "allowed_emails": []}
        )
        allowlist = secrets.get_oauth_allowlist()
        mock_get.assert_called_with("OAUTH_ALLOWLIST")

    assert allowlist == {"allowed_domains": ["dp6.com.br"], "allowed_emails": []}
