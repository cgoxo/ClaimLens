import pymupdf
import pytest

from claimlens.ocr import NoOcr
from claimlens.pipeline.read import read_document
from claimlens.storage import LocalStorage
from tests.conftest import SAMPLES


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def claim(storage):
    data = (SAMPLES / "claim.pdf").read_bytes()
    return read_document("claim", data, "claim.pdf", "c1", storage, NoOcr())


def _span(result, page, text):
    return next(s for s in result.spans if s.page == page and text in s.text)


def test_claim_pages_digital(claim):
    assert [p.kind for p in claim.pages] == ["digital"] * 4
    assert "Rs 51,500" in claim.pages[0].text


def test_spans_have_fonts(claim):
    retyped = next(s for s in claim.spans if s.page == 3 and s.text == "Rs 48,500")
    assert retyped.font == "Times-Roman"
    assert _span(claim, 3, "Rs 45,500").font == "Helvetica"


def test_white_rect_detected(claim):
    old = _span(claim, 3, "Rs 45,500")
    new = _span(claim, 3, "Rs 48,500")
    white = [d for d in claim.drawings if d.page == 3 and d.fill and min(d.fill) >= 0.95]
    assert len(white) == 1
    assert old.seqno < white[0].seqno < new.seqno


def test_file_info(claim):
    info = claim.files[0]
    assert info.producer == "iLovePDF"
    assert info.created.startswith("D:20260313")
    assert info.modified.startswith("D:20260320")


def test_png_stored(claim, storage):
    assert storage.exists("cases/c1/pages/claim/3.png")
    assert claim.pages[2].png_key == "cases/c1/pages/claim/3.png"


def test_jpg_upload_unreadable_with_no_ocr(storage):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.clear_with(200)
    result = read_document("claim", pix.tobytes("jpg"), "photo.jpg", "c2", storage, NoOcr())
    assert [p.kind for p in result.pages] == ["unreadable"]
    assert result.spans == []
