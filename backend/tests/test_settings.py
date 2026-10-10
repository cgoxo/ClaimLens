import pytest
from fastapi.testclient import TestClient

from claimlens.main import create_app
from claimlens.settings import Settings


def test_defaults_are_local(settings):
    assert settings.storage == "local"
    assert settings.db == "local"
    assert settings.auth_mode == "dev"


def test_gcs_requires_bucket(settings):
    with pytest.raises(ValueError):
        Settings(_env_file=None, storage="gcs", bucket=None)


def test_dev_auth_refused_in_prod(settings):
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="prod", auth_mode="dev")


def test_no_allow_list_setting(settings):
    assert not hasattr(settings, "allowed_emails")


def test_health(settings):
    client = TestClient(create_app(settings))
    assert client.get("/health").json() == {"ok": True}
