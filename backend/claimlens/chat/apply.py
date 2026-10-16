"""Apply a reviewer-approved proposal. Nothing here runs without an Apply click."""
import uuid

from claimlens.chat.answer import parse_fact_value, resolve_fact
from claimlens.models import Case, Finding, Outcome, Proposal, now
from claimlens.pipeline.recheck import is_owned, recheck
from claimlens.pipeline.saved import case_ctx
from claimlens.review import compute_outcome, ensure_first_version, record_review, recalculate

STALE = "This finding changed since; ask again"


def _applied(proposal: Proposal, by: str) -> Proposal:
    return proposal.model_copy(update={"status": "applied", "decided_by": by, "decided_at": now(), "error": None})


def _finding(deps, case: Case, fid: str | None) -> Finding:
    found = next((f for f in deps.db.get_findings(case.id) if f.id == fid), None)
    if found is None:
        raise LookupError(f"Finding {fid} not found")
    return found


def _set_severity(deps, case: Case, p: Proposal, by: str) -> Outcome | None:
    before = _finding(deps, case, p.finding_id)
    ensure_first_version(deps, case.id, before)
    updated = deps.db.update_finding(case.id, before.id, severity=p.severity)
    deps.db.add_finding_version(case.id, before.id, updated, "severity", by, p.reason)
    return recalculate(deps, case.id)


def _add_finding(deps, case: Case, p: Proposal, by: str) -> Outcome | None:
    finding = Finding(id=f"reviewer_note-{uuid.uuid4().hex[:8]}", check="reviewer", code="reviewer_note",
                      severity=p.severity or "medium", title=p.title, detail=p.detail,
                      citations=p.citations, verified=True)
    deps.db.put_findings(case.id, [*deps.db.get_findings(case.id), finding])
    deps.db.add_finding_version(case.id, finding.id, finding, "added", by, p.reason)
    return recalculate(deps, case.id)


def _correct_fact(deps, case: Case, p: Proposal, message_id: str, by: str) -> Outcome | None:
    """Compute everything first; write context, corrections, findings and versions only at the end."""
    found = resolve_fact(case, p.path or "")
    if found is None:
        raise ValueError(f"No such fact: {p.path}")
    root, model, fact = found
    new_value = parse_fact_value(p.path, fact, p.value)
    if new_value is None:
        raise ValueError(f"\"{p.value}\" is not a valid value for {p.path}")
    old_value = fact.value
    fact.value, fact.source = new_value, "reviewer"  # the model is a fresh copy; the page, quote and bbox stay
    context = {**(case.context or {}), root: model.model_dump(mode="json")}

    ctx = case_ctx(deps, case)
    if root == "claim":
        ctx.claim_facts = model
    else:
        ctx.policy_facts = model
    new = {f.id: f for f in recheck(ctx)}

    old = deps.db.get_findings(case.id)
    merged: list[Finding] = []
    versions: list[tuple[Finding, str]] = []  # (finding as saved, action)
    needs_first: list[Finding] = []  # old findings with no version 1 yet
    for f in old:
        if not is_owned(f):
            merged.append(f)
            continue
        if f.id in new:
            updated = new[f.id].model_copy(update={"review": f.review})
            action = "restored_by_correction" if f.removed else "rechecked" if updated != f else None
        else:
            updated = f if f.removed else f.model_copy(update={"removed": True})
            action = None if f.removed else "removed_by_correction"
        merged.append(updated)
        if action:
            versions.append((updated, action))
            if not deps.db.get_finding_versions(case.id, f.id):
                needs_first.append(f)
    seen = {f.id for f in old}
    added = [f for fid, f in new.items() if fid not in seen]
    merged += added

    outcome, fields = compute_outcome(case, context, merged)
    entry = {"path": p.path, "old": old_value, "new": new_value, "by": by, "at": now().isoformat(),
             "reason": p.reason, "evidence": p.evidence.model_dump(mode="json") if p.evidence else None,
             "message_id": message_id}

    # Everything is computed. The writes below are not one transaction; the case goes first so a failure
    # part-way never leaves new findings beside the old facts.
    db = deps.db
    db.update_case(case.id, context=context, corrections=[*case.corrections, entry], **fields)
    db.put_findings(case.id, merged)
    for f in needs_first:
        db.add_finding_version(case.id, f.id, f, "analysis", "pipeline", "")
    for f, action in versions:
        db.add_finding_version(case.id, f.id, f, action, by, p.reason)
    for f in added:
        db.add_finding_version(case.id, f.id, f, "added_by_correction", by, p.reason)
    return outcome


def apply(deps, case: Case, proposal: Proposal, message_id: str, by: str) -> tuple[Proposal, Outcome | None]:
    """Make the change a proposal describes. Returns the proposal with its new status and the new outcome."""
    if proposal.finding_id and proposal.finding_version is not None:
        latest = max((v["version"] for v in deps.db.get_finding_versions(case.id, proposal.finding_id)), default=0)
        if latest > proposal.finding_version:
            return proposal.model_copy(update={"status": "stale", "error": STALE}), None
    try:
        if proposal.type == "review_finding":
            _, outcome = record_review(deps, case, proposal.finding_id, proposal.action, proposal.reason, by)
        elif proposal.type == "set_severity":
            outcome = _set_severity(deps, case, proposal, by)
        elif proposal.type == "add_finding":
            outcome = _add_finding(deps, case, proposal, by)
        else:
            outcome = _correct_fact(deps, case, proposal, message_id, by)
    except Exception as e:
        return proposal.model_copy(update={"status": "failed", "error": str(e) or type(e).__name__}), None
    return _applied(proposal, by), outcome
