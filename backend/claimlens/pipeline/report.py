"""Step 5 (Report): score, risk band, payable amount and a short summary."""

import logging

from claimlens.models import SEVERITY_ORDER, Finding
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.settlement import main_treatment_excluded
from claimlens.pipeline.text import parse_money

log = logging.getLogger(__name__)
WEIGHTS = {"critical": 40, "high": 20, "medium": 10, "low": 5, "coverage": 0}


def score(findings: list[Finding]) -> int:
    return min(100, sum(WEIGHTS[f.severity] for f in findings))


def risk_band(value: int) -> str:
    return "low" if value < 30 else "review" if value < 60 else "high"


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.severity))


def payable(ctx: Ctx, findings: list[Finding]) -> float | None:
    f = ctx.claim_facts
    claimed = parse_money(f.amount_claimed.value) if f and f.amount_claimed else None
    if claimed is None:
        return None
    if main_treatment_excluded(ctx.claim_facts, findings):
        return 0.0
    amount = max(0.0, claimed - sum(x.amount_not_payable for x in findings))
    p = ctx.policy_facts
    cap = parse_money(p.sum_insured.value) if p and p.sum_insured else None
    return min(amount, cap) if cap else amount


def summarise(ctx: Ctx, findings: list[Finding]) -> str:
    try:
        return ctx.deps.ai.summarise(findings)
    except Exception:  # the summary is a nicety; never fail a case over it
        log.exception("summary failed, using template")
        return f"{len(findings)} problems found: " + "; ".join(f.title for f in findings)
