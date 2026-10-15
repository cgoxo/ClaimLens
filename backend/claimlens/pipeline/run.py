"""Runs the five steps for one case and records progress on the case."""

import logging
import time

from claimlens.cards import cards_of, ordered
from claimlens.logs import case_logger
from claimlens.pipeline.checks import ALL_CHECKS
from claimlens.pipeline.checks.cards import duplicate_pages
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
        cards = cards_of(case)
        tagged = bool(case.cards)  # cases from before cards keep untagged pages
        plan = [(stream, card, i, f) for stream in ("claim", "policy") for card in ordered(cards, stream)
                for i, f in enumerate(card.files)]
        # page counts were stored at upload; only cases from before cards need their files opened to count
        total = sum(f.pages or open_document(deps.storage.get(f.key), f.name).page_count for _, _, _, f in plan)
        status("READING", "Reading the documents", total)
        read, done, next_page = ReadResult(), 0, {"claim": 1, "policy": 1}

        for stream, card, i, f in plan:
            label = f.name

            def on_page(doc: str, n: int, kind: str) -> None:
                nonlocal done
                done += 1
                verb = "Reading" if kind == "digital" else "OCR on"
                progress.tick(f"{verb} {label}, page {n} ({done} of {total})", done, force=n == 1 or done == total)  # each file's start names its card

            data = deps.storage.get(f.key)  # one file in memory at a time: a claim can be 40 files of 20 MB
            part = read_document(stream, data, f.name, case_id, deps.storage, deps.ocr, on_page=on_page,
                                 start_page=next_page[stream], card_id=card.id if tagged else None, key=f.key,
                                 file_index=i)
            next_page[stream] += len(part.pages)
            read.extend(part)
        db.put_pages(case_id, read.pages)
        ctx = Ctx(case_id=case_id, read=read, deps=deps, cards=cards if tagged else [])
        ctx.skip_pages = {("claim", later.page) for _, later in duplicate_pages(read)}  # never count a page twice

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
