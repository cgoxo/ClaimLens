from dataclasses import dataclass, field
from typing import Any

from claimlens.models import ClaimFacts, PolicyFacts, Span
from claimlens.pipeline.read import ReadResult


@dataclass
class Ctx:
    """Everything the checks need, in memory, for one case run."""

    case_id: str
    read: ReadResult
    deps: Any
    claim_facts: ClaimFacts | None = None
    policy_facts: PolicyFacts | None = None
    files: dict[str, str] = field(default_factory=dict)  # doc -> storage key

    def page_text(self, doc: str, page: int) -> str:
        return next((p.text for p in self.read.pages if p.doc == doc and p.page == page), "")

    def page_kind(self, doc: str, page: int) -> str:
        return next((p.kind for p in self.read.pages if p.doc == doc and p.page == page), "unreadable")

    def spans_on(self, doc: str, page: int) -> list[Span]:
        return [s for s in self.read.spans if s.doc == doc and s.page == page]
