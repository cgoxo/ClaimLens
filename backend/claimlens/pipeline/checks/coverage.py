"""Coverage check: Gemini reads the policy; code re-does the arithmetic it can be wrong about."""

import re
from rapidfuzz import fuzz

from datetime import timedelta

from claimlens.models import Citation, ClaimFacts, Finding, LineDeduction, PolicyFacts
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import labelled_text, locate
from claimlens.pipeline.rules import icu_limit_rupees, is_non_payable, room_limit_rupees, rule_citation
from claimlens.pipeline.text import months_between, normalise, parse_date, parse_money


# Proportionate deduction scales these lines down; it never touches medicines, consumables or implants.
PROPORTIONATE_CATEGORIES = ("doctor", "nursing", "surgery", "investigations")


def _finding(code, title, detail, page, quote, amount=0.0, n=1, deductions=None, items=None) -> Finding:
    return Finding(id=f"{code}-policy-{page}-{n}", check="coverage", code=code, severity="coverage",
                   title=title, detail=detail, amount_not_payable=amount,
                   deductions=deductions or [], items=items or [],
                   citations=[Citation(doc="policy", page=page, quote=quote)])


def _money(fact):
    return parse_money(fact.value) if fact is not None else None


def _lines(f: ClaimFacts):
    for b, bill in enumerate(f.bills):
        for i, line in enumerate(bill.line_items):
            yield b, i, line


def _kind_lines(f: ClaimFacts, category: str, words: tuple[str, ...], not_words: tuple[str, ...] = ()):
    """Lines of one kind: by category; in a bill with no line of that category, by words in the description."""
    for b, bill in enumerate(f.bills):
        categorised = any(line.category == category for line in bill.line_items)
        for i, line in enumerate(bill.line_items):
            desc = line.desc.lower()
            if line.category == category or (not categorised and any(w in desc for w in words)
                                             and not any(w in desc for w in not_words)):
                yield b, i, line


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
                wp.page, wp.quote, n=n, deductions=_claim_deduction(f)))
    return out


def _claim_deduction(f: ClaimFacts) -> list[LineDeduction]:
    claimed = _money(f.amount_claimed)
    return [LineDeduction(bill=-1, line=-1, amount=claimed)] if claimed else []


def _excess_per_day(found, limit: float, fallback: tuple[float, float] | None):
    """(bill, line, rate, excess) for each line over the limit. A line without its own rate and days
    takes the claim-level room facts (once); with none, it gets no deduction."""
    out, used_fallback = [], False
    for b, i, line in found:
        rate, days = _money(line.rate), _money(line.days)
        if rate is None or days is None:
            if fallback is None or used_fallback:
                continue
            (rate, days), used_fallback = fallback, True
        if rate > limit:
            out.append((b, i, rate, (rate - limit) * days))
    return out


def _room_rent(ctx: Ctx) -> list[Finding]:
    f, p = ctx.claim_facts, ctx.policy_facts
    limit, cite = room_limit_rupees(p)
    if limit is None:
        return []
    room = f.room
    rate, days = (_money(room.rate_per_day), _money(room.days)) if room else (None, None)
    fallback = (rate, days) if rate is not None and days is not None else None
    lines = list(_kind_lines(f, "room", ("room",), ("icu", "intensive care")))
    over = _excess_per_day(lines, limit, fallback)
    if not lines and fallback and fallback[0] > limit:
        over = [(-1, -1, fallback[0], (fallback[0] - limit) * fallback[1])]
    if not over:
        return []
    deductions = [LineDeduction(bill=b, line=i, amount=x) for b, i, _, x in over]
    if p.proportionate_deduction is not None:
        ratio = 1 - limit / max(r for _, _, r, _ in over)
        for b, i, line in _lines(f):
            amount = _money(line.amount)
            if line.category in PROPORTIONATE_CATEGORIES and amount:
                deductions.append(LineDeduction(bill=b, line=i, amount=round(amount * ratio, 2)))
    total = sum(d.amount for d in deductions)
    names = [f.bills[b].line_items[i].desc for b, i, _, _ in over if b >= 0]
    top = max(r for _, _, r, _ in over)
    detail = f"Room at Rs {top:,.0f}/day against a Rs {limit:,.0f}/day limit: Rs {total:,.0f} is not payable."
    return [_finding("room_rent_limit", f"Room rent above the Rs {limit:,.0f}/day limit", detail,
                     cite.page, cite.quote, amount=total, deductions=deductions, items=names)]


def _icu(ctx: Ctx) -> list[Finding]:
    f = ctx.claim_facts
    limit, cite = icu_limit_rupees(ctx.policy_facts)
    if limit is None:
        return []
    over = _excess_per_day(_kind_lines(f, "icu", ("icu", "intensive care")), limit, None)
    if not over:
        return []
    deductions = [LineDeduction(bill=b, line=i, amount=x) for b, i, _, x in over]
    total = sum(d.amount for d in deductions)
    return [_finding("icu_limit", f"ICU charges above the Rs {limit:,.0f}/day limit",
                     f"ICU is limited to Rs {limit:,.0f}/day: Rs {total:,.0f} is not payable.",
                     cite.page, cite.quote, amount=total, deductions=deductions,
                     items=[f.bills[b].line_items[i].desc for b, i, _, _ in over])]


