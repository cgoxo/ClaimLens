import threading

import pytest
from fastapi.testclient import TestClient

from claimlens import jobs
from claimlens.db import LocalDb
from claimlens.deps import build_deps
from claimlens.main import create_app
from claimlens.models import Case
from claimlens.settings import Settings

URL = "https://claimlens.example.run.app"
SA = "claimlens-tasks@p.iam.gserviceaccount.com"


def _db(tmp_path, status="QUEUED", **kw):
    db = LocalDb(tmp_path)
    db.create_case(Case(id="c1", owner_email="a@x.com", status=status, **kw))
    return db


def test_inline_runs_handler(settings, monkeypatch):
    seen = []
    monkeypatch.setitem(jobs.HANDLERS, "echo", lambda payload, deps, attempt: seen.append((payload, attempt)))
    jobs.InlineJobs(None).enqueue("echo", {"x": 1})
    assert seen == [({"x": 1}, 0)]


def test_claim_run_rules(tmp_path):
    db = _db(tmp_path)
    assert db.claim_run("c1", 0) is True
    assert db.claim_run("c1", 0) is False  # same delivery again
    db.update_case("c1", status="READING")
    assert db.claim_run("c1", 1) is True  # a retry after the first instance died
    db.update_case("c1", status="READY")
    assert db.claim_run("c1", 5) is False


def test_claim_run_is_atomic(tmp_path):
    db = _db(tmp_path)
    wins, barrier = [], threading.Barrier(8)

    def go():
        barrier.wait()
        wins.append(db.claim_run("c1", 0))

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert wins.count(True) == 1


def test_run_case_job_runs_once(tmp_path, monkeypatch):
    db = _db(tmp_path)
    runs = []
    monkeypatch.setattr(jobs, "run_pipeline", lambda case_id, deps: runs.append(case_id))
    deps = type("D", (), {"db": db})()
    jobs.run_case_job({"case_id": "c1"}, deps, 0)
    jobs.run_case_job({"case_id": "c1"}, deps, 0)
    assert runs == ["c1"]


def _cloud_settings(tmp_path, **kw):
    return Settings(_env_file=None, data_dir=tmp_path, ai="fake", jobs="cloudtasks", tasks_sa=SA, service_url=URL, **kw)


def test_cloudtasks_builds_task(tmp_path):
    class Fake:
        def __init__(self):
            self.calls = []

        def create_task(self, parent, task):
            self.calls.append((parent, task))

    fake = Fake()
    jobs.CloudTasksJobs(_cloud_settings(tmp_path), client=fake).enqueue("run_case", {"case_id": "c1"})
    [(parent, task)] = fake.calls
    assert parent == "projects/social-pulse-510513/locations/asia-south1/queues/claimlens-jobs"
    req = task["http_request"]
    assert req["url"] == f"{URL}/internal/jobs/run_case"
    assert req["http_method"] == "POST" and req["body"] == b'{"case_id": "c1"}'
    assert req["oidc_token"] == {"service_account_email": SA, "audience": URL}
    assert task["dispatch_deadline"].seconds == 1800


def _cloud_client(tmp_path, monkeypatch, ok):
    settings = _cloud_settings(tmp_path)
    deps = build_deps(settings.model_copy(update={"jobs": "inline"}))  # no real Cloud Tasks client in tests
    monkeypatch.setattr(jobs, "verify_task_token", lambda header, s: ok)
    return TestClient(create_app(settings, deps))


def test_internal_endpoint_auth(tmp_path, monkeypatch):
    assert _cloud_client(tmp_path, monkeypatch, False).post("/internal/jobs/run_case", json={}).status_code == 403
    client = _cloud_client(tmp_path, monkeypatch, True)
    assert client.post("/internal/jobs/nope", json={}).status_code == 404
    seen = []
    monkeypatch.setitem(jobs.HANDLERS, "run_case", lambda payload, deps, attempt: seen.append((payload, attempt)))
    r = client.post("/internal/jobs/run_case", json={"case_id": "c1"}, headers={"X-CloudTasks-TaskRetryCount": "2"})
    assert r.status_code == 200 and seen == [({"case_id": "c1"}, 2)]


def test_internal_endpoint_off_in_thread_mode(settings):
    client = TestClient(create_app(settings.model_copy(update={"jobs": "thread"})))
    assert client.post("/internal/jobs/run_case", json={}).status_code == 404


def test_verify_task_token_rejects_garbage(tmp_path):
    assert jobs.verify_task_token("Bearer not-a-token", _cloud_settings(tmp_path)) is False
    assert jobs.verify_task_token("", _cloud_settings(tmp_path)) is False


def test_settings_cloudtasks_needs_sa_and_url(tmp_path):
    with pytest.raises(ValueError):
        Settings(_env_file=None, data_dir=tmp_path, jobs="cloudtasks")


def test_unknown_kind_needs_a_token_first(tmp_path, monkeypatch):
    # without a valid token, every kind looks the same: nothing to learn about which kinds exist
    assert _cloud_client(tmp_path, monkeypatch, False).post("/internal/jobs/nope", json={}).status_code == 403
