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


CARDS = [Card(id="claim", role="claim")]


def read_cards(tmp_path, files):
    """files: [(card_id, name, bytes)] in claim-stream order."""
    storage, read, page = LocalStorage(tmp_path), ReadResult(), 1
    for i, (card_id, name, data) in enumerate(files):
        key = f"cases/c1/{card_id}/{i}.{name.rsplit('.', 1)[-1]}"
        storage.put(key, data, "application/octet-stream")
        part = read_document("claim", data, name, "c1", storage, NoOcr(), start_page=page, card_id=card_id, key=key,
                             file_index=i)
        read.extend(part)
        page += len(part.pages)
    return storage, read


@pytest.fixture
def three(tmp_path):
    return read_cards(tmp_path, [("claim", "form.pdf", one_page(1)), ("claim", "bill.pdf", one_page(3)),
                                 ("claim", "pharmacy.jpg", photo(4))])


def test_stream_numbering_and_tags(three):
    _, read = three
    assert [(p.page, p.card_id, p.file_index, p.file_page) for p in read.pages] == [
        (1, "claim", 0, 1), (2, "claim", 1, 1), (3, "claim", 2, 1)]
    assert read.pages[2].kind == "unreadable"  # a photo, and OCR is off in tests
    assert all(s.page == 2 for s in read.spans if "INV-SEH" in s.text)


def test_file_info_per_file(three):
    _, read = three
    assert [(f.card_id, f.first_page) for f in read.files] == [("claim", 1), ("claim", 2), ("claim", 3)]
    assert read.files[1].producer == "iLovePDF"


def test_pdf_maps_stream_page_to_file(tmp_path):
    two = pymupdf.open(stream=CLAIM, filetype="pdf")
    first, second = pymupdf.open(), pymupdf.open()
    first.insert_pdf(two, from_page=0, to_page=1)
    second.insert_pdf(two, from_page=2, to_page=3)
    storage, read = read_cards(tmp_path, [("claim", "a.pdf", first.tobytes()), ("claim", "b.pdf", second.tobytes())])
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    pdf, index = _pdf(ctx, "claim", 3)
    assert index == 0 and "INV-SEH" in pdf[index].get_text()


def test_locate_on_image_page_does_not_crash(three):
    storage, read = three
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    assert locate(ctx, "claim", 3, "PH-7781") == (False, None)


def test_labelled_text_headers_are_plain(three):
    _, read = three
    assert "=== claim page 2 ===" in labelled_text(read, "claim", CARDS)


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


def test_card_case_reads_files_in_order_with_file_labels(tmp_path):
    from claimlens.models import Case
    from claimlens.pipeline.run import run_pipeline

    deps = _deps(tmp_path)
    claim = Card(id="claim", role="claim")
    for i, (name, data) in enumerate([("claim-form.pdf", one_page(1)), ("hospital-bill.pdf", one_page(3)),
                                      ("pharmacy-bill.pdf", one_page(4)), ("discharge.pdf", one_page(2))]):
        key = f"cases/c1/claim/{i}.pdf"
        deps.storage.put(key, data, "application/pdf")
        claim.files.append(CaseFile(key=key, name=name, pages=1))
    deps.storage.put("cases/c1/policy/0.pdf", (SAMPLES / "policy.pdf").read_bytes(), "application/pdf")
    policy = Card(id="policy", role="policy", files=[CaseFile(key="cases/c1/policy/0.pdf", name="policy.pdf", pages=3)])
    deps.db.create_case(Case(id="c1", owner_email="a@x.com", status="QUEUED", cards=[claim, policy]))
    labels, original = [], deps.db.update_case
    deps.db.update_case = lambda c, **k: (labels.append(k["progress"]["label"]) if k.get("progress") else None,
                                          original(c, **k))[1]
    run_pipeline("c1", deps)
    assert deps.db.get_case("c1").status == "READY"
    assert [(p.page, p.file_index) for p in deps.db.get_pages("c1") if p.doc == "claim"] == [(1, 0), (2, 1), (3, 2), (4, 3)]
    assert "Reading pharmacy-bill.pdf, page 1 (3 of 7)" in labels


def test_editing_tool_cites_the_edited_files_first_page(tmp_path):
    from claimlens.pipeline.checks.tamper import check_tamper

    clean = pymupdf.open(stream=one_page(1), filetype="pdf")
    clean.set_metadata({"producer": "SunriseHMS v4.2", "creator": "SunriseHMS v4.2"})
    storage, read = read_cards(tmp_path, [("claim", "form.pdf", clean.tobytes()), ("claim", "bill.pdf", one_page(3))])
    ctx = Ctx(case_id="c1", read=read, deps=type("D", (), {"storage": storage})())
    [f] = [f for f in check_tamper(ctx) if f.code == "editing_tool"]
    assert (f.citations[0].doc, f.citations[0].page) == ("claim", 2)
