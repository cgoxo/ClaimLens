from claimlens.chat.answer import FAILED, answer, resolve_fact
from claimlens.chat.model import FakeChat, Final, ToolCall
from claimlens.models import Box, ChatMessage, ChatThread, Review
from claimlens.pipeline.run import run_pipeline
from tests.test_pipeline import _deps, _new_case

GOOD_QUOTE = {"doc": "claim", "page": 1, "quote": "Policy number: EH-2025-778812"}
EVIDENCE = {"doc": "claim", "page": 1, "bbox": [50, 50, 100, 60]}


def _setup(tmp_path, script):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    deps.chat_ai = FakeChat(script)
    return deps, deps.db.get_case("c1")


def _ask(deps, case, text="What is wrong?", selection=None, clock=None):
    q = ChatMessage(id="q1", role="reviewer", text=text, by="a@x.com", selection=selection)
    thread = ChatThread(id="t1", created_by="a@x.com", carried_summary="EARLIER-SUMMARY")
    kwargs = {"clock": clock} if clock else {}
    return answer(deps, case, thread, [], q, **kwargs)


def _final(answer_text="Because.", citations=(), proposals=()):
    return Final({"answer": answer_text, "citations": list(citations), "proposals": list(proposals)})


def test_tool_then_final_answer_with_valid_citation(tmp_path):
    deps, case = _setup(tmp_path, [ToolCall("search_text", {"query": "policy"}), _final(citations=[GOOD_QUOTE])])
    msg = _ask(deps, case)
    assert msg.role == "assistant" and msg.verified and len(msg.citations) == 1
    assert msg.tool_calls == [{"name": "search_text", "args": '{"query": "policy"}'}]
    assert msg.text == "Because."


def test_made_up_citation_dropped_and_unverified(tmp_path):
    fake = {"doc": "claim", "page": 1, "quote": "The moon is made of cheese and so is the bill"}
    deps, case = _setup(tmp_path, [_final(citations=[fake])])
    msg = _ask(deps, case)
    assert msg.citations == [] and not msg.verified
    deps, case = _setup(tmp_path / "b", [_final(citations=[])])
    assert not _ask(deps, case).verified


def test_tool_limit_forces_final(tmp_path):
    deps, case = _setup(tmp_path, [ToolCall("list_findings", {}) for _ in range(7)])
    msg = _ask(deps, case)
    assert len(msg.tool_calls) == 6
    assert len(deps.chat_ai.seen) == 7
    assert "Answer now with final_answer." in deps.chat_ai.seen[-1][-1].parts[0].text
    assert msg.text == FAILED and msg.proposals == []


def test_time_limit_forces_final(tmp_path):
    deps, case = _setup(tmp_path, [_final()])
    ticks = iter([0, 100, 100, 100])
    msg = _ask(deps, case, clock=lambda: next(ticks))
    assert msg.tool_calls == [] and msg.text == "Because."
    assert "Answer now" in deps.chat_ai.seen[0][-1].parts[0].text


def test_empty_answer_is_failed(tmp_path):
    deps, case = _setup(tmp_path, [_final("")])
    msg = _ask(deps, case)
    assert msg.text == FAILED and msg.proposals == []


def test_proposal_for_dismissed_finding_dropped_with_note(tmp_path):
    deps, case = _setup(tmp_path, [])
    findings = deps.db.get_findings("c1")
    dismissed, active, gone = findings[0], findings[1], findings[2]
    deps.db.update_finding("c1", dismissed.id, review=Review(action="dismiss", by="a@x.com"))
    deps.db.update_finding("c1", gone.id, removed=True)
    deps.chat_ai = FakeChat([_final(proposals=[
        {"type": "review_finding", "finding_id": dismissed.id, "action": "dismiss"},
        {"type": "review_finding", "finding_id": dismissed.id, "action": "accept"},
        {"type": "review_finding", "finding_id": gone.id, "action": "dismiss"},
        {"type": "review_finding", "finding_id": "nope", "action": "dismiss"},
        {"type": "set_severity", "finding_id": active.id, "severity": "purple"},
        {"type": "review_finding", "finding_id": dismissed.id, "action": "restore", "reason": "ok"},
        {"type": "set_severity", "finding_id": active.id, "severity": "low"},
    ])])
    msg = _ask(deps, deps.db.get_case("c1"))
    assert [(p.type, p.action, p.severity) for p in msg.proposals] == [
        ("review_finding", "restore", None), ("set_severity", None, "low")]
    assert len(msg.notes) == 5 and "dismissed" in msg.notes[0]
    assert all(len(p.id) == 10 and p.finding_version == 0 and p.status == "pending" for p in msg.proposals)


