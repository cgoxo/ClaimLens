import pytest
from fastapi.testclient import TestClient

from claimlens.chat.model import FakeChat, Final
from claimlens.deps import build_deps
from claimlens.main import create_app
from tests.conftest import upload_case

A = {"X-Dev-User": "a@x.com"}
B = {"X-Dev-User": "b@x.com"}


def _final(proposals=()):
    return Final({"answer": "Because.", "citations": [], "proposals": list(proposals)})


@pytest.fixture
def app(settings):
    return create_app(settings, build_deps(settings))


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def case_id(client):
    r = upload_case(client, A)
    assert r.status_code < 300, r.text
    return r.json()["case_id"]


def _url(cid, tail=""):
    return f"/api/cases/{cid}/chat{tail}"


def _ask(client, cid, body):
    return client.post(_url(cid, "/messages"), json=body, headers=A)


def _ask_proposal(app, client, cid):
    """Ask a question whose answer proposes dismissing a finding; return the stored proposal id."""
    app.state.deps.chat_ai = FakeChat([_final([_proposal(app, cid)])])
    reply = _ask(client, cid, {"text": "dismiss it"}).json()
    assert len(reply["proposals"]) == 1
    return reply["proposals"][0]["id"]


def _proposal(app, cid):
    fid = next(f for f in app.state.deps.db.get_findings(cid) if f.code == "editing_tool").id
    return {"id": "p1", "type": "review_finding", "finding_id": fid, "action": "dismiss", "reason": "ok"}


def test_other_user_404(client, case_id):
    assert client.get(_url(case_id), headers=B).status_code == 404
    assert client.post(_url(case_id, "/messages"), json={"text": "hi"}, headers=B).status_code == 404
    assert client.post(_url(case_id, "/new"), headers=B).status_code == 404
    assert client.post(_url(case_id, "/proposals/p1/apply"), headers=B).status_code == 404


def test_not_ready_409(client):
    cid = client.post("/api/cases", json={"cards": [{"id": "claim", "role": "claim"},
                                                     {"id": "policy", "role": "policy"}]},
                      headers=A).json()["case_id"]
    assert client.get(_url(cid), headers=A).status_code == 409
    assert _ask(client, cid, {"text": "hi"}).status_code == 409


def test_chat_off_404(settings):
    off = settings.model_copy(update={"chat": "off"})
    client = TestClient(create_app(off, build_deps(off)))
    cid = upload_case(client, A).json()["case_id"]
    assert client.get(_url(cid), headers=A).status_code == 404
    assert _ask(client, cid, {"text": "hi"}).status_code == 404
    assert client.post(_url(cid, "/new"), headers=A).status_code == 404


def test_ask_and_get(app, client, case_id):
    app.state.deps.chat_ai = FakeChat([_final()])
    r = _ask(client, case_id, {"text": "Why?"})
    assert r.status_code == 200 and r.json()["text"] == "Because."
    got = client.get(_url(case_id), headers=A).json()
    assert [m["role"] for m in got["messages"]] == ["reviewer", "assistant"]
    assert got["thread"]["status"] == "active" and got["previous"] == []


def test_empty_get(app, client, case_id):
    got = client.get(_url(case_id), headers=A).json()
    assert got == {"thread": None, "messages": [], "previous": []}
    assert app.state.deps.db.active_thread(case_id) is None  # a GET creates nothing


def test_new_chat_survives_summary_failure(app, client, case_id):
    app.state.deps.chat_ai = FakeChat([_final()])
    _ask(client, case_id, {"text": "Why?"})

    def boom(messages):
        raise RuntimeError("503")

    app.state.deps.chat_ai.summarise_thread = boom
    r = client.post(_url(case_id, "/new"), headers=A)
    assert r.status_code == 200
    assert r.json()["carried_summary"] == "Earlier chat of 2 messages; summary unavailable."
    got = client.get(_url(case_id), headers=A).json()
    assert got["thread"]["id"] == r.json()["id"] and len(got["previous"]) == 1


def test_huge_text_rejected(client, case_id):
    assert _ask(client, case_id, {"text": " " * 20001}).status_code in (400, 422)


