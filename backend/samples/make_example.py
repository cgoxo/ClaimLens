"""Generate the ClaimLens worked-example PDFs.

Creates two fictional PDFs in the same folder as this script:
  policy.pdf  - a 3-page health policy (schedule, waiting periods, exclusions)
  claim.pdf   - a 4-page claim pack with planted problems, then tampered
                the way a fraudster would (white box + retyped total,
                saved again with an editing tool)

Usage:  pip install reportlab pymupdf && python make_example.py [--clean]\n        --clean also writes claim_clean.pdf (the untampered claim)
"""

from pathlib import Path

import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
W, H = A4
FOOTER = "FICTIONAL SAMPLE FOR TESTING - not a real policy, person or hospital"


def page(c, title, lines, page_no, total_pages):
    c.setFont("Helvetica-Bold", 15)
    c.drawString(50, H - 60, title)
    c.setFont("Helvetica", 11)
    y = H - 95
    for line in lines:
        if line.startswith("## "):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, line[3:])
            c.setFont("Helvetica", 11)
        else:
            c.drawString(50, y, line)
        y -= 18
    c.setFont("Helvetica", 8)
    c.drawString(50, 30, FOOTER)
    c.drawRightString(W - 50, 30, f"Page {page_no} of {total_pages}")
    c.showPage()


def make_policy():
    c = canvas.Canvas(str(OUT / "policy.pdf"), pagesize=A4)
    c.setTitle("Example Health - Family Floater Policy")
    c.setProducer("ExampleHealth PolicyGen 2.1")
    page(c, "Example Health Insurance Co. - Policy Schedule", [
        "Policy number:        EH-2025-778812",
        "Insured person:       Rahul Verma (age 58)",
        "Policy start date:    01-Jan-2026",
        "Policy end date:      31-Dec-2026",
        "Sum insured:          Rs 3,00,000",
        "",
        "## Clause 2.1 - Room rent limit",
        "Room rent is payable up to 1% of the sum insured per day",
        "(Rs 3,000 per day). If a costlier room is chosen, the excess is not payable.",
    ], 1, 3)
    page(c, "Section 3 - Waiting Periods", [
        "## Clause 3.1 - Initial waiting period",
        "No claim is payable in the first 30 days, except for accidents.",
        "",
        "## Clause 3.2 - Specific illnesses: 24 months",
        "Treatment of the following is not payable until 24 months of",
        "continuous cover have been completed:",
        "  - Cataract",
        "  - Hernia",
        "  - Knee replacement",
        "  - Kidney stones",
        "",
        "## Clause 3.3 - Pre-existing diseases: 36 months",
    ], 2, 3)
    page(c, "Section 4 - Exclusions and Section 5 - Claims", [
        "## Clause 4.1 - Exclusions",
        "Cosmetic treatment, dental treatment (unless due to accident),",
        "self-inflicted injury.",
        "",
        "## Clause 5.1 - Claim documents",
        "Claim form, discharge summary, original itemised bills,",
        "pharmacy bills with prescription.",
        "",
        "## Clause 5.2 - Time limit",
        "Documents must be submitted within 30 days of discharge.",
    ], 3, 3)
    c.save()


def make_claim_original(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Claim - Rahul Verma - EH-2025-778812")
    c.setProducer("SunriseHMS v4.2")
    c.setCreator("SunriseHMS v4.2")
    page(c, "Claim Form", [
        "Policy number:     EH-2025-778812",
        "Claimant:          Rahul Verma",
        "Hospital:          Sunrise Eye & General Hospital, Pune",
        "Date of admission: 10-Mar-2026",
        "Date of discharge: 13-Mar-2026",
        "Amount claimed:    Rs 51,500",
        "Date of claim:     22-Mar-2026",
    ], 1, 4)
    page(c, "Discharge Summary - Sunrise Eye & General Hospital", [
        "Patient name:  Rahul Varma          Age: 58",
        "Admitted:      10-Mar-2026",
        "Discharged:    13-Mar-2026",
        "",
        "Diagnosis:     Senile cataract, right eye",
        "Procedure:     Phacoemulsification with IOL implant (11-Mar-2026)",
        "Condition at discharge: Stable",
    ], 2, 4)
    page(c, "Hospital Bill - Invoice INV-SEH-2026-0412", [
        "Patient: Rahul Verma        Bill date: 13-Mar-2026",
        "",
        "Room charges (3 days x Rs 4,500)       Rs 13,500",
        "Surgeon and OT charges                 Rs 22,000",
        "Intraocular lens (IOL)                 Rs  8,000",
        "Consumables                            Rs  2,000",
        "",
        "TOTAL                                  Rs 45,500",
    ], 3, 4)
    page(c, "Pharmacy Bill - Sunrise Hospital Pharmacy", [
        "Bill no: PH-7781            Date: 15-Mar-2026",
        "Patient: Rahul Verma",
        "Type:    Inpatient medicines - Ward 3B",
        "",
        "Eye drops, antibiotics, IV fluids      Rs  3,000",
        "",
        "TOTAL                                  Rs  3,000",
    ], 4, 4)
    c.save()


def tamper(src, dst):
    """Do what a fraudster does: cover the bill total and retype it."""
    doc = pymupdf.open(src)
    bill = doc[2]
    hit = bill.search_for("Rs 45,500")[0]
    box = pymupdf.Rect(hit.x0 - 2, hit.y0 - 1, hit.x1 + 2, hit.y1 + 1)
    bill.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))  # old text stays underneath
    bill.insert_text((hit.x0, hit.y1 - 2.5), "Rs 48,500", fontname="tiro", fontsize=11)
    doc.set_metadata({
        **doc.metadata,
        "producer": "iLovePDF",
        "creationDate": "D:20260313101500+05'30'",
        "modDate": "D:20260320224100+05'30'",
    })
    doc.save(dst)


if __name__ == "__main__":
    import sys

    make_policy()
    original = OUT / "_claim_original.pdf"
    make_claim_original(original)
    tamper(original, OUT / "claim.pdf")
    if "--clean" in sys.argv:
        # the untouched hospital file, for negative tests
        original.replace(OUT / "claim_clean.pdf")
        print("wrote policy.pdf, claim.pdf and claim_clean.pdf")
    else:
        original.unlink()
        print("wrote policy.pdf and claim.pdf")
