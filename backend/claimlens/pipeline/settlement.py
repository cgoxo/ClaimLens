"""Settlement: what the insurer pays, line by line, computed in code from the facts and findings."""

from rapidfuzz import fuzz

from claimlens.models import (Citation, ClaimFacts, Deduction, Finding, Note, PolicyFacts, Settlement,
                              SettlementLine)
from claimlens.pipeline.rules import limit_rupees, rule_citation, sum_insured
from claimlens.pipeline.text import parse_money

# Proportionate deduction scales these lines down; it never touches medicines, consumables or implants.
PROPORTIONATE = ("doctor", "nursing", "surgery", "investigations")
NEVER_PROPORTIONATE = ("medicines", "consumables", "implants")


def _targets(facts: ClaimFacts | None) -> list[str]:
    if facts is None:
        return []
    targets = [str(facts.diagnosis.value)] if facts.diagnosis and facts.diagnosis.value else []
    return targets + [str(p.name.value) for p in facts.procedures if p.name.value]


def main_treatment_excluded(facts: ClaimFacts | None, findings: list[Finding]) -> Finding | None:
    """The finding that rules out the whole claim: a waiting period, or an exclusion of the main treatment."""
    targets = _targets(facts)
    for finding in findings:
        if finding.code == "waiting_period":
            return finding
        if finding.code == "not_covered" and any(
                fuzz.partial_ratio(finding.title.split(":")[0].lower(), t.lower()) >= 80 for t in targets):
            return finding
    return None


def _deduction(amount: float, reason: str, finding_id: str | None = None, rule: Citation | None = None) -> Deduction:
    return Deduction(amount=round(amount), reason=reason, finding_id=finding_id, rule=rule)


def _from_finding(amount: float, finding: Finding) -> Deduction:
    return _deduction(amount, finding.title, finding.id, finding.citations[0] if finding.citations else None)


def _lines(facts: ClaimFacts | None) -> list[SettlementLine]:
    out = []
    for b, bill in enumerate(facts.bills if facts else []):
        for i, item in enumerate(bill.line_items):
            amount = parse_money(item.amount.value) if item.amount else None
            if amount is not None:
                out.append(SettlementLine(bill=b, line=i, desc=item.desc, category=item.category,
                                          claimed=amount, payable=amount))
    return out


def _take(line: SettlementLine, want: float, finding: Finding) -> float:
    """Deduct up to `want` from the line, never more than is left. Returns what was taken."""
    amount = min(round(want), line.payable)
    if amount <= 0:
        return 0.0
    line.deductions.append(_from_finding(amount, finding))
    line.payable -= amount
    return amount


def _apply_line_deductions(lines: list[SettlementLine], findings: list[Finding]) -> list[Deduction]:
    claim_level: list[Deduction] = []
    for finding in findings:
        for d in finding.deductions:
            if d.bill < 0:
                claim_level.append(_from_finding(d.amount, finding))
            elif d.line >= 0:
                for line in lines:
                    if (line.bill, line.line) == (d.bill, d.line):
                        _take(line, d.amount, finding)
            else:  # the whole bill: fill its lines in order
                left = round(d.amount)
                for line in (x for x in lines if x.bill == d.bill):
                    left -= _take(line, left, finding)
    return claim_level


def _sub_limit(policy: PolicyFacts, facts: ClaimFacts | None, amount: float, notes: list[Note]) -> Deduction | None:
    targets = _targets(facts)
    for sub in policy.sub_limits:
        if not any(fuzz.partial_ratio(sub.applies_to.lower(), t.lower()) >= 80 for t in targets):
            continue
        limit = limit_rupees(sub, policy)
        if limit is None:
            notes.append(Note(text=f"The {sub.applies_to} limit is a percentage of the sum insured, which is unknown.",
                              affects_amount=True))
            return None
        if sub.per != "claim":
            notes.append(Note(text=f"The {sub.applies_to} limit is per {sub.per}; it is applied once to this claim."))
        if amount > limit:
            return _deduction(amount - limit, f"Sub-limit: {sub.applies_to}", rule=rule_citation(sub))
        return None
    return None


