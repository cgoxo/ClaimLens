import logging
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from claimlens.auth import current_user
from claimlens.cards import card_label, cards_of, layout_error, stream_of
from claimlens.models import Card, CardRole, Case, CaseFile, Review, now
from claimlens.pipeline.read import open_document

RUNNING = {"QUEUED", "READING", "CHECKING", "PROVING"}
FINISHED = {"READY", "FAILED", "REJECTED"}
STALE_AFTER = timedelta(minutes=15)

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)

ALLOWED = {"pdf", "jpg", "jpeg", "png"}
CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


def _deps(request: Request):
    return request.app.state.deps


def _own_case(request: Request, case_id: str, user: str) -> Case:
    case = _deps(request).db.get_case(case_id)
    if case is None or case.owner_email != user:
        raise HTTPException(404, "Case not found")
    return case


def _expire_if_stale(db, case: Case) -> Case:
    """A run with no progress for STALE_AFTER died (e.g. the server restarted mid-run): record it as FAILED."""
    if case.status in RUNNING and now() - case.updated_at > STALE_AFTER:
        return db.update_case(case.id, status="FAILED", step=case.status, finished_at=now(), progress=None,
                              error="Analysis was interrupted (server restarted). Please upload the claim again.")
    return case


def _unseen(case: Case) -> bool:
    """Finished since the owner last opened it."""
    return (case.status in FINISHED and case.finished_at is not None
            and (case.seen_at is None or case.seen_at < case.finished_at))


async def _validated(doc: str, upload: UploadFile, settings) -> tuple[bytes, str, int]:
    """The file's bytes, extension and page count, or a 400 saying what is wrong with it."""
    name = upload.filename or f"{doc}.pdf"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(400, f"{doc}: file type .{ext} not allowed ({', '.join(sorted(ALLOWED))})")
    data = await upload.read()
    if len(data) > settings.max_file_mb * 1024 * 1024:
        raise HTTPException(400, f"{doc}: file is larger than {settings.max_file_mb} MB")
    try:
        pdf = open_document(data, name)
    except Exception:
        raise HTTPException(400, f"{doc}: not a readable {ext.upper()} file")
    if pdf.needs_pass:
        raise HTTPException(400, f"{doc}: file is password-protected")
    if pdf.page_count == 0:
        raise HTTPException(400, f"{doc}: file has no pages")
    if pdf.page_count > settings.max_pages:
        raise HTTPException(400, f"{doc}: more than {settings.max_pages} pages")
    return data, ext, pdf.page_count


@router.get("/me")
def me(user: str = Depends(current_user)):
    return {"email": user}


class CardIn(BaseModel):
    id: str
    role: CardRole


class NewCase(BaseModel):
    cards: list[CardIn]


@router.post("/cases", status_code=201)
def create_case(body: NewCase, request: Request, user: str = Depends(current_user)):
    """Step 1 of 3: a draft case with the user's cards; files follow one per request."""
    deps = _deps(request)
    settings = deps.settings
    cards = [Card(**c.model_dump()) for c in body.cards]
    if error := layout_error(cards, settings):
        raise HTTPException(400, error)
    if deps.db.count_cases_since(user, now() - timedelta(days=1)) >= settings.daily_case_limit:
        raise HTTPException(429, f"Daily limit of {settings.daily_case_limit} cases reached")
    case_id = uuid4().hex[:12]
    deps.db.create_case(Case(id=case_id, owner_email=user, status="DRAFT", cards=cards))
    return {"case_id": case_id, "status": "DRAFT"}


def _draft(request: Request, case_id: str, user: str) -> Case:
    case = _own_case(request, case_id, user)
    if case.status != "DRAFT":
        raise HTTPException(409, "This case was already submitted")
    return case


