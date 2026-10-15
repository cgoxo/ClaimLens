import json
import shutil
from collections import Counter

import pymupdf
import pytest

from claimlens.ai import FakeAi
from claimlens.db import LocalDb
from claimlens.deps import Deps
from claimlens.models import Case
from claimlens.ocr import NoOcr
from claimlens.pipeline.run import run_pipeline
from claimlens.settings import Settings
from claimlens.storage import LocalStorage
from tests.conftest import FAKE_AI, SAMPLES

EXPECTED = Counter(["font_outlier", "hidden_text", "editing_tool", "sum_mismatch", "inpatient_outside_stay",
                    "name_mismatch", "duplicate_invoice", "waiting_period", "room_rent_limit"])


def _deps(tmp_path, ai=None):
    return Deps(settings=Settings(_env_file=None, data_dir=tmp_path, ai="fake"),
                storage=LocalStorage(tmp_path / "files"), db=LocalDb(tmp_path / "db"),
                ai=ai or FakeAi(FAKE_AI), ocr=NoOcr())


def _new_case(deps, claim=(SAMPLES / "claim.pdf").read_bytes(), claim_name="claim.pdf"):
    files = {"claim": f"cases/c1/{claim_name}", "policy": "cases/c1/policy.pdf"}
    deps.storage.put(files["claim"], claim, "application/octet-stream")
    deps.storage.put(files["policy"], (SAMPLES / "policy.pdf").read_bytes(), "application/pdf")
    deps.db.create_case(Case(id="c1", owner_email="a@x.com", files=files))
    return "c1"


def test_sample_end_to_end(tmp_path):
    deps = _deps(tmp_path)
    deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    assert Counter(f.code for f in deps.db.get_findings("c1")) == EXPECTED
    assert (case.score, case.risk, case.payable) == (100, "high", 0)
    assert case.summary.startswith("High risk")
    assert len(deps.db.get_pages("c1")) == 7
    assert deps.db.get_invoice("PH7781")["case_id"] == "c1"


def test_failure_recorded(tmp_path):
    class Boom(FakeAi):
        def extract_facts(self, claim_text):
            raise RuntimeError("boom")

    deps = _deps(tmp_path, ai=Boom(FAKE_AI))
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    assert (case.status, case.step, case.error) == ("FAILED", "CHECKING", "boom")


def test_empty_facts_still_ready(tmp_path):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    (fixtures / "facts.json").write_text("{}")
    (fixtures / "policy.json").write_text("{}")
    (fixtures / "coverage.json").write_text("[]")
    deps = _deps(tmp_path, ai=FakeAi(fixtures))
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    assert case.payable is None


def test_jpg_claim_ready_with_unreadable_page(tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300), False)
    pix.clear_with(220)
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps, claim=pix.tobytes("jpg"), claim_name="claim.jpg"), deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    claim_pages = [p for p in deps.db.get_pages("c1") if p.doc == "claim"]
    assert [p.kind for p in claim_pages] == ["unreadable"]


# the sample as a user uploads it: the claim form, discharge summary and hospital bill as PDFs, the pharmacy bill a photo
CARD_SAMPLE = [("claim", "claim-form.pdf"), ("claim", "discharge-summary.pdf"), ("claim", "hospital-bill.pdf"),
               ("claim", "pharmacy-bill.jpg"), ("policy", "../policy.pdf")]


def test_multi_file_sample_end_to_end(settings):
    from tests.conftest import upload_case
    from tests.test_api import A, _client

    client = _client(settings)
    files = [(card, name.rsplit("/", 1)[-1], (SAMPLES / "cards" / name).read_bytes()) for card, name in CARD_SAMPLE]
    r = upload_case(client, A, files=files)
    assert r.status_code == 200, r.text
    case = client.get(f"/api/cases/{r.json()['case_id']}", headers=A).json()
    assert case["status"] == "READY", case["error"]
    codes = Counter(f["code"] for f in case["findings"])
    assert {"font_outlier", "hidden_text", "editing_tool", "sum_mismatch", "name_mismatch", "waiting_period",
            "room_rent_limit"} <= set(codes)
    assert not {"duplicate_page_image", "incomplete_bill"} & set(codes)
    [tool] = [f for f in case["findings"] if f["code"] == "editing_tool"]
    assert (tool["citations"][0]["doc"], tool["citations"][0]["page"]) == ("claim", 3)  # only the hospital bill
    assert [p["file_index"] for p in case["pages"] if p["doc"] == "claim"] == [0, 1, 2, 3]
