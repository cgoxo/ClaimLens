import pymupdf
import pytest

from tests.conftest import SAMPLES, upload_case
from tests.test_api import A, _client

POLICY = (SAMPLES / "policy.pdf").read_bytes()
CLAIM = (SAMPLES / "claim.pdf").read_bytes()
CARDS = [{"id": "claim-form", "role": "claim_form"}, {"id": "b1", "role": "bill", "kind": "hospital"},
         {"id": "policy", "role": "policy"}]


@pytest.fixture
def client(settings):
    return _client(settings)


def _draft(client, cards=CARDS):
    r = client.post("/api/cases", json={"cards": cards}, headers=A)
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


def _add(client, case_id, card_id, name, data):
    return client.post(f"/api/cases/{case_id}/files", data={"card_id": card_id},
                       files={"file": (name, data, "application/octet-stream")}, headers=A)


def _jpg():
    return pymupdf.open(stream=CLAIM, filetype="pdf")[3].get_pixmap(dpi=60).tobytes("jpeg")


def test_create_draft_and_layout_error(client):
    r = client.post("/api/cases", json={"cards": CARDS}, headers=A)
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"
    bad = client.post("/api/cases", json={"cards": [{"id": "b1", "role": "bill", "kind": "lab"}]}, headers=A)
    assert bad.status_code == 400 and "exactly one policy card" in bad.json()["detail"]


def test_file_rules(client):
    case_id = _draft(client)
    assert _add(client, case_id, "policy", "policy.jpg", _jpg()).status_code == 201
    assert _add(client, case_id, "zzz", "x.pdf", POLICY).status_code == 400
    assert _add(client, case_id, "b1", "big.pdf", b"x" * (21 * 1024 * 1024)).status_code == 400
    assert _add(client, case_id, "b1", "bill.docx", b"x").status_code == 400
    _add(client, case_id, "claim-form", "claim.pdf", CLAIM)
    assert client.post(f"/api/cases/{case_id}/submit", headers=A).status_code == 200
    assert _add(client, case_id, "b1", "late.pdf", POLICY).status_code == 409


def test_file_order_kept(client):
    case_id = _draft(client)
    assert _add(client, case_id, "b1", "one.pdf", POLICY).json() == {"card_id": "b1", "index": 0, "pages": 3}
    assert _add(client, case_id, "b1", "two.jpg", _jpg()).json() == {"card_id": "b1", "index": 1, "pages": 1}
    card = next(c for c in client.app.state.deps.db.get_case(case_id).cards if c.id == "b1")
    assert [f.key for f in card.files] == [f"cases/{case_id}/b1/0.pdf", f"cases/{case_id}/b1/1.jpg"]


def test_others_cannot_add_files(client):
    case_id = _draft(client)
    r = client.post(f"/api/cases/{case_id}/files", data={"card_id": "b1"},
                    files={"file": ("x.pdf", POLICY, "application/pdf")}, headers={"X-Dev-User": "b@x.com"})
    assert r.status_code == 404


def test_submit_rules(client, monkeypatch):
    case_id = _draft(client)
    _add(client, case_id, "b1", "bill.pdf", CLAIM)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "add the policy" in r.json()["detail"]

    case_id = _draft(client)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "add the claim documents" in r.json()["detail"]

    settings = client.app.state.deps.settings
    monkeypatch.setattr(settings, "max_files", 2)
    case_id = _draft(client)
    for name in ("a.pdf", "b.pdf"):
        _add(client, case_id, "b1", name, POLICY)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "more than 2 files" in r.json()["detail"]

    monkeypatch.setattr(settings, "max_files", 40)
    monkeypatch.setattr(settings, "max_pages", 5)
    case_id = _draft(client)
    _add(client, case_id, "b1", "claim.pdf", CLAIM)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "more than 5 pages" in r.json()["detail"]


def test_submit_queues_once(client):
    jobs = []
    client.app.state.deps.jobs = type("J", (), {"enqueue": lambda self, kind, payload: jobs.append((kind, payload))})()
    case_id = _draft(client)
    _add(client, case_id, "b1", "claim.pdf", CLAIM)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 200 and r.json() == {"case_id": case_id, "status": "QUEUED"}
    assert client.post(f"/api/cases/{case_id}/submit", headers=A).status_code == 409
    assert jobs == [("run_case", {"case_id": case_id})]


def test_empty_cards_dropped_at_submit(client):
    case_id = _draft(client)  # claim-form card stays empty
    _add(client, case_id, "b1", "claim.pdf", CLAIM)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert [c.id for c in client.app.state.deps.db.get_case(case_id).cards] == ["b1", "policy"]


def test_drafts_hidden_from_list(client):
    case_id = _draft(client)
    assert case_id not in [c["id"] for c in client.get("/api/cases", headers=A).json()]


def test_case_has_cards(client):
    case_id = upload_case(client).json()["case_id"]
    cards = client.get(f"/api/cases/{case_id}", headers=A).json()["cards"]
    assert [(c["id"], c["label"]) for c in cards] == [("claim-form", "Claim form"), ("policy", "Policy")]
    assert cards[0]["files"] == [{"name": "claim.pdf", "pages": 4}]
