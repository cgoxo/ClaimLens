"""Arithmetic on policy rules: limits in rupees, the standard non-payable list, stay length."""
import re

from rapidfuzz import fuzz

from claimlens.models import Citation, ClaimFacts, Fact, Limit, PolicyFacts, Rule
from claimlens.pipeline.text import parse_date, parse_money

STANDARD_NON_PAYABLE: tuple[str, ...] = (
    "gloves", "mask", "admission kit", "admission charges", "registration charges", "attendant charges",
    "toiletries", "food for attendant", "cotton", "diapers", "documentation charges",
)


def rule_citation(rule: Rule) -> Citation:
    return Citation(doc="policy", page=rule.page, quote=rule.quote)


def _fact_citation(fact: Fact) -> Citation:
    return Citation(doc="policy", page=fact.page, quote=fact.quote)


def sum_insured(p: PolicyFacts | None) -> float | None:
    if p is None or p.sum_insured is None:
        return None
    return parse_money(p.sum_insured.value)


def limit_rupees(limit: Limit | None, p: PolicyFacts | None) -> float | None:
    if limit is None:
        return None
    if limit.amount is not None:
        return float(limit.amount)
    if limit.percent_of_si is not None:
        si = sum_insured(p)
        if si is not None:
            return limit.percent_of_si / 100 * si
    return None


def room_limit_rupees(p: PolicyFacts | None) -> tuple[float | None, Citation | None]:
    if p is None:
        return None, None
    if p.room_limit is not None:
        v = limit_rupees(p.room_limit, p)
        if v is not None:
            return v, rule_citation(p.room_limit)
    if p.room_rent_limit_per_day is not None:
        v = parse_money(p.room_rent_limit_per_day.value)
        if v is not None:
            return v, _fact_citation(p.room_rent_limit_per_day)
    return None, None


def icu_limit_rupees(p: PolicyFacts | None) -> tuple[float | None, Citation | None]:
    if p is None or p.icu_limit is None:
        return None, None
    v = limit_rupees(p.icu_limit, p)
    return (v, rule_citation(p.icu_limit)) if v is not None else (None, None)


def _same_word(need: str, word: str) -> bool:
    # short words must match exactly: "ask" is not "mask"
    return need == word or (len(need) > 4 and fuzz.ratio(need, word) >= 85)


def is_non_payable(desc: str, p: PolicyFacts | None) -> Citation | None:
    if p is None or p.non_payable is None or not desc:
        return None
    rule = p.non_payable
    names = list(rule.items)
    if rule.standard_list:
        names += STANDARD_NON_PAYABLE
    words = re.findall(r"[a-z0-9]+", desc.lower())
    for name in names:
        need = re.findall(r"[a-z0-9]+", name.lower())
        if need and all(any(_same_word(n, w) for w in words) for n in need):
            return rule_citation(rule)
    return None


def stay_nights(f: ClaimFacts) -> int | None:
    if f.admission_date is None or f.discharge_date is None:
        return None
    a, d = parse_date(f.admission_date.value), parse_date(f.discharge_date.value)
    if a is None or d is None:
        return None
    return (d - a).days
