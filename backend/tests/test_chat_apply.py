from claimlens.chat.apply import apply
from claimlens.models import ClaimFacts, Proposal
from claimlens.pipeline.run import run_pipeline
from claimlens.pipeline.text import parse_money
from claimlens.review import record_review, recalculate
from tests.test_api import A, _client, _upload
from tests.test_pipeline import _deps, _new_case

BY = "a@x.com"
EVIDENCE = {"doc": "claim", "page": 3, "bbox": [189, 210, 234, 224]}


def _setup(tmp_path):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    return deps, deps.db.get_case("c1")


def _proposal(deps, case, **fields):
    p = Proposal(id="p1", reason="because", **fields)
    if p.finding_id:
        versions = deps.db.get_finding_versions(case.id, p.finding_id)
        p = p.model_copy(update={"finding_version": max((v["version"] for v in versions), default=0)})
    return p


def _apply(deps, case, **fields):
    return apply(deps, deps.db.get_case(case.id), _proposal(deps, case, **fields), "m1", BY)


def _by_code(deps, code):
    return next((f for f in deps.db.get_findings("c1") if f.code == code), None)


def _line_total(case):
    bill = ClaimFacts.model_validate(case.context["claim"]).bills[0]
    return sum(parse_money(i.amount.value) for i in bill.line_items if i.amount)


def test_apply_dismiss_equals_review_button(tmp_path):
    deps, case = _setup(tmp_path)
    fid = _by_code(deps, "editing_tool").id
    proposal, current = _apply(deps, case, type="review_finding", finding_id=fid, action="dismiss")
    assert proposal.status == "applied" and proposal.decided_by == BY and proposal.decided_at
    assert deps.db.get_finding_versions("c1", fid)[-1]["action"] == "dismiss"

    deps2, case2 = _setup(tmp_path / "b")
    _, expected = record_review(deps2, case2, fid, "dismiss", "", BY)
    assert current == expected
    assert deps.db.get_case("c1").current == expected


def test_set_severity_changes_score(tmp_path):
    deps, case = _setup(tmp_path)
    f = _by_code(deps, "name_mismatch")
    for other in deps.db.get_findings("c1"):  # leave room under the 100 cap
        if other.severity == "critical":
            record_review(deps, case, other.id, "dismiss", "", BY)
    before = deps.db.get_case("c1").score
    proposal, current = _apply(deps, case, type="set_severity", finding_id=f.id, severity="critical")
    assert proposal.status == "applied"
    assert _by_code(deps, "name_mismatch").severity == "critical"
    assert [(v["version"], v["action"]) for v in deps.db.get_finding_versions("c1", f.id)] == [
        (1, "analysis"), (2, "severity")]
    assert current.score > before
    assert deps.db.get_case("c1").current == current


def test_add_finding_counts(tmp_path):
    deps, case = _setup(tmp_path)
    for other in deps.db.get_findings("c1"):
        if other.severity == "critical":
            record_review(deps, case, other.id, "dismiss", "", BY)
    before = deps.db.get_case("c1").score
    cite = {"doc": "claim", "page": 1, "quote": "Policy number: EH-2025-778812"}
    proposal, current = _apply(deps, case, type="add_finding", title="Odd stamp", detail="d",
                               severity="high", citations=[cite])
    assert proposal.status == "applied"
    added = next(f for f in deps.db.get_findings("c1") if f.check == "reviewer")
    assert added.id.startswith("reviewer_note-") and added.code == "reviewer_note"
    assert added.verified and added.severity == "high" and added.citations[0].quote == cite["quote"]
    assert [(v["version"], v["action"], v["by"]) for v in deps.db.get_finding_versions("c1", added.id)] == [
        (1, "added", BY)]
    assert current.score > before

    _apply(deps, case, type="add_finding", title="Another", citations=[cite])  # no severity: medium
    assert [f.severity for f in deps.db.get_findings("c1") if f.check == "reviewer"][-1] == "medium"


