"""What Read saw, kept so a later question can be answered without opening the files again."""
import gzip
import json
from dataclasses import asdict

from claimlens.cards import cards_of
from claimlens.models import Case, ClaimFacts, FileInfo, PolicyFacts, Span
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import Drawing, ReadResult


def _key(case_id: str) -> str:
    return f"cases/{case_id}/read.json.gz"


def save_read(storage, case_id: str, read: ReadResult) -> None:
    """Spans, hidden layer, drawings and files as gzip JSON (pages live in the database)."""
    doc = {
        "spans": [s.model_dump(mode="json") for s in read.spans],
        "hidden_layer": [s.model_dump(mode="json") for s in read.hidden_layer],
        "drawings": [asdict(d) for d in read.drawings],
        "files": [f.model_dump(mode="json") for f in read.files],
    }
    storage.put(_key(case_id), gzip.compress(json.dumps(doc).encode()), "application/gzip")


def load_read(deps, case_id: str) -> ReadResult:
    """Pages from the database, the rest from storage; an older case with no saved file gets pages only."""
    read = ReadResult(pages=deps.db.get_pages(case_id))
    if not deps.storage.exists(_key(case_id)):
        return read
    doc = json.loads(gzip.decompress(deps.storage.get(_key(case_id))))
    read.spans = [Span.model_validate(s) for s in doc["spans"]]
    read.hidden_layer = [Span.model_validate(s) for s in doc["hidden_layer"]]
    read.drawings = [Drawing(**{**d, "rect": tuple(d["rect"]),
                                "fill": tuple(d["fill"]) if d["fill"] is not None else None})
                     for d in doc["drawings"]]
    read.files = [FileInfo.model_validate(f) for f in doc["files"]]
    return read


def case_ctx(deps, case: Case) -> Ctx:
    """A Ctx for a finished case, rebuilt from what was saved."""
    context = case.context or {}
    return Ctx(
        case_id=case.id,
        read=load_read(deps, case.id),
        deps=deps,
        claim_facts=ClaimFacts.model_validate(context["claim"]) if context.get("claim") else None,
        policy_facts=PolicyFacts.model_validate(context["policy"]) if context.get("policy") else None,
        cards=cards_of(case) if case.cards else [],
    )
