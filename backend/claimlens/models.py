from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field as PydField, field_validator

Severity = Literal["critical", "high", "medium", "low", "coverage"]
Status = Literal["DRAFT", "QUEUED", "READING", "CHECKING", "PROVING", "READY", "FAILED", "REJECTED"]
DocKind = Literal["claim_form", "bill", "discharge_summary", "medical_report", "prescription", "policy",
                  "other_insurance", "not_insurance"]
CardRole = Literal["claim", "policy"]
PageKind = Literal["digital", "scanned", "scanned_with_text", "image", "unreadable"]
SEVERITY_ORDER: list[str] = ["critical", "high", "medium", "low", "coverage"]

Category = Literal["room", "icu", "surgery", "doctor", "nursing", "investigations", "medicines", "consumables",
                   "implants", "ambulance", "other"]

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
    page: int  # in its stream (claim or policy), across all the stream's files
    kind: PageKind
    text: str = ""
    width: float
    height: float
    png_key: str
    card_id: str | None = None  # None for cases from before cards
    file_index: int = 0
    file_page: int = 0  # 1-based page within its file


class CaseFile(BaseModel):
    key: str
    name: str
    content_type: str = "application/pdf"
    pages: int = 0
    client_id: str | None = None  # the browser's id for this file: a re-send after a lost response is a no-op


class Card(BaseModel):
    """One of the two upload forms: the claim (claim form, supporting documents and the one bill,
    possibly photographed in several images) or the policy. Files are in page order."""

    id: str
    role: CardRole
    files: list[CaseFile] = []

    @field_validator("role", mode="before")
    @classmethod
    def _earlier_roles(cls, role):
        """Cases saved while the claim was split into claim-form, bill and supporting cards."""
        return "claim" if role in ("claim_form", "bill", "supporting") else role


class FileInfo(BaseModel):
    doc: str
    card_id: str | None = None
    key: str = ""
    first_page: int = 1  # stream page where this file starts
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
    action: Literal["accept", "dismiss", "restore"]  # "restore" is stored on versions only; a restored finding has review=None
    note: str = ""
    by: str
    at: datetime = PydField(default_factory=now)


class LineDeduction(BaseModel):
    """Rupees a finding takes off a bill line. bill and line index ClaimFacts.bills[bill].line_items[line];
    line = -1 means the whole bill, bill = -1 means claim level."""

    bill: int
    line: int
    amount: float


class Finding(BaseModel):
    id: str
    check: Literal["tamper", "story", "duplicate", "cards", "coverage", "bill_story", "reviewer"]
    code: str
    severity: Severity
    title: str
    detail: str = ""
    citations: list[Citation] = []
    amount_not_payable: float = 0
    deductions: list[LineDeduction] = []
    items: list[str] = []
    verified: bool = False
    review: Review | None = None
    removed: bool = False  # no longer produced after a fact correction: never counts, hidden in the UI


# --- settlement and outcome ---------------------------------------------------

Action = Literal["investigate", "query", "not_payable", "approve_part", "approve"]


class Deduction(BaseModel):
    amount: float
    reason: str
    finding_id: str | None = None
    rule: Citation | None = None


class SettlementLine(BaseModel):
    bill: int
    line: int
    desc: str
    category: Category
    claimed: float
    deductions: list[Deduction] = []
    payable: float


class Note(BaseModel):
    text: str
    affects_amount: bool = False


class Settlement(BaseModel):
    lines: list[SettlementLine]
    claimed: float | None
    whole_claim: Deduction | None = None
    claim_level: list[Deduction] = []
    subtotal: float
    sub_limit: Deduction | None = None
    deductible: Deduction | None = None
    co_pay: Deduction | None = None
    si_cap: Deduction | None = None
    payable: float | None  # None when the claimed amount is unknown
    notes: list[Note] = []


class Recommendation(BaseModel):
    action: Action
    reasons: list[str]


class Outcome(BaseModel):
    score: int
    risk: Literal["low", "review", "high"]
    payable: float | None
    recommendation: Recommendation | None = None
    settlement: Settlement | None = None


class Case(BaseModel):
    id: str
    owner_email: str
    status: Status = "QUEUED"
    step: str | None = None
    error: str | None = None
    created_at: datetime = PydField(default_factory=now)
    updated_at: datetime = PydField(default_factory=now)
    files: dict[str, str] = {}  # cases from before cards: {"claim": key, "policy": key}
    cards: list[Card] = []
    run_attempt: int = -1  # last job delivery that claimed this case (run-once guard)
    score: int | None = None
    risk: Literal["low", "review", "high"] | None = None
    payable: float | None = None
    analysis: Outcome | None = None  # what the first run decided
    current: Outcome | None = None  # after the reviewer's accepts and dismissals
    rules_not_verified: list[dict] = []
    summary: str | None = None
    dropped_findings: list[dict] = []
    context: dict | None = None  # grounded claim/policy facts, saved right after Extract
    progress: dict | None = None  # {step, done, total, label} while running
    finished_at: datetime | None = None
    seen_at: datetime | None = None  # when the owner last opened it after it finished
    findings_count: int | None = None
    corrections: list[dict] = []  # [{path, old, new, by, at, reason, evidence, message_id}]
    rejected: list[dict] = []  # REJECTED: [{name, form, reason, page, quote}] for each file that stopped the case


