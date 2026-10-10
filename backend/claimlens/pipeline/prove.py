"""Step 4 (Prove): every finding must quote text that really is in the document it cites."""

import re

from rapidfuzz import fuzz

from claimlens.models import Citation, Finding
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.text import normalise

DIGITAL_MIN, OCR_MIN = 90, 80
NEGATIONS = {"not", "no", "never", "excluded", "except", "without", "non"}
NUMBER = re.compile(r"\d[\d,.]*\d|\d")


def _same_meaning(quote: str, window: str) -> bool:
    """A fuzzy match may differ in spelling, never in numbers or negations."""
    numbers = set(NUMBER.findall(window))
    words = set(re.findall(r"[a-z]+", window))
    return (all(n in numbers for n in NUMBER.findall(quote))
            and all(w in words for w in set(re.findall(r"[a-z]+", quote)) & NEGATIONS))


def text_holds(text: str, quote: str, floor: int) -> bool:
    text, wanted = normalise(text), normalise(quote)
    if not text or not wanted:
        return False
    if wanted in text:
        return True
    match = fuzz.partial_ratio_alignment(wanted, text)
    if match is None or match.score < floor:
        return False
    return _same_meaning(wanted, text[max(0, match.dest_start - 2):match.dest_end + 2])


def citation_holds(ctx: Ctx, c: Citation) -> bool:
    if c.source == "metadata":
        return any(f.doc == c.doc for f in ctx.read.files)
    if c.source == "hidden_layer":
        layer = " ".join(s.text for s in ctx.read.hidden_layer if s.doc == c.doc and s.page == c.page)
        return text_holds(layer, c.quote, DIGITAL_MIN)
    floor = DIGITAL_MIN if ctx.page_kind(c.doc, c.page) == "digital" else OCR_MIN
    return text_holds(ctx.page_text(c.doc, c.page), c.quote, floor)


def prove(ctx: Ctx, findings: list[Finding]) -> tuple[list[Finding], list[dict]]:
    kept, dropped = [], []
    for f in findings:
        citations = [c for c in f.citations if citation_holds(ctx, c)]
        if citations:
            kept.append(f.model_copy(update={"citations": citations, "verified": True}))
        else:
            where = ", ".join(f"{c.doc} p.{c.page}" for c in f.citations) or "no citation"
            dropped.append({"title": f.title, "reason": f"quoted text not found on {where}"})
    return kept, dropped
