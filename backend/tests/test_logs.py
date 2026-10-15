import json
import logging

import pytest

from claimlens import logs
from tests.test_api import A, _client


@pytest.fixture
def client(settings):
    return _client(settings)


def _requests(caplog):
    return [r for r in caplog.records if r.name == "claimlens.request"]


def test_api_request_logged_with_user(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/api/me", headers=A)
    [r] = _requests(caplog)
    assert (r.user, r.status, r.path, r.method, r.case_id) == ("a@x.com", 200, "/api/me", "GET", None)
    assert isinstance(r.latency_ms, int)


def test_case_id_extracted(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/api/cases/nope", headers=A)
    [r] = _requests(caplog)
    assert (r.case_id, r.status, r.levelname) == ("nope", 404, "WARNING")


def test_unauthenticated_logs_null_user(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/api/me")
    [r] = _requests(caplog)
    assert (r.user, r.status) == (None, 401)


def test_health_and_static_not_logged(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/health")
    assert _requests(caplog) == []


def test_json_formatter():
    record = logging.LogRecord("claimlens.request", logging.WARNING, __file__, 1, "GET /api/x 404", None, None)
    record.user, record.status = "a@x.com", 404
    out = json.loads(logs.JsonFormatter().format(record))
    assert out["severity"] == "WARNING"
    assert (out["message"], out["user"], out["status"]) == ("GET /api/x 404", "a@x.com", 404)


def test_pipeline_failure_logged_with_owner(tmp_path, caplog):
    from claimlens.ai import FakeAi
    from claimlens.pipeline.run import run_pipeline
    from tests.conftest import FAKE_AI
    from tests.test_pipeline import _deps, _new_case

    class Boom(FakeAi):
        def extract_facts(self, claim_text):
            raise RuntimeError("boom")

    deps = _deps(tmp_path, ai=Boom(FAKE_AI))
    run_pipeline(_new_case(deps), deps)
    [r] = [r for r in caplog.records if "failed during" in r.getMessage()]
    assert (r.case_id, r.user) == ("c1", "a@x.com")


def test_unhandled_error_logged_as_500_with_user(settings, caplog):
    from fastapi.testclient import TestClient

    from claimlens.deps import build_deps
    from claimlens.main import create_app

    deps = build_deps(settings)
    deps.db.list_cases = lambda owner: (_ for _ in ()).throw(RuntimeError("db down"))
    client = TestClient(create_app(settings, deps), raise_server_exceptions=False)
    caplog.set_level(logging.INFO)
    assert client.get("/api/cases", headers=A).status_code == 500
    [r] = _requests(caplog)
    assert (r.status, r.user, r.levelname) == (500, "a@x.com", "ERROR")
    assert r.exc_info and str(r.exc_info[1]) == "db down"
