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


def test_fabricated_quote_sharing_a_label_word_dropped(ctx):
    from claimlens.pipeline.extract import locate

    # page 1 has the label "Hospital:"; a made-up hospital must not ground on it
    assert locate(ctx, "claim", 1, "Apollo Hospital") == (False, None)
    assert locate(ctx, "claim", 1, "Sunrise Eye & General Hospital, Pune")[0]


def test_ocr_word_spans_give_a_box_for_a_multi_word_quote():
    from claimlens.models import PageInfo, Span
    from claimlens.pipeline.context import Ctx
    from claimlens.pipeline.extract import locate
    from claimlens.pipeline.read import ReadResult

    words = [("Total", 10), ("Rs", 60), ("13,500", 80), ("Paid", 200)]
    spans = [Span(doc="claim", page=1, text=t, font="ocr", size=0, bbox=(x, 50, x + 30, 60), seqno=i)
             for i, (t, x) in enumerate(words)]
    read = ReadResult(pages=[PageInfo(doc="claim", page=1, kind="image", text=" ".join(t for t, _ in words),
                                      width=300, height=100, png_key="k")], spans=spans)
    ctx = Ctx(case_id="c1", read=read, deps=None)
    assert locate(ctx, "claim", 1, "Rs 13,500") == (True, (60, 50, 110, 60))
    assert locate(ctx, "claim", 1, "Rs 99,999") == (False, None)


def test_column_major_form_quote_grounds_against_what_the_ai_read(tmp_path):
    """Labels drawn first, values after: get_text() order differs from the row the AI was shown."""
    import pymupdf

    from claimlens.ocr import NoOcr
    from claimlens.pipeline.context import Ctx
    from claimlens.pipeline.extract import labelled_text, locate
    from claimlens.pipeline.read import read_document
    from claimlens.storage import LocalStorage

    pdf = pymupdf.open()
    page = pdf.new_page()
    for y, label in ((100, "Patient Name:"), (120, "Hospital:")):
        page.insert_text((50, y), label)
    for y, value in ((100, "Ravi Kumar"), (120, "City Care, Pune")):
        page.insert_text((200, y), value)
    data = pdf.tobytes()
    storage = LocalStorage(tmp_path)
    storage.put("cases/c1/claim.pdf", data, "application/pdf")
    read = read_document("claim", data, "claim.pdf", "c1", storage, NoOcr(), key="cases/c1/claim.pdf")
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())

    assert "Patient Name:   Ravi Kumar" in labelled_text(read, "claim")
    found, bbox = locate(ctx, "claim", 1, "Patient Name: Ravi Kumar")
    assert found and bbox is not None
    assert locate(ctx, "claim", 1, "Patient Name: Apollo Clinic") == (False, None)


def _with_policy_rules(tmp_path, **rules):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    policy = json.loads((fixtures / "policy.json").read_text())
    policy.update(rules)
    (fixtures / "policy.json").write_text(json.dumps(policy))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    return c


def test_rule_with_wrong_quote_is_dropped_and_listed(tmp_path):
    c = _with_policy_rules(tmp_path, co_pays=[{"percent": 10, "clause": "9.9", "page": 1, "quote": "no such sentence"}])
    assert c.policy_facts.co_pays == []
    assert c.rules_not_verified[0]["rule"] == "CoPay"


def test_rule_with_real_quote_is_kept(tmp_path):
    c = _with_policy_rules(tmp_path, room_limit={
        "percent_of_si": 1, "clause": "2.1", "page": 1,
        "quote": "Room rent is payable up to 1% of the sum insured per day"})
    assert c.policy_facts.room_limit.percent_of_si == 1
    assert c.rules_not_verified == []
