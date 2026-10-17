import json
import logging
import random
import time
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from claimlens.models import ClaimFacts, CoverageItem, DocLabel, Finding, PolicyFacts, StoryVerdict


log = logging.getLogger(__name__)
ATTEMPTS = 4  # waits of 4, 8, 16 s: a burst of cases shouldn't fail on a passing rate limit


class Ai(Protocol):
    def classify_documents(self, files_text: str) -> list[DocLabel]: ...
    def extract_facts(self, claim_text: str) -> ClaimFacts: ...
    def extract_policy(self, policy_text: str) -> PolicyFacts: ...
    def judge_coverage(self, policy_text: str, facts: ClaimFacts) -> list[CoverageItem]: ...
    def judge_bill_story(self, story_text: str, items_json: str) -> list[StoryVerdict]: ...
    def summarise(self, findings: list[Finding], outcome: str = "") -> str: ...


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

    def judge_bill_story(self, story_text: str, items_json: str) -> list[StoryVerdict]:
        """No verdicts unless a fixture says otherwise: every line fits."""
        if not (self.folder / "bill_story.json").is_file():
            return []
        return TypeAdapter(list[StoryVerdict]).validate_python(self._load("bill_story"))

    def summarise(self, findings: list[Finding], outcome: str = "") -> str:
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
- Each line item's `category` is one of: room, icu, surgery, doctor, nursing, investigations, medicines,
  consumables, implants, ambulance, other. Examples: room = "Deluxe room charges"; icu = "ICU charges";
  surgery = "Surgeon fee" or "OT charges"; doctor = "Consultant visit"; nursing = "Nursing charges";
  investigations = "CBC test" or "MRI scan"; medicines = "Injection Ceftriaxone"; consumables = "Syringes, gloves";
  implants = "Knee implant" or "Stent"; ambulance = "Ambulance charges"; other = anything else.
- For room and ICU lines give `days` and `rate` (per day) as printed on the line. Plain numbers.
- `patient_age`: the patient's age in years, if printed.
- `room_type`: the room type exactly as written (for example "Single private room").
- `hospital_name`: the hospital's name as printed.
- If something is not in the documents, use null. Never invent values."""

POLICY_PROMPT = """You read an insurance policy. The text is split into pages marked "=== policy page N ===".
Fill the JSON schema. For every value give `page` and `quote`, an exact short copy of the text on that page.
- `insurer_name`: the insurance company's name as printed.
- `start_date`: the policy start date, as written.
- `sum_insured` and `room_rent_limit_per_day`: plain numbers (rupees). For the room limit, quote the sentence
  that sets the limit. Fill `room_rent_limit_per_day` only when the policy states a rupee amount per day; when
  the limit is a percentage, leave it null and use `room_limit.percent_of_si`. Never convert a percentage to rupees.
- `waiting_periods`: one entry per condition listed under a waiting period, with `months`, the clause number
  and a quote of the sentence that states the waiting rule.
- Find every rule below. For each rule give `clause` (the clause number), `page` and `quote`: an exact one-line
  copy of the sentence on that page that states the rule.
- `co_pays`: one entry per co-payment. `percent` is a plain number of percent (`10` for 10%). `applies` is "all",
  "age_over" (with `age`, the threshold age in years: "insured above 60" gives `age: 60`) or "other" (put the condition in `condition_text`).
- `deductible`: `amount` in rupees; `per` is "claim" or "year".
- `room_limit`: the room rent limit per day. Give `amount` in rupees or `percent_of_si` as a plain number of
  percent (`1` for 1% of the sum insured), never both. `room_type_text` is the room type it names, if any.
- `icu_limit`: the ICU limit per day, with `amount` or `percent_of_si` as above.
- `proportionate_deduction`: set when the policy cuts other charges in proportion to a room rent excess.
- `sub_limits`: one entry per cap on a treatment or condition (`applies_to`), with `amount` or `percent_of_si`,
  and `per` ("claim", "eye" or "year").
- `initial_waiting`: the waiting period after the policy starts, `days` as a number.
- `pre_existing`: the pre-existing disease waiting period, `months` as a number.
- `exclusions`: one entry per excluded thing (`what`).
- `non_payable`: the items the policy never pays, in `items`. Set `standard_list` to true when the policy refers
  to the regulator's list of non-payable items instead of listing them.
- `window`: the days of cover before (`pre_days`) and after (`post_days`) hospitalisation.
- Money is a plain number of rupees. Percentages are a plain number of percent.
- If the policy does not have a rule, use null (or [] for lists). Never invent a rule.
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

BILL_STORY_PROMPT = """You check whether each bill line fits the patient's diagnosis and treatment. You get the
treatment story (the diagnosis, procedures and discharge summary, pages marked "=== claim page N ===") and the
bill lines as JSON.
`item` is the bill line's description as printed.
For each bill line that is not plainly part of the treatment, give a verdict:
fits, unusual or unrelated.
- fits: the line belongs to this diagnosis and treatment. You may leave these out.
- unusual: it could belong, but a doctor would ask about it. Use this only when a doctor would ask.
- unrelated: it has nothing to do with this diagnosis and treatment.
Quote the bill line exactly: `bill_page` and `bill_quote`, one line copied as written.
For an unrelated or unusual line, `story_quote` quotes the diagnosis or procedure line it was judged against,
with `story_page`: an exact copy from the story. Never invent a quote. If the story has no diagnosis or
procedure text, give `fits`.
Give a short plain `reason`.
Judge only medical fit, not price. Do not guess: if the story does not say, leave the line out."""

SUMMARY_PROMPT = """Write 3-4 plain sentences for an insurance claim reviewer, using ONLY the findings given.
Start with the overall risk. If a recommendation line is given, state it. Do not add facts that are not in the findings."""


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
        for attempt in range(ATTEMPTS):
            try:
                response = self.client.models.generate_content(model=self.model, contents=text, config=config)
                return response.text or ""
            except Exception as e:
                # a rate limit (429) or a server hiccup (5xx) passes; anything else is a real error
                code = getattr(e, "code", None)
                if attempt == ATTEMPTS - 1 or not (code == 429 or (isinstance(code, int) and code >= 500)):
                    raise
                wait = 4 * 2 ** attempt * random.uniform(0.75, 1.25)  # jitter: concurrent cases don't retry in step
                log.warning("Gemini busy (%s), retrying in %.0fs", code, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")

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

    def judge_bill_story(self, story_text: str, items_json: str) -> list[StoryVerdict]:
        raw = self._ask(BILL_STORY_PROMPT, f"{story_text}\n\n=== bill lines ===\n{items_json}", list[StoryVerdict])
        return TypeAdapter(list[StoryVerdict]).validate_json(raw)

    def summarise(self, findings: list[Finding], outcome: str = "") -> str:
        lines = "\n".join(f"- [{f.severity}] {f.title}. {f.detail}" for f in findings) or "- no problems found"
        if outcome:
            lines = f"{outcome}\n\n{lines}"
        return self._ask(SUMMARY_PROMPT, lines).strip()
