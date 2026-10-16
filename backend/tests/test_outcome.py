import pytest

from claimlens.models import (Bill, ClaimFacts, Deduction, Fact, Finding, Note, PolicyFacts, Review, Settlement)
from claimlens.pipeline.outcome import outcome, outcome_text, recommend
from claimlens.pipeline.run import run_pipeline
from tests.test_pipeline import _deps, _new_case


def _f(code="x", severity="low", title="A finding", review=None):
    return Finding(id=f"{code}-1", check="story", code=code, severity=severity, title=title, review=review)


def _fact(v):
    return Fact(value=v, page=1, quote=str(v))


def _settlement(claimed=1000.0, payable=1000.0, whole=None, notes=()):
    return Settlement(lines=[], claimed=claimed, subtotal=payable or 0, payable=payable, whole_claim=whole,
                      notes=list(notes))


POLICY = PolicyFacts(sum_insured=_fact(300000))
FACTS = ClaimFacts(discharge_date=_fact("2026-01-05"), bills=[Bill(page=1, kind="hospital", inpatient=True)])


def _action(findings=(), risk="low", settlement=None, policy=POLICY, facts=FACTS):
    return recommend(list(findings), risk, settlement or _settlement(), policy, facts).action


def test_recommend_table():
    note = Note(text="Co-pay unknown", affects_amount=True)
    whole = Deduction(amount=1000, reason="Waiting period")
    no_discharge = ClaimFacts(bills=[Bill(page=1, kind="hospital", inpatient=True)])
    rows = [
        (_action(risk="high"), "investigate"),
        (_action([_f(severity="critical")]), "investigate"),
        (_action(risk="review"), "query"),
        (_action(settlement=_settlement(claimed=None, payable=None)), "query"),
        (_action(policy=PolicyFacts()), "query"),
        (_action([_f("unreadable_file")]), "query"),
        (_action(facts=no_discharge), "query"),
        (_action(settlement=_settlement(notes=[note])), "query"),
        (_action(settlement=_settlement(payable=0, whole=whole)), "not_payable"),
        (_action(settlement=_settlement(payable=0)), "not_payable"),
        (_action(settlement=_settlement(payable=900)), "approve_part"),
        (_action(settlement=_settlement(payable=999.5)), "approve"),
        (_action(), "approve"),
        (_action([_f(severity="critical")], risk="review", settlement=_settlement(payable=0)), "investigate"),
    ]
    for got, want in rows:
        assert got == want


def test_reasons_name_things():
    r = recommend([_f(severity="critical", title="Font edited")], "low", _settlement(), POLICY, FACTS)
    assert "Font edited" in r.reasons[0]
    r = recommend([], "low", _settlement(notes=[Note(text="Co-pay unknown", affects_amount=True)]), POLICY, FACTS)
    assert r.reasons == ["Co-pay unknown"]


def test_no_policy_gives_query():
    r = recommend([], "low", _settlement(), None, FACTS)
    assert r.action == "query" and "The policy couldn't be read" in r.reasons[0]


def test_dismissed_finding_not_counted():
    f = _f("x", "critical", review=Review(action="dismiss", by="a@x.com"))
    o = outcome(POLICY, FACTS, [f])
    assert o.score == 0 and o.recommendation.action != "investigate"


def test_outcome_text_names_recommendation():
    o = outcome(POLICY, FACTS, [])
    assert "Recommendation" in outcome_text(o)


def test_pipeline_sample_has_analysis(tmp_path):
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    assert case.analysis.recommendation.action in ("investigate", "query", "not_payable", "approve_part", "approve")
    assert case.analysis.settlement.payable == case.payable
    assert case.current.payable == case.payable


def test_risk_band_reasons_name_findings():
    fs = [_f("a", "low", title="Minor thing"), _f("b", "high", title="Amount in a different font: 18,450.00."),
          _f("c", "medium", title="Bill items don't add up to the total"), _f("d", "low", title="Fourth"),
          _f("e", "coverage", title="Room limit")]
    r = recommend(fs, "high", _settlement(), POLICY, FACTS)
    assert r.action == "investigate"
    assert r.reasons == ["High risk: Amount in a different font: 18,450.00; "
                         "Bill items don't add up to the total; Minor thing"]
    r = recommend(fs, "review", _settlement(), POLICY, FACTS)
    assert r.action == "query" and r.reasons[0].startswith("Review-band risk: Amount in a different font")


def test_reasons_strip_trailing_punctuation():
    r = recommend([_f(severity="critical", title="Font edited.")], "low", _settlement(), POLICY, FACTS)
    assert r.reasons == ["Font edited (critical)"]
    r = recommend([_f("unreadable_file", title="Scan unreadable.")], "low", _settlement(), POLICY, FACTS)
    assert r.reasons == ["Scan unreadable: the file could not be read."]
    whole = Deduction(amount=1000, reason="Waiting period.")
    r = recommend([], "low", _settlement(payable=0, whole=whole), POLICY, FACTS)
    assert r.reasons == ["The whole claim is excluded: Waiting period."]


def test_approve_part_explains_bills_capped_at_claimed():
    from claimlens.models import LineItem
    from claimlens.pipeline.settlement import settle
    facts = ClaimFacts(amount_claimed=_fact(8000), discharge_date=_fact("2026-01-05"), bills=[Bill(
        page=1, kind="hospital", inpatient=True,
        line_items=[LineItem(desc="Room", amount=_fact(6000)), LineItem(desc="Drugs", amount=_fact(4000))])])
    s = settle(POLICY, facts, [])
    s.payable = 7000.0
    r = recommend([], "low", s, POLICY, facts)
    assert r.action == "approve_part"
    assert r.reasons[0] == "Bills total Rs 10,000; capped at the claimed Rs 8,000."
