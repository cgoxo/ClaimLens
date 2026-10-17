from claimlens.models import (Bill, Citation, ClaimFacts, CoPay, Deductible, Fact, Finding, LineDeduction, LineItem,
                              PolicyFacts, SubLimit)
from claimlens.pipeline.settlement import NEVER_PROPORTIONATE, PROPORTIONATE, settle


def F(v):
    return Fact(value=v, page=1, quote=str(v))


def line(desc, amount, category="other"):
    return LineItem(desc=desc, amount=F(amount) if amount is not None else None, category=category)


def facts(claimed, *bills, diagnosis=None, age=None):
    return ClaimFacts(amount_claimed=F(claimed), bills=list(bills), diagnosis=F(diagnosis) if diagnosis else None,
                      patient_age=F(age) if age is not None else None)


def finding(code, title, *deds, fid=None):
    return Finding(id=fid or f"{code}-1", check="coverage", code=code, severity="coverage", title=title,
                   deductions=[LineDeduction(bill=b, line=i, amount=a) for b, i, a in deds],
                   citations=[Citation(doc="policy", page=2, quote="q")])


def bill(*lines):
    return Bill(page=1, line_items=list(lines))


def test_constants():
    assert PROPORTIONATE == ("doctor", "nursing", "surgery", "investigations")
    assert NEVER_PROPORTIONATE == ("medicines", "consumables", "implants")


def test_no_rules_pays_claimed():
    s = settle(None, facts(50000, bill(line("Room", 30000), line("Drugs", 20000))), [])
    assert s.payable == 50000 and s.subtotal == 50000 and s.claimed == 50000
    assert len(s.lines) == 2


def test_line_deductions_capped_at_line():
    f = facts(10000, bill(line("Gloves", 500), line("Surgery", 9500)))
    s = settle(None, f, [finding("non_payable_items", "Non-payable", (0, 0, 800))])
    assert s.lines[0].payable == 0 and s.lines[0].deductions[0].amount == 500
    assert s.lines[0].deductions[0].reason == "Non-payable"
    assert s.lines[0].deductions[0].finding_id == "non_payable_items-1"
    assert s.lines[0].deductions[0].rule.page == 2
    assert s.payable == 9500


def test_whole_bill_deduction_spreads_over_lines():
    f = facts(10000, bill(line("A", 4000), line("B", 6000)))
    s = settle(None, f, [finding("bill_outside_cover_window", "Outside window", (0, -1, 7000))])
    assert [x.payable for x in s.lines] == [0, 3000] and s.payable == 3000


def test_whole_claim_waiting_period_pays_zero():
    f = facts(50000, bill(line("Room", 50000)))
    s = settle(None, f, [finding("waiting_period", "Waiting period", (-1, -1, 50000))])
    assert s.whole_claim.amount == 50000 and s.payable == 0


def test_whole_claim_not_covered_main_treatment():
    f = facts(50000, bill(line("Room", 50000)), diagnosis="Cataract surgery")
    s = settle(None, f, [finding("not_covered", "Cataract: excluded", (-1, -1, 50000))])
    assert s.whole_claim is not None and s.payable == 0


def test_claimed_caps_subtotal():
    f = facts(40000, bill(line("A", 30000), line("B", 30000)))
    s = settle(None, f, [])
    assert s.subtotal == 40000 and s.payable == 40000


def test_claim_level_deducted_from_admissible_bills():
    f = facts(100000, bill(line("A", 60000)))
    s = settle(None, f, [finding("room_rent_limit", "Room", (-1, -1, 10000))])
    assert s.claim_level[0].amount == 10000 and s.subtotal == 50000 and s.payable == 50000


def test_sub_limit_cataract_40000():
    p = PolicyFacts(sub_limits=[SubLimit(applies_to="cataract", amount=40000, page=3, quote="q")])
    s = settle(p, facts(90000, bill(line("Surgery", 90000)), diagnosis="Cataract left eye"), [])
    assert s.sub_limit.amount == 50000 and s.payable == 40000 and s.sub_limit.rule.page == 3


def test_sub_limit_per_eye_has_note():
    p = PolicyFacts(sub_limits=[SubLimit(applies_to="cataract", amount=40000, per="eye", page=3, quote="q")])
    s = settle(p, facts(90000, bill(line("Surgery", 90000)), diagnosis="Cataract"), [])
    assert any("per eye" in n.text for n in s.notes)


def test_percent_sub_limit_without_sum_insured_gives_note():
    p = PolicyFacts(sub_limits=[SubLimit(applies_to="cataract", percent_of_si=10, page=3, quote="q")])
    s = settle(p, facts(90000, bill(line("Surgery", 90000)), diagnosis="Cataract"), [])
    assert s.payable == 90000 and any(n.affects_amount for n in s.notes)


def test_deductible_then_copay_order():
    p = PolicyFacts(deductible=Deductible(amount=25000, page=1, quote="q"),
                    co_pays=[CoPay(percent=10, page=1, quote="q")])
    s = settle(p, facts(100000, bill(line("All", 100000))), [])
    assert s.deductible.amount == 25000 and s.co_pay.amount == 7500 and s.payable == 67500


def test_copay_age_over_unknown_age_gives_note():
    p = PolicyFacts(co_pays=[CoPay(percent=20, applies="age_over", age=60, page=1, quote="q")])
    s = settle(p, facts(10000, bill(line("All", 10000))), [])
    assert s.payable == 10000 and s.co_pay is None
    assert any(n.affects_amount for n in s.notes)


