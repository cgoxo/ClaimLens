from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field as PydField

Severity = Literal["critical", "high", "medium", "low", "coverage"]
Status = Literal["QUEUED", "READING", "CHECKING", "PROVING", "READY", "FAILED"]
PageKind = Literal["digital", "scanned", "scanned_with_text", "image", "unreadable"]
SEVERITY_ORDER: list[str] = ["critical", "high", "medium", "low", "coverage"]

BBox = tuple[float, float, float, float]


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- what the Read step sees -------------------------------------------------

class Span(BaseModel):
    doc: str
    page: int
    text: str
    font: str
    size: float
    bbox: BBox
    seqno: int = 0
    confidence: float = 1.0


class PageInfo(BaseModel):
    doc: str
    page: int
    kind: PageKind
    text: str = ""
    width: float
    height: float
    png_key: str


class FileInfo(BaseModel):
    doc: str
    producer: str = ""
    creator: str = ""
    created: str = ""
    modified: str = ""
    eof_count: int = 1


# --- findings and cases ------------------------------------------------------

class Citation(BaseModel):
    doc: str
    page: int
    quote: str
    bbox: BBox | None = None
    # where the proof lives: the visible page text, the file's metadata, or the invisible OCR layer
    source: Literal["page", "metadata", "hidden_layer"] = "page"


class Review(BaseModel):
    action: Literal["accept", "dismiss"]
    note: str = ""
    by: str
    at: datetime = PydField(default_factory=now)


class Finding(BaseModel):
    id: str
    check: Literal["tamper", "story", "duplicate", "coverage"]
    code: str
    severity: Severity
    title: str
    detail: str = ""
    citations: list[Citation] = []
    amount_not_payable: float = 0
    verified: bool = False
    review: Review | None = None


class Case(BaseModel):
    id: str
    owner_email: str
    status: Status = "QUEUED"
    step: str | None = None
    error: str | None = None
    created_at: datetime = PydField(default_factory=now)
    updated_at: datetime = PydField(default_factory=now)
    files: dict[str, str] = {}
    score: int | None = None
    risk: Literal["low", "review", "high"] | None = None
    payable: float | None = None
    summary: str | None = None
    dropped_findings: list[dict] = []
    context: dict | None = None  # grounded claim/policy facts, saved right after Extract
    progress: dict | None = None  # {step, done, total, label} while running
    finished_at: datetime | None = None
    seen_at: datetime | None = None  # when the owner last opened it after it finished
    findings_count: int | None = None


# --- facts the AI pulls out (each value carries its proof) ------------------

class Fact(BaseModel):
    value: str | float | None = None
    page: int
    quote: str
    bbox: BBox | None = None


class Procedure(BaseModel):
    name: Fact
    date: Fact | None = None


class Room(BaseModel):
    rate_per_day: Fact | None = None
    days: Fact | None = None


class LineItem(BaseModel):
    desc: str
    amount: Fact | None = None


class Bill(BaseModel):
    page: int
    kind: Literal["hospital", "pharmacy", "other"] = "other"
    invoice_no: Fact | None = None
    date: Fact | None = None
    inpatient: bool = False
    line_items: list[LineItem] = []
    total: Fact | None = None


class ClaimFacts(BaseModel):
    policy_number: Fact | None = None
    hospital_name: Fact | None = None
    claimant_name: Fact | None = None
    admission_date: Fact | None = None
    discharge_date: Fact | None = None
    claim_date: Fact | None = None
    amount_claimed: Fact | None = None
    diagnosis: Fact | None = None
    names: list[Fact] = []
    procedures: list[Procedure] = []
    room: Room | None = None
    bills: list[Bill] = []


class WaitingPeriod(BaseModel):
    condition: str
    months: int
    clause: str = ""
    page: int
    quote: str


class PolicyFacts(BaseModel):
    insurer_name: Fact | None = None
    policy_number: Fact | None = None
    start_date: Fact | None = None
    sum_insured: Fact | None = None
    room_rent_limit_per_day: Fact | None = None
    waiting_periods: list[WaitingPeriod] = []


class CoverageItem(BaseModel):
    item: str
    verdict: Literal["covered", "not_covered", "partly_covered", "unknown"]
    reason: str = ""
    clause: str = ""
    page: int | None = None
    quote: str = ""
    amount_not_payable: float = 0
