from collections import Counter

import pymupdf
import pytest

from claimlens.models import Card, CaseFile
from claimlens.ocr import NoOcr
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import _pdf, labelled_text, locate
from claimlens.pipeline.read import ReadResult, read_document
from claimlens.storage import LocalStorage
from tests.conftest import SAMPLES
from tests.test_pipeline import EXPECTED, _deps, _new_case

CLAIM = (SAMPLES / "claim.pdf").read_bytes()


def one_page(n: int) -> bytes:
    """Page n (1-based) of the sample claim as its own PDF, keeping the file's metadata."""
    src = pymupdf.open(stream=CLAIM, filetype="pdf")
    out = pymupdf.open()
    out.insert_pdf(src, from_page=n - 1, to_page=n - 1)
    out.set_metadata(src.metadata)
    return out.tobytes()


def photo(n: int) -> bytes:
    return pymupdf.open(stream=CLAIM, filetype="pdf")[n - 1].get_pixmap(dpi=100).tobytes("jpeg")


CARDS = [Card(id="claim-form", role="claim_form"), Card(id="b1", role="bill", kind="hospital"),
         Card(id="b2", role="bill", kind="pharmacy")]


def read_cards(tmp_path, files):
    """files: [(card_id, name, bytes)] in claim-stream order."""
    storage, read, page = LocalStorage(tmp_path), ReadResult(), 1
    for i, (card_id, name, data) in enumerate(files):
        key = f"cases/c1/{card_id}/{i}.{name.rsplit('.', 1)[-1]}"
        storage.put(key, data, "application/octet-stream")
        part = read_document("claim", data, name, "c1", storage, NoOcr(), start_page=page, card_id=card_id, key=key)
        read.extend(part)
        page += len(part.pages)
    return storage, read


@pytest.fixture
def three(tmp_path):
    return read_cards(tmp_path, [("claim-form", "form.pdf", one_page(1)), ("b1", "bill.pdf", one_page(3)),
                                 ("b2", "pharmacy.jpg", photo(4))])


def test_stream_numbering_and_tags(three):
    _, read = three
    assert [(p.page, p.card_id, p.file_page) for p in read.pages] == [
        (1, "claim-form", 1), (2, "b1", 1), (3, "b2", 1)]
    assert read.pages[2].kind == "unreadable"  # a photo, and OCR is off in tests
    assert all(s.page == 2 for s in read.spans if "INV-SEH" in s.text)


def test_file_info_per_file(three):
    _, read = three
    assert [(f.card_id, f.first_page) for f in read.files] == [("claim-form", 1), ("b1", 2), ("b2", 3)]
    assert read.files[1].producer == "iLovePDF"


def test_pdf_maps_stream_page_to_file(tmp_path):
    two = pymupdf.open(stream=CLAIM, filetype="pdf")
    first, second = pymupdf.open(), pymupdf.open()
    first.insert_pdf(two, from_page=0, to_page=1)
    second.insert_pdf(two, from_page=2, to_page=3)
    storage, read = read_cards(tmp_path, [("b1", "a.pdf", first.tobytes()), ("b1", "b.pdf", second.tobytes())])
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    pdf, index = _pdf(ctx, "claim", 3)
    assert index == 0 and "INV-SEH" in pdf[index].get_text()


def test_locate_on_image_page_does_not_crash(three):
    storage, read = three
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    assert locate(ctx, "claim", 3, "PH-7781") == (False, None)


def test_labelled_text_has_card_headers(three):
    _, read = three
    text = labelled_text(read, "claim", CARDS)
    assert "=== claim page 1 · Claim form ===" in text
    assert "=== claim page 2 · Bill 1 (hospital) ===" in text
    assert "=== claim page 3 · Bill 2 (pharmacy) ===" in text


def test_labelled_text_skips_pages(three):
    _, read = three
    assert "claim page 2" not in labelled_text(read, "claim", CARDS, skip={("claim", 2)})


def test_old_case_reads_as_before(tmp_path):
    deps = _deps(tmp_path)
    deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    from claimlens.pipeline.run import run_pipeline

    run_pipeline(_new_case(deps), deps)
    assert len(deps.db.get_pages("c1")) == 7
    assert Counter(f.code for f in deps.db.get_findings("c1")) == EXPECTED


def test_card_case_progress_labels_and_context(tmp_path):
    from claimlens.models import Case
    from claimlens.pipeline.run import run_pipeline

    deps = _deps(tmp_path)
    cards = [Card(id="claim-form", role="claim_form"), Card(id="b1", role="bill", kind="hospital"),
             Card(id="supporting", role="supporting"), Card(id="b2", role="bill", kind="pharmacy"),
             Card(id="policy", role="policy")]
    blobs = {"claim-form": one_page(1), "b1": one_page(3), "b2": one_page(4), "supporting": one_page(2),
             "policy": (SAMPLES / "policy.pdf").read_bytes()}
    for card in cards:
        key = f"cases/c1/{card.id}/0.pdf"
        deps.storage.put(key, blobs[card.id], "application/pdf")
        card.files = [CaseFile(key=key, name=f"{card.id}.pdf", pages=3 if card.id == "policy" else 1)]
    deps.db.create_case(Case(id="c1", owner_email="a@x.com", status="QUEUED", cards=cards))
    labels, original = [], deps.db.update_case
    deps.db.update_case = lambda c, **k: (labels.append(k["progress"]["label"]) if k.get("progress") else None,
                                          original(c, **k))[1]
    run_pipeline("c1", deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    # stream order: claim form, bills in card order, then supporting
    assert [(p.page, p.card_id) for p in deps.db.get_pages("c1") if p.doc == "claim"] == [
        (1, "claim-form"), (2, "b1"), (3, "b2"), (4, "supporting")]
    assert "Reading Bill 2 · pharmacy, page 1 (3 of 7)" in labels


def test_editing_tool_cites_the_edited_files_first_page(tmp_path):
    from claimlens.pipeline.checks.tamper import check_tamper

    clean = pymupdf.open(stream=one_page(1), filetype="pdf")
    clean.set_metadata({"producer": "SunriseHMS v4.2", "creator": "SunriseHMS v4.2"})
    storage, read = read_cards(tmp_path, [("claim-form", "form.pdf", clean.tobytes()), ("b1", "bill.pdf", one_page(3))])
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    [f] = [f for f in check_tamper(ctx) if f.code == "editing_tool"]
    assert (f.citations[0].doc, f.citations[0].page) == ("claim", 2)


def test_context_bills_have_card_labels(three):
    from claimlens.models import Bill, ClaimFacts, Fact
    from claimlens.pipeline.run import context_of

    storage, read = three
    ctx = Ctx(case_id="c1", read=read, deps=None, cards=CARDS)
    ctx.claim_facts = ClaimFacts(bills=[Bill(page=2, kind="hospital", total=Fact(value=48500, page=2, quote="x")),
                                        Bill(page=3, kind="pharmacy")])
    assert [b["card"] for b in context_of(ctx)["claim"]["bills"]] == ["Bill 1 · hospital", "Bill 2 · pharmacy"]
