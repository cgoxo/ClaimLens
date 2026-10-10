import json
import shutil

import pytest

from claimlens.ai import FakeAi
from claimlens.models import Citation, Finding, PageInfo
from claimlens.pipeline.checks import ALL_CHECKS
from claimlens.pipeline.extract import extract
from claimlens.pipeline.prove import prove
from claimlens.pipeline.report import payable, risk_band, score, sort_findings, summarise
from tests.conftest import FAKE_AI, make_ctx


def _finding(doc, page, quote, severity="high", code="x"):
    return Finding(id=f"{code}-{page}-{quote[:5]}", check="story", code=code, severity=severity, title=quote,
                   citations=[Citation(doc=doc, page=page, quote=quote)])


def test_prove_keeps_real_quote(ctx):
    kept, dropped = prove(ctx, [_finding("claim", 3, "Rs 48,500")])
    assert len(kept) == 1 and kept[0].verified and dropped == []


def test_prove_drops_invented_quote(ctx):
    kept, dropped = prove(ctx, [_finding("claim", 2, "patient has diabetes, a pre-existing disease")])
    assert kept == []
    assert dropped[0]["title"].startswith("patient has diabetes") and dropped[0]["reason"]


def test_prove_ocr_threshold(ctx):
    ctx.read.pages.append(PageInfo(doc="claim", page=9, kind="image", text="Total amount Rs 12,345 paid",
                                   width=100, height=100, png_key="k"))
    kept, _ = prove(ctx, [_finding("claim", 9, "Totai arnount Rs 12,345 paid")])  # OCR letter typos
    assert len(kept) == 1
    # the same near-miss on a digital page is not good enough
    kept, _ = prove(ctx, [_finding("claim", 1, "Amount claimed: Rs 51,599 extra words")])
    assert kept == []


def test_score_caps_at_100():
    assert score([_finding("claim", 1, "a", "critical")] * 3) == 100
    assert score([_finding("claim", 1, "a", "low"), _finding("claim", 1, "b", "coverage")]) == 5


def test_risk_bands():
    assert (risk_band(29), risk_band(30), risk_band(59), risk_band(60)) == ("low", "review", "review", "high")


def test_sort_findings():
    order = [f.severity for f in sort_findings([_finding("c", 1, "a", s) for s in ("low", "coverage", "critical", "high")])]
    assert order == ["critical", "high", "low", "coverage"]


def _checked(ctx):
    findings = [f for check in ALL_CHECKS for f in check(ctx)]
    kept, _ = prove(ctx, findings)
    return kept


def test_payable_zero_when_main_procedure_not_covered(ctx):
    assert payable(ctx, _checked(ctx)) == 0


def test_payable_subtracts_room_excess_when_covered(tmp_path):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    policy = json.loads((fixtures / "policy.json").read_text())
    policy["waiting_periods"] = []
    (fixtures / "policy.json").write_text(json.dumps(policy))
    coverage = json.loads((fixtures / "coverage.json").read_text())
    (fixtures / "coverage.json").write_text(json.dumps([c for c in coverage if c["clause"] != "3.2"]))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    assert payable(c, _checked(c)) == 47000


def test_payable_none_without_claimed_amount(ctx):
    ctx.claim_facts.amount_claimed = None
    assert payable(ctx, []) is None


def test_summary_from_ai(ctx):
    assert summarise(ctx, []).startswith("High risk")


def test_summary_fallback(ctx):
    class Broken:
        def summarise(self, findings):
            raise RuntimeError("down")

    ctx.deps.ai = Broken()
    findings = [_finding("claim", 1, f"problem {i}") for i in range(7)]
    assert summarise(ctx, findings).startswith("7 problems found")
