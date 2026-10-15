import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from claimlens.models import ClaimFacts, CoverageItem, DocLabel, Finding, PolicyFacts


class Ai(Protocol):
    def classify_documents(self, files_text: str) -> list[DocLabel]: ...
    def extract_facts(self, claim_text: str) -> ClaimFacts: ...
    def extract_policy(self, policy_text: str) -> PolicyFacts: ...
    def judge_coverage(self, policy_text: str, facts: ClaimFacts) -> list[CoverageItem]: ...
    def summarise(self, findings: list[Finding]) -> str: ...


class FakeAi:
    """Returns hand-written answers from a fixtures folder; ignores its input."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def _load(self, name: str):
        return json.loads((self.folder / f"{name}.json").read_text())

    def classify_documents(self, files_text: str) -> list[DocLabel]:
        """No labels unless a fixture says otherwise: nothing is rejected."""
        if not (self.folder / "documents.json").is_file():
            return []
        return TypeAdapter(list[DocLabel]).validate_python(self._load("documents"))

    def extract_facts(self, claim_text: str) -> ClaimFacts:
        return ClaimFacts.model_validate(self._load("facts"))

    def extract_policy(self, policy_text: str) -> PolicyFacts:
        return PolicyFacts.model_validate(self._load("policy"))

    def judge_coverage(self, policy_text: str, facts: ClaimFacts) -> list[CoverageItem]:
        return TypeAdapter(list[CoverageItem]).validate_python(self._load("coverage"))

    def summarise(self, findings: list[Finding]) -> str:
        return self._load("summary")["text"]


FACTS_PROMPT = """You read insurance claim documents. The text is split into pages marked "=== claim page N ===".
Fill the JSON schema. Rules:
- For every value give `page` (the page it is on) and `quote`: a short, exact copy of the text on that page
  that shows the value. Copy characters exactly as written (keep "Rs", commas and hyphens). One line at most.
- Dates: `value` exactly as written. Money and counts: `value` as a plain number.
- `names`: every place the patient or claimant name appears, one entry per page.
- `bills`: one entry per bill. `inpatient` is true when the bill is for an inpatient / ward / hospital-stay.
  Give every line item with its amount, and the bill total as printed.
- `room`: the room rate per day and number of days, if the bill shows them.
- `hospital_name`: the hospital's name as printed.
- If something is not in the documents, use null. Never invent values."""

POLICY_PROMPT = """You read an insurance policy. The text is split into pages marked "=== policy page N ===".
Fill the JSON schema. For every value give `page` and `quote`, an exact short copy of the text on that page.
- `insurer_name`: the insurance company's name as printed.
- `start_date`: the policy start date, as written.
- `sum_insured` and `room_rent_limit_per_day`: plain numbers (rupees). For the room limit, quote the sentence
  that sets the limit.
- `waiting_periods`: one entry per condition listed under a waiting period, with `months`, the clause number
  and a quote of the sentence that states the waiting rule.
- If something is not in the policy, use null. Never invent values."""

DOCUMENTS_PROMPT = """You check what each uploaded file of a health insurance claim is. The files are marked
"=== file N: <name> (<form>) ===". For each file say what it is:
claim_form, bill (hospital, pharmacy or lab bill / invoice / receipt), discharge_summary, medical_report
(lab or scan report, doctor's notes), prescription, policy (the insurance policy, schedule or wording),
other_insurance (another insurance document, e.g. a pre-authorisation or ID card), or not_insurance
(anything else: a CV, a bank statement, a photo, an unrelated letter).
`what`: a few plain words, e.g. "a CV". `quote`: a short exact copy of text from that file that shows what it is.
Judge only from the text. Give one entry per file."""

COVERAGE_PROMPT = """You check an insurance claim against its policy. You get the policy text (pages marked
"=== policy page N ===") and the claim facts as JSON. List the claimed treatments and charges as items.
For each item, decide covered / not_covered / partly_covered. Cite the clause, the policy page, and copy the exact sentence you relied on. If the policy doesn't say, answer unknown. Do not guess.
Set `amount_not_payable` in rupees when part of an item is not payable, otherwise 0."""

SUMMARY_PROMPT = """Write 3-4 plain sentences for an insurance claim reviewer, using ONLY the findings given.
Start with the overall risk. Do not add facts that are not in the findings."""


def _schema(model) -> dict:
    """JSON schema for Gemini, without the bbox fields (code fills those in)."""
    schema = TypeAdapter(model).json_schema()

    def strip(node):
        if isinstance(node, dict):
            node.get("properties", {}).pop("bbox", None)
            if "required" in node:
                node["required"] = [r for r in node["required"] if r != "bbox"]
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)

    strip(schema)
    return schema


class VertexGemini:
    def __init__(self, project: str, location: str, model: str):
        from google import genai

        self.client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model

    def _ask(self, system: str, text: str, schema=None) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(system_instruction=system, temperature=0)
        if schema is not None:
            config.response_mime_type = "application/json"
            config.response_json_schema = _schema(schema)
        response = self.client.models.generate_content(model=self.model, contents=text, config=config)
        return response.text or ""

    def classify_documents(self, files_text: str) -> list[DocLabel]:
        return TypeAdapter(list[DocLabel]).validate_json(self._ask(DOCUMENTS_PROMPT, files_text, list[DocLabel]))

    def extract_facts(self, claim_text: str) -> ClaimFacts:
        return ClaimFacts.model_validate_json(self._ask(FACTS_PROMPT, claim_text, ClaimFacts))

    def extract_policy(self, policy_text: str) -> PolicyFacts:
        return PolicyFacts.model_validate_json(self._ask(POLICY_PROMPT, policy_text, PolicyFacts))

    def judge_coverage(self, policy_text: str, facts: ClaimFacts) -> list[CoverageItem]:
        claim = facts.model_dump_json(exclude_none=True)
        raw = self._ask(COVERAGE_PROMPT, f"{policy_text}\n\n=== claim facts ===\n{claim}", list[CoverageItem])
        return TypeAdapter(list[CoverageItem]).validate_json(raw)

    def summarise(self, findings: list[Finding]) -> str:
        lines = "\n".join(f"- [{f.severity}] {f.title}. {f.detail}" for f in findings) or "- no problems found"
        return self._ask(SUMMARY_PROMPT, lines).strip()
