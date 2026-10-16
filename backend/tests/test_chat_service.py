import pytest

from claimlens.chat.model import FakeChat, Final
from claimlens.chat.service import ChatUnavailable, NotPending, ask, decide, get_or_create_thread, new_chat
from claimlens.pipeline.run import run_pipeline
from tests.test_pipeline import _deps, _new_case

BY = "a@x.com"


def _setup(tmp_path, script=()):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    deps.chat_ai = FakeChat(list(script))
    return deps, deps.db.get_case("c1")


def _final(proposals=()):
    return Final({"answer": "Because.", "citations": [], "proposals": list(proposals)})


def _dismiss_proposal(deps):
    fid = next(f for f in deps.db.get_findings("c1") if f.code == "editing_tool").id
    return {"id": "p1", "type": "review_finding", "finding_id": fid, "action": "dismiss", "reason": "ok"}


def test_ask_stores_both_messages(tmp_path):
    deps, case = _setup(tmp_path, [_final()])
    reply = ask(deps, case, "Why?", None, BY)
    thread = deps.db.active_thread("c1")
    msgs = deps.db.get_messages("c1", thread.id)
    assert [m.role for m in msgs] == ["reviewer", "assistant"]
    assert msgs[0].text == "Why?" and msgs[0].by == BY
    assert msgs[1].id == reply.id and reply.text == "Because."
    assert get_or_create_thread(deps, case, BY).id == thread.id


def test_failed_answer_stores_nothing(tmp_path):
    deps, case = _setup(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("503")

    deps.chat_ai.step = boom
    with pytest.raises(ChatUnavailable):
        ask(deps, case, "Why?", None, BY)
    thread = deps.db.active_thread("c1")
    assert thread is None or deps.db.get_messages("c1", thread.id) == []


def test_history_is_prior_messages_only(tmp_path):
    deps, case = _setup(tmp_path, [_final(), _final()])
    ask(deps, case, "one", None, BY)
    ask(deps, case, "two", None, BY)
    assert len(deps.db.get_messages("c1", deps.db.active_thread("c1").id)) == 4


def test_new_chat_carries_summary(tmp_path):
    deps, case = _setup(tmp_path, [_final()])
    ask(deps, case, "Why?", None, BY)
    old = deps.db.active_thread("c1")
    deps.chat_ai.summarise_thread = lambda messages: " ".join(["w"] * 200)
    fresh = new_chat(deps, case, BY)
    assert fresh.id != old.id and fresh.status == "active"
    assert len(fresh.carried_summary.split()) == 150
    closed = next(t for t in deps.db.list_threads("c1") if t.id == old.id)
    assert closed.status == "closed" and closed.summary == fresh.carried_summary
    assert deps.db.active_thread("c1").id == fresh.id


def test_new_chat_with_no_messages_has_empty_summary(tmp_path):
    deps, case = _setup(tmp_path)
    first = get_or_create_thread(deps, case, BY)
    fresh = new_chat(deps, case, BY)
    assert fresh.carried_summary == "" and fresh.id != first.id


def test_ignore_changes_nothing_else(tmp_path):
    deps, case = _setup(tmp_path)
    deps.chat_ai.script = [_final([_dismiss_proposal(deps)])]
    reply = ask(deps, case, "Dismiss?", None, BY)
    before = (deps.db.get_case("c1"), deps.db.get_findings("c1"))
    proposal, outcome = decide(deps, deps.db.get_case("c1"), reply.proposals[0].id, "ignore", "b@x.com")
    assert proposal.status == "ignored" and proposal.decided_by == "b@x.com" and outcome is None
    assert (deps.db.get_case("c1"), deps.db.get_findings("c1")) == before
    saved = deps.db.get_messages("c1", deps.db.active_thread("c1").id)[-1].proposals[0]
    assert saved.status == "ignored"


def test_second_decision_not_pending(tmp_path):
    deps, case = _setup(tmp_path)
    deps.chat_ai.script = [_final([_dismiss_proposal(deps)])]
    reply = ask(deps, case, "Dismiss?", None, BY)
    pid = reply.proposals[0].id
    proposal, outcome = decide(deps, case, pid, "apply", BY)
    assert proposal.status == "applied" and outcome is not None
    versions = len(deps.db.get_finding_versions("c1", proposal.finding_id))
    for decision in ("apply", "ignore"):
        with pytest.raises(NotPending):
            decide(deps, deps.db.get_case("c1"), pid, decision, BY)
    assert len(deps.db.get_finding_versions("c1", proposal.finding_id)) == versions
