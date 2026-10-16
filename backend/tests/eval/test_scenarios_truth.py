from collections import Counter
from datetime import date, timedelta

import numpy as np
import pymupdf
from reportlab.pdfbase.pdfmetrics import stringWidth

from eval.scenarios.forgeries import FORGERIES, pick
from eval.scenarios.recipe import Pharmacy, Recipe, make_recipe
from eval.scenarios.render import W, clauses, policy_pdf, render
from eval.scenarios.truth import expected_recommendation, expected_settlement, policy_facts, truth_of


def _truth(names=(), fmt="one_pdf", ocr=True, seed=3):
    recipe = make_recipe(seed, "t1", rules=False)  # the plain claim: what each forgery does shows alone
    for n in names:
        recipe = FORGERIES[n].apply(recipe)
    return recipe, truth_of(recipe, list(names), fmt, ocr=ocr)


def test_clean_claim():
    recipe, t = _truth()
    assert t.codes == Counter() and t.status == "READY" and t.band == "low"
    assert t.payable == recipe.claimed


def test_waiting_period_pays_nothing_and_stays_low():
    _, t = _truth(["waiting_period"])
    assert t.codes == Counter({"waiting_period": 1}) and t.band == "low" and t.payable == 0


def test_room_over_limit_reduces_payable():
    recipe, t = _truth(["room_over_limit"], seed=5)
    assert t.codes == Counter({"room_rent_limit": 1})
    assert t.payable == recipe.claimed - (recipe.room_rate - recipe.room_limit) * recipe.days


def test_retyped_total():
    _, t = _truth(["retype_total"])
    assert t.codes == Counter({"font_outlier": 1, "hidden_text": 1, "sum_mismatch": 1, "editing_tool": 1})
    assert t.band == "high"  # 40 + 40 + 20 + 20


def test_name_typo_is_low_and_another_person_is_high():
    _, typo = _truth(["name_typo"])
    _, other = _truth(["different_name"])
    assert typo.codes == Counter({"name_mismatch": 1}) and typo.severities["name_mismatch"] == ["low"]
    assert other.severities["name_mismatch"] == ["high"]


def test_rejections_have_no_codes():
    for name in ("cv_in_claim", "bill_in_policy", "policy_in_claim"):
        _, t = _truth([name])
        assert t.status == "REJECTED" and t.codes == Counter() and t.payable is None


def test_photos_without_ocr_are_unreadable_notes_only():
    recipe, t = _truth(fmt="photos", ocr=False)
    files = render(recipe, [], "photos")
    claim_files = [f for f in files if f[0] == "claim"]
    assert t.codes == Counter({"unreadable_file": len(claim_files)}) and t.payable is None


def test_photos_with_ocr_lose_only_pdf_structure_signals():
    _, t = _truth(["retype_total"], fmt="photos", ocr=True)
    assert t.codes == Counter({"sum_mismatch": 1})  # fonts, hidden text, file metadata don't survive a photo


def test_pick_never_combines_conflicts():
    rng = np.random.default_rng(0)
    for _ in range(300):
        chosen = pick(rng)
        for a in chosen:
            assert not (FORGERIES[a].conflicts & set(chosen)), chosen


def test_render_is_deterministic():
    recipe = make_recipe(9, "t1")
    a = render(recipe, ["retype_total"], "split_files")
    b = render(recipe, ["retype_total"], "split_files")
    assert [(c, n) for c, n, _ in a] == [(c, n) for c, n, _ in b]


def _text(pdf: bytes) -> str:
    return " ".join(" ".join(page.get_text().split()) for page in pymupdf.open(stream=pdf, filetype="pdf"))


def _all_rules() -> Recipe:
    return Recipe(run="t", seed=1, patient="Asha Iyer", condition="Appendicitis", room_limit=3000, icu_limit_pct=2,
                  proportionate=True, deductible=25000, co_pay=20, co_pay_age=60, sub_limit=80000,
                  non_payable_standard=True, pre_days=30, post_days=60)


def test_policy_pdf_prints_every_rule():
    r = _all_rules()
    text = _text(policy_pdf(r))
    sentences = [
        "Room rent is payable up to 1% of the sum insured per day",
        "ICU charges are payable up to 2% of the sum insured per day.",
        "Proportionate deduction applies to doctor, nursing, surgery and test charges.",
        "A deductible of Rs 25,000 applies to each claim, before any co-pay.",
        "A co-pay of 20% applies if the patient is aged over 60.",
        "Appendicitis treatment is payable up to Rs 80,000 per claim.",
        "Standard non-payable items (gloves, masks, admission kit, etc.) are not payable.",
        "Bills are covered from 30 days before admission to 60 days after discharge."]
    for sentence in sentences:
        assert sentence in text, sentence
    assert [c.quote for c in clauses(r)] == sentences
    assert all(stringWidth(c.quote, "Helvetica", 11) < W - 100 for c in clauses(r))  # each fits on one line
    assert "Clause 5.5" in text and "Clause 2.2" in text


