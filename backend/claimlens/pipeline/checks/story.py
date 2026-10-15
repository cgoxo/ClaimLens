"""Story check: do the facts across the documents agree with each other? Code only."""

import re

from rapidfuzz import fuzz

from claimlens.models import Citation, Fact, Finding
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.text import parse_date, parse_money


def _cite(fact: Fact) -> Citation:
    return Citation(doc="claim", page=fact.page, quote=fact.quote, bbox=fact.bbox)


def _finding(code: str, severity: str, title: str, detail: str, fact: Fact, n: int) -> Finding:
    return Finding(id=f"{code}-claim-{fact.page}-{n}", check="story", code=code, severity=severity,
                   title=title, detail=detail, citations=[_cite(fact)])


def _sum_mismatch(ctx: Ctx) -> list[Finding]:
    out = []
    for n, bill in enumerate(ctx.claim_facts.bills, 1):
        amounts = [parse_money(i.amount.value) for i in bill.line_items if i.amount]
        total = parse_money(bill.total.value) if bill.total else None
        if not amounts or total is None or None in amounts:
            continue
        if abs(sum(amounts) - total) > 1:
            out.append(_finding("sum_mismatch", "high", f"Bill items add up to Rs {sum(amounts):,.0f}, total says Rs {total:,.0f}",
                                f"Line items on page {bill.page} sum to Rs {sum(amounts):,.0f}.", bill.total, n))
    return out


def _date_order(ctx: Ctx) -> list[Finding]:
    f, p = ctx.claim_facts, ctx.policy_facts
    chain: list[tuple[str, Fact]] = []
    if p and p.start_date:
        chain.append(("policy start", p.start_date))
    chain += [(label, fact) for label, fact in (("admission", f.admission_date),) if fact]
    chain += [(f"procedure {pr.name.value}", pr.date) for pr in f.procedures if pr.date]
    chain += [(label, fact) for label, fact in (("discharge", f.discharge_date), ("claim", f.claim_date)) if fact]
    dated = [(label, fact, d) for label, fact in chain if (d := parse_date(fact.value))]
    out = []
    for n, ((la, _, da), (lb, fb, db_)) in enumerate(zip(dated, dated[1:]), 1):
        if da > db_:
            out.append(_finding("date_order", "high", f"{lb.capitalize()} date is before {la} date",
                                f"{la} {da:%d-%b-%Y} comes after {lb} {db_:%d-%b-%Y}.", fb, n))
    return out


def _inpatient_outside_stay(ctx: Ctx) -> list[Finding]:
    f = ctx.claim_facts
    start = parse_date(f.admission_date.value) if f.admission_date else None
    end = parse_date(f.discharge_date.value) if f.discharge_date else None
    if not (start and end):
        return []
    out = []
    for n, bill in enumerate(f.bills, 1):
        d = parse_date(bill.date.value) if bill.date else None
        if bill.inpatient and d and not (start <= d <= end):
            out.append(_finding("inpatient_outside_stay", "high",
                                f"Inpatient {bill.kind} bill dated {d:%d-%b} is outside the hospital stay",
                                f"The patient was in hospital {start:%d-%b} to {end:%d-%b-%Y}.", bill.date, n))
    return out


def _name_mismatch(ctx: Ctx) -> list[Finding]:
    f = ctx.claim_facts
    if not f.claimant_name or not f.claimant_name.value:
        return []
    expected = str(f.claimant_name.value).lower()
    out, seen = [], set()
    for n, name in enumerate(f.names, 1):
        if not name.value or (str(name.value).lower(), name.page) in seen:
            continue
        seen.add((str(name.value).lower(), name.page))
        ratio = fuzz.ratio(expected, str(name.value).lower())
        if ratio >= 100:
            continue
        severity = "low" if ratio >= 85 else "high"
        out.append(_finding("name_mismatch", severity, f"Name mismatch: {name.value} vs {f.claimant_name.value}",
                            "Possible typo." if severity == "low" else "Looks like a different person.", name, n))
    return out


def _claimed_amount_mismatch(ctx: Ctx) -> list[Finding]:
    f = ctx.claim_facts
    claimed = parse_money(f.amount_claimed.value) if f.amount_claimed else None
    totals = [parse_money(b.total.value) if b.total else None for b in f.bills]
    if claimed is None or not totals or None in totals:
        return []
    if abs(claimed - sum(totals)) > 1:
        return [_finding("claimed_amount_mismatch", "medium",
                         f"Claimed Rs {claimed:,.0f} but bills total Rs {sum(totals):,.0f}",
                         "The claim form amount doesn't match the bills.", f.amount_claimed, 1)]
    return []


def _policy_number_mismatch(ctx: Ctx) -> list[Finding]:
    claim, policy = ctx.claim_facts.policy_number, ctx.policy_facts.policy_number if ctx.policy_facts else None
    if not (claim and policy and claim.value and policy.value):
        return []
    key = lambda v: re.sub(r"[^A-Z0-9]", "", str(v).upper())
    if key(claim.value) == key(policy.value):
        return []
    finding = _finding("policy_number_mismatch", "high",
                       f"Claim names policy {claim.value}, but the uploaded policy is {policy.value}",
                       "The claim form and the policy document carry different policy numbers.", claim, 1)
    cite_policy = Citation(doc="policy", page=policy.page, quote=policy.quote, bbox=policy.bbox)
    return [finding.model_copy(update={"citations": [*finding.citations, cite_policy]})]


def check_story(ctx: Ctx) -> list[Finding]:
    if ctx.claim_facts is None:
        return []
    return (_sum_mismatch(ctx) + _date_order(ctx) + _inpatient_outside_stay(ctx)
            + _name_mismatch(ctx) + _claimed_amount_mismatch(ctx) + _policy_number_mismatch(ctx))
