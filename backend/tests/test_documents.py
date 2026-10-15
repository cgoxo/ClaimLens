"""The document check: stop before any analysis when a file isn't an insurance document, or is in the wrong form."""

import pymupdf

from claimlens.ai import FakeAi
from claimlens.models import DocLabel
from claimlens.pipeline.run import run_pipeline
from tests.conftest import FAKE_AI, SAMPLES
from tests.test_api import A, _client
from tests.test_read_cards import one_page, photo

CV = "Curriculum Vitae\nRavi Kumar, software engineer\nExperience: 2019-2024 Acme Ltd, Bengaluru\nSkills: Python, SQL"


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(text.split("\n")):
        page.insert_text((50, 80 + 16 * i), line)
    return doc.tobytes()


class Labelling(FakeAi):
    """FakeAi whose document labels are given per file name; files not named get no label."""

    def __init__(self, labels: dict[str, tuple[str, str, str]]):
        super().__init__(FAKE_AI)
        self.labels, self.extracted = labels, False

    def classify_documents(self, text: str) -> list[DocLabel]:
        out = []
        for n, line in enumerate(l for l in text.splitlines() if l.startswith("=== file ")):
            name = line.split(": ", 1)[1].split(" (", 1)[0]
            if name in self.labels:
                kind, what, quote = self.labels[name]
                out.append(DocLabel(file=n + 1, kind=kind, what=what, quote=quote))
        return out

    def extract_facts(self, claim_text):
        self.extracted = True
        return super().extract_facts(claim_text)


def _run(settings, files, labels):
    from tests.conftest import upload_case

    client = _client(settings)
    ai = Labelling(labels)
    client.app.state.deps.ai = ai
    r = upload_case(client, A, files=files)
    assert r.status_code == 200, r.text
    return client, client.get(f"/api/cases/{r.json()['case_id']}", headers=A).json(), ai


SAMPLE = [("claim", "claim.pdf", (SAMPLES / "claim.pdf").read_bytes())]
POLICY = [("policy", "policy.pdf", (SAMPLES / "policy.pdf").read_bytes())]


def test_a_cv_stops_the_case_before_any_analysis(settings):
    client, case, ai = _run(settings, SAMPLE + [("claim", "resume.pdf", _pdf(CV))] + POLICY,
                            {"resume.pdf": ("not_insurance", "a CV", "Curriculum Vitae")})
    assert case["status"] == "REJECTED"
    assert case["rejected"] == [{"name": "resume.pdf", "form": "Claim", "reason": "This is a CV, not an insurance document.",
                                 "page": 5, "quote": "Curriculum Vitae"}]
    assert case["findings"] == [] and case["risk"] is None
    assert not ai.extracted  # stopped before the facts were read
    row = next(c for c in client.get("/api/cases", headers=A).json() if c["id"] == case["id"])
    assert row["status"] == "REJECTED"
    assert case["seen_at"] is not None  # a rejected case counts as finished: opening it marks it seen


def test_a_label_without_real_evidence_is_ignored(settings):
    _, case, _ = _run(settings, SAMPLE + POLICY, {"claim.pdf": ("not_insurance", "a recipe", "two cups of flour")})
    assert case["status"] == "READY"


def test_a_bill_in_the_policy_form_stops_the_case(settings):
    _, case, _ = _run(settings, SAMPLE + POLICY + [("policy", "bill.pdf", one_page(3))],
                      {"bill.pdf": ("bill", "a hospital bill", "Hospital Bill - Invoice INV-SEH-2026-0412")})
    assert case["status"] == "REJECTED"
    [r] = case["rejected"]
    assert (r["name"], r["form"]) == ("bill.pdf", "Policy")
    assert r["reason"] == "This is a bill, but it's in the Policy form."


def test_the_policy_in_the_claim_form_stops_the_case(settings):
    files = SAMPLE + [("claim", "policy-copy.pdf", (SAMPLES / "policy.pdf").read_bytes())] + POLICY
    _, case, _ = _run(settings, files, {"policy-copy.pdf": ("policy", "the policy", "Policy Schedule")})
    assert [r["reason"] for r in case["rejected"]] == ["This is an insurance policy, but it's in the Claim form."]


def test_an_unreadable_file_is_noted_and_the_analysis_goes_on(settings):
    _, case, _ = _run(settings, SAMPLE + [("claim", "blurry.jpg", photo(4))] + POLICY, {})
    assert case["status"] == "READY"
    [note] = [f for f in case["findings"] if f["code"] == "unreadable_file"]
    assert note["severity"] == "low"
    assert note["title"] == "blurry.jpg couldn't be read, so it wasn't checked"
