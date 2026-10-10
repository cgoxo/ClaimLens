"""Hit real GCP. Run with: .venv/bin/pytest -m live"""

import os
from collections import Counter
from uuid import uuid4

import pytest

from claimlens.models import Case
from claimlens.pipeline.extract import extract
from claimlens.pipeline.run import run_pipeline
from claimlens.settings import Settings
from tests.conftest import make_ctx
from tests.test_pipeline import EXPECTED, _deps, _new_case

pytestmark = pytest.mark.live


@pytest.fixture
def vertex():
    from claimlens.ai import VertexGemini

    s = Settings(_env_file=None)
    return VertexGemini(s.gcp_project, s.vertex_location, s.gemini_model)


def test_vertex_extract_grounds(tmp_path, vertex):
    ctx = make_ctx(tmp_path, ai=vertex)
    extract(ctx)
    assert ctx.claim_facts.claimant_name is not None
    total = next(b.total for b in ctx.claim_facts.bills if b.page == 3)
    assert total.value == 48500 and total.bbox is not None


def test_vertex_pipeline_codes(tmp_path, vertex):
    deps = _deps(tmp_path, ai=vertex)
    deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    run_pipeline(_new_case(deps), deps)
    case = deps.db.get_case("c1")
    assert case.status == "READY", case.error
    assert Counter(f.code for f in deps.db.get_findings("c1")) == EXPECTED
    assert (case.score, case.risk, case.payable) == (100, "high", 0)


@pytest.mark.skipif(not os.environ.get("BUCKET"), reason="BUCKET not set")
def test_gcs_roundtrip():
    from claimlens.storage import GcsStorage

    s, key = GcsStorage(os.environ["BUCKET"]), f"tests/{uuid4().hex}.txt"
    s.put(key, b"hi", "text/plain")
    assert s.exists(key) and s.get(key) == b"hi"
    with pytest.raises(KeyError):
        s.get(f"tests/{uuid4().hex}")


@pytest.mark.skipif(not os.environ.get("FIRESTORE_LIVE"), reason="FIRESTORE_LIVE not set")
def test_firestore_roundtrip():
    from claimlens.db import FirestoreDb
    from claimlens.models import Finding, PageInfo

    s = Settings(_env_file=None)
    db, cid = FirestoreDb(s.gcp_project, s.firestore_db), f"test-{uuid4().hex[:8]}"
    db.create_case(Case(id=cid, owner_email="live@test"))
    assert db.update_case(cid, status="READING").status == "READING"
    assert cid in [c.id for c in db.list_cases("live@test")]
    db.put_findings(cid, [Finding(id="f1", check="story", code="x", severity="low", title="t")])
    assert db.update_finding(cid, "f1", verified=True).verified
    db.put_pages(cid, [PageInfo(doc="claim", page=1, kind="digital", width=1, height=1, png_key="k")])
    assert len(db.get_pages(cid)) == 1
    db.put_invoice(f"TEST{cid}", {"case_id": cid})
    assert db.get_invoice(f"TEST{cid}")["case_id"] == cid
