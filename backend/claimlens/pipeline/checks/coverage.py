"""Coverage check: Gemini reads the policy; code re-does the arithmetic it can be wrong about."""

import re
from rapidfuzz import fuzz

from claimlens.models import Citation, ClaimFacts, Finding, PolicyFacts
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import labelled_text, locate
from claimlens.pipeline.text import months_between, normalise, parse_date, parse_money


def _finding(code, title, detail, page, quote, amount=0.0, n=1) -> Finding:
    return Finding(id=f"{code}-policy-{page}-{n}", check="coverage", code=code, severity="coverage",
                   title=title, detail=detail, amount_not_payable=amount,
                   citations=[Citation(doc="policy", page=page, quote=quote)])


def policy_start(p: PolicyFacts):
    return parse_date(p.start_date.value) if p.start_date else None


def treated_date(f: ClaimFacts):
    """When treatment happened: the first procedure date, else the admission date."""
    return (next((parse_date(pr.date.value) for pr in f.procedures if pr.date), None)
            or (parse_date(f.admission_date.value) if f.admission_date else None))


def _waiting_periods(ctx: Ctx) -> list[Finding]:
    f, p = ctx.claim_facts, ctx.policy_facts
    start, treated = policy_start(p), treated_date(f)
    if not (start and treated):
        return []
    targets = [str(f.diagnosis.value)] if f.diagnosis and f.diagnosis.value else []
    targets += [str(pr.name.value) for pr in f.procedures if pr.name.value]
    out = []
    for n, wp in enumerate(p.waiting_periods, 1):
        if not any(fuzz.partial_ratio(wp.condition.lower(), t.lower()) >= 80 for t in targets):
            continue
        months = months_between(start, treated)
        if months < wp.months:
            out.append(_finding(
                "waiting_period", f"{wp.condition} is in its {wp.months}-month waiting period (clause {_clause_no(wp.clause) or wp.clause})",
                f"The policy started {start:%d-%b-%Y}; treatment on {treated:%d-%b-%Y} is only {months} months later.",
                wp.page, wp.quote, n=n))
    return out


def _room_rent(ctx: Ctx) -> list[Finding]:
    room, limit_fact = ctx.claim_facts.room, ctx.policy_facts.room_rent_limit_per_day
    if not (room and room.rate_per_day and room.days and limit_fact):
        return []
    rate, days, limit = (parse_money(room.rate_per_day.value), parse_money(room.days.value),
                         parse_money(limit_fact.value))
    if None in (rate, days, limit) or rate <= limit:
        return []
    excess = (rate - limit) * days
    return [_finding("room_rent_limit", f"Room rent above the Rs {limit:,.0f}/day limit",
                     f"Room at Rs {rate:,.0f}/day for {days:.0f} days: Rs {excess:,.0f} is not payable.",
                     limit_fact.page, limit_fact.quote, amount=excess)]


def _clause_no(clause: str) -> str:
    m = re.search(r"\d+(?:\.\d+)*", clause or "")
    return m.group(0) if m else ""


def check_coverage(ctx: Ctx) -> list[Finding]:
    if ctx.claim_facts is None or ctx.policy_facts is None:
        return []
    derived = _waiting_periods(ctx) + _room_rent(ctx)
    covered_clauses = {_clause_no(wp.clause) for wp in ctx.policy_facts.waiting_periods
                       for f in derived if f.code == "waiting_period" and wp.quote == f.citations[0].quote}
    covered_quotes = {(f.citations[0].page, normalise(f.citations[0].quote)) for f in derived}
    has_room = any(f.code == "room_rent_limit" for f in derived)

    # Gemini often lists one item per bill line for the same rule: group them by clause.
    groups: dict[tuple, list] = {}
    items = ctx.deps.ai.judge_coverage(labelled_text(ctx.read, "policy", ctx.cards), ctx.claim_facts)
    for item in items:
        if item.verdict not in ("not_covered", "partly_covered") or item.page is None:
            continue
        clause = _clause_no(item.clause)
        if (clause and clause in covered_clauses) or (item.page, normalise(item.quote)) in covered_quotes:
            continue
        if has_room and "room" in item.item.lower():
            continue
        groups.setdefault((clause,) if clause else (item.page, normalise(item.quote)), []).append(item)

    for n, group in enumerate(groups.values(), 1):
        first = group[0]
        verdict = "not_covered" if any(i.verdict == "not_covered" for i in group) else "partly_covered"
        clause = f" (clause {_clause_no(first.clause)})" if _clause_no(first.clause) else ""
        names = ", ".join(dict.fromkeys(i.item for i in group))
        derived.append(_finding(verdict, f"{names}: {verdict.replace('_', ' ')}{clause}", first.reason,
                                first.page, first.quote, amount=sum(i.amount_not_payable for i in group), n=n))
    return [_with_box(ctx, f) for f in derived]


def _with_box(ctx: Ctx, finding: Finding) -> Finding:
    """Point at the clause on the policy page, so the reviewer sees exactly which rule applies."""
    cite = finding.citations[0]
    _, bbox = locate(ctx, "policy", cite.page, cite.quote)
    return finding.model_copy(update={"citations": [cite.model_copy(update={"bbox": bbox})]})
