from claimlens.models import Case, ClaimFacts
from claimlens.pipeline.checks.duplicate import check_duplicate, invoice_key, register_invoices
from claimlens.pipeline.checks.story import check_story


def _codes(findings, code):
    return [f for f in findings if f.code == code]


def test_sum_mismatch(ctx):
    found = _codes(check_story(ctx), "sum_mismatch")
    assert len(found) == 1 and found[0].severity == "high"
    c = found[0].citations[0]
    assert (c.doc, c.page, c.quote) == ("claim", 3, "Rs 48,500")


def test_inpatient_outside_stay(ctx):
    found = _codes(check_story(ctx), "inpatient_outside_stay")
    assert len(found) == 1 and found[0].severity == "high"
    c = found[0].citations[0]
    assert (c.page, c.quote) == (4, "Date: 15-Mar-2026")


def test_name_mismatch_low(ctx):
    found = _codes(check_story(ctx), "name_mismatch")
    assert len(found) == 1 and found[0].severity == "low"
    assert found[0].citations[0].quote == "Rahul Varma"


def test_no_claimed_amount_mismatch(ctx):
    assert _codes(check_story(ctx), "claimed_amount_mismatch") == []


def test_no_date_order_finding(ctx):
    assert _codes(check_story(ctx), "date_order") == []


def test_missing_fields_no_crash(ctx):
    ctx.claim_facts = ClaimFacts()
    assert check_story(ctx) == []
    assert check_duplicate(ctx) == []


def test_invoice_key():
    assert invoice_key("INV-SEH-2026-0412") == "INVSEH20260412"
    assert invoice_key(" inv seh/2026.0412 ") == "INVSEH20260412"


def test_duplicate_found(ctx):
    ctx.deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    found = check_duplicate(ctx)
    assert len(found) == 1 and found[0].severity == "critical"
    assert "CLM-1043" in found[0].detail
    assert found[0].citations[0].quote == "INV-SEH-2026-0412"


def test_duplicate_same_case_ignored(ctx):
    ctx.deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": ctx.case_id})
    assert check_duplicate(ctx) == []


def test_register_invoices(ctx):
    register_invoices(ctx)
    assert ctx.deps.db.get_invoice("INVSEH20260412")["case_id"] == ctx.case_id
    assert ctx.deps.db.get_invoice("PH7781")["amount"] == 3000


def test_date_order_detects_discharge_before_admission(ctx):
    ctx.claim_facts.discharge_date = ctx.claim_facts.discharge_date.model_copy(update={"value": "05-Mar-2026"})
    found = _codes(check_story(ctx), "date_order")
    assert found and found[0].citations[0].quote == "Date of discharge: 13-Mar-2026"


def _with_policy_number(ctx, value):
    from claimlens.pipeline.checks.story import check_story

    pn = ctx.policy_facts.policy_number
    ctx.policy_facts = ctx.policy_facts.model_copy(
        update={"policy_number": None if value is None else pn.model_copy(update={"value": value})})
    return [f for f in check_story(ctx) if f.code == "policy_number_mismatch"]


def test_policy_number_match_no_finding(ctx):
    assert _with_policy_number(ctx, "EH-2025-778812") == []


def test_policy_number_formatting_ignored(ctx):
    assert _with_policy_number(ctx, "EH 2025/778812") == []


def test_policy_number_mismatch(ctx):
    [f] = _with_policy_number(ctx, "EH-2024-000001")
    assert f.severity == "high"
    assert f.title == "Claim names policy EH-2025-778812, but the uploaded policy is EH-2024-000001"
    assert [c.doc for c in f.citations] == ["claim", "policy"]


def test_policy_number_missing_skips(ctx):
    assert _with_policy_number(ctx, None) == []


def test_policy_number_ocr_confusions_ignored(ctx):
    # O/0 and I/l/1 read differently by OCR are the same number
    assert _with_policy_number(ctx, "EH-2O25-7788I2") == []


def test_policy_number_containing_the_other_is_medium(ctx):
    # renewal / endorsement suffix, or a member number inside a group policy
    [f] = _with_policy_number(ctx, "EH-2025-778812/2026/01")
    assert f.severity == "medium"
    assert "renewal" in f.detail


