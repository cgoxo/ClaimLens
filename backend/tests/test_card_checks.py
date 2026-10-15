import pymupdf

from claimlens.models import Bill, Card, ClaimFacts, Fact
from claimlens.pipeline.checks.cards import check_cards, duplicate_pages
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import labelled_text
from claimlens.pipeline.prove import prove
from tests.test_read_cards import CLAIM, one_page, photo, read_cards


def _ctx(tmp_path, files, cards, bills=()):
    storage, read = read_cards(tmp_path, files)
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})(), cards=cards)
    ctx.claim_facts = ClaimFacts(bills=list(bills))
    return ctx


def _bill(page, no):
    return Bill(page=page, kind="hospital", invoice_no=Fact(value=no, page=page, quote=no))


def _codes(findings, code):
    return [f for f in findings if f.code == code]


TWO_BILLS = [Card(id="b1", role="bill", kind="hospital"), Card(id="b2", role="bill", kind="pharmacy")]


def test_bill_split_across_cards(tmp_path):
    ctx = _ctx(tmp_path, [("b1", "a.pdf", one_page(3)), ("b2", "b.pdf", one_page(4))], TWO_BILLS,
               [_bill(1, "INV-SEH-2026-0412"), _bill(2, "INV SEH 2026 0412")])
    [f] = _codes(check_cards(ctx), "bill_split_across_cards")
    assert f.severity == "high"
    assert f.title == "Invoice INV-SEH-2026-0412 appears in two cards (Bill 1 · hospital, Bill 2 · pharmacy)"
    assert [c.page for c in f.citations] == [1, 2]


def test_mixed_bill_in_card(tmp_path):
    cards = [Card(id="b1", role="bill", kind="hospital")]
    ctx = _ctx(tmp_path, [("b1", "a.pdf", one_page(3)), ("b1", "b.pdf", one_page(4))], cards,
               [_bill(1, "INV-SEH-2026-0412"), _bill(2, "PH-7781")])
    [f] = _codes(check_cards(ctx), "mixed_bill_in_card")
    assert f.severity == "medium"
    assert f.title == "Bill 1 · hospital holds more than one bill (INV-SEH-2026-0412, PH-7781)"


def test_duplicate_page_found_hidden_from_ai_and_proven(tmp_path):
    ctx = _ctx(tmp_path, [("b1", "a.pdf", one_page(3)), ("b2", "b.pdf", one_page(4)), ("b2", "again.pdf", one_page(4))],
               TWO_BILLS)
    assert [(a.page, b.page) for a, b in duplicate_pages(ctx.read)] == [(2, 3)]
    ctx.skip_pages = {("claim", 3)}
    assert "claim page 3" not in labelled_text(ctx.read, "claim", ctx.cards, ctx.skip_pages)
    [f] = _codes(check_cards(ctx), "duplicate_page_image")
    assert f.severity == "high" and f.title == "Claim page 3 is the same page as page 2"
    kept, _ = prove(ctx, [f])
    assert kept and kept[0].citations[0].page == 3


def test_look_alike_pages_with_different_numbers_are_not_duplicates(tmp_path):
    other = pymupdf.open(stream=one_page(4), filetype="pdf")
    page = other[0]
    hit = page.search_for("Rs  3,000")[0]
    page.add_redact_annot(hit, "Rs  3,900")
    page.apply_redactions()
    ctx = _ctx(tmp_path, [("b1", "a.pdf", one_page(4)), ("b2", "b.pdf", other.tobytes())], TWO_BILLS)
    assert duplicate_pages(ctx.read) == []


def test_pages_without_text_are_not_compared(tmp_path):
    ctx = _ctx(tmp_path, [("b2", "a.jpg", photo(4)), ("b2", "b.jpg", photo(4))], TWO_BILLS)  # OCR off
    assert duplicate_pages(ctx.read) == []


def _numbered(*labels):
    doc = pymupdf.open()
    for label in labels:
        doc.new_page().insert_text((50, 80), f"Hospital Bill INV-77 item {label}   Rs 1,000   {label}")
    return doc.tobytes()


def test_incomplete_bill(tmp_path):
    cards = [Card(id="b1", role="bill", kind="hospital")]
    ctx = _ctx(tmp_path, [("b1", "a.pdf", _numbered("Page 1 of 3", "Page 2 of 3"))], cards)
    [f] = _codes(check_cards(ctx), "incomplete_bill")
    assert f.severity == "medium" and f.title == "Bill 1 · hospital is missing page 3 of 3"


def test_slice_of_a_bigger_pack_is_not_incomplete(tmp_path):
    # the sample hospital bill is page 3 of a 4-page claim pack: it starts at 3, so it is not a bill's own numbering
    ctx = _ctx(tmp_path, [("b1", "a.pdf", one_page(3))], [Card(id="b1", role="bill", kind="hospital")])
    assert _codes(check_cards(ctx), "incomplete_bill") == []


def test_clean_cards_give_nothing(tmp_path):
    cards = [Card(id="claim-form", role="claim_form"), *TWO_BILLS]
    ctx = _ctx(tmp_path, [("claim-form", "f.pdf", one_page(1)), ("b1", "a.pdf", one_page(3)),
                          ("b2", "b.pdf", one_page(4))], cards, [_bill(2, "INV-SEH-2026-0412"), _bill(3, "PH-7781")])
    assert check_cards(ctx) == []