def test_correct_fact_bad_path_dropped(tmp_path):
    deps, case = _setup(tmp_path, [_final(proposals=[
        {"type": "correct_fact", "path": "claim.nope", "value": "x", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.bills[99].total", "value": "100", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.bills", "value": "100", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.amount_claimed", "value": "lots", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.admission_date", "value": "not a date", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.amount_claimed", "value": "Rs 18,450"},
        {"type": "correct_fact", "path": "claim.amount_claimed", "value": "Rs 18,450", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.admission_date", "value": "11-Mar-2026", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "claim.claimant_name", "value": "Rahul V", "evidence": EVIDENCE},
        {"type": "correct_fact", "path": "policy.sum_insured", "value": "5,00,000", "evidence": EVIDENCE},
    ])])
    msg = _ask(deps, case)
    assert [(p.path, p.value) for p in msg.proposals] == [
        ("claim.amount_claimed", 18450.0), ("claim.admission_date", "2026-03-11"),
        ("claim.claimant_name", "Rahul V"), ("policy.sum_insured", 500000.0)]
    assert len(msg.notes) == 6
    assert resolve_fact(case, "claim.bills[0].total") is not None
    assert resolve_fact(case, "claim.bills.0.total") is not None


def test_add_finding_needs_proved_citations(tmp_path):
    bad = {"doc": "claim", "page": 1, "quote": "nothing like this on the page at all, honest"}
    deps, case = _setup(tmp_path, [_final(proposals=[
        {"type": "add_finding", "title": "Odd", "detail": "d", "severity": "low", "citations": [GOOD_QUOTE]},
        {"type": "add_finding", "title": "Made up", "detail": "d", "severity": "low", "citations": [bad]},
    ])])
    msg = _ask(deps, case)
    assert [p.title for p in msg.proposals] == ["Odd"] and len(msg.notes) == 1


def test_selection_words_included_in_first_turn(tmp_path):
    deps, case = _setup(tmp_path, [_final()])
    box = Box(doc="claim", page=1, bbox=(138.0, 86.0, 222.0, 98.0))
    _ask(deps, case, "What is this?", selection=box)
    first = deps.chat_ai.seen[0][0].parts[0].text
    assert "EH-2025-778812" in first and "What is this?" in first and "EARLIER-SUMMARY" in first
    assert "font_outlier" in first  # the overview's finding list


def test_document_injection_cannot_apply(tmp_path):
    deps, case = _setup(tmp_path, [_final(proposals=[
        {"type": "review_finding", "finding_id": "font_outlier-claim-3-1", "action": "dismiss"}])])
    before = deps.db.get_findings("c1")
    msg = _ask(deps, case)
    assert len(msg.proposals) == 1 and msg.proposals[0].status == "pending"
    assert deps.db.get_findings("c1") == before
    assert deps.db.get_case("c1").context == case.context


def test_factual_answer_without_citation_is_unverified(tmp_path):
    deps, case = _setup(tmp_path, [_final("The bill is Rs 18,450.")])
    assert not _ask(deps, case).verified


def test_proposal_only_answer_without_digits_is_verified(tmp_path):
    deps, case = _setup(tmp_path, [])
    fid = next(f for f in deps.db.get_findings("c1") if f.code == "editing_tool").id
    prop = {"type": "review_finding", "finding_id": fid, "action": "dismiss"}
    deps.chat_ai = FakeChat([_final("I suggest dismissing it.", proposals=[prop])])
    msg = _ask(deps, case)
    assert len(msg.proposals) == 1 and msg.verified
    deps.chat_ai = FakeChat([_final("I suggest dismissing finding 3.", proposals=[prop])])
    assert not _ask(deps, case).verified


def test_failed_finish_is_unverified(tmp_path):
    deps, case = _setup(tmp_path, [_final("")])
    msg = _ask(deps, case)
    assert msg.text == FAILED and not msg.verified


def test_nested_array_tool_args_stored_as_string(tmp_path):
    args = {"bbox": [[1, 2], [3, 4]], "query": "x" * 5000}
    deps, case = _setup(tmp_path, [ToolCall("search_text", args), _final()])
    call = _ask(deps, case).tool_calls[0]
    assert call["name"] == "search_text" and isinstance(call["args"], str) and len(call["args"]) == 2000
    assert call["args"].startswith('{"bbox": [[1, 2], [3, 4]]')
