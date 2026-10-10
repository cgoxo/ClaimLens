"""Regression tests for the final-review findings."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from claimlens.deps import build_deps
from claimlens.main import create_app
from claimlens.models import Case, ClaimFacts, Bill, Fact, Span, now
from claimlens.pipeline.checks.duplicate import check_duplicate, invoice_key, register_invoices
from claimlens.pipeline.checks.tamper import check_tamper
from claimlens.pipeline.prove import prove
from claimlens.pipeline.text import parse_date
from tests.test_prove_report import _finding


# 1: ISO dates must not swap day and month
def test_parse_date_iso_with_low_day():
    assert parse_date("2026-03-05") == date(2026, 3, 5)
    assert parse_date("2026/03/05") == date(2026, 3, 5)
    assert parse_date("05/03/2026") == date(2026, 3, 5)


# 2: Prove must not accept a changed number or an added negation
def test_prove_rejects_changed_number(ctx):
    kept, _ = prove(ctx, [_finding("policy", 1, "(Rs 30,000 per day). If a costlier room is chosen")])
    assert kept == []


def test_prove_rejects_added_negation(ctx):
    quote = "Room rent is not payable up to 1% of the sum insured per day"
    kept, _ = prove(ctx, [_finding("policy", 1, quote)])
    assert kept == []


# 3: file-metadata findings survive when page 1 has no readable text
def test_metadata_findings_kept_without_page_text(ctx):
    for p in ctx.read.pages:
        if p.doc == "claim" and p.page == 1:
            p.text, p.kind = "", "unreadable"
    ctx.read.spans = [s for s in ctx.read.spans if not (s.doc == "claim" and s.page == 1)]
    kept, _ = prove(ctx, check_tamper(ctx))
    assert "editing_tool" in {f.code for f in kept}


# 4: ocr_layer_mismatch is proven against the hidden layer
def test_ocr_layer_mismatch_is_proven(ctx):
    page = next(p for p in ctx.read.pages if p.doc == "claim" and p.page == 2)
    page.kind, page.text = "scanned_with_text", "Total Rs 4,500"
    ctx.read.spans = [s for s in ctx.read.spans if not (s.doc == "claim" and s.page == 2)]
    ctx.read.spans.append(Span(doc="claim", page=2, text="Total Rs 4,500", font="ocr", size=0, bbox=(0, 0, 9, 9)))
    ctx.read.hidden_layer.append(Span(doc="claim", page=2, text="Paid 7", font="GlyphLessFont",
                                      size=10, bbox=(0, 0, 9, 9)))
    kept, _ = prove(ctx, check_tamper(ctx))
    assert "ocr_layer_mismatch" in {f.code for f in kept}


# 5: placeholder invoice numbers are not invoices
def test_placeholder_invoice_numbers_ignored(ctx):
    assert invoice_key("N/A") is None and invoice_key("—") is None and invoice_key("12") is None
    ctx.deps.db.put_invoice("NA", {"case_id": "other"})
    ctx.claim_facts = ClaimFacts(bills=[Bill(page=3, invoice_no=Fact(value="N/A", page=3, quote="N/A"))])
    assert check_duplicate(ctx) == []
    register_invoices(ctx)


# 6: the registry keeps the first claim; same-owner resubmission is worded as such
def test_registry_keeps_first_case(ctx):
    ctx.deps.db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "CLM-1043"})
    register_invoices(ctx)
    assert ctx.deps.db.get_invoice("INVSEH20260412")["case_id"] == "CLM-1043"


def test_resubmission_by_same_owner_says_so(ctx):
    db = ctx.deps.db
    db.create_case(Case(id="old", owner_email="a@x.com"))
    db.create_case(Case(id=ctx.case_id, owner_email="a@x.com"))
    db.put_invoice("INVSEH20260412", {"invoice_no": "INV-SEH-2026-0412", "case_id": "old"})
    found = check_duplicate(ctx)
    assert found and "your earlier case" in found[0].detail


# 7: unverified emails are not allowed in, even if on the list
def test_firebase_requires_verified_email(settings, monkeypatch):
    import claimlens.auth as auth

    app = create_app(settings.model_copy(update={"auth_mode": "firebase"}))
    c = TestClient(app)
    monkeypatch.setattr(auth, "verify_firebase_token", lambda t, p: {"email": "a@b.com", "email_verified": False})
    assert c.get("/api/me", headers={"Authorization": "Bearer t"}).status_code == 403


# 9: a case whose background run died is reported as failed, not stuck
def test_stale_running_case_reported_failed(settings):
    deps = build_deps(settings)
    deps.db.create_case(Case(id="s1", owner_email="a@x.com", status="CHECKING",
                             updated_at=now() - timedelta(minutes=20)))
    case = TestClient(create_app(settings, deps)).get("/api/cases/s1", headers={"X-Dev-User": "a@x.com"}).json()
    assert case["status"] == "FAILED" and "interrupted" in case["error"]
