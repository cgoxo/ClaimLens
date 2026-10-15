"""What ClaimLens should find for a recipe: codes, status, risk band, payable, and the true facts (for the
offline AI stand-in). Built from the final recipe, with the product's own weights and bands."""

from collections import Counter
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from claimlens.models import Bill, ClaimFacts, DocLabel, Fact, LineItem, PolicyFacts, Procedure, Room, WaitingPeriod
from claimlens.pipeline.report import WEIGHTS, risk_band
from claimlens.pipeline.text import months_between
from eval.scenarios.recipe import WAITING_LIST, Recipe, day, money
from eval.scenarios.render import claim_pages

SEVERITY = {"font_outlier": "critical", "hidden_text": "critical", "editing_tool": "high", "late_edit": "medium",
            "multiple_saves": "medium", "sum_mismatch": "high", "date_order": "high",
            "inpatient_outside_stay": "high", "claimed_amount_mismatch": "medium", "duplicate_invoice": "critical",
            "policy_number_mismatch": "high", "waiting_period": "coverage", "room_rent_limit": "coverage",
            "duplicate_page_image": "high", "incomplete_bill": "medium", "unreadable_file": "low"}
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


def _fact(value, page, quote=None) -> Fact:
    return Fact(value=value, page=page, quote=str(quote if quote is not None else value))


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
                  line_items=[LineItem(desc=d, amount=_fact(a, 3, money(a))) for d, a in items])]
    for k, p in enumerate(pharmacies):
        bills.append(Bill(page=4 + k, kind="pharmacy", inpatient=p.inpatient, invoice_no=_fact(p.invoice, 4 + k),
                          date=_fact(day(p.day), 4 + k), total=_fact(p.amount, 4 + k, money(p.amount)),
                          line_items=[LineItem(desc="Medicines", amount=_fact(p.amount, 4 + k, money(p.amount)))]))
    names = [_fact(r.names.get(title.split(" - ")[0], r.patient), n) for n, (title, _) in enumerate(pages, 1)]
    stay = f"{r.days} days x Rs {r.room_rate:,}"
    return ClaimFacts(
        policy_number=_fact(r.policy_no_on_claim, 1), hospital_name=_fact(r.hospital, 1),
        claimant_name=_fact(r.names.get("Claim Form", r.patient), 1), admission_date=_fact(day(r.admission), 1),
        discharge_date=_fact(day(r.discharge), 1), claim_date=_fact(day(r.claim_day), 1),
        amount_claimed=_fact(r.claimed, 1, money(r.claimed)), diagnosis=_fact(r.condition, 2), names=names,
        procedures=[Procedure(name=_fact(r.procedure, 2), date=_fact(day(r.procedure_day), 2, f"({day(r.procedure_day)})"))],
        room=Room(rate_per_day=_fact(r.room_rate, 3, stay), days=_fact(r.days, 3, stay)), bills=bills)


def policy_facts(r: Recipe) -> PolicyFacts:
    limit = (_fact(r.room_limit, 1, "Room rent is payable up to 1% of the sum insured per day")
             if r.room_limit else None)
    return PolicyFacts(insurer_name=_fact("Example Health Insurance Co.", 1), policy_number=_fact(r.policy_no, 1),
                       start_date=_fact(day(r.start), 1), sum_insured=_fact(r.sum_insured, 1, money(r.sum_insured)),
                       room_rent_limit_per_day=limit,
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
    return out


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
    waiting = r.condition in WAITING_LIST and months_between(r.start, r.procedure_day) < 24
    if waiting:
        found.append(("waiting_period", "coverage"))
    excess = (r.room_rate - r.room_limit) * r.days if r.room_limit and r.room_rate > r.room_limit else 0
    if excess:
        found.append(("room_rent_limit", "coverage"))
    payable = 0.0 if waiting else float(min(r.claimed - excess, r.sum_insured))
    return _done(found, payable, facts, policy_facts(r), labels)


def _done(found, payable, facts, policy, labels) -> Truth:
    severities: dict[str, list] = {}
    for code, sev in found:
        severities.setdefault(code, []).append(sev)
    score = min(100, sum(WEIGHTS[s] for _, s in found))
    return Truth(Counter(c for c, _ in found), severities, "READY", risk_band(score), payable, facts, policy, labels)
