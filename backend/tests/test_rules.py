from claimlens.models import ClaimFacts, Fact, Limit, NonPayable, PolicyFacts, RoomLimit
from claimlens.pipeline.rules import (STANDARD_NON_PAYABLE, icu_limit_rupees, is_non_payable, limit_rupees,
                                      room_limit_rupees, stay_nights, sum_insured)


def F(v):
    return Fact(value=v, page=1, quote=str(v))


def test_percent_of_si_becomes_rupees():
    p = PolicyFacts(sum_insured=F("Rs 3,00,000"), room_limit=RoomLimit(percent_of_si=1, page=1, quote="q"))
    v, c = room_limit_rupees(p)
    assert v == 3000.0
    assert c.doc == "policy" and c.quote == "q"


def test_amount_wins_over_percent():
    p = PolicyFacts(sum_insured=F("Rs 3,00,000"), room_limit=RoomLimit(amount=4000, percent_of_si=1, page=1, quote="q"))
    assert limit_rupees(p.room_limit, p) == 4000


def test_no_sum_insured_percent_gives_none():
    p = PolicyFacts(icu_limit=Limit(percent_of_si=2, page=1, quote="q"))
    assert icu_limit_rupees(p)[0] is None


def test_legacy_room_fact_used_when_no_rule():
    p = PolicyFacts(room_rent_limit_per_day=F("₹ 3,000"))
    v, c = room_limit_rupees(p)
    assert v == 3000 and c.doc == "policy" and c.page == 1


def test_no_policy():
    assert room_limit_rupees(None) == (None, None)
    assert is_non_payable("gloves", None) is None
    assert STANDARD_NON_PAYABLE


def test_standard_list_matches_gloves():
    rule = NonPayable(standard_list=True, clause="Annex", page=4, quote="q")
    assert is_non_payable("Surgical gloves (2 pairs)", PolicyFacts(non_payable=rule)).page == 4
    off = NonPayable(standard_list=False, items=[], page=4, quote="q")
    assert is_non_payable("Surgical gloves (2 pairs)", PolicyFacts(non_payable=off)) is None


def test_listed_items_match():
    rule = NonPayable(items=["Telephone charges"], page=2, quote="q")
    assert is_non_payable("telephone charges", PolicyFacts(non_payable=rule)) is not None
    assert is_non_payable("MRI brain", PolicyFacts(non_payable=rule)) is None


def test_stay_nights():
    f = ClaimFacts(admission_date=F("10-Mar-2026"), discharge_date=F("13-Mar-2026"))
    assert stay_nights(f) == 3
    assert stay_nights(ClaimFacts()) is None


def test_short_or_partial_descriptions_do_not_match():
    p = PolicyFacts(non_payable=NonPayable(standard_list=True, page=4, quote="q"))
    for d in ["Room charges", "Charges", "Food", "Admission", "Ask doctor", "Cot", "love"]:
        assert is_non_payable(d, p) is None, d
    assert is_non_payable("Admission kit charges", p) is not None


def test_trailing_slash_dash_money():
    p = PolicyFacts(sum_insured=F("Rs. 3,00,000/-"), room_limit=RoomLimit(percent_of_si=1, page=1, quote="q"))
    assert sum_insured(p) == 300000.0
    assert room_limit_rupees(p)[0] == 3000.0


def test_decimal_sum_insured():
    p = PolicyFacts(sum_insured=F("₹ 48,500.00"), room_limit=RoomLimit(percent_of_si=1, page=1, quote="q"))
    assert room_limit_rupees(p)[0] == 485.0
