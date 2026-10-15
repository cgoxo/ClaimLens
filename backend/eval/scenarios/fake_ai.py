"""An AI stand-in for the offline run: it 'reads' exactly the true facts, so any difference from the expected
result is the product's logic, not the model's."""

from claimlens.models import ClaimFacts, CoverageItem, DocLabel, Finding, PolicyFacts
from eval.scenarios.truth import Truth


class TruthAi:
    def __init__(self, truth: Truth):
        self.truth = truth

    def classify_documents(self, files_text: str) -> list[DocLabel]:
        out = []
        for line in files_text.splitlines():
            if not line.startswith("=== file "):
                continue
            n, rest = line.removeprefix("=== file ").split(": ", 1)
            name = rest.rsplit(" (", 1)[0]
            kind, quote = self.truth.labels.get(name, ("claim_form", "Claim Form"))
            out.append(DocLabel(file=int(n), kind=kind, what="a CV" if kind == "not_insurance" else "", quote=quote))
        return out

    def extract_facts(self, claim_text: str) -> ClaimFacts:
        return self.truth.facts or ClaimFacts()

    def extract_policy(self, policy_text: str) -> PolicyFacts:
        return self.truth.policy or PolicyFacts()

    def judge_coverage(self, policy_text: str, facts: ClaimFacts) -> list[CoverageItem]:
        return []  # waiting periods and room limits are worked out by code; no other exclusions in these policies

    def summarise(self, findings: list[Finding]) -> str:
        return f"{len(findings)} findings."
