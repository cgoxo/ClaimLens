"""A reviewer's decision on a finding, and the outcome recalculated from it."""
import logging

from claimlens.models import Case, ClaimFacts, Finding, Outcome, PolicyFacts, Review
from claimlens.pipeline.outcome import outcome
from claimlens.pipeline.report import risk_band, score

log = logging.getLogger("claimlens")


class ReviewConflict(Exception):
    """The action doesn't fit the finding's state (restoring a finding that isn't dismissed)."""


def compute_outcome(case: Case, context: dict | None, findings: list[Finding]) -> tuple[Outcome, dict]:
    """The new outcome and the case fields to store for it. Pure; older cases keep their stored payable."""
    if case.analysis is None:  # analysed before the rulebook: no settlement to recompute
        kept = [f for f in findings if not f.removed and not (f.review and f.review.action == "dismiss")]
        value = score(kept)
        o = Outcome(score=value, risk=risk_band(value), payable=case.payable)
        return o, {"current": o, "score": o.score, "risk": o.risk}
    context = context or {}
    facts = ClaimFacts.model_validate(context["claim"]) if context.get("claim") else None
    policy = PolicyFacts.model_validate(context["policy"]) if context.get("policy") else None
    o = outcome(policy, facts, findings)
    return o, {"current": o, "score": o.score, "risk": o.risk, "payable": o.payable}


def recalculate(deps, case_id: str) -> Outcome | None:
    """Recompute the outcome from the stored findings and store it; None (logged) when that fails."""
    try:
        case = deps.db.get_case(case_id)
        o, fields = compute_outcome(case, case.context, deps.db.get_findings(case_id))
        deps.db.update_case(case_id, **fields)
        return o
    except Exception:
        log.exception("case %s: recalculating failed", case_id)
        return None


def ensure_first_version(deps, case_id: str, finding: Finding) -> None:
    if not deps.db.get_finding_versions(case_id, finding.id):
        deps.db.add_finding_version(case_id, finding.id, finding, "analysis", "pipeline", "")


def record_review(deps, case: Case, fid: str, action: str, note: str, by: str) -> tuple[Finding, Outcome | None]:
    """Accept, dismiss or restore a finding, keep its versions and recalculate.
    LookupError when the finding doesn't exist; ReviewConflict when restoring one that isn't dismissed."""
    db = deps.db
    before = next((f for f in db.get_findings(case.id) if f.id == fid), None)
    if before is None:
        raise LookupError(fid)
    if action == "restore" and not (before.review and before.review.action == "dismiss"):
        raise ReviewConflict("Only a dismissed finding can be restored")
    ensure_first_version(deps, case.id, before)
    new = None if action == "restore" else Review(action=action, note=note, by=by)
    finding = db.update_finding(case.id, fid, review=new)
    if finding is None:
        raise LookupError(fid)
    db.add_finding_version(case.id, fid, finding, action, by, note)
    return finding, recalculate(deps, case.id)
