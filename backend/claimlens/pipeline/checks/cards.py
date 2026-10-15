"""Card checks: did the user group the files the way the documents say? Code only."""

import re
from collections import Counter
from itertools import combinations

from rapidfuzz import fuzz

from claimlens.cards import card_label
from claimlens.models import Citation, Finding, PageInfo
from claimlens.pipeline.checks.duplicate import invoice_key
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import ReadResult
from claimlens.pipeline.text import normalise

NUMBERS = re.compile(r"\d[\d,./-]*\d|\d")
PAGE_OF = re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.I)
MIN_TEXT = 40  # characters: below this a page can't be told apart from another


def duplicate_pages(read: ReadResult) -> list[tuple[PageInfo, PageInfo]]:
    """Claim pages that are the same page uploaded twice: the same numbers, and nearly the same words.

    Compared on text, not pixels: two photos of one page differ more in pixels than two pages of one
    hospital's template do, but they carry the same amounts, dates and invoice numbers.
    """
    pages = [(p, normalise(p.text)) for p in read.pages if p.doc == "claim" and len(p.text.strip()) >= MIN_TEXT]
    out = []
    for (a, ta), (b, tb) in combinations(pages, 2):
        if Counter(NUMBERS.findall(ta)) == Counter(NUMBERS.findall(tb)) and fuzz.ratio(ta, tb) >= 90:
            if not any(later.page == b.page for _, later in out):
                out.append((a, b))
    return out


def _first_line(ctx: Ctx, page: int) -> Citation:
    line = next((l.strip() for l in ctx.page_text("claim", page).splitlines() if l.strip()), "")
    return Citation(doc="claim", page=page, quote=line, source="page" if line else "metadata")


def _bills_by_card(ctx: Ctx) -> dict[str, list]:
    card_of = {p.page: p.card_id for p in ctx.read.pages if p.doc == "claim"}
    out: dict[str, list] = {}
    for bill in ctx.claim_facts.bills if ctx.claim_facts else []:
        key = invoice_key(bill.invoice_no.value) if bill.invoice_no and bill.invoice_no.value else None
        if key and (card := card_of.get(bill.page)):
            out.setdefault(card, []).append((key, bill))
    return out


def _cite(bill) -> Citation:
    f = bill.invoice_no
    return Citation(doc="claim", page=f.page, quote=f.quote, bbox=f.bbox)


def _split_and_mixed(ctx: Ctx) -> list[Finding]:
    by_card, out = _bills_by_card(ctx), []
    seen: dict[str, tuple[str, object]] = {}
    for card_id, bills in by_card.items():
        for key, bill in bills:
            if key in seen and seen[key][0] != card_id:
                first_card, first = seen[key]
                out.append(Finding(
                    id=f"bill_split_across_cards-claim-{bill.page}-1", check="cards", code="bill_split_across_cards",
                    severity="high",
                    title=f"Invoice {first.invoice_no.value} appears in two cards "
                          f"({card_label(ctx.cards, first_card)}, {card_label(ctx.cards, card_id)})",
                    detail="One bill was split across cards, or the same bill was uploaded as two bills.",
                    citations=[_cite(first), _cite(bill)]))
            seen.setdefault(key, (card_id, bill))
        card = next((c for c in ctx.cards if c.id == card_id), None)
        distinct = list(dict.fromkeys(key for key, _ in bills))
        if card is not None and card.role == "bill" and len(distinct) > 1:
            first_of = {key: bill for key, bill in reversed(bills)}
            out.append(Finding(
                id=f"mixed_bill_in_card-claim-{bills[0][1].page}-1", check="cards", code="mixed_bill_in_card",
                severity="medium",
                title=f"{card_label(ctx.cards, card_id)} holds more than one bill "
                      f"({', '.join(str(first_of[k].invoice_no.value) for k in distinct)})",
                detail="Each bill should be its own card, so its items and total are checked on their own.",
                citations=[_cite(first_of[k]) for k in distinct]))
    return out


def _duplicates(ctx: Ctx) -> list[Finding]:
    return [Finding(
        id=f"duplicate_page_image-claim-{later.page}-1", check="cards", code="duplicate_page_image", severity="high",
        title=f"Claim page {later.page} is the same page as page {earlier.page}",
        detail="The same page was uploaded twice. It was left out of the analysis so nothing is counted twice.",
        citations=[_first_line(ctx, later.page)]) for earlier, later in duplicate_pages(ctx.read)]


def _incomplete(ctx: Ctx) -> list[Finding]:
    out = []
    for card in (c for c in ctx.cards if c.role == "bill"):
        pages = [p for p in ctx.read.pages if p.doc == "claim" and p.card_id == card.id]
        marks = [(int(n), int(m)) for p in pages for n, m in PAGE_OF.findall(p.text)]
        if not marks:
            continue
        total = max(m for _, m in marks)
        found = {n for n, _ in marks}
        # numbering that doesn't start at 1 is a slice of a bigger document (a claim pack), not this bill's own
        missing = [n for n in range(1, total + 1) if n not in found] if 1 in found else []
        if missing:
            out.append(Finding(
                id=f"incomplete_bill-claim-{pages[0].page}-1", check="cards", code="incomplete_bill",
                severity="medium",
                title=f"{card_label(ctx.cards, card.id)} is missing page{'s' if len(missing) > 1 else ''} "
                      f"{', '.join(map(str, missing))} of {total}",
                detail="The bill numbers its pages, and not all of them were uploaded.",
                citations=[_first_line(ctx, pages[0].page)]))
    return out


def check_cards(ctx: Ctx) -> list[Finding]:
    if not ctx.cards:
        return _duplicates(ctx)
    return _split_and_mixed(ctx) + _duplicates(ctx) + _incomplete(ctx)
