import json
import shutil

from claimlens.ai import FakeAi
from claimlens.pipeline.checks.bill_story import check_bill_story
from claimlens.pipeline.extract import extract
from claimlens.pipeline.prove import prove
from tests.conftest import FAKE_AI, make_ctx


def _verdict(verdict="unrelated", quote="Surgeon and OT charges"):
    return {"item": "Surgeon and OT charges", "verdict": verdict, "reason": "Not part of an eye operation.",
            "bill_page": 3, "bill_quote": quote, "story_page": 2, "story_quote": "Senile cataract, right eye"}


def _ctx(tmp_path, verdicts):
    fixtures = tmp_path / "ai"
    shutil.copytree(FAKE_AI, fixtures)
    (fixtures / "bill_story.json").write_text(json.dumps(verdicts))
    c = make_ctx(tmp_path, ai=FakeAi(fixtures))
    extract(c)
    return c


class Raises:
    def judge_bill_story(self, *a):
        raise RuntimeError("boom")


def test_unrelated_charge_becomes_medium(tmp_path):
    found = check_bill_story(_ctx(tmp_path, [_verdict()]))
    assert len(found) == 1
    f = found[0]
    assert (f.check, f.code, f.severity) == ("bill_story", "charge_unrelated_to_treatment", "medium")
    assert "Senile cataract" in f.title and f.detail.endswith("Check with the hospital.")
    assert f.deductions == []
    assert (f.citations[0].doc, f.citations[0].page, f.citations[0].quote) == ("claim", 3, "Surgeon and OT charges")


def test_unusual_charge_is_low(tmp_path):
    f = check_bill_story(_ctx(tmp_path, [_verdict("unusual")]))[0]
    assert (f.code, f.severity) == ("charge_unusual_for_treatment", "low")


def test_fits_makes_nothing(tmp_path):
    assert check_bill_story(_ctx(tmp_path, [_verdict("fits")])) == []


def test_off_setting_skips_call(ctx):
    ctx.deps.settings.bill_story = "off"
    ctx.deps.ai = Raises()
    assert check_bill_story(ctx) == []


def test_ai_failure_gives_low_note(ctx):
    ctx.deps.ai = Raises()
    found = check_bill_story(ctx)
    assert [(f.code, f.severity) for f in found] == [("bill_story_unavailable", "low")]
    assert found[0].detail == "The check of the bill against the treatment couldn't run."
    kept, dropped = prove(ctx, found)
    assert kept and not dropped


def test_made_up_quote_dropped_by_prove(tmp_path):
    c = _ctx(tmp_path, [_verdict(quote="Chemotherapy session")])
    kept, dropped = prove(c, check_bill_story(c))
    assert kept == [] and len(dropped) == 1
