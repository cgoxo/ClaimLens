import json
import shutil
from datetime import date

from claimlens.ai import FakeAi
from claimlens.pipeline.extract import extract
from claimlens.pipeline.text import normalise, parse_date, parse_money
from tests.conftest import FAKE_AI, make_ctx


def test_parse_date_formats():
    for s in ("13/03/2026", "13-Mar-2026", "2026-03-13"):
        assert parse_date(s) == date(2026, 3, 13)
    assert parse_date("soon") is None
    assert parse_date(None) is None


def test_normalise_currency_forms():
    assert normalise("₹ 48,500") == normalise("Rs. 48,500") == normalise("INR 48,500") == "rs 48,500"


def test_parse_money():
    assert parse_money("Rs 3,00,000") == 300000
    assert parse_money(4500) == 4500
    assert parse_money("lots") is None


def test_extract_grounds_bill_total(ctx):
    total = ctx.claim_facts.bills[0].total
    assert total.bbox is not None
    x0, y0, x1, y1 = total.bbox
    assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842


def test_extract_policy_facts(ctx):
    assert ctx.policy_facts.waiting_periods[0].months == 24
    assert ctx.policy_facts.start_date.value == "01-Jan-2026"


def test_ungrounded_fact_dropped(tmp_path):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    facts = json.loads((fixtures / "facts.json").read_text())
    facts["claimant_name"]["quote"] = "Imaginary Person"
    (fixtures / "facts.json").write_text(json.dumps(facts))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    assert c.claim_facts.claimant_name is None


def test_ai_sees_page_as_a_person_does(ctx):
    from claimlens.pipeline.extract import labelled_text

    text = labelled_text(ctx.read, "claim")
    assert "Rs 48,500" in text
    assert "Rs 45,500" not in text  # hidden under the white box
    assert "Date: 15-Mar-2026" in text
