"""What ClaimLens should find for a recipe: codes, status, risk band, payable, and the true facts (for the
offline AI stand-in). Built from the final recipe, with the product's own weights and bands."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from rapidfuzz import fuzz

from claimlens.models import (Bill, ClaimFacts, CoPay, Deductible, Fact, Limit, LineItem, NonPayable, PolicyFacts,
                              Procedure, ProportionateDeduction, Room, RoomLimit, StoryVerdict, SubLimit,
                              WaitingPeriod, Window)
from claimlens.pipeline.report import WEIGHTS, risk_band
from claimlens.pipeline.text import months_between
from eval.scenarios.recipe import STANDARD_CONSUMABLES, WAITING_LIST, Recipe, day, money
from eval.scenarios.render import claim_pages, clauses

SEVERITY = {"font_outlier": "critical", "hidden_text": "critical", "editing_tool": "high", "late_edit": "medium",
            "multiple_saves": "medium", "sum_mismatch": "high", "date_order": "high",
            "inpatient_outside_stay": "high", "claimed_amount_mismatch": "medium", "duplicate_invoice": "critical",
            "policy_number_mismatch": "high", "waiting_period": "coverage", "room_rent_limit": "coverage",
            "duplicate_page_image": "high", "incomplete_bill": "medium", "unreadable_file": "low",
            "room_days_exceed_stay": "high", "duplicate_charge": "medium", "charge_unrelated_to_treatment": "medium",
            "charge_unusual_for_treatment": "low", "bill_story_unavailable": "low", "icu_limit": "coverage",
            "non_payable_items": "coverage", "bill_outside_cover_window": "coverage"}
# what each bill line is, from its description (the AI stand-in "reads" this)
CATEGORIES = {"Surgeon and OT charges": "surgery", "Anaesthesia": "doctor", "Consumables": "consumables",
              "Medicines": "medicines", "Lab tests": "investigations", "Nursing charges": "nursing"}
PROPORTIONATE_KINDS = {"doctor", "nursing", "surgery", "investigations"}
PDF_ONLY = {"font_outlier", "hidden_text", "editing_tool", "late_edit", "multiple_saves"}  # lost in a photo
LABELS = {"claim": ("claim_form", "Claim Form"), "claim-form": ("claim_form", "Claim Form"),
          "discharge-summary": ("discharge_summary", "Discharge Summary"), "hospital-bill": ("bill", "Hospital Bill"),
          "hospital-bill-again": ("bill", "Hospital Bill"), "pharmacy": ("bill", "Pharmacy Bill"),
          "resume": ("not_insurance", "Curriculum Vitae"), "policy": ("policy", "Policy Schedule"),
          "policy-copy": ("policy", "Policy Schedule")}


@dataclass
class Truth:
    codes: Counter
    severities: dict
    status: str
    band: str | None
    payable: float | None
    facts: ClaimFacts | None = None
    policy: PolicyFacts | None = None
    labels: dict = field(default_factory=dict)  # file stem -> (kind, quote)
    story_verdicts: list = field(default_factory=list)  # StoryVerdict answers for the bill-against-story call
    recommendation: str | None = None  # investigate, query, not_payable, approve_part or approve


def _fact(value, page, quote=None) -> Fact:
    return Fact(value=value, page=page, quote=str(quote if quote is not None else value))


def category_of(desc: str) -> str:
    if desc.startswith("Room charges"):
        return "room"
    if desc.startswith("ICU charges"):
        return "icu"
    return CATEGORIES.get(desc, "consumables" if desc in STANDARD_CONSUMABLES else "other")


def _line(r: Recipe, desc: str, amount: float) -> LineItem:
    category = category_of(desc)
    days, rate = {"room": (r.days, r.room_rate), "icu": (r.icu_days, r.icu_rate)}.get(category, (None, None))
    quote = f"{days} days x Rs {rate:,}" if days else ""
    return LineItem(desc=desc, amount=_fact(amount, 3, money(amount)), category=category,
                    days=_fact(days, 3, quote) if days else None, rate=_fact(rate, 3, quote) if days else None)


def claim_facts(r: Recipe, missing_last: bool) -> ClaimFacts:
    pages = claim_pages(r)
    if missing_last:
        pages = pages[:-1]
    pharmacies = r.pharmacies[: len(pages) - 3]
    items = list(r.items)
    if r.shown_item is not None:
        items[r.shown_item[0]] = (items[r.shown_item[0]][0], r.shown_item[1])
    total = r.shown_total if r.shown_total is not None else r.hospital_total
    bills = [Bill(page=3, kind="hospital", inpatient=True, invoice_no=_fact(r.invoice, 3),
                  date=_fact(day(r.bill_day), 3), total=_fact(total, 3, money(total)),
                  line_items=[_line(r, d, a) for d, a in items])]
    for k, p in enumerate(pharmacies):
        bills.append(Bill(page=4 + k, kind="pharmacy", inpatient=p.inpatient, invoice_no=_fact(p.invoice, 4 + k),
                          date=_fact(day(p.day), 4 + k), total=_fact(p.amount, 4 + k, money(p.amount)),
                          line_items=[LineItem(desc="Medicines", category="medicines",
                                               amount=_fact(p.amount, 4 + k, money(p.amount)))]))
    names = [_fact(r.names.get(title.split(" - ")[0], r.patient), n) for n, (title, _) in enumerate(pages, 1)]
    stay = f"{r.days} days x Rs {r.room_rate:,}"
    return ClaimFacts(
        policy_number=_fact(r.policy_no_on_claim, 1), hospital_name=_fact(r.hospital, 1),
        claimant_name=_fact(r.names.get("Claim Form", r.patient), 1), admission_date=_fact(day(r.admission), 1),
        discharge_date=_fact(day(r.discharge), 1), claim_date=_fact(day(r.claim_day), 1),
        patient_age=_fact(r.patient_age, 2, f"{r.patient_age} years") if r.patient_age else None,
        amount_claimed=_fact(r.claimed, 1, money(r.claimed)), diagnosis=_fact(r.condition, 2), names=names,
        procedures=[Procedure(name=_fact(r.procedure, 2), date=_fact(day(r.procedure_day), 2, f"({day(r.procedure_day)})"))],
        room=Room(rate_per_day=_fact(r.room_rate, 3, stay), days=_fact(r.days, 3, stay)), bills=bills)


def policy_facts(r: Recipe) -> PolicyFacts:
    rules = {}
    for c in clauses(r):
        where = dict(clause=c.number, page=c.page, quote=c.quote)
        rules[c.kind] = {
            "room_limit": lambda: RoomLimit(**where, percent_of_si=1),
            "icu_limit": lambda: Limit(**where, percent_of_si=r.icu_limit_pct),
            "proportionate": lambda: ProportionateDeduction(**where),
            "deductible": lambda: Deductible(**where, amount=r.deductible),
            "co_pay": lambda: CoPay(**where, percent=r.co_pay,
                                    applies="all" if r.co_pay_age is None else "age_over", age=r.co_pay_age),
            "sub_limit": lambda: SubLimit(**where, applies_to=r.condition, amount=r.sub_limit),
            "non_payable": lambda: NonPayable(**where, standard_list=True),
            "window": lambda: Window(**where, pre_days=r.pre_days, post_days=r.post_days)}[c.kind]()
    return PolicyFacts(insurer_name=_fact("Example Health Insurance Co.", 1), policy_number=_fact(r.policy_no, 1),
                       start_date=_fact(day(r.start), 1), sum_insured=_fact(r.sum_insured, 1, money(r.sum_insured)),
                       room_limit=rules.get("room_limit"), icu_limit=rules.get("icu_limit"),
                       proportionate_deduction=rules.get("proportionate"), deductible=rules.get("deductible"),
                       co_pays=[rules["co_pay"]] if "co_pay" in rules else [],
                       sub_limits=[rules["sub_limit"]] if "sub_limit" in rules else [],
                       non_payable=rules.get("non_payable"), window=rules.get("window"),
                       waiting_periods=[WaitingPeriod(condition=c, months=24, clause="3.2", page=2,
                                                      quote="not payable until 24 months of") for c in WAITING_LIST])


def _story(r: Recipe, facts: ClaimFacts) -> list[tuple[str, str]]:
    out = []
    items = [li.amount.value for li in facts.bills[0].line_items]
    if abs(sum(items) - facts.bills[0].total.value) > 1:
        out.append(("sum_mismatch", "high"))
    chain = [r.start, r.admission, r.procedure_day, r.discharge, r.claim_day]
    out += [("date_order", "high")] * sum(1 for a, b in zip(chain, chain[1:]) if a > b)
    for bill in facts.bills:
        d = r.bill_day if bill.kind == "hospital" else next(p.day for p in r.pharmacies if p.invoice == bill.invoice_no.value)
        if bill.inpatient and not (r.admission <= d <= r.discharge):
            out.append(("inpatient_outside_stay", "high"))
    claimant = str(facts.claimant_name.value).lower()
    for name in {(str(n.value).lower(), n.page) for n in facts.names}:
        ratio = fuzz.ratio(claimant, name[0])
        if ratio < 100:
            out.append(("name_mismatch", "low" if ratio >= 85 else "high"))
    if abs(facts.amount_claimed.value - sum(b.total.value for b in facts.bills)) > 1:
        out.append(("claimed_amount_mismatch", "medium"))
    key = lambda v: "".join(c for c in v.upper() if c.isalnum()).translate(str.maketrans("OIL", "011"))
    a, b = key(r.policy_no_on_claim), key(r.policy_no)
    if a != b:
        out.append(("policy_number_mismatch", "medium" if a in b or b in a else "high"))
    nights = (r.discharge - r.admission).days
    if nights >= 0 and r.days + r.icu_days > nights + 1:
        out.append(("room_days_exceed_stay", "high"))
    seen = set()
    for bill in facts.bills:
        for li in bill.line_items:
            key = (" ".join(li.desc.lower().split()), li.amount.value, bill.date.value)
            if key in seen:
                out.append(("duplicate_charge", "medium"))
            seen.add(key)
    return out


def in_waiting(r: Recipe) -> bool:
    return r.condition in WAITING_LIST and months_between(r.start, r.procedure_day) < 24


def outside_window(r: Recipe, p) -> bool:
    return r.pre_days is not None and (p.day < r.admission - timedelta(days=r.pre_days)
                                       or p.day > r.discharge + timedelta(days=r.post_days))


def expected_settlement(r: Recipe, missing_last: bool = False) -> float:
    """What the insurer should pay, worked out from the recipe's own numbers (not by calling the product):
    bills less what the rules take, capped at the claim, then condition limit, deductible, co-pay, sum insured.
    `missing_last`: the last pharmacy page never reached the claim."""
    if in_waiting(r):
        return 0.0
    items = list(r.items)
    if r.shown_item is not None:  # a retyped line is the amount the bill shows
        items[r.shown_item[0]] = (items[r.shown_item[0]][0], r.shown_item[1])
    pharmacies = r.pharmacies[:-1] if missing_last else r.pharmacies
    billed = sum(a for _, a in items) + sum(p.amount for p in pharmacies)

    cut = 0
    room_limit = r.sum_insured / 100 if r.room_limit else None
    if room_limit and r.room_rate > room_limit:
        cut += round((r.room_rate - room_limit) * r.days)
        if r.proportionate:
            share = 1 - room_limit / r.room_rate
            cut += sum(round(round(a * share, 2)) for d, a in items if category_of(d) in PROPORTIONATE_KINDS)
    if r.icu_limit_pct and r.icu_days:
        icu_limit = r.sum_insured * r.icu_limit_pct / 100
        if r.icu_rate > icu_limit:
            cut += round((r.icu_rate - icu_limit) * r.icu_days)
    if r.non_payable_standard:
        named = {d for d, _ in r.consumables}
        cut += sum(a for d, a in items if d in named)
    cut += sum(p.amount for p in pharmacies if outside_window(r, p))

    amount = max(0, min(r.claimed, billed - cut))
    if r.sub_limit:
        amount = min(amount, r.sub_limit)
    amount -= min(r.deductible, amount)
    if r.co_pay and (r.co_pay_age is None or (r.patient_age is not None and r.patient_age > r.co_pay_age)):
        amount -= round(amount * r.co_pay / 100)
    return float(round(max(0, min(amount, r.sum_insured))))


def expected_recommendation(found: list, band: str | None, claimed: float | None, payable: float | None,
                            whole_claim: bool = False, amount_unclear: bool = False) -> str:
    """The reviewer's action, in the product's order: investigate, query, not_payable, approve_part, approve."""
    if band == "high" or any(sev == "critical" for _, sev in found):
        return "investigate"
    if (band == "review" or claimed is None or amount_unclear
            or any(code == "unreadable_file" for code, _ in found)):
        return "query"
    if whole_claim or payable == 0:
        return "not_payable"
    return "approve_part" if payable < claimed - 1 else "approve"


def truth_of(r: Recipe, forgeries: list[str], fmt: str, ocr: bool) -> Truth:
    from eval.scenarios.render import render

    files = render(r, forgeries, fmt)
    labels = {}
    for card, name, _ in files:
        stem = name.rsplit(".", 1)[0]
        labels[name] = LABELS.get(stem) or LABELS.get(stem.rstrip("0123456789-").rstrip("-")) or LABELS["claim"]
    if {"cv_in_claim", "bill_in_policy", "policy_in_claim"} & set(forgeries):
        return Truth(Counter(), {}, "REJECTED", None, None, labels=labels)
    found: list[tuple[str, str]] = []
    claim_files = [f for f in files if f[0] == "claim"]
    if fmt == "photos" and not ocr:
        found += [("unreadable_file", "low")] * len(claim_files)
        return _done(found, None, None, policy_facts(r), labels)
    facts = claim_facts(r, "missing_page" in forgeries)
    if r.shown_total is not None or r.shown_item is not None:
        found += [("font_outlier", "critical"), ("hidden_text", "critical"), ("editing_tool", "high")]
    if "editor_resave" in forgeries:
        found.append(("editing_tool", "high"))
    if "late_edit" in forgeries:
        found.append(("late_edit", "medium"))
    if "incremental_save" in forgeries:
        found.append(("multiple_saves", "medium"))
    if fmt == "photos":
        found = [f for f in found if f[0] not in PDF_ONLY]
    found += _story(r, facts)
    if "reused_invoice" in forgeries:
        found.append(("duplicate_invoice", "critical"))
    if "duplicate_page" in forgeries:
        found.append(("duplicate_page_image", "high"))
    if "missing_page" in forgeries:
        found.append(("incomplete_bill", "medium"))
    waiting = in_waiting(r)
    if waiting:
        found.append(("waiting_period", "coverage"))
    excess = (r.room_rate - r.room_limit) * r.days if r.room_limit and r.room_rate > r.room_limit else 0
    if excess:
        found.append(("room_rent_limit", "coverage"))
    if r.icu_limit_pct and r.icu_days and r.icu_rate > r.sum_insured * r.icu_limit_pct / 100:
        found.append(("icu_limit", "coverage"))
    if r.non_payable_standard and r.consumables:
        found.append(("non_payable_items", "coverage"))
    present = r.pharmacies[:len(facts.bills) - 1]
    found += [("bill_outside_cover_window", "coverage")] * sum(1 for p in present if outside_window(r, p))
    verdicts = []
    if r.unrelated_item:
        desc = r.unrelated_item[0]
        found.append(("charge_unrelated_to_treatment", "medium"))
        verdicts = [StoryVerdict(item=desc, verdict="unrelated", reason=f"{desc} has no link to {r.condition}.",
                                 bill_page=3, bill_quote=desc)]
    payable = expected_settlement(r, "missing_page" in forgeries)
    unclear = bool(r.co_pay and r.co_pay_age is not None and r.patient_age is None and not waiting)
    return _done(found, payable, facts, policy_facts(r), labels, r.claimed, waiting, unclear, verdicts)


def _done(found, payable, facts, policy, labels, claimed=None, whole_claim=False, unclear=False,
          verdicts=()) -> Truth:
    severities: dict[str, list] = {}
    for code, sev in found:
        severities.setdefault(code, []).append(sev)
    score = min(100, sum(WEIGHTS[s] for _, s in found))
    band = risk_band(score)
    return Truth(Counter(c for c, _ in found), severities, "READY", band, payable, facts, policy, labels,
                 list(verdicts), expected_recommendation(found, band, claimed, payable, whole_claim, unclear))
