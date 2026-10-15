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


def test_gemini_retries_rate_limits_then_succeeds(monkeypatch):
    from google.genai import errors

    import claimlens.ai as ai

    sleeps = []
    monkeypatch.setattr(ai.time, "sleep", lambda s: sleeps.append(s))

    class Models:
        calls = 0

        def generate_content(self, **kw):
            Models.calls += 1
            if Models.calls <= 2:
                raise errors.ClientError(429, {"error": {"code": 429, "message": "busy", "status": "RESOURCE_EXHAUSTED"}})
            return type("R", (), {"text": "ok"})()

    g = ai.VertexGemini.__new__(ai.VertexGemini)
    g.client, g.model = type("C", (), {"models": Models()})(), "m"
    assert g._ask("system", "text") == "ok" and len(sleeps) == 2 and sleeps[1] > sleeps[0]


def test_gemini_does_not_retry_a_bad_request(monkeypatch):
    from google.genai import errors

    import claimlens.ai as ai
    import pytest

    monkeypatch.setattr(ai.time, "sleep", lambda s: None)

    class Models:
        def generate_content(self, **kw):
            raise errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})

    g = ai.VertexGemini.__new__(ai.VertexGemini)
    g.client, g.model = type("C", (), {"models": Models()})(), "m"
    with pytest.raises(errors.ClientError):
        g._ask("system", "text")
