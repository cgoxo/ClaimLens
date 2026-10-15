"""Upload checks on the claim's own pages: the same page uploaded twice, a page missing. Code only."""

import re
from collections import Counter
from itertools import combinations

from rapidfuzz import fuzz

from claimlens.models import Citation, Finding, PageInfo
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import ReadResult
from claimlens.pipeline.text import MONEY_RE, normalise

NUMBERS = re.compile(r"\d[\d,./-]*\d|\d")
DATE = re.compile(r"\b\d{1,2}[-/ ](\d{1,2}|[a-z]{3,9})[-/ ]\d{2,4}\b", re.I)
PAGE_OF = re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.I)
MIN_TEXT = 40  # characters: below this a page can't be told apart from another


def _distinctive(page: PageInfo) -> bool:
    """Enough text, and an amount or a date: a bill or report page, not a repeated terms-and-conditions page."""
    text = page.text
    return len(text.strip()) >= MIN_TEXT and bool(MONEY_RE.search(text) or DATE.search(text))


def duplicate_pages(read: ReadResult) -> list[tuple[PageInfo, PageInfo]]:
    """Claim pages that are the same page uploaded twice: the same numbers, and nearly the same words.

    Compared on text, not pixels: two photos of one page differ more in pixels than two pages of one
    hospital's template do, but they carry the same amounts, dates and invoice numbers.
    """
    pages = [(p, normalise(p.text)) for p in read.pages if p.doc == "claim" and _distinctive(p)]
    out = []
    for (a, ta), (b, tb) in combinations(pages, 2):
        if Counter(NUMBERS.findall(ta)) == Counter(NUMBERS.findall(tb)) and fuzz.ratio(ta, tb) >= 90:
            if not any(later.page == b.page for _, later in out):
                out.append((a, b))
    return out


def _first_line(ctx: Ctx, page: int) -> Citation:
    line = next((l.strip() for l in ctx.page_text("claim", page).splitlines() if l.strip()), "")
    return Citation(doc="claim", page=page, quote=line, source="page" if line else "metadata")


def _duplicates(ctx: Ctx) -> list[Finding]:
    return [Finding(
        id=f"duplicate_page_image-claim-{later.page}-1", check="cards", code="duplicate_page_image", severity="high",
        title=f"Claim page {later.page} is the same page as page {earlier.page}",
        detail="The same page was uploaded twice. It was left out of the analysis so nothing is counted twice.",
        citations=[_first_line(ctx, later.page)]) for earlier, later in duplicate_pages(ctx.read)]


def _incomplete(ctx: Ctx) -> list[Finding]:
    """Pages that number themselves "page n of m" where some n never turns up.

    Each document numbers its own pages, so marks are grouped by their total m. Numbering that doesn't
    include page 1 is a slice of a bigger pack, and an unreadable page might be the missing one: both skipped.
    """
    pages = [p for p in ctx.read.pages if p.doc == "claim"]
    if not pages or any(not p.text.strip() for p in pages):
        return []
    seen: dict[int, dict[int, PageInfo]] = {}
    for p in pages:
        for n, m in PAGE_OF.findall(p.text):
            seen.setdefault(int(m), {}).setdefault(int(n), p)
    out = []
    for total, found in sorted(seen.items()):
        missing = [n for n in range(1, total + 1) if n not in found] if 1 in found else []
        if missing:
            first = found[1]
            out.append(Finding(
                id=f"incomplete_bill-claim-{first.page}-{total}", check="cards", code="incomplete_bill",
                severity="medium",
                title=f"The claim is missing page{'s' if len(missing) > 1 else ''} "
                      f"{', '.join(map(str, missing))} of {total}",
                detail="A document numbers its pages, and not all of them were uploaded.",
                citations=[_first_line(ctx, first.page)]))
    return out


def check_cards(ctx: Ctx) -> list[Finding]:
    return _duplicates(ctx) + _incomplete(ctx)
