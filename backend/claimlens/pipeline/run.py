"""Runs the five steps for one case and records progress on the case."""

import logging

from claimlens.pipeline.checks import ALL_CHECKS
from claimlens.pipeline.checks.duplicate import register_invoices
from claimlens.pipeline.context import Ctx
from claimlens.pipeline.extract import extract
from claimlens.pipeline.prove import prove
from claimlens.pipeline.read import ReadResult, read_document
from claimlens.pipeline.report import payable, risk_band, score, sort_findings, summarise

log = logging.getLogger(__name__)


def run_pipeline(case_id: str, deps) -> None:
    db, step = deps.db, "QUEUED"

    def status(value: str) -> None:
        nonlocal step
        step = value
        db.update_case(case_id, status=value)

    try:
        case = db.get_case(case_id)
        status("READING")
        read = ReadResult()
        for doc, key in case.files.items():
            data = deps.storage.get(key)
            read.extend(read_document(doc, data, key.rsplit("/", 1)[-1], case_id, deps.storage, deps.ocr))
        db.put_pages(case_id, read.pages)
        ctx = Ctx(case_id=case_id, read=read, deps=deps, files=dict(case.files))

        status("CHECKING")
        extract(ctx)
        findings = [f for check in ALL_CHECKS for f in check(ctx)]

        status("PROVING")
        kept, dropped = prove(ctx, findings)
        kept = sort_findings(kept)
        db.put_findings(case_id, kept)

        value = score(kept)
        report = dict(score=value, risk=risk_band(value), payable=payable(ctx, kept),
                      summary=summarise(ctx, kept), dropped_findings=dropped)
        register_invoices(ctx)
        db.update_case(case_id, status="READY", step=None, **report)
    except Exception as e:
        log.exception("case %s failed during %s", case_id, step)
        db.update_case(case_id, status="FAILED", step=step, error=str(e))
