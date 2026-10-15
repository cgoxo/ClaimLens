import pymupdf

from claimlens.models import Card
from claimlens.pipeline.checks.cards import check_cards, duplicate_pages
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import labelled_text
from claimlens.pipeline.prove import prove
from tests.test_read_cards import one_page, photo, read_cards

CLAIM = [Card(id="claim", role="claim")]


def _ctx(tmp_path, files):
    storage, read = read_cards(tmp_path, [("claim", name, data) for name, data in files])
    return Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})(), cards=CLAIM)


def _codes(findings, code):
    return [f for f in findings if f.code == code]


def _pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        y = 80
        for line in text.split("\n"):
            doc_page = doc[-1] if y > 80 else doc.new_page()
            doc_page.insert_text((50, y), line)
            y += 16
    return doc.tobytes()


def test_duplicate_page_found_hidden_from_ai_and_proven(tmp_path):
    ctx = _ctx(tmp_path, [("bill.pdf", one_page(3)), ("pharmacy.pdf", one_page(4)), ("again.pdf", one_page(4))])
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
    page.add_redact_annot(page.search_for("Rs  3,000")[0], "Rs  3,900")
    page.apply_redactions()
    ctx = _ctx(tmp_path, [("a.pdf", one_page(4)), ("b.pdf", other.tobytes())])
    assert duplicate_pages(ctx.read) == []


def test_identical_boilerplate_pages_are_not_duplicates(tmp_path):
    # a terms page repeated at the end of two documents: same words and numbers, but no amount or date
    terms = ("Terms and conditions\nSunrise Eye & General Hospital, 12 MG Road, Pune 411001\n"
             "GSTIN 27ABCDE1234F1Z5   Reg. No. 4471\nPhone 020 2611 0000. Payment is due on receipt.")
    ctx = _ctx(tmp_path, [("bill.pdf", _pdf("Hospital bill INV-1 total Rs 45,500 on 13-Mar-2026", terms)),
                          ("lab.pdf", _pdf("Lab report LR-9 total Rs 2,000 on 12-Mar-2026", terms))])
    assert duplicate_pages(ctx.read) == []


def test_pages_without_text_are_not_compared(tmp_path):
    ctx = _ctx(tmp_path, [("a.jpg", photo(4)), ("b.jpg", photo(4))])  # OCR off
    assert duplicate_pages(ctx.read) == []


def test_incomplete_claim(tmp_path):
    ctx = _ctx(tmp_path, [("bill-1.pdf", _pdf("Bill INV-77   Rs 1,000   Page 1 of 3")),
                          ("bill-2.pdf", _pdf("Bill INV-77   Rs 2,000   Page 2 of 3"))])
    [f] = _codes(check_cards(ctx), "incomplete_bill")
    assert f.severity == "medium" and f.title == "The claim is missing page 3 of 3"


def test_documents_with_their_own_numbering_are_checked_separately(tmp_path):
    ctx = _ctx(tmp_path, [("summary.pdf", _pdf("Discharge summary   Page 1 of 1")),
                          ("bill.pdf", _pdf("Bill INV-77 Page 1 of 2", "Bill INV-77 Page 2 of 2"))])
    assert _codes(check_cards(ctx), "incomplete_bill") == []


def test_slice_of_a_bigger_pack_is_not_incomplete(tmp_path):
    # the sample hospital bill is page 3 of a 4-page claim pack: numbering that skips page 1 is not checked
    ctx = _ctx(tmp_path, [("bill.pdf", one_page(3))])
    assert _codes(check_cards(ctx), "incomplete_bill") == []


def test_unreadable_page_makes_page_count_unknowable(tmp_path):
    # page 4 of 4 is a photo and OCR is off: it may well be there, so say nothing
    ctx = _ctx(tmp_path, [("a.pdf", one_page(1)), ("b.pdf", one_page(2)), ("c.pdf", one_page(3)), ("d.jpg", photo(4))])
    assert _codes(check_cards(ctx), "incomplete_bill") == []


def test_clean_claim_gives_nothing(tmp_path):
    ctx = _ctx(tmp_path, [(f"{n}.pdf", one_page(n)) for n in (1, 2, 3, 4)])
    assert check_cards(ctx) == []