@router.post("/cases/{case_id}/files", status_code=201)
async def add_file(case_id: str, request: Request, file: UploadFile, card_id: str = Form(),
                   client_id: str | None = Form(None), user: str = Depends(current_user)):
    """Step 2 of 3: one file into one card (Cloud Run caps a request body at 32 MB, so never all at once)."""
    deps = _deps(request)
    case = _draft(request, case_id, user)
    card = next((c for c in case.cards if c.id == card_id), None)
    if card is None:
        raise HTTPException(400, f"no card {card_id!r} in this case")
    if client_id and (sent := next(((i, f) for i, f in enumerate(card.files) if f.client_id == client_id), None)):
        return {"card_id": card_id, "index": sent[0], "pages": sent[1].pages}  # a re-send: already have it
    settings = deps.settings
    held = [f for c in case.cards for f in c.files]
    if len(held) >= settings.max_files:
        raise HTTPException(400, f"at most {settings.max_files} files per claim")
    data, ext, pages = await _validated(card_id, file, settings)
    if sum(f.pages for f in held) + pages > settings.max_pages:
        raise HTTPException(400, f"at most {settings.max_pages} pages per claim")
    key = f"cases/{case_id}/{card_id}/{uuid4().hex[:12]}.{ext}"  # unique: uploads may arrive together
    deps.storage.put(key, data, CONTENT_TYPES[ext])
    index = deps.db.add_case_file(case_id, card_id, CaseFile(
        key=key, name=file.filename or key, content_type=CONTENT_TYPES[ext], pages=pages, client_id=client_id))
    return {"card_id": card_id, "index": index, "pages": pages}


@router.post("/cases/{case_id}/submit")
def submit_case(case_id: str, request: Request, user: str = Depends(current_user)):
    """Step 3 of 3: check the totals and queue the analysis."""
    deps = _deps(request)
    settings = deps.settings
    case = _draft(request, case_id, user)
    cards = [c for c in case.cards if c.files]
    if not any(stream_of(c) == "policy" for c in cards):
        raise HTTPException(400, "add the policy")
    if not any(stream_of(c) == "claim" for c in cards):
        raise HTTPException(400, "add the claim documents")
    files = [f for c in cards for f in c.files]
    if len(files) > settings.max_files:
        raise HTTPException(400, f"more than {settings.max_files} files")
    if sum(f.pages for f in files) > settings.max_pages:
        raise HTTPException(400, f"more than {settings.max_pages} pages")
    deps.db.update_case(case_id, status="QUEUED", cards=cards)
    try:
        deps.jobs.enqueue("run_case", {"case_id": case_id})
    except Exception:
        # nothing will run it: give the case back to the user, who can submit again
        deps.db.update_case(case_id, status="DRAFT")
        log.exception("case %s: enqueue failed", case_id)
        raise HTTPException(503, "Couldn't start the analysis. Please try again.")
    return {"case_id": case_id, "status": "QUEUED"}


@router.get("/cases")
def list_cases(request: Request, user: str = Depends(current_user)):
    db = _deps(request).db
    return [{**c.model_dump(mode="json", include={"id", "status", "risk", "score", "created_at", "progress",
                                                  "findings_count"}), "unseen": _unseen(c)}
            for c in (_expire_if_stale(db, c) for c in db.list_cases(user)) if c.status != "DRAFT"]


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request, user: str = Depends(current_user)):
    case = _own_case(request, case_id, user)
    db = _deps(request).db
    case = _expire_if_stale(db, case)
    if _unseen(case):
        case = db.update_case(case_id, seen_at=now())
    cards = cards_of(case)
    return {
        **case.model_dump(mode="json"),
        "cards": [{"id": c.id, "role": c.role, "label": card_label(cards, c.id),
                   "files": [{"name": f.name, "pages": f.pages} for f in c.files]} for c in cards],
        "findings": [f.model_dump(mode="json") for f in db.get_findings(case_id)],
        "pages": [p.model_dump(mode="json", include={"doc", "page", "kind", "width", "height", "card_id", "file_index"})
                  for p in db.get_pages(case_id)],
    }


@router.get("/cases/{case_id}/pages/{doc}/{page}.png")
def page_image(case_id: str, doc: str, page: int, request: Request, user: str = Depends(current_user)):
    _own_case(request, case_id, user)
    deps = _deps(request)
    info = next((p for p in deps.db.get_pages(case_id) if p.doc == doc and p.page == page), None)
    if info is None:
        raise HTTPException(404, "Page not found")
    return Response(deps.storage.get(info.png_key), media_type="image/png")


class ReviewIn(BaseModel):
    action: Literal["accept", "dismiss"]
    note: str = ""


@router.post("/cases/{case_id}/findings/{fid}/review")
def review(case_id: str, fid: str, body: ReviewIn, request: Request, user: str = Depends(current_user)):
    _own_case(request, case_id, user)
    finding = _deps(request).db.update_finding(
        case_id, fid, review=Review(action=body.action, note=body.note, by=user))
    if finding is None:
        raise HTTPException(404, "Finding not found")
    return finding.model_dump(mode="json")