def test_correct_total_clears_sum_mismatch_and_changes_payable(tmp_path):
    deps, case = _setup(tmp_path)
    old_total = case.context["claim"]["bills"][0]["total"]
    total = _line_total(case)
    assert _by_code(deps, "sum_mismatch")
    proposal, current = _apply(deps, case, type="correct_fact", path="claim.bills[0].total",
                               value=f"Rs {total:,.0f}", evidence=EVIDENCE)
    assert proposal.status == "applied", proposal.error
    mismatch = _by_code(deps, "sum_mismatch")
    assert mismatch.removed
    assert [v["action"] for v in deps.db.get_finding_versions("c1", mismatch.id)] == [
        "analysis", "removed_by_correction"]
    saved = deps.db.get_case("c1")
    fact = saved.context["claim"]["bills"][0]["total"]
    assert fact["value"] == total and fact["source"] == "reviewer"
    assert (fact["page"], fact["quote"], fact["bbox"]) == (old_total["page"], old_total["quote"], old_total["bbox"])
    (entry,) = saved.corrections
    assert entry["path"] == "claim.bills[0].total" and entry["old"] == old_total["value"]
    assert entry["new"] == total and entry["by"] == BY and entry["message_id"] == "m1"
    assert entry["reason"] == "because" and entry["evidence"]["page"] == 3 and entry["at"]
    assert saved.current == current and current.payable == saved.payable

    # the waiting period ruled the whole claim out; dismiss it, then a corrected claimed amount moves the payable
    record_review(deps, saved, _by_code(deps, "waiting_period").id, "dismiss", "", BY)
    payable = deps.db.get_case("c1").payable
    assert payable > 0
    proposal, current = _apply(deps, case, type="correct_fact", path="claim.amount_claimed",
                               value="Rs 20,000", evidence=EVIDENCE)
    assert proposal.status == "applied", proposal.error
    assert current.payable == 20000.0 != payable


def test_correct_money_written_as_text(tmp_path):
    deps, case = _setup(tmp_path)
    proposal, _ = _apply(deps, case, type="correct_fact", path="claim.amount_claimed",
                         value="Rs 18,450", evidence=EVIDENCE)
    assert proposal.status == "applied", proposal.error
    assert deps.db.get_case("c1").context["claim"]["amount_claimed"]["value"] == 18450.0


def test_correction_keeps_gemini_and_tamper_findings(tmp_path):
    deps, case = _setup(tmp_path)
    before = deps.db.get_findings("c1")
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=_line_total(case), evidence=EVIDENCE)
    after = {f.id: f for f in deps.db.get_findings("c1")}
    kept = [f for f in before if f.check in ("tamper", "cards", "bill_story")]
    assert kept
    for f in kept:
        assert after[f.id] == f
        assert deps.db.get_finding_versions("c1", f.id) == []


def test_stale_proposal_refused(tmp_path):
    deps, case = _setup(tmp_path)
    fid = _by_code(deps, "name_mismatch").id
    p = _proposal(deps, case, type="review_finding", finding_id=fid, action="dismiss")
    record_review(deps, case, fid, "accept", "", BY)
    stale, current = apply(deps, deps.db.get_case("c1"), p, "m1", BY)
    assert stale.status == "stale" and stale.error == "This finding changed since; ask again"
    assert current is None
    assert _by_code(deps, "name_mismatch").review.action == "accept"


def test_failed_correction_writes_nothing(tmp_path, monkeypatch):
    deps, case = _setup(tmp_path)
    findings, context = deps.db.get_findings("c1"), deps.db.get_case("c1").context

    def boom(ctx):
        raise RuntimeError("recheck exploded")

    monkeypatch.setattr("claimlens.chat.apply.recheck", boom)
    proposal, current = _apply(deps, case, type="correct_fact", path="claim.bills[0].total",
                               value=1.0, evidence=EVIDENCE)
    assert proposal.status == "failed" and "recheck exploded" in proposal.error and current is None
    assert deps.db.get_findings("c1") == findings
    saved = deps.db.get_case("c1")
    assert saved.context == context and saved.corrections == []
    assert all(deps.db.get_finding_versions("c1", f.id) == [] for f in findings)


