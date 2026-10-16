"""The recommendation and the stored outcome: score, risk, settlement and what to do about the claim."""

from claimlens.models import SEVERITY_ORDER, ClaimFacts, Finding, Outcome, PolicyFacts, Recommendation, Settlement
from claimlens.pipeline.report import risk_band, score
from claimlens.pipeline.rules import sum_insured
from claimlens.pipeline.settlement import settle


def _clean(text: str) -> str:
    """Drop trailing punctuation so a title or reason can sit inside a sentence."""
    return text.strip().rstrip(".:;,! ")


def _behind_risk(findings: list[Finding]) -> str:
    """The titles of up to three highest-severity active findings, joined; '' when none carry weight."""
    ranked = sorted((f for f in findings if f.severity != "coverage"), key=lambda f: SEVERITY_ORDER.index(f.severity))
    return "; ".join(_clean(f.title) for f in ranked[:3])


def recommend(findings: list[Finding], risk: str, settlement: Settlement, policy: PolicyFacts | None,
              facts: ClaimFacts | None) -> Recommendation:
    """Precedence: investigate, query, not_payable, approve_part, approve."""
    criticals = [f for f in findings if f.severity == "critical"]
    if risk == "high" or criticals:
        behind = _behind_risk(findings)
        reasons = [f"{_clean(f.title)} (critical)" for f in criticals] or [
            f"High risk: {behind}" if behind else "The risk score is high."]
        return Recommendation(action="investigate", reasons=reasons)

    questions: list[str] = []
    if risk == "review":
        behind = _behind_risk(findings)
        questions.append(f"Review-band risk: {behind}" if behind else "The risk score is in the review band.")
    if settlement.claimed is None:
        questions.append("The claimed amount is missing.")
    if policy is None:
        questions.append("The policy couldn't be read.")
    elif sum_insured(policy) is None:
        questions.append("The policy has no readable sum insured.")
    questions += [f"{_clean(f.title)}: the file could not be read." for f in findings if f.code == "unreadable_file"]
    if facts is not None and facts.discharge_date is None and any(b.inpatient for b in facts.bills):
        questions.append("An inpatient claim has no discharge date.")
    questions += [n.text for n in settlement.notes if n.affects_amount]
    if questions:
        return Recommendation(action="query", reasons=questions)

    payable, claimed = settlement.payable, settlement.claimed
    if settlement.whole_claim is not None:
        return Recommendation(action="not_payable",
                              reasons=[f"The whole claim is excluded: {_clean(settlement.whole_claim.reason)}."])
    if payable == 0:
        return Recommendation(action="not_payable", reasons=["Nothing is payable after the deductions."])
    if payable < claimed - 1:
        deductions = [x for line in settlement.lines for x in line.deductions] + settlement.claim_level
        deductions += [x for x in (settlement.sub_limit, settlement.deductible, settlement.co_pay,
                                   settlement.si_cap) if x]
        reasons = []
        if settlement.lines and sum(x.claimed for x in settlement.lines) > claimed + 1:
            reasons.append(f"Bills total Rs {sum(x.claimed for x in settlement.lines):,.0f}; "
                           f"capped at the claimed Rs {claimed:,.0f}.")
        reasons += [f"{_clean(x.reason)}: Rs {x.amount:,.0f} is not payable." for x in deductions]
        return Recommendation(action="approve_part",
                              reasons=reasons or [f"Rs {claimed - payable:,.0f} of the claim is not payable."])
    return Recommendation(action="approve", reasons=["The claimed amount is payable in full."])


def outcome(policy: PolicyFacts | None, facts: ClaimFacts | None, findings: list[Finding]) -> Outcome:
    kept = [f for f in findings if not (f.review and f.review.action == "dismiss")]
    value = score(kept)
    risk = risk_band(value)
    settlement = settle(policy, facts, kept)
    return Outcome(score=value, risk=risk, payable=settlement.payable,
                   recommendation=recommend(kept, risk, settlement, policy, facts), settlement=settlement)


def outcome_text(o: Outcome) -> str:
    """The outcome in a few plain lines, for the summary prompt."""
    lines = [f"Risk: {o.risk} (score {o.score})."]
    if o.recommendation:
        lines.append(f"Recommendation: {o.recommendation.action.replace('_', ' ')}. "
                     + " ".join(o.recommendation.reasons))
    if o.settlement and o.settlement.claimed is not None and o.payable is not None:
        lines.append(f"Claimed Rs {o.settlement.claimed:,.0f}; payable Rs {o.payable:,.0f}.")
    return "\n".join(lines)