def _co_pay(policy: PolicyFacts, facts: ClaimFacts | None, amount: float, notes: list[Note]) -> Deduction | None:
    age = parse_money(facts.patient_age.value) if facts and facts.patient_age else None
    percent, reasons, cite = 0.0, [], None
    for cp in policy.co_pays:
        if cp.applies == "other":
            notes.append(Note(text=f"Co-pay not applied automatically: {cp.condition_text or cp.clause}"))
            continue
        if cp.applies == "age_over":
            if cp.age is None:
                notes.append(Note(text="A co-pay applies above an age the policy does not state.",
                                  affects_amount=True))
                continue
            if age is None:
                notes.append(Note(text=f"A co-pay applies above age {cp.age} and the patient's age is unknown.",
                                  affects_amount=True))
                continue
            if age <= cp.age:
                continue
        percent += cp.percent
        reasons.append(f"Co-pay {cp.percent:g}%")
        cite = cite or rule_citation(cp)
    if not reasons:
        return None
    return _deduction(min(amount, amount * percent / 100), ", ".join(reasons), rule=cite)


def settle(policy: PolicyFacts | None, facts: ClaimFacts | None, findings: list[Finding]) -> Settlement:
    notes: list[Note] = []
    claimed = parse_money(facts.amount_claimed.value) if facts and facts.amount_claimed else None
    lines = _lines(facts)
    skipped = sum(1 for bill in (facts.bills if facts else []) for it in bill.line_items
                  if it.amount is None or parse_money(it.amount.value) is None)
    if skipped:
        notes.append(Note(text=f"{skipped} bill line(s) have no amount and are left out of the settlement."))
    if claimed is None:
        notes.append(Note(text="The claimed amount is missing, so no payable amount can be worked out.",
                          affects_amount=True))
        return Settlement(lines=lines, claimed=None, subtotal=0.0, payable=None, notes=notes)

    whole = main_treatment_excluded(facts, findings)
    if whole is not None:
        return Settlement(lines=lines, claimed=claimed, whole_claim=_from_finding(claimed, whole),
                          subtotal=0.0, payable=0.0, notes=notes)

    if not lines:
        notes.append(Note(text="No bill line has an amount; the settlement starts from the claimed amount."))
    claim_level = _apply_line_deductions(lines, findings)
    admissible = sum(x.payable for x in lines) if lines else claimed
    for d in claim_level:  # claim-level deductions cannot take more than the bills leave
        d.amount = min(d.amount, admissible)
        admissible -= d.amount
    subtotal = max(0.0, min(claimed, admissible))
    amount = subtotal

    sub_limit = deductible = co_pay = si_cap = None
    if policy is not None:
        sub_limit = _sub_limit(policy, facts, amount, notes)
        amount -= sub_limit.amount if sub_limit else 0
        if policy.deductible is not None:
            deductible = _deduction(min(policy.deductible.amount, amount), "Deductible",
                                    rule=rule_citation(policy.deductible))
            amount -= deductible.amount
            if policy.deductible.per == "year":
                notes.append(Note(text="The deductible is per year; it is applied once to this claim."))
        co_pay = _co_pay(policy, facts, amount, notes)
        amount -= co_pay.amount if co_pay else 0
        si = sum_insured(policy)
        if si is not None and amount > si:
            fact = policy.sum_insured
            si_cap = _deduction(amount - si, "Sum insured cap",
                                rule=Citation(doc="policy", page=fact.page, quote=fact.quote))
            amount -= si_cap.amount

    return Settlement(lines=lines, claimed=claimed, claim_level=claim_level, subtotal=subtotal,
                      sub_limit=sub_limit, deductible=deductible, co_pay=co_pay, si_cap=si_cap,
                      payable=round(max(0.0, amount)), notes=notes)
