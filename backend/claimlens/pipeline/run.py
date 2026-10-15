"""Runs the five steps for one case and records progress on the case."""

import logging
import time

from claimlens.logs import case_logger
from claimlens.pipeline.checks import ALL_CHECKS
from claimlens.pipeline.checks.coverage import policy_start, treated_date
from claimlens.pipeline.checks.duplicate import register_invoices
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import extract
from claimlens.pipeline.prove import prove
from claimlens.models import now
from claimlens.pipeline.read import ReadResult, open_document, read_document
from claimlens.pipeline.report import payable, risk_band, score, sort_findings, summarise
from claimlens.pipeline.text import months_between

log = logging.getLogger(__name__)


class Progress:
    """Writes {step, done, total, label} to the case: every step change, other updates at most once a second."""

    def __init__(self, db, case_id: str, clock=time.monotonic):
        self.db, self.case_id, self.clock = db, case_id, clock
        self.step_name, self.total, self.last = "", 0, None

    def _write(self, label: str, done: int, at: float | None = None, **fields) -> None:
        self.last = self.clock() if at is None else at
        progress = {"step": self.step_name, "done": done, "total": self.total, "label": label}
        if fields:  # carries real case fields (status, context): a failure must fail the case
            self.db.update_case(self.case_id, progress=progress, **fields)
            return
        try:
            self.db.update_case(self.case_id, progress=progress)
        except Exception:  # progress alone is cosmetic: never fail a case over it
            log.warning("progress write failed for case %s", self.case_id, exc_info=True)

    def step(self, step: str, label: str, total: int = 0, **fields) -> None:
        """A new step; `fields` (e.g. status) go in the same write."""
        self.step_name, self.total = step, total
        self._write(label, 0, **fields)

    def tick(self, label: str, done: int, force: bool = False) -> None:
        at = self.clock()
        if force or self.last is None or at - self.last >= 1.0:
            self._write(label, done, at)


def context_of(ctx: Ctx) -> dict:
    """What the claim is about, for the reviewer: grounded facts only, plus policy age at treatment."""
    f, p = ctx.claim_facts, ctx.policy_facts
    start = policy_start(p) if p else None
    treated = treated_date(f) if f else None
    return {
        "claim": f.model_dump(mode="json", exclude_none=True) if f else None,
        "policy": p.model_dump(mode="json", exclude_none=True) if p else None,
        "policy_age_months": months_between(start, treated) if start and treated else None,
    }


def run_pipeline(case_id: str, deps) -> None:
    db, step, clog = deps.db, "QUEUED", log
    progress = Progress(db, case_id)

    def status(value: str, label: str, total: int = 0) -> None:
        nonlocal step
        step = value
        progress.step(value, label, total, status=value)

    try:
        case = db.get_case(case_id)
        clog = case_logger(case_id, case.owner_email)
        step = "READING"
        files = {doc: (deps.storage.get(key), key.rsplit("/", 1)[-1]) for doc, key in case.files.items()}
        total = sum(open_document(data, name).page_count for data, name in files.values())
        status("READING", "Reading the documents", total)
        read, done = ReadResult(), 0

        def on_page(doc: str, n: int, kind: str) -> None:
            nonlocal done
            done += 1
            verb = "Reading" if kind == "digital" else "OCR on"
            progress.tick(f"{verb} {doc} page {n} ({done} of {total})", done, force=done == total or done == 1)

        for doc, (data, name) in files.items():
            read.extend(read_document(doc, data, name, case_id, deps.storage, deps.ocr, on_page=on_page))
        db.put_pages(case_id, read.pages)
        ctx = Ctx(case_id=case_id, read=read, deps=deps, files=dict(case.files))

        status("CHECKING", "Extracting facts with Gemini")
        extract(ctx)
        findings = []
        for n, check in enumerate(ALL_CHECKS):
            name = check.__name__.removeprefix("check_")
            label = "Checking coverage with Gemini" if name == "coverage" else f"Checking: {name}"
            if n == 0:  # the context rides on the first check's progress write
                progress.step("CHECKING", label, total=len(ALL_CHECKS), context=context_of(ctx))
            else:
                progress.tick(label, n, force=True)
            findings += check(ctx)

        status("PROVING", "Proving findings")
        kept, dropped = prove(ctx, findings)
        kept = sort_findings(kept)
        db.put_findings(case_id, kept)

        value = score(kept)
        report = dict(score=value, risk=risk_band(value), payable=payable(ctx, kept),
                      summary=summarise(ctx, kept), dropped_findings=dropped,
                      findings_count=len(kept))
        register_invoices(ctx)
        db.update_case(case_id, status="READY", step=None, progress=None, finished_at=now(), **report)
    except Exception as e:
        clog.exception("case %s failed during %s", case_id, step)
        db.update_case(case_id, status="FAILED", step=step, error=str(e), progress=None, finished_at=now())
