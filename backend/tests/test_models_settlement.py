import json

from claimlens.models import Case, Finding, LineItem, PolicyFacts, Rule, WaitingPeriod
from tests.conftest import FAKE_AI


def test_old_policy_json_still_validates():
    policy = PolicyFacts.model_validate(json.loads((FAKE_AI / "policy.json").read_text()))
    assert policy.co_pays == []
    assert policy.room_limit is None


def test_waiting_period_is_a_rule():
    assert issubclass(WaitingPeriod, Rule)


def test_line_item_defaults_to_other():
    assert LineItem(desc="x").category == "other"


def test_old_finding_json_has_no_deductions():
    finding = Finding.model_validate({"id": "f1", "check": "story", "code": "c", "severity": "low", "title": "t"})
    assert finding.deductions == []
    assert finding.items == []


def test_case_without_outcomes_validates():
    case = Case(id="c", owner_email="a@x")
    assert case.analysis is None
    assert case.current is None
    assert case.rules_not_verified == []
