"""Duplicate check: was this invoice already used in another claim?"""

import re

from claimlens.models import Citation, Finding, now
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.text import parse_money


def invoice_key(no) -> str | None:
    """Normalised invoice number, or None for placeholders like "N/A" or "-"."""
    if isinstance(no, float) and no.is_integer():
        no = int(no)
    key = re.sub(r"[^A-Z0-9]", "", str(no).upper())
    return key if len(key) >= 4 and any(ch.isdigit() for ch in key) else None


def _owner(ctx: Ctx, case_id: str) -> str | None:
    case = ctx.deps.db.get_case(case_id)
    return case.owner_email if case else None


def check_duplicate(ctx: Ctx) -> list[Finding]:
    if ctx.claim_facts is None:
        return []
    out = []
    for n, bill in enumerate(ctx.claim_facts.bills, 1):
        key = invoice_key(bill.invoice_no.value) if bill.invoice_no and bill.invoice_no.value else None
        prior = ctx.deps.db.get_invoice(key) if key else None
        if not prior or prior.get("case_id") == ctx.case_id:
            continue
        no, earlier = bill.invoice_no.value, prior["case_id"]
        mine = _owner(ctx, ctx.case_id)
        if mine and _owner(ctx, earlier) == mine:
            title = f"Invoice {no} was already submitted in your earlier case {earlier}"
            detail = f"Invoice {no} was already submitted in your earlier case {earlier}. If this is a resubmission, check that case."
        else:
            title = f"Invoice {no} was already used in claim {earlier}"
            detail = f"Invoice {no} appears in an earlier claim ({earlier})."
        out.append(Finding(
            id=f"duplicate_invoice-claim-{bill.page}-{n}", check="duplicate", code="duplicate_invoice",
            severity="critical", title=title, detail=detail,
            citations=[Citation(doc="claim", page=bill.invoice_no.page, quote=bill.invoice_no.quote,
                                bbox=bill.invoice_no.bbox)]))
    return out


def register_invoices(ctx: Ctx) -> None:
    """Remember this claim's invoices; the first claim to use an invoice keeps it."""
    if ctx.claim_facts is None:
        return
    for bill in ctx.claim_facts.bills:
        key = invoice_key(bill.invoice_no.value) if bill.invoice_no and bill.invoice_no.value else None
        if key and ctx.deps.db.get_invoice(key) is None:
            ctx.deps.db.put_invoice(key, {
                "invoice_no": str(bill.invoice_no.value),
                "amount": parse_money(bill.total.value) if bill.total else None,
                "case_id": ctx.case_id,
                "created_at": now().isoformat(),
            })
