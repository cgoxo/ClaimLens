"""Chat threads, carried memory, and the ask / decide entry points the API calls."""
import uuid
from typing import Literal

from claimlens.chat.answer import answer
from claimlens.chat.apply import apply
from claimlens.models import Box, Case, ChatMessage, ChatThread, Outcome, Proposal, now

SUMMARY_WORDS = 150


class ChatUnavailable(Exception):
    """The model could not answer, even after retries."""


class NotPending(Exception):
    """The proposal was already applied, ignored, stale or failed."""


def _id() -> str:
    return uuid.uuid4().hex[:12]


def get_or_create_thread(deps, case: Case, by: str) -> ChatThread:
    thread = deps.db.active_thread(case.id)
    if thread is None:
        thread = ChatThread(id=_id(), created_by=by)
        deps.db.create_thread(case.id, thread)
    return thread


def ask(deps, case: Case, text: str, selection: Box | None, by: str) -> ChatMessage:
    """Answer first; store the question and the answer only if the answer worked."""
    thread = get_or_create_thread(deps, case, by)
    history = deps.db.get_messages(case.id, thread.id)[-deps.settings.chat_history:]
    question = ChatMessage(id=_id(), role="reviewer", text=text, selection=selection, by=by)
    try:
        reply = answer(deps, case, thread, history, question)
    except Exception as e:
        raise ChatUnavailable(str(e) or type(e).__name__) from e
    reply = reply.model_copy(update={"id": _id()})
    deps.db.add_message(case.id, thread.id, question)
    deps.db.add_message(case.id, thread.id, reply)
    return reply


def new_chat(deps, case: Case, by: str) -> ChatThread:
    """Close the active thread with a short summary and start a fresh one that carries it."""
    summary = ""
    thread = deps.db.active_thread(case.id)
    if thread is not None:
        messages = deps.db.get_messages(case.id, thread.id)
        if messages:
            summary = " ".join(deps.chat_ai.summarise_thread(messages).split()[:SUMMARY_WORDS])
        deps.db.close_thread(case.id, thread.id, summary)
    fresh = ChatThread(id=_id(), carried_summary=summary, created_by=by, created_at=now())
    deps.db.create_thread(case.id, fresh)
    return fresh


def decide(deps, case: Case, proposal_id: str, decision: Literal["apply", "ignore"],
           by: str) -> tuple[Proposal, Outcome | None]:
    thread = deps.db.active_thread(case.id)
    found = None
    for message in deps.db.get_messages(case.id, thread.id) if thread else []:
        proposal = next((p for p in message.proposals if p.id == proposal_id), None)
        if proposal:
            found = (message, proposal)
    if found is None:
        raise LookupError(f"Proposal {proposal_id} not found")
    message, proposal = found
    if proposal.status != "pending":
        raise NotPending(f"Proposal is {proposal.status}")
    if decision == "ignore":
        proposal = proposal.model_copy(update={"status": "ignored", "decided_by": by, "decided_at": now()})
        outcome = None
    else:
        proposal, outcome = apply(deps, case, proposal, message.id, by)
    deps.db.update_proposal(case.id, thread.id, message.id, proposal)
    return proposal, outcome
