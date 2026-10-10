import pymupdf
import pytest
from fastapi.testclient import TestClient

from claimlens.deps import build_deps
from claimlens.main import create_app
from claimlens.pipeline.run import run_pipeline
from tests.conftest import SAMPLES

A = {"X-Dev-User": "a@x.com"}


def _client(settings):
    deps = build_deps(settings)
    deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    app = create_app(settings, deps)
    app.state.start = run_pipeline  # run synchronously in tests
    return TestClient(app)


@pytest.fixture
def client(settings):
    return _client(settings)


def _files(claim=None, claim_name="claim.pdf"):
    return {"claim": (claim_name, claim or (SAMPLES / "claim.pdf").read_bytes(), "application/pdf"),
            "policy": ("policy.pdf", (SAMPLES / "policy.pdf").read_bytes(), "application/pdf")}


def _upload(client, headers=A, **kw):
    return client.post("/api/cases", files=_files(**kw), headers=headers)


def test_requires_dev_header(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=A).json() == {"email": "a@x.com"}


def test_upload_and_get_ready(client):
    r = _upload(client)
    assert r.status_code == 201 and r.json()["status"] == "QUEUED"
    case = client.get(f"/api/cases/{r.json()['case_id']}", headers=A).json()
    assert case["status"] == "READY"
    assert len(case["findings"]) == 9
    assert case["findings"][0]["severity"] == "critical"
    assert case["findings"][-1]["severity"] == "coverage"
    assert len(case["pages"]) == 7 and "text" not in case["pages"][0]


def test_page_png(client):
    cid = _upload(client).json()["case_id"]
    r = client.get(f"/api/cases/{cid}/pages/claim/3.png", headers=A)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get(f"/api/cases/{cid}/pages/claim/99.png", headers=A).status_code == 404


def test_review_finding(client):
    cid = _upload(client).json()["case_id"]
    fid = client.get(f"/api/cases/{cid}", headers=A).json()["findings"][0]["id"]
    r = client.post(f"/api/cases/{cid}/findings/{fid}/review", json={"action": "accept", "note": "ok"}, headers=A)
    assert r.status_code == 200
    assert r.json()["review"]["action"] == "accept" and r.json()["review"]["by"] == "a@x.com"
    assert client.post(f"/api/cases/{cid}/findings/nope/review", json={"action": "accept"}, headers=A).status_code == 404
    assert client.post(f"/api/cases/{cid}/findings/{fid}/review", json={"action": "maybe"}, headers=A).status_code == 422


def test_other_users_case_404(client):
    cid = _upload(client).json()["case_id"]
    assert client.get(f"/api/cases/{cid}", headers={"X-Dev-User": "b@x.com"}).status_code == 404
    assert client.get(f"/api/cases/{cid}/pages/claim/1.png", headers={"X-Dev-User": "b@x.com"}).status_code == 404


def test_list_cases_only_mine(client):
    _upload(client)
    _upload(client, headers={"X-Dev-User": "b@x.com"})
    mine = client.get("/api/cases", headers=A).json()
    assert len(mine) == 1 and set(mine[0]) == {"id", "status", "risk", "score", "created_at"}


def test_bad_file_400(client):
    r = _upload(client, claim=b"just some text")
    assert r.status_code == 400 and "claim" in r.json()["detail"]


def test_encrypted_pdf_400(client, tmp_path):
    doc = pymupdf.open(SAMPLES / "claim.pdf")
    out = tmp_path / "locked.pdf"
    doc.save(out, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    r = _upload(client, claim=out.read_bytes())
    assert r.status_code == 400 and "password" in r.json()["detail"]


def test_wrong_type_400(client):
    assert _upload(client, claim_name="claim.docx").status_code == 400


def test_too_many_pages_400(settings):
    c = _client(settings.model_copy(update={"max_pages": 2}))
    assert _upload(c).status_code == 400


def test_daily_limit_429(settings):
    c = _client(settings.model_copy(update={"daily_case_limit": 1}))
    assert _upload(c).status_code == 201
    assert _upload(c).status_code == 429


def test_firebase_mode(settings, monkeypatch):
    import claimlens.auth as auth

    s = settings.model_copy(update={"auth_mode": "firebase", "allowed_emails": ["a@b.com"]})
    c = _client(s)
    assert c.get("/api/me").status_code == 401
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token, project: {"email": "x@y.com", "email_verified": True})
    assert c.get("/api/me", headers={"Authorization": "Bearer t"}).status_code == 403
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token, project: {"email": "A@B.com", "email_verified": True})
    assert c.get("/api/me", headers={"Authorization": "Bearer t"}).json() == {"email": "a@b.com"}
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token, project: (_ for _ in ()).throw(ValueError("bad")))
    assert c.get("/api/me", headers={"Authorization": "Bearer t"}).status_code == 401