def test_copay_age_over_applies_only_above_threshold():
    p = PolicyFacts(co_pays=[CoPay(percent=20, applies="age_over", age=60, page=1, quote="q")])
    assert settle(p, facts(10000, bill(line("All", 10000)), age=61), []).payable == 8000
    assert settle(p, facts(10000, bill(line("All", 10000)), age=60), []).payable == 10000


def test_copay_age_over_without_threshold_gives_note():
    p = PolicyFacts(co_pays=[CoPay(percent=20, applies="age_over", page=1, quote="q")])
    s = settle(p, facts(10000, bill(line("All", 10000)), age=70), [])
    assert s.payable == 10000 and any(n.affects_amount for n in s.notes)


def test_copay_other_is_note_only():
    p = PolicyFacts(co_pays=[CoPay(percent=20, applies="other", condition_text="zone B", page=1, quote="q")])
    s = settle(p, facts(10000, bill(line("All", 10000))), [])
    assert s.payable == 10000 and s.co_pay is None and s.notes


def test_sum_insured_cap():
    p = PolicyFacts(sum_insured=F("Rs 3,00,000"))
    s = settle(p, facts(400000, bill(line("All", 400000))), [])
    assert s.si_cap.amount == 100000 and s.payable == 300000


def test_line_without_amount_left_out_with_note():
    s = settle(None, facts(5000, bill(line("A", 5000), line("B", None))), [])
    assert len(s.lines) == 1 and s.payable == 5000 and any("no amount" in n.text for n in s.notes)


def test_no_claimed_amount_gives_none():
    s = settle(None, ClaimFacts(bills=[bill(line("A", 5000))]), [])
    assert s.payable is None and any(n.affects_amount for n in s.notes)
    assert settle(None, None, []).payable is None


def test_money_strings_parse():
    p = PolicyFacts(sum_insured=F("Rs 3,00,000"), deductible=Deductible(amount=10000, page=1, quote="q"))
    s = settle(p, facts("₹ 4,00,000.00", bill(line("A", "Rs 4,00,000"))), [])
    assert s.claimed == 400000 and s.payable == 300000


def test_bill_total_stands_in_when_no_line_has_amount():
    b = Bill(page=1, line_items=[line("A", None)], total=F("Rs 20,000"))
    s = settle(None, facts(30000, b), [finding("bill_outside_cover_window", "Outside window", (0, -1, 5000))])
    assert len(s.lines) == 1 and s.lines[0].line == -1 and s.lines[0].desc == "Bill total"
    assert s.lines[0].claimed == 20000 and s.lines[0].deductions[0].amount == 5000
    assert s.payable == 15000


def test_bill_total_not_added_when_a_line_has_amount():
    b = Bill(page=1, line_items=[line("A", 5000)], total=F(5000))
    s = settle(None, facts(5000, b), [])
    assert len(s.lines) == 1 and s.lines[0].desc == "A"


def test_no_bill_evidence_falls_back_to_claimed_with_note():
    s = settle(None, facts(30000, bill(line("A", None))), [])
    assert s.payable == 30000
    assert any(n.affects_amount and "nothing supports" in n.text for n in s.notes)


def test_deduction_on_missing_line_gives_note():
    f = facts(5000, bill(line("A", 5000), line("B", None)))
    s = settle(None, f, [finding("non_payable_items", "Non-payable", (0, 1, 300), (0, 9, 200), (3, 0, 100))])
    assert s.payable == 5000
    assert len([n for n in s.notes if n.affects_amount and "Non-payable" in n.text]) == 3


def test_whole_bill_deduction_larger_than_bill():
    f = facts(10000, bill(line("A", 4000)))
    s = settle(None, f, [finding("bill_outside_cover_window", "Outside window", (0, -1, 6000))])
    assert s.lines[0].payable == 0 and s.payable == 0
    assert any(n.affects_amount and "Outside window" in n.text and "2,000" in n.text for n in s.notes)


def test_two_findings_same_line_cumulative_cap():
    f = facts(1000, bill(line("A", 1000)))
    s = settle(None, f, [finding("a", "First", (0, 0, 700)), finding("b", "Second", (0, 0, 700))])
    assert [d.amount for d in s.lines[0].deductions] == [700, 300] and s.payable == 0
    assert any("Second" in n.text and n.affects_amount for n in s.notes)


def test_claim_level_larger_than_bills():
    f = facts(10000, bill(line("A", 4000)))
    s = settle(None, f, [finding("room_rent_limit", "Room", (-1, -1, 9000.4))])
    assert s.claim_level[0].amount == 4000 and s.payable == 0
    assert any(n.affects_amount and "Room" in n.text for n in s.notes)


def test_amount_string_not_a_number_is_left_out():
    s = settle(None, facts(5000, bill(line("A", 5000), line("B", "n/a"))), [])
    assert len(s.lines) == 1 and any("no amount" in n.text for n in s.notes)


def test_age_from_text_with_units():
    for text in ("45 years", "45 yrs", "45", "45Y"):
        policy = PolicyFacts(co_pays=[CoPay(clause="5", page=1, quote="q", percent=10, applies="age_over", age=40)])
        s = settle(policy, facts(1000, bill(line("Room", 1000)), age=text), [])
        assert s.co_pay is not None and s.co_pay.amount == 100 and not any(n.affects_amount for n in s.notes), text
