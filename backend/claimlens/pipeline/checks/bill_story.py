"""Bill-against-story check: does each bill line fit the diagnosis and treatment? Advisory, and fails open."""

import json
import logging

from claimlens.models import Citation, Finding
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.read import visible_text

log = logging.getLogger(__name__)

NOTE = "Check with the hospital."


def _story_text(ctx: Ctx) -> str:
    f = ctx.claim_facts
    parts = []
    if f.diagnosis and f.diagnosis.value:
        parts.append(f"Diagnosis: {f.diagnosis.value}")
    parts += [f"Procedure: {p.name.value}" for p in f.procedures if p.name and p.name.value]
    for info in ctx.read.pages:
        if info.doc == "claim" and "discharge summary" in info.text.lower():
            parts.append(f"=== claim page {info.page} ===\n{visible_text(ctx.read, 'claim', info.page)}")
    return "\n".join(parts)


def _items_json(ctx: Ctx) -> str:
    return json.dumps([{"desc": line.desc, "category": line.category,
                        "amount": line.amount.value if line.amount else None, "page": bill.page}
                       for bill in ctx.claim_facts.bills for line in bill.line_items])


def _finding(ctx: Ctx, n: int, v) -> Finding:
    unrelated = v.verdict == "unrelated"
    diagnosis = ctx.claim_facts.diagnosis.value if ctx.claim_facts.diagnosis else "this treatment"
    return Finding(
        id=f"bill_story-claim-{v.bill_page}-{n}", check="bill_story",
        code="charge_unrelated_to_treatment" if unrelated else "charge_unusual_for_treatment",
        severity="medium" if unrelated else "low",
        title=f"{v.item} charges don't fit the treatment ({diagnosis})" if unrelated
        else f"{v.item} charges are unusual for the treatment ({diagnosis})",
        detail=f"{v.reason} {NOTE}".strip(),
        citations=[Citation(doc="claim", page=v.bill_page, quote=v.bill_quote)])


def check_bill_story(ctx: Ctx) -> list[Finding]:
    f = ctx.claim_facts
    if ctx.deps.settings.bill_story == "off" or f is None or not f.bills:
        return []
    if not ((f.diagnosis and f.diagnosis.value) or f.procedures):
        return []
    try:
        verdicts = ctx.deps.ai.judge_bill_story(_story_text(ctx), _items_json(ctx))
        return [_finding(ctx, n, v) for n, v in enumerate(
            (v for v in verdicts if v.verdict in ("unrelated", "unusual")), 1)]
    except Exception:
        log.exception("bill-against-story check failed")
        return [Finding(
            id="bill_story_unavailable-claim-1-1", check="bill_story", code="bill_story_unavailable",
            severity="low", title="The bill couldn't be checked against the treatment",
            detail="The check of the bill against the treatment couldn't run.",
            citations=[Citation(source="metadata", doc="claim", page=1, quote="")])]
