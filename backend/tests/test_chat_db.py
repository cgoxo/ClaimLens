from datetime import timedelta

import pytest

from claimlens.db import LocalDb
from claimlens.models import ChatMessage, ChatThread, Proposal, now


@pytest.fixture
def db(tmp_path):
    return LocalDb(tmp_path / "db")


def _msg(id, role="reviewer", by="a@x.com", at=None, **kw):
    return ChatMessage(id=id, role=role, text="hi", by=by, created_at=at or now(), **kw)


def test_thread_lifecycle(db):
    assert db.active_thread("c1") is None
    db.create_thread("c1", ChatThread(id="t1", created_by="a@x.com"))
    assert db.active_thread("c1").id == "t1"
    db.close_thread("c1", "t1", "All done.")
    assert db.active_thread("c1") is None
    [thread] = db.list_threads("c1")
    assert thread.status == "closed" and thread.summary == "All done."


def test_list_threads_newest_first(db):
    t0 = now()
    db.create_thread("c1", ChatThread(id="old", created_by="a", created_at=t0 - timedelta(hours=1)))
    db.create_thread("c1", ChatThread(id="new", created_by="a", created_at=t0))
    assert [t.id for t in db.list_threads("c1")] == ["new", "old"]


def test_messages_ordered(db):
    db.create_thread("c1", ChatThread(id="t1", created_by="a"))
    t0 = now()
    db.add_message("c1", "t1", _msg("m2", at=t0 + timedelta(seconds=2)))
    db.add_message("c1", "t1", _msg("m1", at=t0))
    assert [m.id for m in db.get_messages("c1", "t1")] == ["m1", "m2"]
    assert db.get_messages("c1", "nope") == []


def test_update_proposal_persists_status(db):
    db.create_thread("c1", ChatThread(id="t1", created_by="a"))
    prop = Proposal(id="p1", type="set_severity", finding_id="f1", severity="high")
    db.add_message("c1", "t1", _msg("m1", role="assistant", proposals=[prop]))
    db.update_proposal("c1", "t1", "m1", prop.model_copy(update={"status": "applied", "decided_by": "a@x.com"}))
    [m] = db.get_messages("c1", "t1")
    assert m.proposals[0].status == "applied" and m.proposals[0].decided_by == "a@x.com"


def test_count_messages_since(db):
    t0 = now()
    since = t0 - timedelta(hours=1)
    db.create_thread("c1", ChatThread(id="t1", created_by="a"))
    db.create_thread("c2", ChatThread(id="t2", created_by="a"))
    db.add_message("c1", "t1", _msg("m1", at=t0))
    db.add_message("c2", "t2", _msg("m2", at=t0))
    db.add_message("c1", "t1", _msg("m3", at=t0 - timedelta(days=1)))
    db.add_message("c1", "t1", _msg("m4", role="assistant", by="assistant", at=t0))
    db.add_message("c1", "t1", _msg("m5", by="b@x.com", at=t0))
    assert db.count_messages_since("a@x.com", since) == 2
