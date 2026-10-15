import pymupdf
import pytest

from tests.conftest import SAMPLES, upload_case
from tests.test_api import A, _client

POLICY = (SAMPLES / "policy.pdf").read_bytes()
CLAIM = (SAMPLES / "claim.pdf").read_bytes()
CARDS = [{"id": "claim", "role": "claim"}, {"id": "policy", "role": "policy"}]


@pytest.fixture
def client(settings):
    return _client(settings)


def _draft(client, cards=CARDS):
    r = client.post("/api/cases", json={"cards": cards}, headers=A)
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


def _add(client, case_id, card_id, name, data, client_id=None):
    form = {"card_id": card_id, **({"client_id": client_id} if client_id else {})}
    return client.post(f"/api/cases/{case_id}/files", data=form,
                       files={"file": (name, data, "application/octet-stream")}, headers=A)


def _jpg():
    return pymupdf.open(stream=CLAIM, filetype="pdf")[3].get_pixmap(dpi=60).tobytes("jpeg")


def test_create_draft_and_layout_error(client):
    r = client.post("/api/cases", json={"cards": CARDS}, headers=A)
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"
    bad = client.post("/api/cases", json={"cards": [{"id": "claim", "role": "claim"}]}, headers=A)
    assert bad.status_code == 400 and "exactly one policy card" in bad.json()["detail"]


def test_file_rules(client):
    case_id = _draft(client)
    assert _add(client, case_id, "policy", "policy.jpg", _jpg()).status_code == 201
    assert _add(client, case_id, "zzz", "x.pdf", POLICY).status_code == 400
    assert _add(client, case_id, "claim", "big.pdf", b"x" * (21 * 1024 * 1024)).status_code == 400
    assert _add(client, case_id, "claim", "bill.docx", b"x").status_code == 400
    _add(client, case_id, "claim", "claim.pdf", CLAIM)
    assert client.post(f"/api/cases/{case_id}/submit", headers=A).status_code == 200
    assert _add(client, case_id, "claim", "late.pdf", POLICY).status_code == 409


def test_file_order_kept(client):
    case_id = _draft(client)
    assert _add(client, case_id, "claim", "one.pdf", POLICY).json() == {"card_id": "claim", "index": 0, "pages": 3}
    assert _add(client, case_id, "claim", "two.jpg", _jpg()).json() == {"card_id": "claim", "index": 1, "pages": 1}
    card = next(c for c in client.app.state.deps.db.get_case(case_id).cards if c.id == "claim")
    assert [f.name for f in card.files] == ["one.pdf", "two.jpg"]


def test_others_cannot_add_files(client):
    case_id = _draft(client)
    r = client.post(f"/api/cases/{case_id}/files", data={"card_id": "claim"},
                    files={"file": ("x.pdf", POLICY, "application/pdf")}, headers={"X-Dev-User": "b@x.com"})
    assert r.status_code == 404


def test_submit_rules(client, monkeypatch):
    case_id = _draft(client)
    _add(client, case_id, "claim", "bill.pdf", CLAIM)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "add the policy" in r.json()["detail"]

    case_id = _draft(client)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 400 and "add the claim documents" in r.json()["detail"]



def test_submit_queues_once(client):
    jobs = []
    client.app.state.deps.jobs = type("J", (), {"enqueue": lambda self, kind, payload: jobs.append((kind, payload))})()
    case_id = _draft(client)
    _add(client, case_id, "claim", "claim.pdf", CLAIM)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    r = client.post(f"/api/cases/{case_id}/submit", headers=A)
    assert r.status_code == 200 and r.json() == {"case_id": case_id, "status": "QUEUED"}
    assert client.post(f"/api/cases/{case_id}/submit", headers=A).status_code == 409
    assert jobs == [("run_case", {"case_id": case_id})]


def test_drafts_hidden_from_list(client):
    case_id = _draft(client)
    assert case_id not in [c["id"] for c in client.get("/api/cases", headers=A).json()]


def test_case_has_cards(client):
    case_id = upload_case(client).json()["case_id"]
    cards = client.get(f"/api/cases/{case_id}", headers=A).json()["cards"]
    assert [(c["id"], c["label"]) for c in cards] == [("claim", "Claim"), ("policy", "Policy")]
    assert cards[0]["files"] == [{"name": "claim.pdf", "pages": 4}]


def test_file_limits_are_enforced_at_upload(client, monkeypatch):
    settings = client.app.state.deps.settings
    monkeypatch.setattr(settings, "max_files", 2)
    case_id = _draft(client)
    assert _add(client, case_id, "claim", "a.pdf", POLICY).status_code == 201
    assert _add(client, case_id, "policy", "p.pdf", POLICY).status_code == 201
    r = _add(client, case_id, "claim", "c.pdf", POLICY)
    assert r.status_code == 400 and "at most 2 files" in r.json()["detail"]
    monkeypatch.setattr(settings, "max_files", 40)
    monkeypatch.setattr(settings, "max_pages", 7)
    r = _add(client, case_id, "claim", "claim.pdf", CLAIM)  # 3 + 3 + 4 pages
    assert r.status_code == 400 and "at most 7 pages" in r.json()["detail"]


def test_same_file_sent_twice_is_kept_once(client):
    # the response to the first upload was lost, so the browser sends the same file again
    case_id = _draft(client)
    first = _add(client, case_id, "claim", "bill.pdf", CLAIM, client_id="f-123").json()
    again = _add(client, case_id, "claim", "bill.pdf", CLAIM, client_id="f-123").json()
    assert first == again == {"card_id": "claim", "index": 0, "pages": 4}
    assert len(client.app.state.deps.db.get_case(case_id).cards[0].files) == 1


def test_concurrent_uploads_keep_every_file(client):
    from concurrent.futures import ThreadPoolExecutor

    case_id = _draft(client)
    with ThreadPoolExecutor(6) as pool:
        codes = list(pool.map(lambda i: _add(client, case_id, "claim", f"{i}.pdf", POLICY).status_code, range(6)))
    files = client.app.state.deps.db.get_case(case_id).cards[0].files
    assert codes == [201] * 6 and len({f.key for f in files}) == 6


def test_failed_enqueue_leaves_the_case_a_draft(client):
    class Down:
        def enqueue(self, kind, payload):
            raise RuntimeError("tasks api unavailable")

    client.app.state.deps.jobs = Down()
    case_id = _draft(client)
    _add(client, case_id, "claim", "claim.pdf", CLAIM)
    _add(client, case_id, "policy", "policy.pdf", POLICY)
    assert client.post(f"/api/cases/{case_id}/submit", headers=A).status_code == 503
    assert client.app.state.deps.db.get_case(case_id).status == "DRAFT"