def test_non_finite_selection_400(app, client, case_id):
    page = app.state.deps.db.get_pages(case_id)[0]
    for bbox in ("[0, 0, Infinity, 10]", "[NaN, 0, 10, 10]"):
        body = '{"text": "x", "selection": {"doc": "%s", "page": %d, "bbox": %s}}' % (page.doc, page.page, bbox)
        r = client.post(_url(case_id, "/messages"), content=body,
                        headers={**A, "Content-Type": "application/json"})
        assert r.status_code == 400, bbox


def test_too_long_400(client, case_id):
    assert _ask(client, case_id, {"text": "   "}).status_code == 400
    assert _ask(client, case_id, {"text": "x" * 2001}).status_code == 400


def test_bad_selection_400(app, client, case_id):
    app.state.deps.chat_ai = FakeChat([_final()])
    page = app.state.deps.db.get_pages(case_id)[0]
    w, h = page.width, page.height

    def sel(doc=page.doc, pg=page.page, bbox=(0, 0, 10, 10)):
        return {"text": "what is this", "selection": {"doc": doc, "page": pg, "bbox": list(bbox)}}

    for bad in (sel(bbox=(5, 5, 5, 20)), sel(bbox=(5, 5, 20, 5)), sel(bbox=(10, 0, 5, 10)),
                sel(bbox=(0, 0, w + 1, 10)), sel(bbox=(0, 0, 10, h + 1)), sel(bbox=(-1, 0, 10, 10)),
                sel(pg=999), sel(doc="nope")):
        r = _ask(client, case_id, bad)
        assert r.status_code == 400 and r.json()["detail"], bad
    assert _ask(client, case_id, sel()).status_code == 200


def test_daily_limit_429(app, client, case_id):
    app.state.deps.settings = app.state.deps.settings.model_copy(update={"chat_daily_limit": 1})
    app.state.deps.chat_ai = FakeChat([_final(), _final(), _final()])
    assert _ask(client, case_id, {"text": "one"}).status_code == 200
    assert _ask(client, case_id, {"text": "two"}).status_code == 429


def test_unavailable_503(app, client, case_id):
    def boom(*a, **k):
        raise RuntimeError("down")

    app.state.deps.chat_ai.step = boom
    r = _ask(client, case_id, {"text": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "Couldn't answer right now, try again"


def test_apply_twice_409(app, client, case_id):
    pid = _ask_proposal(app, client, case_id)
    url = _url(case_id, f"/proposals/{pid}/apply")
    assert client.post(url, headers=A).status_code == 200
    assert client.post(url, headers=A).status_code == 409
    assert client.post(_url(case_id, f"/proposals/{pid}/ignore"), headers=A).status_code == 409
    assert client.post(_url(case_id, "/proposals/nope/apply"), headers=A).status_code == 404


def test_apply_returns_current(app, client, case_id):
    pid = _ask_proposal(app, client, case_id)
    r = client.post(_url(case_id, f"/proposals/{pid}/apply"), headers=A).json()
    assert r["proposal"]["status"] == "applied"
    assert r["current"] is not None and "score" in r["current"]


def test_ignore_returns_no_current(app, client, case_id):
    pid = _ask_proposal(app, client, case_id)
    r = client.post(_url(case_id, f"/proposals/{pid}/ignore"), headers=A).json()
    assert r["proposal"]["status"] == "ignored" and r["current"] is None


def test_new_chat_route(app, client, case_id):
    app.state.deps.chat_ai = FakeChat([_final()])
    _ask(client, case_id, {"text": "Why?"})
    first = client.get(_url(case_id), headers=A).json()["thread"]
    fresh = client.post(_url(case_id, "/new"), headers=A).json()
    assert fresh["id"] != first["id"] and fresh["carried_summary"] == "Summary."
    got = client.get(_url(case_id), headers=A).json()
    assert got["thread"]["id"] == fresh["id"] and got["messages"] == []
    assert [p["id"] for p in got["previous"]] == [first["id"]]
    assert got["previous"][0]["summary"] == "Summary." and "created_at" in got["previous"][0]
