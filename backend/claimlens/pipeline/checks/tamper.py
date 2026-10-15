"""Tamper check: signs that a document was edited after it was made. Code only, no AI."""

import re
from collections import Counter
from datetime import datetime

from claimlens.models import Citation, Finding, Span
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import covered_spans
from claimlens.pipeline.text import MONEY_RE

EDITING_TOOLS = ["ilovepdf", "smallpdf", "sejda", "pdfescape", "photoshop", "canva",
                 "pdf-xchange", "foxit phantompdf", "sodapdf"]
NUMBER_TOKEN = re.compile(r"\d[\d,./-]*")


class _Ids:
    def __init__(self):
        self.seen = Counter()

    def __call__(self, code: str, doc: str, page: int) -> str:
        key = f"{code}-{doc}-{page}"
        self.seen[key] += 1
        return f"{key}-{self.seen[key]}"


def _pdf_date(s: str) -> datetime | None:
    m = re.match(r"D:(\d{14})", s or "")
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S") if m else None


def _cite(span: Span) -> Citation:
    return Citation(doc=span.doc, page=span.page, quote=span.text, bbox=span.bbox)


def _first_line(ctx: Ctx, doc: str, page: int = 1) -> Citation:
    """File-level findings point at the file's first page for display; their proof is the file metadata."""
    spans = sorted(ctx.spans_on(doc, page), key=lambda s: s.seqno)
    if spans:
        return _cite(spans[0]).model_copy(update={"source": "metadata"})
    line = next((l.strip() for l in ctx.page_text(doc, page).splitlines() if l.strip()), "")
    return Citation(doc=doc, page=page, quote=line, source="metadata")


def _font_outliers(ctx: Ctx, ids: _Ids) -> list[Finding]:
    out = []
    for page in ctx.read.pages:
        if page.kind != "digital":
            continue
        money = [s for s in ctx.spans_on(page.doc, page.page) if MONEY_RE.search(s.text)]
        if len(money) < 2:
            continue
        font, _ = Counter(s.font for s in money).most_common(1)[0]
        size, _ = Counter(s.size for s in money).most_common(1)[0]
        for s in money:
            if s.font != font or abs(s.size - size) > 0.5:
                out.append(Finding(
                    id=ids("font_outlier", s.doc, s.page), check="tamper", code="font_outlier",
                    severity="critical", title=f"Amount in a different font: {s.text}",
                    detail=f"'{s.text}' uses {s.font} {s.size}pt; other amounts on this page use {font} {size}pt.",
                    citations=[_cite(s)]))
    return out


def _hidden_text(ctx: Ctx, ids: _Ids) -> list[Finding]:
    return [Finding(
        id=ids("hidden_text", s.doc, s.page), check="tamper", code="hidden_text",
        severity="critical", title=f"Hidden text under a white box: {s.text}",
        detail=f"'{s.text}' is covered by a white box drawn on top of it.",
        citations=[_cite(s)]) for s, _ in covered_spans(ctx.read)]


def _ocr_layer_mismatch(ctx: Ctx, ids: _Ids) -> list[Finding]:
    out = []
    for page in ctx.read.pages:
        if page.kind != "scanned_with_text":
            continue
        ocr_tokens = {t for s in ctx.spans_on(page.doc, page.page) for t in NUMBER_TOKEN.findall(s.text)}
        for s in ctx.read.hidden_layer:
            if s.doc != page.doc or s.page != page.page:
                continue
            missing = [t for t in NUMBER_TOKEN.findall(s.text) if t not in ocr_tokens]
            if missing:
                out.append(Finding(
                    id=ids("ocr_layer_mismatch", s.doc, s.page), check="tamper", code="ocr_layer_mismatch",
                    severity="critical", title=f"Hidden text says {missing[0]}, but the image doesn't",
                    detail=f"The invisible text layer contains {', '.join(missing)}, which the page image does not show.",
                    citations=[Citation(doc=s.doc, page=s.page, quote=s.text, bbox=s.bbox, source="hidden_layer")]))
    return out


def _file_info(ctx: Ctx, ids: _Ids) -> list[Finding]:
    out = []
    for info in ctx.read.files:
        cite, page = _first_line(ctx, info.doc, info.first_page), info.first_page
        created, modified = _pdf_date(info.created), _pdf_date(info.modified)
        dates = f"created {created:%d-%b-%Y}, modified {modified:%d-%b-%Y}" if created and modified else ""
        tool = next((t for t in EDITING_TOOLS if t in f"{info.producer} {info.creator}".lower()), None)
        if tool:
            name = info.producer if tool in info.producer.lower() else info.creator
            out.append(Finding(
                id=ids("editing_tool", info.doc, page), check="tamper", code="editing_tool", severity="high",
                title=f"File was saved with an editing tool ({name})",
                detail=f"The {info.doc} file says it was produced by {name}. {dates}".strip(),
                citations=[cite]))
        elif created and modified and (modified - created).days >= 1:
            out.append(Finding(
                id=ids("late_edit", info.doc, page), check="tamper", code="late_edit", severity="medium",
                title="File was changed after it was created", detail=dates, citations=[cite]))
        if info.eof_count > 1:
            out.append(Finding(
                id=ids("multiple_saves", info.doc, page), check="tamper", code="multiple_saves", severity="medium",
                title=f"File was saved {info.eof_count} times",
                detail="Each extra save can mean an edit after the original was made.", citations=[cite]))
    return out


def check_tamper(ctx: Ctx) -> list[Finding]:
    ids = _Ids()
    return _font_outliers(ctx, ids) + _hidden_text(ctx, ids) + _ocr_layer_mismatch(ctx, ids) + _file_info(ctx, ids)
