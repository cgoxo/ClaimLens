from claimlens.ai import FakeAi
from claimlens.models import ClaimFacts, Fact
from claimlens.pipeline.extract import extract
from claimlens.pipeline.run import context_of, run_pipeline
from tests.conftest import FAKE_AI, make_ctx
from tests.test_pipeline import _deps, _new_case


def test_new_facts_grounded(ctx):
    assert ctx.claim_facts.hospital_name.value == "Sunrise Eye & General Hospital, Pune"
    assert ctx.claim_facts.hospital_name.bbox is not None
    assert ctx.policy_facts.insurer_name.page == 1


def test_fabricated_hospital_dropped(tmp_path):
    class Fake(FakeAi):
        def extract_facts(self, claim_text) -> ClaimFacts:
            facts = super().extract_facts(claim_text)
            return facts.model_copy(update={"hospital_name": Fact(value="Apollo Clinic, Delhi", page=1, quote="Apollo Clinic, Delhi")})

    c = make_ctx(tmp_path, ai=Fake(FAKE_AI))
    extract(c)
    assert c.claim_facts.hospital_name is None


def test_context_of_sample(ctx):
    out = context_of(ctx)
    assert out["policy_age_months"] == 2
    assert out["claim"]["policy_number"]["value"] == "EH-2025-778812"
    assert out["policy"]["insurer_name"]["page"] == 1


def test_context_none_when_no_dates(ctx):
    ctx.policy_facts = ctx.policy_facts.model_copy(update={"start_date": None})
    assert context_of(ctx)["policy_age_months"] is None


def test_context_saved_before_checks(tmp_path, monkeypatch):
    seen = []

    def spy(ctx):
        seen.append(ctx.deps.db.get_case("c1").context)
        return []

    monkeypatch.setattr("claimlens.pipeline.run.ALL_CHECKS", [spy])
    deps = _deps(tmp_path)
    run_pipeline(_new_case(deps), deps)
    assert seen and seen[0] is not None and "claim" in seen[0]
