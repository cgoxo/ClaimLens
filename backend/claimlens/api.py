from datetime import timedelta

RUNNING = {"QUEUED", "READING", "CHECKING", "PROVING"}
FINISHED = {"READY", "FAILED"}
STALE_AFTER = timedelta(minutes=15)
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from claimlens.auth import current_user
from claimlens.models import Case, Review, now
from claimlens.pipeline.read import open_document

router = APIRouter(prefix="/api")

ALLOWED = {"claim": {"pdf", "jpg", "jpeg", "png"}, "policy": {"pdf"}}
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


async def _validated(doc: str, upload: UploadFile, settings) -> tuple[bytes, str]:
    name = upload.filename or f"{doc}.pdf"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED[doc]:
        raise HTTPException(400, f"{doc}: file type .{ext} not allowed ({', '.join(sorted(ALLOWED[doc]))})")
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
    return data, ext


@router.get("/me")
def me(user: str = Depends(current_user)):
    return {"email": user}


@router.post("/cases", status_code=201)
async def create_case(request: Request, claim: UploadFile, policy: UploadFile, user: str = Depends(current_user)):
    deps = _deps(request)
    settings = deps.settings
    if deps.db.count_cases_since(user, now() - timedelta(days=1)) >= settings.daily_case_limit:
        raise HTTPException(429, f"Daily limit of {settings.daily_case_limit} cases reached")
    uploads = {"claim": await _validated("claim", claim, settings),
               "policy": await _validated("policy", policy, settings)}
    case_id = uuid4().hex[:12]
    files = {}
    for doc, (data, ext) in uploads.items():
        files[doc] = f"cases/{case_id}/{doc}.{ext}"
        deps.storage.put(files[doc], data, CONTENT_TYPES[ext])
    deps.db.create_case(Case(id=case_id, owner_email=user, files=files))
    request.app.state.start(case_id, deps)
    return {"case_id": case_id, "status": "QUEUED"}


@router.get("/cases")
def list_cases(request: Request, user: str = Depends(current_user)):
    db = _deps(request).db
    return [{**c.model_dump(mode="json", include={"id", "status", "risk", "score", "created_at", "progress",
                                                  "findings_count"}), "unseen": _unseen(c)}
            for c in (_expire_if_stale(db, c) for c in db.list_cases(user))]


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request, user: str = Depends(current_user)):
    case = _own_case(request, case_id, user)
    db = _deps(request).db
    case = _expire_if_stale(db, case)
    if _unseen(case):
        case = db.update_case(case_id, seen_at=now())
    return {
        **case.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in db.get_findings(case_id)],
        "pages": [p.model_dump(mode="json", include={"doc", "page", "kind", "width", "height"})
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