def test_removed_finding_not_counted_and_hidden(settings):
    client = _client(settings)
    cid = _upload(client).json()["case_id"]
    db = client.app.state.deps.db
    before = client.get(f"/api/cases/{cid}", headers=A).json()
    fid = next(f["id"] for f in before["findings"] if f["code"] == "waiting_period")
    db.update_finding(cid, fid, removed=True)
    after = recalculate(client.app.state.deps, cid)
    assert after.payable > before["current"]["payable"]  # the waiting period no longer rules the claim out
    shown = client.get(f"/api/cases/{cid}", headers=A).json()["findings"]
    assert fid not in [f["id"] for f in shown] and len(shown) == len(before["findings"]) - 1


def _correct_total(deps, case):
    return _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=_line_total(case),
                  evidence=EVIDENCE)


def test_unchanged_finding_gets_no_version_so_pending_proposal_not_stale(tmp_path):
    deps, case = _setup(tmp_path)
    fid = _by_code(deps, "name_mismatch").id
    pending = _proposal(deps, case, type="review_finding", finding_id=fid, action="dismiss")
    assert _correct_total(deps, case)[0].status == "applied"
    assert deps.db.get_finding_versions("c1", fid) == []
    done, _ = apply(deps, deps.db.get_case("c1"), pending, "m2", BY)
    assert done.status == "applied"


def test_removed_finding_cannot_be_reviewed(tmp_path, settings):
    deps, case = _setup(tmp_path)
    _correct_total(deps, case)
    fid = _by_code(deps, "sum_mismatch").id
    for action in ("dismiss", "restore"):
        p, current = _apply(deps, case, type="review_finding", finding_id=fid, action=action)
        assert p.status == "failed" and p.error == "Finding was removed by a correction" and current is None
    client = _client(settings)
    cid = _upload(client).json()["case_id"]
    client.app.state.deps.db.update_finding(cid, "waiting_period-policy-2-1", removed=True)
    r = client.post(f"/api/cases/{cid}/findings/waiting_period-policy-2-1/review", json={"action": "dismiss"},
                    headers=A)
    assert r.status_code == 409


def test_removed_finding_produced_again_is_restored(tmp_path):
    deps, case = _setup(tmp_path)
    _correct_total(deps, case)
    fid = _by_code(deps, "sum_mismatch").id
    assert _by_code(deps, "sum_mismatch").removed
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=1.0, evidence=EVIDENCE)
    assert not _by_code(deps, "sum_mismatch").removed
    assert [v["action"] for v in deps.db.get_finding_versions("c1", fid)] == [
        "analysis", "removed_by_correction", "restored_by_correction"]


def test_dismissed_finding_stays_dismissed_and_others_untouched(tmp_path):
    from claimlens.models import Finding

    deps, case = _setup(tmp_path)
    mismatch = _by_code(deps, "sum_mismatch")
    record_review(deps, case, mismatch.id, "dismiss", "", BY)
    note = Finding(id="reviewer_note-1", check="reviewer", code="reviewer_note", severity="low", title="n")
    gem = Finding(id="not_covered-1", check="coverage", code="not_covered", severity="coverage", title="g")
    deps.db.put_findings("c1", [*deps.db.get_findings("c1"), note, gem])
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=1.0, evidence=EVIDENCE)
    after = {f.id: f for f in deps.db.get_findings("c1")}
    assert after[mismatch.id].review.action == "dismiss" and not after[mismatch.id].removed
    assert after["reviewer_note-1"] == note and after["not_covered-1"] == gem