def test_name_mismatch_works_without_a_grounded_claimant_name(ctx):
    # on photos OCR may read "Iyer" as "lyer", so the claimant fact fails grounding; the names on the pages remain
    from claimlens.models import Fact

    f = ctx.claim_facts
    names = [Fact(value="Kavya lyer", page=1, quote="Kavya lyer"), Fact(value="Suresh Reddy", page=2, quote="Suresh Reddy"),
             Fact(value="Kavya lyer", page=3, quote="Kavya lyer")]
    ctx.claim_facts = f.model_copy(update={"claimant_name": None, "names": names})
    [m] = _codes(check_story(ctx), "name_mismatch")
    assert m.severity == "high" and "Suresh Reddy" in m.title and m.citations[0].page == 2


def test_no_majority_name_means_no_name_finding(ctx):
    from claimlens.models import Fact

    names = [Fact(value="A Kumar", page=1, quote="A Kumar"), Fact(value="B Rao", page=2, quote="B Rao")]
    ctx.claim_facts = ctx.claim_facts.model_copy(update={"claimant_name": None, "names": names})
    assert _codes(check_story(ctx), "name_mismatch") == []


def _fact(value, quote=None, page=3):
    from claimlens.models import Fact

    return Fact(value=value, page=page, quote=quote or str(value))


def _set_bills(ctx, bills):
    ctx.claim_facts = ctx.claim_facts.model_copy(update={"bills": bills})


def _room_days(ctx, days):
    from claimlens.models import Room

    room = ctx.claim_facts.room
    ctx.claim_facts = ctx.claim_facts.model_copy(
        update={"room": Room(rate_per_day=room.rate_per_day if room else None, days=_fact(days, f"{days} days"))})
    return _codes(check_story(ctx), "room_days_exceed_stay")


def test_room_days_exceed_stay(ctx):
    from claimlens.pipeline.rules import stay_nights

    assert stay_nights(ctx.claim_facts) == 3
    [f] = _room_days(ctx, 6)
    assert f.severity == "high" and f.citations[0].quote == "6 days"


def test_room_days_within_tolerance(ctx):
    assert _room_days(ctx, 4) == []


def test_room_days_ignored_when_dates_inverted(ctx):
    ctx.claim_facts.discharge_date = ctx.claim_facts.discharge_date.model_copy(update={"value": "05-Mar-2026"})
    assert _room_days(ctx, 9) == []


def test_room_days_summed_over_room_and_icu_lines(ctx):
    from claimlens.models import Bill, LineItem

    bill = Bill(page=3, kind="hospital", inpatient=True, line_items=[
        LineItem(desc="Room", category="room", days=_fact(2), amount=_fact(2000)),
        LineItem(desc="ICU", category="icu", days=_fact(3), amount=_fact(9000))])
    _set_bills(ctx, [bill])
    [f] = _codes(check_story(ctx), "room_days_exceed_stay")
    assert f.severity == "high"


def _two_lines(ctx, dates, desc="CBC test", amount=450, same_bill=True):
    from claimlens.models import Bill, LineItem

    def line():
        return LineItem(desc=desc, amount=_fact(amount, f"Rs {amount}"))

    def bill(d):
        return Bill(page=3, kind="hospital", date=_fact(d) if d else None, line_items=[line()])

    if same_bill:
        b = bill(dates[0])
        b.line_items.append(line())
        _set_bills(ctx, [b])
    else:
        _set_bills(ctx, [bill(d) for d in dates])
    return _codes(check_story(ctx), "duplicate_charge")


def test_duplicate_charge_same_day(ctx):
    [f] = _two_lines(ctx, ["12-Mar-2026"])
    assert f.severity == "medium" and f.citations[0].quote == "Rs 450"


def test_same_item_different_days_not_duplicate(ctx):
    assert _two_lines(ctx, ["12-Mar-2026", "13-Mar-2026"], "Paracetamol", 120, same_bill=False) == []


def test_duplicate_across_bills_same_day(ctx):
    assert len(_two_lines(ctx, ["12-Mar-2026", "12-Mar-2026"], "Paracetamol", 120, same_bill=False)) == 1


def test_no_date_never_duplicate(ctx):
    assert _two_lines(ctx, [None]) == []
