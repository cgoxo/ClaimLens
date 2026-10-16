"""Chat routes: owner only, case READY, and CHAT must be on."""
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from claimlens.api import _deps, _own_case
from claimlens.auth import current_user
from claimlens.chat import service
from claimlens.models import BBox, Box, Case, now

router = APIRouter(prefix="/api")


def _chat_case(request: Request, case_id: str, user: str) -> Case:
    if _deps(request).settings.chat == "off":
        raise HTTPException(404, "Not found")
    case = _own_case(request, case_id, user)
    if case.status != "READY":
        raise HTTPException(409, "The case isn't ready yet")
    return case


class MessageIn(BaseModel):
    text: str = Field(max_length=20000)  # a blunt bound before stripping; the real limit is chat_max_chars
    selection: Box | None = None


def _check_selection(deps, case_id: str, sel: Box) -> Box:
    page = next((p for p in deps.db.get_pages(case_id) if p.doc == sel.doc and p.page == sel.page), None)
    if page is None:
        raise HTTPException(400, f"There is no page {sel.page} in {sel.doc}")
    x0, y0, x1, y1 = sel.bbox
    if not all(math.isfinite(v) for v in sel.bbox):
        raise HTTPException(400, "The selected box is not valid")
    if x1 <= x0 or y1 <= y0:
        raise HTTPException(400, "The selected box has no size")
    if x0 < 0 or y0 < 0 or x1 > page.width or y1 > page.height:
        raise HTTPException(400, "The selected box is outside the page")
    return sel


@router.get("/cases/{case_id}/chat")
def get_chat(case_id: str, request: Request, user: str = Depends(current_user)):
    case = _chat_case(request, case_id, user)
    deps = _deps(request)
    thread = deps.db.active_thread(case.id)  # read only: the thread is created by the first message
    previous = [{"id": t.id, "summary": t.summary, "created_at": t.created_at.isoformat()}
                for t in deps.db.list_threads(case.id) if t.status != "active"]
    messages = deps.db.get_messages(case.id, thread.id) if thread else []
    return {"thread": thread.model_dump(mode="json") if thread else None,
            "messages": [m.model_dump(mode="json") for m in messages],
            "previous": previous}


@router.post("/cases/{case_id}/chat/messages")
def post_message(case_id: str, body: MessageIn, request: Request, user: str = Depends(current_user)):
    case = _chat_case(request, case_id, user)
    deps = _deps(request)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Write a question first")
    if len(text) > deps.settings.chat_max_chars:
        raise HTTPException(400, f"Keep it under {deps.settings.chat_max_chars} characters")
    selection = _check_selection(deps, case.id, body.selection) if body.selection else None
    if deps.db.count_messages_since(user, now() - timedelta(days=1)) >= deps.settings.chat_daily_limit:
        raise HTTPException(429, f"Daily limit of {deps.settings.chat_daily_limit} chat messages reached")
    try:
        reply = service.ask(deps, case, text, selection, user)
    except service.ChatUnavailable:
        raise HTTPException(503, "Couldn't answer right now, try again")
    return reply.model_dump(mode="json")


@router.post("/cases/{case_id}/chat/new")
def new_chat(case_id: str, request: Request, user: str = Depends(current_user)):
    case = _chat_case(request, case_id, user)
    return service.new_chat(_deps(request), case, user).model_dump(mode="json")


def _decide(request: Request, case_id: str, pid: str, decision: str, user: str):
    case = _chat_case(request, case_id, user)
    try:
        proposal, outcome = service.decide(_deps(request), case, pid, decision, user)
    except LookupError:
        raise HTTPException(404, "Proposal not found")
    except service.NotPending as e:
        raise HTTPException(409, str(e))
    return {"proposal": proposal.model_dump(mode="json"),
            "current": outcome.model_dump(mode="json") if outcome else None}


@router.post("/cases/{case_id}/chat/proposals/{pid}/apply")
def apply_proposal(case_id: str, pid: str, request: Request, user: str = Depends(current_user)):
    return _decide(request, case_id, pid, "apply", user)


@router.post("/cases/{case_id}/chat/proposals/{pid}/ignore")
def ignore_proposal(case_id: str, pid: str, request: Request, user: str = Depends(current_user)):
    return _decide(request, case_id, pid, "ignore", user)
