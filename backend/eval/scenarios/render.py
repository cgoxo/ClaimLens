"""Draw a recipe as the files a user would upload: the claim (as one PDF, one PDF per page, or a photo per page)
and the policy. Forgeries that work on the files themselves are applied here."""

import io
from datetime import timedelta

import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from eval.forensics.photo import to_photo
from eval.scenarios.recipe import WAITING_LIST, Recipe, day, money

W, H = A4
FOOTER = "FICTIONAL SAMPLE FOR TESTING - not a real policy, person or hospital"


def claim_pages(r: Recipe) -> list[tuple[str, list[str]]]:
    """(title, lines) for each claim page, in pack order."""
    name = lambda title: r.names.get(title, r.patient)
    pages = [("Claim Form", [
        f"Policy number:     {r.policy_no_on_claim}", f"Claimant:          {name('Claim Form')}",
        f"Hospital:          {r.hospital}", f"Date of admission: {day(r.admission)}",
        f"Date of discharge: {day(r.discharge)}", f"Amount claimed:    {money(r.claimed)}",
        f"Date of claim:     {day(r.claim_day)}"])]
    pages.append(("Discharge Summary", [
        f"Patient name:  {name('Discharge Summary')}", f"Admitted:      {day(r.admission)}",
        f"Discharged:    {day(r.discharge)}", "", f"Diagnosis:     {r.condition}",
        f"Procedure:     {r.procedure} ({day(r.procedure_day)})", "Condition at discharge: Stable"]))
    items = [f"{d:<38} {money(a)}" for d, a in r.items]
    pages.append((f"Hospital Bill - Invoice {r.invoice}", [
        f"Patient: {name('Hospital Bill')}        Bill date: {day(r.bill_day)}", "", *items, "",
        f"{'TOTAL':<38} {money(r.hospital_total)}"]))
    for p in r.pharmacies:
        pages.append(("Pharmacy Bill", [
            f"Bill no: {p.invoice}            Date: {day(p.day)}", f"Patient: {name('Pharmacy Bill')}",
            f"Type:    {'Inpatient medicines - Ward 3B' if p.inpatient else 'Outpatient medicines'}", "",
            f"{'Medicines':<38} {money(p.amount)}", "", f"{'TOTAL':<38} {money(p.amount)}"]))
    return pages


def _pdf(pages: list[tuple[str, list[str]]], producer: str = "HospitalHMS v4.2") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setProducer(producer)
    c.setCreator(producer)
    for n, (title, lines) in enumerate(pages, 1):
        c.setFont("Helvetica-Bold", 15)
        c.drawString(50, H - 60, title)
        c.setFont("Helvetica", 11)
        for i, line in enumerate(lines):
            c.drawString(50, H - 95 - 18 * i, line)
        c.setFont("Helvetica", 8)
        c.drawString(50, 30, FOOTER)
        c.drawRightString(W - 50, 30, f"Page {n} of {len(pages)}")
        c.showPage()
    c.save()
    return buf.getvalue()


def policy_pdf(r: Recipe) -> bytes:
    limit = (["## Clause 2.1 - Room rent limit", "Room rent is payable up to 1% of the sum insured per day",
              f"({money(r.room_limit)} per day). If a costlier room is chosen, the excess is not payable."]
             if r.room_limit else ["## Clause 2.1 - Room", "Room rent is payable at actuals."])
    return _pdf([
        ("Example Health Insurance Co. - Policy Schedule", [
            f"Policy number:        {r.policy_no}", f"Insured person:       {r.patient}",
            f"Policy start date:    {day(r.start)}", f"Sum insured:          {money(r.sum_insured)}", "", *limit]),
        ("Section 3 - Waiting Periods", [
            "## Clause 3.2 - Specific illnesses: 24 months",
            "Treatment of the following is not payable until 24 months of", "continuous cover have been completed:",
            *[f"  - {c}" for c in WAITING_LIST]]),
        ("Section 4 - Exclusions", ["Cosmetic treatment, dental treatment (unless due to accident),",
                                    "self-inflicted injury."])], producer="ExampleHealth PolicyGen 2.1")


def cv_pdf() -> bytes:
    return _pdf([("Curriculum Vitae", ["Ravi Kumar - Software Engineer", "Experience: 2019-2024 Acme Ltd, Bengaluru",
                                       "Skills: Python, SQL, Kubernetes", "Education: B.Tech, IIT Delhi, 2019"])],
                producer="Word")


