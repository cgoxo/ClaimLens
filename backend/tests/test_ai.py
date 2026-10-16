import json
import shutil

from claimlens.ai import FakeAi, _schema
from claimlens.models import PolicyFacts, StoryVerdict
from tests.conftest import FAKE_AI


def test_policy_schema_has_rules():
    text = json.dumps(_schema(PolicyFacts))
    assert "co_pays" in text
    assert "bbox" not in text


def test_fake_ai_bill_story_defaults_empty():
    assert FakeAi(FAKE_AI).judge_bill_story("", "[]") == []


def test_fake_ai_bill_story_from_fixture(tmp_path):
    folder = tmp_path / "ai"
    shutil.copytree(FAKE_AI, folder)
    verdict = {"item": "Cosmetic filler", "verdict": "unrelated", "bill_page": 3, "bill_quote": "Cosmetic filler 9,000"}
    (folder / "bill_story.json").write_text(json.dumps([verdict]))
    out = FakeAi(folder).judge_bill_story("story", "[]")
    assert out == [StoryVerdict(**verdict)]
