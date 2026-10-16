"""Step 5 (Report): score, risk band and a short summary."""

import logging

from claimlens.models import SEVERITY_ORDER, Finding
from claimlens.pipeline.context import Ctx

log = logging.getLogger(__name__)
WEIGHTS = {"critical": 40, "high": 20, "medium": 10, "low": 5, "coverage": 0}


def score(findings: list[Finding]) -> int:
    return min(100, sum(WEIGHTS[f.severity] for f in findings))


def risk_band(value: int) -> str:
    return "low" if value < 30 else "review" if value < 60 else "high"


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.severity))


def summarise(ctx: Ctx, findings: list[Finding], outcome_text: str = "") -> str:
    try:
        return ctx.deps.ai.summarise(findings, outcome_text)
    except Exception:  # the summary is a nicety; never fail a case over it
        log.exception("summary failed, using template")
        return f"{len(findings)} problems found: " + "; ".join(f.title for f in findings)