def test_policy_facts_carry_every_rule_with_its_quote():
    p = policy_facts(_all_rules())
    assert p.room_limit.percent_of_si == 1 and p.icu_limit.percent_of_si == 2 and p.proportionate_deduction
    assert p.deductible.amount == 25000 and p.co_pays[0].applies == "age_over" and p.co_pays[0].age == 60
    assert p.sub_limits[0].applies_to == "Appendicitis" and p.non_payable.standard_list
    assert (p.window.pre_days, p.window.post_days) == (30, 60)
    assert all(rule.quote and rule.clause for rule in
               [p.room_limit, p.icu_limit, p.proportionate_deduction, p.deductible, *p.co_pays, *p.sub_limits,
                p.non_payable, p.window])


def test_rules_are_off_unless_the_recipe_has_them():
    text = _text(policy_pdf(Recipe(run="t", seed=1, patient="Asha Iyer")))
    for word in ("deductible", "co-pay", "ICU", "Proportionate", "window", "Section 5"):
        assert word not in text


def _plain(**changes) -> Recipe:  # room 3 x 3,000 plus one 91,000 line: bills of 100,000
    return Recipe(run="t", seed=1, patient="Asha Iyer", other_items=[("Surgeon and OT charges", 91000)],
                  claimed=100000, **changes)


def test_truth_settlement_copay_and_deductible():
    assert expected_settlement(_plain()) == 100000
    assert expected_settlement(_plain(deductible=25000, co_pay=10)) == 67500  # (100,000 - 25,000) x 90%


def test_truth_settlement_follows_the_order_of_the_rules():
    # waiting period: nothing is payable whatever else applies
    waiting = _plain(condition="Hernia", sub_limit=60000, deductible=10000, co_pay=20, start=date(2025, 6, 1))
    assert expected_settlement(waiting) == 0
    # sub-limit first, then deductible, then co-pay: (60,000 - 10,000) x 80%
    assert expected_settlement(_plain(sub_limit=60000, deductible=10000, co_pay=20)) == 40000
    # the co-pay above an age: applies over it, not at it, and not when the age is unknown
    assert expected_settlement(_plain(co_pay=20, co_pay_age=60, patient_age=61)) == 80000
    assert expected_settlement(_plain(co_pay=20, co_pay_age=60, patient_age=60)) == 100000
    assert expected_settlement(_plain(co_pay=20, co_pay_age=60)) == 100000


def test_truth_settlement_room_icu_proportionate_non_payable_and_window():
    # room 3 days at Rs 4,500 against a Rs 3,000 limit: Rs 4,500 excess, a third off the surgeon's line
    r = _plain(room_limit=3000, room_rate=4500, proportionate=True)
    r = r.copy(claimed=r.hospital_total)
    assert expected_settlement(r) == r.hospital_total - 4500 - round(91000 / 3)
    # ICU 2 days at Rs 9,000 against 2% of Rs 3,00,000 (Rs 6,000): Rs 6,000 excess; the gloves and mask are not paid
    r = _plain(icu_limit_pct=2, icu_days=2, icu_rate=9000, consumables=[("Gloves", 700), ("Face mask", 300)],
               non_payable_standard=True)
    r = r.copy(claimed=r.hospital_total)
    assert expected_settlement(r) == r.hospital_total - 6000 - 1000
    # the same gloves on a policy without the clause are paid
    assert expected_settlement(r.copy(non_payable_standard=False, icu_limit_pct=None)) == r.hospital_total
    # a pharmacy bill dated 40 days before admission against a 30-day window
    early = Pharmacy("PH-1", date(2026, 3, 10) - timedelta(days=40), 800, inpatient=False)
    w = _plain(pre_days=30, post_days=60, pharmacies=[early])
    w = w.copy(claimed=w.hospital_total + 800)
    assert expected_settlement(w) == w.hospital_total


def test_recommendation_precedence():
    assert expected_recommendation([("font_outlier", "critical")], "low", 100, 0) == "investigate"
    assert expected_recommendation([], "high", 100, 100) == "investigate"
    assert expected_recommendation([], "review", 100, 0) == "query"
    assert expected_recommendation([], "low", 100, 0, whole_claim=True) == "not_payable"
    assert expected_recommendation([], "low", 100, 0) == "not_payable"
    assert expected_recommendation([], "low", 100, 98) == "approve_part"
    assert expected_recommendation([], "low", 100, 100) == "approve"
    assert expected_recommendation([], "low", 100, 99.5) == "approve"
    assert expected_recommendation([], "low", 100, 100, amount_unclear=True) == "query"
    assert expected_recommendation([("unreadable_file", "low")], "low", None, None) == "query"


def test_new_forgeries_expect_their_findings():
    _, extra = _truth(["extra_room_days"])
    assert extra.codes == Counter({"room_days_exceed_stay": 1})
    assert extra.severities["room_days_exceed_stay"] == ["high"]
    _, unrelated = _truth(["unrelated_charge"])
    assert unrelated.codes == Counter({"charge_unrelated_to_treatment": 1})
    assert [v.verdict for v in unrelated.story_verdicts] == ["unrelated"] and unrelated.band == "low"
    _, dup = _truth(["duplicate_line"])
    assert dup.codes == Counter({"duplicate_charge": 1})
