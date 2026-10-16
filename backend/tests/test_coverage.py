import json
import shutil
from datetime import date

from claimlens.ai import FakeAi
from claimlens.pipeline.checks.coverage import check_coverage, months_between
from claimlens.pipeline.extract import extract
from tests.conftest import FAKE_AI, make_ctx


def _by_clause(findings):
    return {f.citations[0].quote: f for f in findings}


def test_waiting_period_not_covered(ctx):
    found = [f for f in check_coverage(ctx) if f.code == "waiting_period"]
    assert len(found) == 1
    f = found[0]
    assert f.severity == "coverage" and "3.2" in f.title
    c = f.citations[0]
    assert (c.doc, c.page, c.quote) == ("policy", 2, "not payable until 24 months")


def test_room_rent_excess(ctx):
    found = [f for f in check_coverage(ctx) if f.code == "room_rent_limit"]
    assert len(found) == 1
    assert found[0].amount_not_payable == 4500
    assert found[0].citations[0].page == 1


def test_override_when_ai_says_covered(tmp_path):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    (fixtures / "coverage.json").write_text(json.dumps([
        {"item": "Cataract surgery", "verdict": "covered", "clause": "3.2", "page": 2, "quote": "not payable until 24 months"}
    ]))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    codes = sorted(f.code for f in check_coverage(c))
    assert codes == ["room_rent_limit", "waiting_period"]


def test_no_policy_facts_no_crash(ctx):
    ctx.policy_facts = None
    check_coverage(ctx)


def test_months_between():
    assert months_between(date(2026, 1, 1), date(2026, 3, 11)) == 2
    assert months_between(date(2024, 1, 1), date(2026, 1, 1)) == 24


def _with_coverage(tmp_path, items):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    (fixtures / "coverage.json").write_text(json.dumps(items))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    return c


def test_ai_items_for_same_clause_merge_into_code_finding(tmp_path):
    quote = "Treatment of the following is not payable until 24 months of continuous cover have been completed"
    items = [{"item": name, "verdict": "not_covered", "clause": "Clause 3.2", "page": 2, "quote": quote}
             for name in ("Room charges", "Surgeon and OT charges", "Pharmacy")]
    items.append({"item": "Room charges (3 days x Rs 4,500)", "verdict": "partly_covered", "clause": "Clause 2.1",
                  "page": 1, "quote": "(Rs 3,000 per day)", "amount_not_payable": 4500})
    codes = sorted(f.code for f in check_coverage(_with_coverage(tmp_path, items)))
    assert codes == ["room_rent_limit", "waiting_period"]


def test_ai_items_for_other_clause_become_one_finding(tmp_path):
    items = [{"item": name, "verdict": "not_covered", "clause": "4.1", "page": 3,
              "quote": "Cosmetic treatment, dental treatment", "amount_not_payable": amount}
             for name, amount in (("Tooth cleaning", 500), ("Whitening", 700))]
    found = [f for f in check_coverage(_with_coverage(tmp_path, items)) if f.code == "not_covered"]
    assert len(found) == 1
    assert found[0].amount_not_payable == 1200
    assert "Tooth cleaning" in found[0].title and "Whitening" in found[0].title


def test_waiting_period_title_uses_bare_clause_number(ctx):
    ctx.policy_facts.waiting_periods[0].clause = "Clause 3.2"
    found = [f for f in check_coverage(ctx) if f.code == "waiting_period"]
    assert found[0].title.endswith("(clause 3.2)")


def test_coverage_citations_get_a_box_on_the_policy_page(ctx):
    found = {f.code: f for f in check_coverage(ctx)}
    for code in ("waiting_period", "room_rent_limit"):
        assert found[code].citations[0].bbox is not None, code


# --- line deductions ----------------------------------------------------------

from claimlens.models import (Bill, Fact, LineDeduction, LineItem, Limit, NonPayable,  # noqa: E402
                              ProportionateDeduction, RoomLimit, Window)


def _fact(value):
    return Fact(value=value, page=3, quote=str(value))


def _line(desc, amount, category="other", days=None, rate=None):
    return LineItem(desc=desc, amount=_fact(amount), category=category,
                    days=_fact(days) if days is not None else None,
                    rate=_fact(rate) if rate is not None else None)


def _only(ctx, code):
    found = [f for f in check_coverage(ctx) if f.code == code]
    assert len(found) == 1, [f.code for f in check_coverage(ctx)]
    return found[0]


def test_room_excess_is_a_line_deduction(ctx):
    f = _only(ctx, "room_rent_limit")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=4500)]
    assert f.amount_not_payable == 4500
    assert f.items == ["Room charges (3 days x Rs 4,500)"]


def _room_case(ctx, proportionate):
    ctx.policy_facts.room_limit = RoomLimit(clause="2.1", page=1, quote="(Rs 3,000 per day)", amount=3000)
    if proportionate:
        ctx.policy_facts.proportionate_deduction = ProportionateDeduction(
            clause="2.2", page=1, quote="proportionate deduction")
    ctx.claim_facts.bills = [
        Bill(page=3, kind="hospital", line_items=[_line("Ward", 13500, "room", 3, 4500),
                                                   _line("Dr visit", 9000, "doctor")]),
        Bill(page=4, kind="pharmacy", line_items=[_line("Tablets", 6000, "medicines")]),
    ]


def test_proportionate_deduction_reduces_doctor_not_medicines(ctx):
    _room_case(ctx, True)
    f = _only(ctx, "room_rent_limit")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=4500), LineDeduction(bill=0, line=1, amount=3000)]
    assert f.amount_not_payable == 7500


def test_no_proportionate_without_clause(ctx):
    _room_case(ctx, False)
    f = _only(ctx, "room_rent_limit")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=4500)]


