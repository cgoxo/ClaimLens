import pytest

from claimlens.cards import card_label, cards_of, layout_error, ordered
from claimlens.models import Card, Case


def _card(id, role, kind=None):
    return Card(id=id, role=role, kind=kind)


def test_cards_of_old_case():
    case = Case(id="x", owner_email="a@x.com", files={"claim": "cases/x/claim.pdf", "policy": "cases/x/policy.pdf"})
    cards = cards_of(case)
    assert [(c.id, c.role) for c in cards] == [("claim", "claim_form"), ("policy", "policy")]
    assert cards[0].files[0].key == "cases/x/claim.pdf" and cards[0].files[0].name == "claim.pdf"


def test_cards_of_new_case_keeps_cards():
    cards = [_card("policy", "policy"), _card("b1", "bill", "hospital")]
    assert cards_of(Case(id="x", owner_email="a@x.com", cards=cards)) == cards


def test_ordered_claim_stream():
    cards = [_card("policy", "policy"), _card("supporting", "supporting"), _card("b2", "bill", "pharmacy"),
             _card("claim-form", "claim_form"), _card("b1", "bill", "hospital")]
    assert [c.id for c in ordered(cards, "claim")] == ["claim-form", "b2", "b1", "supporting"]
    assert [c.id for c in ordered(cards, "policy")] == ["policy"]


def test_labels():
    cards = [_card("claim-form", "claim_form"), _card("b1", "bill", "hospital"), _card("b2", "bill", "pharmacy"),
             _card("supporting", "supporting"), _card("policy", "policy")]
    assert [card_label(cards, c.id) for c in cards] == [
        "Claim form", "Bill 1 · hospital", "Bill 2 · pharmacy", "Supporting documents", "Policy"]


VALID = [_card("claim-form", "claim_form"), _card("b1", "bill", "hospital"), _card("policy", "policy")]


@pytest.mark.parametrize("cards, message", [
    ([*VALID, _card("p2", "policy")], "exactly one policy card"),
    ([_card("policy", "policy"), *[_card(f"b{i}", "bill", "other") for i in range(11)]], "at most 10 bills"),
    ([_card("b1", "bill"), _card("policy", "policy")], "bill b1 needs a kind"),
    ([_card("Bad Id", "bill", "lab"), _card("policy", "policy")], "card id"),
    ([_card("b1", "bill", "lab"), _card("b1", "bill", "lab"), _card("policy", "policy")], "duplicate card id"),
    ([_card("c1", "claim_form"), _card("c2", "claim_form"), _card("policy", "policy")], "at most one claim form"),
    (VALID, None),
])
def test_layout_errors(settings, cards, message):
    error = layout_error(cards, settings)
    assert error == message if message is None else message in error