def test_unparseable_correction_fails_writing_nothing(tmp_path):
    deps, case = _setup(tmp_path)
    findings, saved = deps.db.get_findings("c1"), deps.db.get_case("c1")
    p, current = _apply(deps, case, type="correct_fact", path="claim.amount_claimed", value="lots",
                        evidence=EVIDENCE)
    assert p.status == "failed" and p.error and current is None
    assert deps.db.get_findings("c1") == findings
    assert deps.db.get_case("c1").context == saved.context and deps.db.get_case("c1").corrections == []


def test_stale_set_severity_refused(tmp_path):
    deps, case = _setup(tmp_path)
    fid = _by_code(deps, "name_mismatch").id
    p = _proposal(deps, case, type="set_severity", finding_id=fid, severity="critical")
    record_review(deps, case, fid, "accept", "", BY)
    stale, current = apply(deps, deps.db.get_case("c1"), p, "m1", BY)
    assert stale.status == "stale" and current is None
    assert _by_code(deps, "name_mismatch").severity == "low"


def _rerun(monkeypatch, make):
    """Make the correction's re-run produce exactly the findings `make()` returns."""
    monkeypatch.setattr("claimlens.chat.apply.recheck", lambda ctx: make())


def _story(fid, page, quote, severity="high"):
    from claimlens.models import Citation, Finding
    return Finding(id=fid, check="story", code="inpatient_outside_stay", severity=severity, title=fid,
                   citations=[Citation(doc="claim", page=page, quote=quote)])


def _seed_story(deps, *findings):
    deps.db.put_findings("c1", [f for f in deps.db.get_findings("c1") if f.code != "inpatient_outside_stay"]
                         + list(findings))


def test_correction_does_not_move_review_to_a_different_finding(tmp_path, monkeypatch):
    deps, case = _setup(tmp_path)
    _seed_story(deps, _story("oos-1", 1, "bill one"), _story("oos-2", 2, "bill two"))
    record_review(deps, case, "oos-1", "dismiss", "", BY)
    # correcting bill one removes its finding; bill two's finding now sits under the first id
    _rerun(monkeypatch, lambda: [_story("oos-1", 2, "bill two")])
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=1.0, evidence=EVIDENCE)
    after = deps.db.get_findings("c1")
    old = next(f for f in after if f.id == "oos-1")
    assert old.removed and old.review is not None  # the dismissal stays with the removed finding
    moved = [f for f in after if f.id.startswith("oos-1-")]
    assert len(moved) == 1 and moved[0].review is None and not moved[0].removed
    assert deps.db.get_finding_versions("c1", "oos-1")[-1]["action"] == "removed_by_correction"
    assert [v["action"] for v in deps.db.get_finding_versions("c1", moved[0].id)] == ["added_by_correction"]


def test_correction_keeps_review_when_citation_unchanged(tmp_path, monkeypatch):
    deps, case = _setup(tmp_path)
    _seed_story(deps, _story("oos-1", 1, "bill one"))
    record_review(deps, case, "oos-1", "dismiss", "", BY)
    _rerun(monkeypatch, lambda: [_story("oos-1", 1, "bill one")])
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=1.0, evidence=EVIDENCE)
    assert _by_code(deps, "inpatient_outside_stay").review.action == "dismiss"


def test_correction_keeps_reviewer_severity(tmp_path, monkeypatch):
    deps, case = _setup(tmp_path)
    _seed_story(deps, _story("oos-1", 1, "bill one"))
    p, _ = _apply(deps, case, type="set_severity", finding_id="oos-1", severity="low")
    assert p.status == "applied", p.error
    _rerun(monkeypatch, lambda: [_story("oos-1", 1, "bill one", severity="high")])
    _apply(deps, case, type="correct_fact", path="claim.bills[0].total", value=1.0, evidence=EVIDENCE)
    assert _by_code(deps, "inpatient_outside_stay").severity == "low"
