"""Step 1b (Check documents): is every file an insurance document, in the right form? If not, stop.

The AI says what each file is and quotes it; code decides, and only on a label whose quote is really in
the file. A file with no readable text can't be judged: it gets a note, and the analysis goes on.
"""

from dataclasses import dataclass

from claimlens.cards import card_label
from claimlens.models import Citation, Finding, PageInfo
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.prove import text_holds

PER_FILE_CHARS = 3000  # enough to tell what a document is; keeps the call small
NAMES = {"claim_form": "a claim form", "bill": "a bill", "discharge_summary": "a discharge summary",
         "medical_report": "a medical report", "prescription": "a prescription", "policy": "an insurance policy",
         "other_insurance": "an insurance document"}


@dataclass
class FileText:
    n: int
    name: str
    doc: str  # stream: claim or policy
    form: str  # the form it was uploaded in: "Claim" or "Policy"
    pages: list[PageInfo]

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)


def file_texts(ctx: Ctx) -> list[FileText]:
    names = {f.key: f.name for c in ctx.cards for f in c.files}
    forms = {f.key: card_label(ctx.cards, c.id) for c in ctx.cards for f in c.files}
    out = []
    for n, info in enumerate(ctx.read.files, 1):
        nxt = min((f.first_page for f in ctx.read.files if f.doc == info.doc and f.first_page > info.first_page),
                  default=10**9)
        pages = [p for p in ctx.read.pages if p.doc == info.doc and info.first_page <= p.page < nxt]
        out.append(FileText(n=n, name=names.get(info.key, info.key.rsplit("/", 1)[-1]), doc=info.doc,
                            form=forms.get(info.key, info.doc.capitalize()), pages=pages))
    return out


def _listing(files: list[FileText]) -> str:
    return "\n\n".join(f"=== file {f.n}: {f.name} ({f.form} form) ===\n{f.text[:PER_FILE_CHARS]}"
                       for f in files)


def _reason(kind: str, what: str, form: str) -> str | None:
    if kind == "not_insurance":
        return f"This is {what}, not an insurance document." if what else "This is not an insurance document."
    if form == "Policy" and kind not in ("policy", "other_insurance"):
        return f"This is {NAMES[kind]}, but it's in the Policy form."
    if form == "Claim" and kind == "policy":
        return "This is an insurance policy, but it's in the Claim form."
    return None


def check_documents(ctx: Ctx) -> tuple[list[dict], list[Finding]]:
    """(files that stop the case, notes about files that couldn't be checked)."""
    files = file_texts(ctx)
    readable = [f for f in files if f.text.strip()]
    notes = [Finding(
        id=f"unreadable_file-{f.doc}-{f.pages[0].page if f.pages else 1}-1", check="cards", code="unreadable_file",
        severity="low", title=f"{f.name} couldn't be read, so it wasn't checked",
        detail="It has no readable text (a photo with OCR off, or too blurry), so nothing on it could be verified.",
        citations=[Citation(doc=f.doc, page=f.pages[0].page if f.pages else 1, quote="", source="metadata")])
        for f in files if not f.text.strip()]
    if not readable:
        return [], notes
    by_n = {f.n: f for f in readable}
    rejected = []
    for label in ctx.deps.ai.classify_documents(_listing(readable)):
        f = by_n.get(label.file)
        if f is None or not label.quote or not text_holds(f.text, label.quote, 90):
            continue  # no proof in the file: never stop a claim on the AI's word alone
        if reason := _reason(label.kind, label.what, f.form):
            page = next((p.page for p in f.pages if text_holds(p.text, label.quote, 90)), f.pages[0].page)
            rejected.append({"name": f.name, "form": f.form, "reason": reason, "page": page, "quote": label.quote})
    return rejected, notes
