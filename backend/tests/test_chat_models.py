from claimlens.models import Case, ChatMessage, ChatThread, Fact, Finding, Proposal
from claimlens.settings import Settings


def test_old_fact_defaults_to_document():
    fact = Fact.model_validate({"value": 1, "page": 1, "quote": "q"})
    assert fact.source == "document"
    assert Fact(value=1, page=1, quote="q", source="reviewer").source == "reviewer"


def test_old_finding_not_removed():
    f = Finding.model_validate({"id": "f1", "check": "story", "code": "c", "severity": "low", "title": "t"})
    assert f.removed is False
    assert Finding(id="f2", check="reviewer", code="reviewer_note", severity="low", title="t").check == "reviewer"
    assert Case(id="c", owner_email="a@b.c").corrections == []


def test_proposal_defaults_pending():
    p = Proposal(id="p1", type="review_finding")
    assert p.status == "pending"
    assert p.reason == "" and p.finding_id is None and p.evidence is None
    assert p.decided_by is None and p.decided_at is None and p.error is None
    m = ChatMessage(id="m1", role="reviewer", text="hi", by="a@b.c")
    assert m.verified is True and m.proposals == [] and m.created_at is not None
    t = ChatThread(id="t1", created_by="a@b.c")
    assert t.status == "active" and t.summary == "" and t.carried_summary == ""


def test_chat_settings_defaults():
    s = Settings(_env_file=None)
    assert s.chat == "on"
    assert (s.chat_max_tools, s.chat_seconds, s.chat_history) == (6, 60, 20)
    assert (s.chat_max_chars, s.chat_daily_limit, s.chat_tool_chars) == (2000, 200, 8000)
