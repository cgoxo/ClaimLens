"""Ask the AI for facts, then keep only facts whose quote really is on the cited page."""

import pymupdf
from pydantic import BaseModel
from rapidfuzz import fuzz

from claimlens.models import Fact, WaitingPeriod
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import ReadResult, reading_lines, visible_text
from claimlens.pipeline.text import normalise


def labelled_text(read: ReadResult, doc: str) -> str:
    """What the AI reads: each page as a person sees it (text hidden under white boxes left out)."""
    return "\n\n".join(f"=== {doc} page {p.page} ===\n{visible_text(read, doc, p.page)}"
                         for p in read.pages if p.doc == doc)


def _pdf(ctx: Ctx, doc: str) -> pymupdf.Document | None:
    cache = ctx.__dict__.setdefault("_pdfs", {})
    if doc not in cache:
        key = ctx.files.get(doc)
        cache[doc] = pymupdf.open(stream=ctx.deps.storage.get(key), filetype="pdf") if key else None
    return cache[doc]


def locate(ctx: Ctx, doc: str, page: int, quote: str) -> tuple[bool, tuple | None]:
    """Is the quote on that page, and where? Returns (found, bbox)."""
    if not quote or not ctx.page_text(doc, page):
        return False, None
    if ctx.page_kind(doc, page) == "digital":
        pdf = _pdf(ctx, doc)
        if pdf is not None and 1 <= page <= pdf.page_count:
            hits = pdf[page - 1].search_for(quote)
            if hits:
                return True, tuple(hits[0])
    wanted = normalise(quote)
    best = max(ctx.spans_on(doc, page), key=lambda s: fuzz.partial_ratio(wanted, normalise(s.text)), default=None)
    if best is not None and fuzz.partial_ratio(wanted, normalise(best.text)) >= 90 and len(normalise(best.text)) >= len(wanted) * 0.9:
        return True, best.bbox
    # compare with the page as the AI was shown it (rows rebuilt left to right), not the PDF's drawing order
    if wanted in normalise(visible_text(ctx.read, doc, page)) or wanted in normalise(ctx.page_text(doc, page)):
        return True, _window_bbox(ctx.spans_on(doc, page), wanted)
    return False, None


def _window_bbox(spans: list, wanted: str) -> tuple | None:
    """Box around the shortest run of spans, in reading order (e.g. OCR words, label + value), containing the quote."""
    spans = [s for line in reading_lines(spans) for s in line]
    longest = min(len(spans), len(wanted.split()) + 2)  # a quote of n words spans at most n (+ split) spans
    for size in range(2, longest + 1):
        for i in range(len(spans) - size + 1):
            run = spans[i:i + size]
            if wanted in normalise(" ".join(s.text for s in run)):
                return (min(s.bbox[0] for s in run), min(s.bbox[1] for s in run),
                        max(s.bbox[2] for s in run), max(s.bbox[3] for s in run))
    return None


def ground(ctx: Ctx, doc: str, fact: Fact | None) -> Fact | None:
    if fact is None:
        return None
    found, bbox = locate(ctx, doc, fact.page, fact.quote)
    return fact.model_copy(update={"bbox": bbox}) if found else None


def _ground_model(ctx: Ctx, doc: str, model: BaseModel) -> BaseModel | None:
    """Ground every Fact inside a model. A required fact that fails drops its parent."""
    if isinstance(model, WaitingPeriod):
        return model if locate(ctx, doc, model.page, model.quote)[0] else None
    updates = {}
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        if isinstance(value, Fact):
            new = ground(ctx, doc, value)
        elif isinstance(value, BaseModel):
            new = _ground_model(ctx, doc, value)
        elif isinstance(value, list):
            new = [g for item in value
                   if (g := ground(ctx, doc, item) if isinstance(item, Fact)
                       else _ground_model(ctx, doc, item) if isinstance(item, BaseModel) else item) is not None]
        else:
            continue
        if new is None and field.is_required():
            return None
        updates[name] = new
    return model.model_copy(update=updates)


def extract(ctx: Ctx) -> None:
    ai = ctx.deps.ai
    ctx.claim_facts = _ground_model(ctx, "claim", ai.extract_facts(labelled_text(ctx.read, "claim")))
    ctx.policy_facts = _ground_model(ctx, "policy", ai.extract_policy(labelled_text(ctx.read, "policy")))