# --- facts the AI pulls out (each value carries its proof) ------------------

class Fact(BaseModel):
    value: str | float | None = None
    page: int
    quote: str
    bbox: BBox | None = None
    source: Literal["document", "reviewer"] = "document"


class Procedure(BaseModel):
    name: Fact
    date: Fact | None = None


class Room(BaseModel):
    rate_per_day: Fact | None = None
    days: Fact | None = None


class LineItem(BaseModel):
    desc: str
    amount: Fact | None = None
    category: Category = "other"
    days: Fact | None = None
    rate: Fact | None = None


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
    patient_age: Fact | None = None
    room_type: Fact | None = None
    bills: list[Bill] = []


class Rule(BaseModel):
    """A policy rule with its proof: the clause, and a quote from the page it sits on."""

    clause: str = ""
    page: int
    quote: str


class WaitingPeriod(Rule):
    condition: str
    months: int


class CoPay(Rule):
    percent: float
    applies: Literal["all", "age_over", "other"] = "all"
    age: int | None = None
    condition_text: str = ""


class Deductible(Rule):
    amount: float
    per: Literal["claim", "year"] = "claim"


class Limit(Rule):
    """Per day. percent_of_si=1 means 1%."""

    amount: float | None = None
    percent_of_si: float | None = None


class RoomLimit(Limit):
    room_type_text: str = ""


class SubLimit(Limit):
    applies_to: str
    per: Literal["claim", "eye", "year"] = "claim"


class Exclusion(Rule):
    what: str


class NonPayable(Rule):
    items: list[str] = []
    standard_list: bool = False


class Window(Rule):
    pre_days: int | None = None
    post_days: int | None = None


class InitialWaiting(Rule):
    days: int


class PreExisting(Rule):
    months: int


class ProportionateDeduction(Rule):
    pass


class PolicyFacts(BaseModel):
    insurer_name: Fact | None = None
    policy_number: Fact | None = None
    start_date: Fact | None = None
    sum_insured: Fact | None = None
    room_rent_limit_per_day: Fact | None = None  # older cases; newer ones use room_limit
    waiting_periods: list[WaitingPeriod] = []
    co_pays: list[CoPay] = []
    deductible: Deductible | None = None
    room_limit: RoomLimit | None = None
    icu_limit: Limit | None = None
    proportionate_deduction: ProportionateDeduction | None = None
    sub_limits: list[SubLimit] = []
    initial_waiting: InitialWaiting | None = None
    pre_existing: PreExisting | None = None
    exclusions: list[Exclusion] = []
    non_payable: NonPayable | None = None
    window: Window | None = None


class DocLabel(BaseModel):
    """What the AI says one uploaded file is, with a quote from it as proof."""

    file: int  # 1-based, in the order the files were listed
    kind: DocKind
    what: str = ""  # a few words: "a CV", "a bank statement"
    quote: str = ""


class CoverageItem(BaseModel):
    item: str
    verdict: Literal["covered", "not_covered", "partly_covered", "unknown"]
    reason: str = ""
    clause: str = ""
    page: int | None = None
    quote: str = ""
    amount_not_payable: float = 0


class StoryVerdict(BaseModel):
    """Whether one bill item fits the treatment story, with a quote from the bill (and the story if any)."""

    item: str
    verdict: Literal["fits", "unusual", "unrelated"]
    reason: str = ""
    bill_page: int
    bill_quote: str
    story_page: int | None = None
    story_quote: str = ""


# --- chat ---------------------------------------------------------------------

class Box(BaseModel):
    doc: str
    page: int
    bbox: BBox


ProposalType = Literal["review_finding", "set_severity", "add_finding", "correct_fact"]
ProposalStatus = Literal["pending", "applying", "applied", "ignored", "stale", "failed"]


class Proposal(BaseModel):
    id: str
    type: ProposalType
    reason: str = ""
    finding_id: str | None = None
    action: Literal["accept", "dismiss", "restore"] | None = None
    severity: Severity | None = None
    title: str = ""
    detail: str = ""
    citations: list[Citation] = []
    path: str | None = None
    value: str | float | None = None
    evidence: Box | None = None
    finding_version: int | None = None
    status: ProposalStatus = "pending"
    decided_by: str | None = None
    decided_at: datetime | None = None
    error: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: Literal["reviewer", "assistant"]
    text: str
    selection: Box | None = None
    citations: list[Citation] = []
    proposals: list[Proposal] = []
    tool_calls: list[dict] = []
    verified: bool = True
    notes: list[str] = []
    by: str
    created_at: datetime = PydField(default_factory=now)


class ChatThread(BaseModel):
    id: str
    status: Literal["active", "closed"] = "active"
    carried_summary: str = ""
    summary: str = ""
    created_by: str
    created_at: datetime = PydField(default_factory=now)