def test_icu_limit(ctx):
    ctx.policy_facts.sum_insured = _fact("Rs 3,00,000")
    ctx.policy_facts.icu_limit = Limit(clause="2.3", page=1, quote="ICU", percent_of_si=2)
    ctx.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[_line("ICU stay", 24000, "icu", 2, 12000)])]
    f = _only(ctx, "icu_limit")
    assert f.severity == "coverage"
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=12000)]
    assert f.amount_not_payable == 12000


def test_non_payable_standard_list(ctx):
    ctx.policy_facts.non_payable = NonPayable(clause="4.2", page=3, quote="non-payable items", standard_list=True)
    ctx.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[_line("Admission kit", 800),
                                                                       _line("Surgeon", 5000, "surgery")])]
    f = _only(ctx, "non_payable_items")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=800)]
    assert f.items == ["Admission kit"] and f.amount_not_payable == 800


def test_pharmacy_after_post_window(ctx):
    ctx.policy_facts.window = Window(clause="5.1", page=3, quote="post-hospitalisation", pre_days=30, post_days=60)
    ctx.claim_facts.bills = [
        Bill(page=4, kind="pharmacy", date=_fact("27-May-2026"), line_items=[_line("Tablets", 3000)], total=_fact(3000)),
        Bill(page=5, kind="pharmacy", date=_fact("20-Mar-2026"), line_items=[_line("Tablets", 900)]),
        Bill(page=6, kind="pharmacy", line_items=[_line("Tablets", 900)]),
    ]
    f = _only(ctx, "bill_outside_cover_window")
    assert f.deductions == [LineDeduction(bill=0, line=-1, amount=3000)]


def test_not_covered_maps_to_line(tmp_path):
    items = [{"item": "Cosmetic laser", "verdict": "not_covered", "clause": "4.1", "page": 3,
              "quote": "Cosmetic treatment, dental treatment"}]
    c = _with_coverage(tmp_path, items)
    c.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[_line("Surgeon", 5000),
                                                                     _line("Cosmetic laser therapy", 2500)])]
    f = _only(c, "not_covered")
    assert f.deductions == [LineDeduction(bill=0, line=1, amount=2500)]
    assert f.amount_not_payable == 2500


def test_unmatched_item_is_a_claim_level_deduction(tmp_path):
    items = [{"item": "Whitening", "verdict": "not_covered", "clause": "4.1", "page": 3,
              "quote": "Cosmetic treatment, dental treatment", "amount_not_payable": 700}]
    f = _only(_with_coverage(tmp_path, items), "not_covered")
    assert f.deductions == [LineDeduction(bill=-1, line=-1, amount=700)]


def test_waiting_period_deducts_the_claim(ctx):
    f = _only(ctx, "waiting_period")
    assert f.deductions == [LineDeduction(bill=-1, line=-1, amount=51500)]
    assert f.amount_not_payable == 51500


# --- fix round 1 ----------------------------------------------------------------

def test_two_items_on_one_line_deduct_it_once(tmp_path):
    items = [{"item": name, "verdict": "not_covered", "clause": "4.1", "page": 3,
              "quote": "Cosmetic treatment, dental treatment"} for name in ("Cosmetic laser", "Laser therapy")]
    c = _with_coverage(tmp_path, items)
    c.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[_line("Cosmetic laser therapy", 2500)])]
    f = _only(c, "not_covered")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=2500)]
    assert f.items == ["Cosmetic laser therapy"] and f.amount_not_payable == 2500


def test_room_excess_is_capped_at_the_line_amount(ctx):
    _room_case(ctx, False)
    ctx.claim_facts.bills[0].line_items[0] = _line("Ward", 2000, "room", 3, 4500)
    f = _only(ctx, "room_rent_limit")
    assert f.deductions == [LineDeduction(bill=0, line=0, amount=2000)]


def test_room_line_is_not_also_proportionately_cut(ctx):
    _room_case(ctx, True)
    ctx.claim_facts.bills[0].line_items[0] = _line("Nursing - room", 13500, "nursing", 3, 4500)
    ctx.claim_facts.bills[0].line_items[1:] = [_line("Dr visit", 9000, "doctor")]
    f = _only(ctx, "room_rent_limit")
    assert [d for d in f.deductions if d.line == 0] == [LineDeduction(bill=0, line=0, amount=4500)]


def test_icu_words_need_a_whole_word(ctx):
    ctx.policy_facts.icu_limit = Limit(clause="2.3", page=1, quote="ICU", amount=6000)
    ctx.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[
        _line("Particulars of stay", 9000, "other", 2, 12000), _line("Bathroom fittings", 500, "other", 1, 9000)])]
    assert [f for f in check_coverage(ctx) if f.code == "icu_limit"] == []
    ctx.policy_facts.room_limit = RoomLimit(clause="2.1", page=1, quote="(Rs 3,000 per day)", amount=3000)
    assert [d for f in check_coverage(ctx) if f.code == "room_rent_limit" for d in f.deductions
            if d.bill == 0 and d.line == 1] == []


def test_coverage_item_with_icu_letters_is_not_skipped(tmp_path):
    items = [{"item": "Ventricular septal defect repair", "verdict": "not_covered", "clause": "4.1", "page": 3,
              "quote": "Cosmetic treatment, dental treatment", "amount_not_payable": 900}]
    c = _with_coverage(tmp_path, items)
    c.policy_facts.icu_limit = Limit(clause="2.3", page=1, quote="ICU", amount=6000)
    c.claim_facts.bills = [Bill(page=3, kind="hospital", line_items=[_line("ICU stay", 24000, "icu", 2, 12000)])]
    assert _only(c, "not_covered").amount_not_payable == 900
