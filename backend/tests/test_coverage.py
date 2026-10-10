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