def _non_payable(ctx: Ctx) -> list[Finding]:
    p, hits, cite = ctx.policy_facts, [], None
    for b, i, line in _lines(ctx.claim_facts):
        amount = _money(line.amount)
        c = is_non_payable(line.desc, p) if amount else None
        if c:
            hits.append((b, i, line.desc, amount))
            cite = c
    if not hits:
        return []
    total = sum(h[3] for h in hits)
    return [_finding("non_payable_items", "Items the policy does not pay for",
                     f"{len(hits)} bill item(s) are on the policy's non-payable list: Rs {total:,.0f} is not payable.",
                     cite.page, cite.quote, amount=total,
                     deductions=[LineDeduction(bill=b, line=i, amount=a) for b, i, _, a in hits],
                     items=[h[2] for h in hits])]


def _outside_window(ctx: Ctx) -> list[Finding]:
    f, w = ctx.claim_facts, ctx.policy_facts.window
    if w is None or f.admission_date is None or f.discharge_date is None:
        return []
    admitted, discharged = parse_date(f.admission_date.value), parse_date(f.discharge_date.value)
    if admitted is None or discharged is None:
        return []
    cite, out = rule_citation(w), []
    for b, bill in enumerate(f.bills):
        when = parse_date(bill.date.value) if bill.date else None
        if when is None:
            continue
        early = w.pre_days is not None and when < admitted - timedelta(days=w.pre_days)
        late = w.post_days is not None and when > discharged + timedelta(days=w.post_days)
        amount = _money(bill.total) or sum(_money(line.amount) or 0 for line in bill.line_items)
        if not (early or late) or not amount:
            continue
        side = (f"more than {w.pre_days} days before admission" if early
                else f"more than {w.post_days} days after discharge")
        out.append(_finding("bill_outside_cover_window", f"Bill dated {when:%d-%b-%Y} is outside the cover window",
                            f"The bill is dated {side}: Rs {amount:,.0f} is not payable.",
                            cite.page, cite.quote, amount=amount, n=len(out) + 1,
                            deductions=[LineDeduction(bill=b, line=-1, amount=amount)],
                            items=[line.desc for line in bill.line_items]))
    return out


def _match_line(f: ClaimFacts, item: str):
    """The bill line whose description best matches a coverage item, if any is close enough."""
    best, score = None, 79
    for b, i, line in _lines(f):
        s = fuzz.partial_ratio(item.lower(), line.desc.lower())
        if s > score:
            best, score = (b, i, line), s
    return best


def _clause_no(clause: str) -> str:
    m = re.search(r"\d+(?:\.\d+)*", clause or "")
    return m.group(0) if m else ""


def check_coverage(ctx: Ctx) -> list[Finding]:
    if ctx.claim_facts is None or ctx.policy_facts is None:
        return []
    derived = (_waiting_periods(ctx) + _room_rent(ctx) + _icu(ctx) + _non_payable(ctx)
               + _outside_window(ctx))
    covered_clauses = {_clause_no(wp.clause) for wp in ctx.policy_facts.waiting_periods
                       for f in derived if f.code == "waiting_period" and wp.quote == f.citations[0].quote}
    covered_quotes = {(f.citations[0].page, normalise(f.citations[0].quote)) for f in derived}
    has_room = any(f.code == "room_rent_limit" for f in derived)
    has_icu = any(f.code == "icu_limit" for f in derived)

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
        if has_icu and ("icu" in item.item.lower() or "intensive care" in item.item.lower()):
            continue
        groups.setdefault((clause,) if clause else (item.page, normalise(item.quote)), []).append(item)

    for n, group in enumerate(groups.values(), 1):
        first = group[0]
        verdict = "not_covered" if any(i.verdict == "not_covered" for i in group) else "partly_covered"
        clause = f" (clause {_clause_no(first.clause)})" if _clause_no(first.clause) else ""
        names = ", ".join(dict.fromkeys(i.item for i in group))
        deductions, lines = [], []
        for i in group:
            hit = _match_line(ctx.claim_facts, i.item)
            if hit is None:
                deductions.append(LineDeduction(bill=-1, line=-1, amount=i.amount_not_payable))
                continue
            b, li, line = hit
            whole = _money(line.amount) if i.verdict == "not_covered" else None
            deductions.append(LineDeduction(bill=b, line=li, amount=whole or i.amount_not_payable))
            lines.append(line.desc)
        deductions = [d for d in deductions if d.amount]
        derived.append(_finding(verdict, f"{names}: {verdict.replace('_', ' ')}{clause}", first.reason,
                                first.page, first.quote, amount=sum(d.amount for d in deductions), n=n,
                                deductions=deductions, items=lines))
    return [_with_box(ctx, f) for f in derived]


def _with_box(ctx: Ctx, finding: Finding) -> Finding:
    """Point at the clause on the policy page, so the reviewer sees exactly which rule applies."""
    cite = finding.citations[0]
    _, bbox = locate(ctx, "policy", cite.page, cite.quote)
    return finding.model_copy(update={"citations": [cite.model_copy(update={"bbox": bbox})]})