def _retype(doc: pymupdf.Document, page_index: int, old: str, new: str) -> None:
    """What a fraudster does: a white box over the printed amount, the new amount typed on top."""
    page = doc[page_index]
    hit = page.search_for(old)[0]
    page.draw_rect(pymupdf.Rect(hit.x0 - 2, hit.y0 - 1, hit.x1 + 2, hit.y1 + 1), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((hit.x0, hit.y1 - 2.5), new, fontname="tiro", fontsize=11)


def _apply_file_forgeries(pack: bytes, r: Recipe, forgeries: list[str], bill_page: int) -> bytes:
    """Edits to the PDF holding the hospital bill (the whole pack, or just the bill's own file)."""
    doc = pymupdf.open(stream=pack, filetype="pdf")
    meta = dict(doc.metadata)
    if r.shown_total is not None:
        _retype(doc, bill_page, money(r.hospital_total), money(r.shown_total))
    if r.shown_item is not None:
        index, shown = r.shown_item
        _retype(doc, bill_page, money(r.items[index][1]), money(shown))
    if r.shown_total is not None or r.shown_item is not None or "editor_resave" in forgeries:
        meta["producer"] = "iLovePDF"
    if "late_edit" in forgeries:
        meta["creationDate"], meta["modDate"] = "D:20260301101500+05'30'", "D:20260306224100+05'30'"
    doc.set_metadata(meta)
    out = doc.tobytes()
    if "incremental_save" in forgeries:  # saved again later: an incremental update ends with a second %%EOF
        out += b"\n%%EOF\n"
    return out


def _split(pack: bytes) -> list[bytes]:
    src = pymupdf.open(stream=pack, filetype="pdf")
    out = []
    for i in range(src.page_count):
        doc = pymupdf.open()
        doc.insert_pdf(src, from_page=i, to_page=i)
        doc.set_metadata(src.metadata)
        out.append(doc.tobytes())
    return out


def render(r: Recipe, forgeries: list[str], fmt: str) -> list[tuple[str, str, bytes]]:
    """[(card id, file name, bytes)] for the claim and policy cards."""
    pages = claim_pages(r)
    clean = _pdf(pages)
    pack = _apply_file_forgeries(clean, r, forgeries, bill_page=2)
    names = ["claim-form", "discharge-summary", "hospital-bill", *[f"pharmacy-{k + 1}" for k in range(len(r.pharmacies))]]
    if fmt == "one_pdf":
        claim = [("claim", "claim.pdf", pack)]
        if "duplicate_page" in forgeries:  # the hospital bill uploaded again
            claim.append(("claim", "hospital-bill-again.pdf", _split(pack)[2]))
    else:
        files = _split(clean)  # each document its own file: only the bill's file was edited
        files[2] = _apply_file_forgeries(files[2], r, forgeries, bill_page=0)
        if "duplicate_page" in forgeries:
            files.append(files[2])
            names = [*names, "hospital-bill-again"]
        if fmt == "split_files":
            claim = [("claim", f"{n}.pdf", data) for n, data in zip(names, files)]
        else:  # photos: each page photographed
            claim = []
            for k, (n, data) in enumerate(zip(names, files)):
                png = pymupdf.open(stream=data, filetype="pdf")[0].get_pixmap(dpi=150).tobytes("png")
                claim.append(("claim", f"{n}.jpg", to_photo(png, r.seed * 100 + k)[0]))
    if "missing_page" in forgeries:  # the last pharmacy page never uploaded
        claim = claim[:-1] if fmt != "one_pdf" else [("claim", "claim.pdf", _drop_last(pack))]
    if "cv_in_claim" in forgeries:
        claim.append(("claim", "resume.pdf", cv_pdf()))
    policy = [("policy", "policy.pdf", policy_pdf(r))]
    if "bill_in_policy" in forgeries:
        policy.append(("policy", "hospital-bill.pdf", _split(pack)[2]))
    if "policy_in_claim" in forgeries:
        claim.append(("claim", "policy-copy.pdf", policy_pdf(r)))
    return claim + policy


def _drop_last(pack: bytes) -> bytes:
    doc = pymupdf.open(stream=pack, filetype="pdf")
    doc.delete_page(doc.page_count - 1)
    return doc.tobytes()


def pharmacy_after(r: Recipe) -> Recipe:
    """An inpatient pharmacy bill dated two days after discharge."""
    from eval.scenarios.recipe import Pharmacy

    extra = Pharmacy(f"PH-{r.run}-{r.seed}-late", r.discharge + timedelta(days=2), 2400, inpatient=True)
    return r.copy(pharmacies=[*r.pharmacies, extra], claimed=r.claimed + extra.amount)
